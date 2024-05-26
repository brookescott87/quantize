import sys
import os
import re
from pathlib import Path
from functools import cached_property
import datetime
import json
import clear_screen
import huggingface_hub
from typing import List

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

class ProxyObject:
    @classmethod
    def __init_subclass__(cls):
        if '__init_proxy__' in cls.__dict__:
            cls.__init_proxy__()

    def refresh(self):
        for k in self.__dict__:
            if not k.startswith('_'):
                self.__dict__.pop(k, None)

    def knows(self, name):
        return name in self.__dict__
    
    def known(self, name):
        return name.__dict__.get(name)
    
    def forget(self, *names):
        for k in names:
            if k in self.__dict__:
                self.__dict__.pop(k, None)

class Model(ProxyObject):
    cache = dict()
    aliases = {
        'microsoft/WizardLM-2-8x22B': 'alpindale/WizardLM-2-8x22B'
    }

    @cached_property
    def model_info(self): return hfapi.model_info(self.repo_id, files_metadata=False)
    
    @cached_property
    def files(self): return hfapi.model_info(self.repo_id, files_metadata=True).siblings
    
    @cached_property
    def card_data(self): return self.model_info.card_data
    
    @cached_property
    def owner(self): return self.repo_id.split('/')[0]

    @cached_property
    def model_name(self): return self.repo_id.split('/')[-1]

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

    def catalog_name(self):
        psize,name = self.parse_param_size('-')
        return f'{self.model_type}.{psize}b.{name}'.lower()
    
    def formal_name(self):
        psize,name = self.parse_param_size(' ')
        return f'{name} {psize}B'

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
            if repo_id.endswith('-GGUF'):
                obj = object.__new__(QuantModel)
            else:
                obj = object.__new__(BaseModel)
            if not isinstance(obj, cls):
                print(f'Warning: {cls} object created as {obj.__class__}')
            obj._repo_id = repo_id
            Model.cache[repo_id] = obj
            return obj
        else:
            return None

    @property
    def repo_id(self):
        return self._repo_id

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

    @staticmethod
    def calc_params_from_config(config:dict):
        blocks = config['num_hidden_layers']
        embeds = config['hidden_size']
        ffs = config['intermediate_size']
        heads = config['num_attention_heads']
        kvs = config['num_key_value_heads']
        vocabs = config['vocab_size']
        return Model.calc_params(blocks, embeds, ffs, heads, kvs, vocabs)

class BaseModel(Model):
    @cached_property
    def config(self):
        if hfs.isfile(path := self.repo_id + '/config.json'):
            return json.loads(hfs.read_text(path))
        else:
            raise RuntimeError(f'Base model {self.model_name} lacks a config.json')

    @cached_property
    def num_params(self):
        return self.config and Model.calc_params_from_config(self.config)
    
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

class QuantModel(Model):
    class proxy_property:
        def __init__(self, cp):
            self.cp = cp

        def __call__(self, qm):
            return self.cp.func(qm.base_model)

    @cached_property
    def base_model(self):
        return self.card_data and BaseModel(self.card_data.base_model)

    @classmethod
    def __init_proxy__(cls):
        for attrname,bcp in BaseModel.__dict__.items():
            if isinstance(bcp, cached_property):
                p = cls.proxy_property(bcp)
                qcp = cached_property(p)
                qcp.attrname = attrname
                setattr(cls, attrname, qcp)