import sys
import os
import io
import re
from pathlib import Path
from functools import cached_property
from dataclasses import dataclass
import datetime
import json
import clear_screen
import huggingface_hub
import hashlib
from typing import List
from .defs import *
from .misc import *
from .iobuffer import *

MAX_BLOB_SIZE = 1*MB
MAX_UPLOAD_SIZE = 50*GB

organization = os.getenv('HF_DEFAULT_ORGANIZATION')

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

paramsize_rx = re.compile('((\d+x)?(\d{1,3}(\.\d)?))[Bb]$')

@classmethod
def UploadInfo_from_path(cls, path: str) -> huggingface_hub.lfs.UploadInfo:
    hexdigest = digest = None
    if os.path.exists(sha_path := path + '.sha256'):
        if os.path.getmtime(sha_path) > os.path.getmtime(path):
            with open(sha_path, 'rt') as file:
                hexdigest = file.read().strip()
                digest = bytes.fromhex(hexdigest)
                print(f'Read hash from {sha_path}')
        else:
            os.unlink(sha_path)

    size = os.path.getsize(path)
    if size >= MAX_UPLOAD_SIZE:
        raise ValueError(f'File {path} size {size} exceeds maximum of 50 GB')
    with io.open(path, 'rb') as file:
        sample = file.peek(512)[:512]
        if not digest:
            pl = ProgressLine(size, f'Hashing {os.path.basename(path)}')
            h = hashlib.sha256(usedforsecurity=False)
            buffer = IOBuffer(MiB)
            while nbytes := buffer.readfrom(file):
                h.update(buffer.bytes)
                pl.update_progress(nbytes)
            pl.finish()
            digest = h.digest()

    if not hexdigest and size > MAX_BLOB_SIZE:
        hexdigest = digest.hex()
        with io.open(sha_path, 'wt') as file:
            file.write(hexdigest + '\n')
            print(f'Wrote hash to {sha_path}')

    return cls(size=size, sha256=digest, sample=sample)

setattr(huggingface_hub.lfs.UploadInfo, 'from_path', UploadInfo_from_path)

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

def list_models(private=False):
    return [m.id for m in hfapi.list_models(author=organization) if private or not m.private]

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
    def is_quant(self):
        return False

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

    def iterfiles(self, matcher=None):
        for mf in self.files:
            if not matcher or matcher(mf.name):
                yield mf

    @cached_property
    def card_data(self): return self.model_info.card_data
    
    @cached_property
    def owner(self): return self.repo_id.split('/')[0]

    @cached_property
    def repo_name(self): return self.repo_id.split('/')[-1]

    @property
    def model_name(self): return self.repo_name

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

    @cached_property
    def catalog_name(self):
        psize,parts = self.parse_param_size()
        name = '-'.join(parts)
        return f'{self.model_type}.{psize}b.{name}'.lower()

    @cached_property
    def formal_name(self):
        psize,parts = self.parse_param_size()
        name = ' '.join([p[0].upper()+p[1:] for p in parts])
        return f'{name} {psize}B'

    @cached_property
    def num_params(self):
        return self.card_data and self.card_data.get('parameter_count') or self.calculated_params

    def __new__(cls, repo_id:str):
        if repo_id:
            if '/' not in repo_id:
                repo_id = organization + '/' + repo_id
            if (repo_id := Model.aliases.get(repo_id,repo_id)) in Model.cache:
                return Model.cache[repo_id]
            if not hfapi.repo_exists(repo_id):
                raise ValueError(f'Repository {repo_id} does not exist')
            if (instcls := cls) is Model:
                instcls = QuantModel if '-GGUF-' in repo_id or repo_id.endswith('-GGUF') else BaseModel
            if not (obj := object.__new__(instcls)):
                raise RuntimeError(f"Failed to create object of type {instcls}")
            obj._repo_id = repo_id
            Model.cache[repo_id] = obj
            return obj
        else:
            return None

    def parse_param_size(self):
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
        return (pstr,parts)

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
    def calculated_params(self):
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
            return 'llama3' if self.vocab_size > 100*KB else 'llama2'
        else:
            return mtype
        
    @cached_property
    def vocab_size(self): return self.config.get('vocab_size')

    @cached_property
    def num_experts(self): return self.config.get('num_local_experts')

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

        match self.model_type:
            case 'mistral': return 'MistralInstruct'
            case 'llama2': return 'general'
            case 'llama3': return 'Llama3'
            case 'gemma2': return 'Gemma2'
            case 'cohere': return 'CommandR'
            case _: return None

class QuantModel(Model):
    class proxy_property:
        def __init__(self, cp):
            self.cp = cp

        def __call__(self, qm):
            return self.cp.func(qm.base_model)

    @property
    def is_quant(self):
        return True

    @property
    def model_name(self):
        return self.base_model.model_name

    @cached_property
    def base_model(self):
        return self.card_data and BaseModel(self.card_data.base_model)

    @classmethod
    def __init_proxy__(cls):
        for attrname,bcp in vars(BaseModel).items():
            if isinstance(bcp, cached_property):
                p = cls.proxy_property(bcp)
                qcp = cached_property(p)
                qcp.attrname = attrname
                setattr(cls, attrname, qcp)
