import sys
import os
import re
from pathlib import Path
from functools import cached_property
from dataclasses import dataclass
import datetime
import json
import clear_screen
import huggingface_hub
from typing import List,Any,Callable
from . import readme

organization = os.getenv('HF_DEFAULT_ORGANIZATION')

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

paramsize_rx = re.compile('((\d+x)?(\d{1,3}(\.\d)?))[Bb]$')

class Uploader(object):
    def __init__(self, repo_id: str, folder_path: Path, max_retries:int = 0):
        self.repo_id = repo_id
        self.folder_path = folder_path
        self.max_retries = max_retries
        self.total_retries = 0
        self.repo_exists = hfapi.repo_exists(repo_id)
        self.start_time = None

    @property
    def elapsed(self):
        return datetime.datetime.now() - self.start_time if self.start_time else datetime.timedelta(0)
        
    def upload(self, message: str, allow_patterns:List[str], ignore_patterns:List[str]=None, *, skip=False):
        if skip:
            return True
        retries = 0
        finished = False

        if not self.repo_exists:
            hfapi.create_repo(self.repo_id, private = True, repo_type = 'model')
            self.repo_exists = True
        self.start_time = datetime.datetime.now()

        while not (finished or (self.max_retries and retries > self.max_retries)):
            clear_screen.clear()
            sys.stdout.write(f'{self.repo_id}: {message}')

            if retries:
                sys.stdout.write(f' (retry {retries}')
                if self.max_retries:
                    sys.stdout.write(f' of {self.max_retries}')
                sys.stdout.write(')')
            sys.stdout.write('\n')
            try:
                hfapi.upload_folder(repo_id=self.repo_id, folder_path=self.folder_path, commit_message=message,
                                    repo_type='model', allow_patterns=allow_patterns, ignore_patterns=ignore_patterns)
                finished = True
            except KeyboardInterrupt:
                print('\n*** Keyboard interrupt ***')
                break
            except RuntimeError:
                retries += 1
                print('Upload failed')

        self.total_retries += retries
        return finished

def list_models():
    return [m.id for m in hfapi.list_models(author=organization) if not m.private]

class settable_cached_property(cached_property):
    fset: Callable[[Any, Any], None] | None

    def setter(self, fset: Callable[[Any, Any], None], /):
        if not callable(fset):
            raise TypeError('setter function is not callable')
        self.fset = fset
        return self

    def __set__(self, instance: Any, value: Any, /) -> None:
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property instance without calling __set_name__ on it.")
        try:
            cache = instance.__dict__
        except AttributeError:  # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        with self.lock:
            if self.fset:
                self.fset(instance, value)
            try:
                cache[self.attrname] = value
            except TypeError:
                msg = (
                    f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                    f"does not support item assignment for caching {self.attrname!r} property."
                )
                raise TypeError(msg) from None


class ProxyObject:
    @classmethod
    def __init_subclass__(cls):
        if '__init_proxy__' in cls.__dict__:
            cls.__init_proxy__()

    def refresh(self):
        for k in self.__dict__:
            if not k.startswith('_'):
                self.__dict__.pop(k, None)

    def knows(self, name:str) -> bool:
        return name in self.__dict__
    
    def known(self, name:str) -> Any:
        return name.__dict__.get(name)
    
    def forget(self, *names):
        for k in names:
            if k in self.__dict__:
                self.__dict__.pop(k, None)

@dataclass
class ModelFile:
    name: str
    size: int
    hash: str

class Model(ProxyObject):
    cache = dict()
    aliases = {
        'microsoft/WizardLM-2-8x22B': 'alpindale/WizardLM-2-8x22B'
    }

    def path(self, name:str) -> str:
        return self.repo_id + '/' + name

    @cached_property
    def model_info(self): return hfapi.model_info(self.repo_id, files_metadata=False)
    
    @cached_property
    def files(self):
        siblings = hfapi.model_info(self.repo_id, files_metadata=True).siblings
        return [ModelFile(rs.rfilename, rs.size, rs.lfs.sha256 if rs.lfs else rs.blob_id) for rs in siblings]
    
    @cached_property
    def card_data(self): return self.model_info.card_data
    
    @cached_property
    def owner(self): return self.repo_id.split('/')[0]

    @cached_property
    def model_name(self): return self.repo_id.split('/')[-1]

    @property
    def repo_id(self): return self._repo_id

    @settable_cached_property
    def readme(self):
        if hfs.exists(path := self.path('README.md')):
            return hfs.read_text(path, encoding='utf-8')
        else:
            return None
    
    @readme.setter
    def readme(self, value:str):
        hfs.write_text(self.path('README.md'), value, encoding='utf-8')

    def download(self):
        return Path(hfapi.snapshot_download(repo_id=self.repo_id))

    def __new__(cls, repo_id:str):
        if repo_id:
            if '/' not in repo_id:
                repo_id = organization + '/' + repo_id
            if (repo_id := Model.aliases.get(repo_id,repo_id)) in Model.cache:
                return Model.cache[repo_id]
            if not hfapi.repo_exists(repo_id):
                raise ValueError(f'Repository {repo_id} does not exist')
            if cls is Model:
                if repo_id.endswith('-GGUF'):
                    cls = QuantModel
                else:
                    cls = BaseModel
            if not (obj := object.__new__(cls)):
                raise RuntimeError(f"Failed to create object of type {cls}")
            obj._repo_id = repo_id
            Model.cache[repo_id] = obj
            return obj
        else:
            return None

    @staticmethod
    def calc_params(blocks, embeds, ffs, heads, kvs, vocabs):
        if heads % kvs:
            raise ValueError('heads must be a multiple of kvs')
        else:
            dkvs = int(heads/kvs)
        if embeds % dkvs:
            raise ValueError('embeds must be a multiple of heads/kvs')
        else:
            kvembeds = int(embeds / dkvs)
        return embeds*(1 + blocks*(2 + 3*ffs + 2*(embeds + kvembeds)) + 2*vocabs)

class BaseModel(Model):
    @cached_property
    def config(self):
        if hfs.isfile(path := self.repo_id + '/config.json'):
            return json.loads(hfs.read_text(path))
        else:
            raise RuntimeError(f'Base model {self.model_name} lacks a config.json')

    @cached_property
    def num_params(self):
        if config := self.config:
            blocks = config['num_hidden_layers']
            embeds = config['hidden_size']
            ffs = config['intermediate_size']
            heads = config['num_attention_heads']
            kvs = config['num_key_value_heads']
            vocabs = config['vocab_size']
            return self.calc_params(blocks, embeds, ffs, heads, kvs, vocabs)
        else:
            return None
    
    @cached_property
    def context(self): return self.config.get('max_position_embeddings')

    @cached_property
    def model_type(self):
        if (mtype := self.config.get('model_type')) == 'llama':
            return 'llama3' if self.vocab_size > 100000 else 'llama2'
        else:
            return mtype
        
    @cached_property
    def vocab_size(self): return self.config.get('vocab_size')

    @cached_property
    def num_experts(self): return self.config.get('num_local_experts')

    @cached_property
    def catalog_name(self):
        psize,name = self.parse_param_size('-')
        return f'{self.model_type}.{psize}b.{name}'.lower()

    @cached_property
    def formal_name(self):
        psize,name = self.parse_param_size(' ')
        return f'{name} {psize}B'

    def parse_param_size(self,joiner):
        if nexperts := self.num_experts:
            nexperts = f'{nexperts}x'
        nparams = self.num_params / 1e9
        bparams = round(nparams)
        perr = nparams / 10
        pstr = (nexperts or '') + str(bparams)
        mstr = None
        for p in (parts := self.model_name.split('-')):
            if not p == mstr:
                if m := paramsize_rx.match(p):
                    if m.group(2) == nexperts:
                        if nerr := abs(nparams - float(m.group(3))) < perr:
                            perr = nerr
                            pstr = m.group(1)
                            mstr = p
        if mstr:
            parts = [p for p in parts if not p == mstr]
        return (pstr,joiner.join(parts))



class QuantModel(Model):
    class proxy_property:
        def __init__(self, cp):
            self.cp = cp

        def __call__(self, qm):
            return self.cp.func(qm.base_model)

    @cached_property
    def base_model(self):
        return self.card_data and BaseModel(self.card_data.base_model)

    @property
    def description(self):
        if buf := self.readme:
            info = readme.extract_info(buf)
            return info.vars['Description']
        return None
    
    @classmethod
    def __init_proxy__(cls):
        for attrname,bcp in BaseModel.__dict__.items():
            if isinstance(bcp, cached_property):
                p = cls.proxy_property(bcp)
                qcp = cached_property(p)
                qcp.attrname = attrname
                setattr(cls, attrname, qcp)
