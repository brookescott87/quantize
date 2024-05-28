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
from typing import List
from . import readme
from .misc import *

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

    def read_json(self, filename:str) -> dict:
        if hfs.isfile(path := self.path(filename)):
            return json.loads(hfs.read_text(path))
        else:
            raise FileNotFoundError(f"'{filename}' not found in model {self.repo_id}")

    @property
    def url(self):
        return 'https://huggingface.co/' + self.repo_id

    @cached_property
    def model_info(self):
        return hfapi.model_info(self.repo_id, files_metadata=False)
    
    @cached_property
    def model_info_full(self):
        self.model_info = mi = hfapi.model_info(self.repo_id, files_metadata=True)
        return mi
    
    @cached_property
    def files(self):
        siblings = self.model_info_full.siblings
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
            inst = cls.__instantiator__(repo_id)
            if not (obj := object.__new__(inst)):
                raise RuntimeError(f"Failed to create object of type {cls}")
            obj._repo_id = repo_id
            Model.cache[repo_id] = obj
            return obj
        else:
            return None
        
    @classmethod
    def __instantiator__(cls, repo_id:str):
        if repo_id.endswith('-GGUF'):
            return QuantModel.__instantiator__(repo_id)
        else:
            return BaseModel

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
        return self.read_json('config.json')

    @cached_property
    def tokenizer(self):
        return self.read_json('tokenizer.json')

    @cached_property
    def tokenizer_config(self):
        return self.read_json('tokenizer_config.json')

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

    def guess_prompt_format(self):
        bos,eos = [self.tokenizer_config.get(k) for k in ('bos_token','eos_token')]

        if bos == '<|im_start|>' or eos == '<|im_end|>':
            return 'ChatML'
        if bos == '<|begin_of_text|>' or eos in ('<|end_of_text|>','<|eot_id|>'):
            return 'Llama3'
        
        if ct := str(self.tokenizer_config.get('chat_template','')):
            for k in ('<|im_start|>','<|im_end|>'):
                if k in ct: return 'ChatML'
            for k in ('<|begin_of_text|>','<|end_of_text|>','<|eot_id|>'):
                if k in ct: return 'Llama3'

        return None

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

    @classmethod
    def __instantiator__(cls, repo_id: str):
        if repo_id.split('/')[0] in ('backyardai', 'FaradayDotDev'):
            return BackyardQuantModel.__instantiator__(repo_id)
        return QuantModel

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

class BackyardQuantModel(QuantModel):
    @property
    def description(self):
        if buf := self.readme:
            info = readme.extract_info(buf)
            return info.vars['Description']
        return None

    file_format = 'gguf_v2'

    def manifest_files(self):
        mi = self.model_info_full
        lfstem = self.catalog_name + '.' + self.file_format
        for sib in mi.siblings:
            fn = sib.rfilename
            if fn.endswith('.gguf'):
                lqtype = (qtype := fn.split('.')[-2]).lower()
                lfname = (lname := lfstem + '.' + lqtype) + '.gguf'
                yield {
                    'commitHash': mi.sha,
                    'isDeprecated': False,
                    'displayLink' : self.url + '/',
                    'hfPathFromRoot': fn,
                    'fileFormat': 'gguf_v2',
                    'hfRepo': self.repo_id,
                    'localFilename': lfname,
                    'size': sib.size,
                    'displayName': f'{self.formal_name} ({qtype})',
                    'name': lname,
                    'cloudCtxSize': None
                }
    
    def generate_manifest(self, recommended = False, prompt_format = False, readable = False):
        if not self.description or self.description == '(Add description here)':
            raise RuntimeError('Description must be set.')
        if prompt_format is False:
            prompt_format = self.base_model.guess_prompt_format()
        timestamp = datetime.datetime.strftime(datetime.datetime.now(tz=datetime.UTC),'%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        return to_json({
            'ctxSize': self.context,
            'description': self.description,
            'displayName': self.formal_name,
            'name': self.catalog_name,
            'recommended': recommended,
            'files': list(self.manifest_files()),
            'featureToNewUsers': False,
            'updatedAt': timestamp,
            'createdAt': timestamp,
            'promptFormat': prompt_format or 'general',
            'isDefault': not prompt_format
        }, readable)
    
    def show_manifest(self, recommended = False):
        print(self.generate_manifest(recommended, readable = True))
    