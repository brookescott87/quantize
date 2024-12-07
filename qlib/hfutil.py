import sys
import os
import io
import re
from pathlib import Path as LocalPath
from functools import cached_property
from dataclasses import dataclass
import datetime
import json
import clear_screen
import huggingface_hub
import hashlib
from typing import List, Optional, Tuple
from .defs import *
from .misc import *
from .iobuffer import *

MAX_BLOB_SIZE = 1*MB
MAX_UPLOAD_SIZE = 50*GB

organization = os.getenv('HF_DEFAULT_ORGANIZATION')

try:
    eval('repo_type_and_id_from_hf_id_default')
except NameError:
    repo_type_and_id_from_hf_id_default = huggingface_hub.repo_type_and_id_from_hf_id

def repo_type_and_id_from_hf_id(hf_id: str, hub_url: Optional[str] = None) -> Tuple[Optional[str], Optional[str], str]:
    repo_type, namespace, repo_id = repo_type_and_id_from_hf_id_default(hf_id, hub_url)
    return repo_type, namespace or organization, repo_id

huggingface_hub.repo_type_and_id_from_hf_id = repo_type_and_id_from_hf_id

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

paramsize_rx = re.compile('((\d+x)?(\d{1,3}(\.\d)?))[Bb]$')

## Uncomment these lines if you have issues with chmod failing 
# import huggingface_hub.file_download
# import shutil
# huggingface_hub.file_download._chmod_and_move = shutil.move

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
            print(size, f'Hashing {os.path.basename(path)}')
            pl = ProgressLine(size)
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
    def __init__(self, repo_id: str, folder_path: LocalPath, max_retries:int = 0):
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

def is_safetensors_model(repo_id:str) -> bool:
    try:
        for jf in ('config', 'generation_config', 'special_tokens_map', 'tokenizer', 'tokenizer_config'):
            if not hfapi.file_exists(repo_id, jf + '.json'):
                return False
        msize = 0
        for rs in hfapi.model_info(repo_id, files_metadata=True).siblings:
            if rs.rfilename.endswith('.safetensors'):
                if (msize := msize + rs.size) >= 12_000_000_000:
                    return True
    except KeyboardInterrupt as kbe:
        raise kbe
    except:
        pass
    return False

def recent_safetensors_models(*,days=0, hours=0, mins=0, secs=0, limit=None):
    secs = ((((days * 24) + hours) * 60) + mins) * 60 + secs
    cutoff = secs and (datetime.datetime.now(tz=datetime.timezone.utc) - 
                datetime.timedelta(seconds=int(secs), microseconds=int((secs % 1) * 1_000_000))) or None
    count = 0
    if not (cutoff or limit):
        raise ValueError('unbounded search not allowed')
    for mi in hfapi.list_models(sort='createdAt'):
        if cutoff and mi.created_at < cutoff:
            break
        if is_safetensors_model(mi.id):
            count += 1
            yield mi.id
            if limit and not count < limit:
                break

@dataclass
class ModelFile:
    model: 'Model'
    name: str
    size: int
    hash: str

    @classmethod
    def from_sibling(cls, model: 'Model', rs=huggingface_hub.hf_api.RepoSibling):
        return cls(model, rs.rfilename, rs.size, rs.lfs.sha256 if rs.lfs else rs.blob_id)

class RepositoryNotFoundError(Exception):
    def __init__(self, repo_id):
        super().__init__(f'Repository {repr(repo_id)} was not found on HuggingFace')

class Model(ProxyObject):
    cache = dict()
    aliases = {
        'microsoft/WizardLM-2-8x22B': 'alpindale/WizardLM-2-8x22B'
    }

    prompt_formats = ['general','ChatML','Llama3','Gemma2','CommandR','MistralInstruct']

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
    def is_source(self):
        return False

    @property
    def base_model(self):
        return self

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
        return [ModelFile.from_sibling(self, rs) for rs in self.model_info_full.siblings]

    def iterfiles(self, full=False, matcher=None, cls=ModelFile):
        for rs in hfapi.model_info(self.repo_id, files_metadata=full).siblings:
            if not matcher or matcher(rs.rfilename):
                yield cls(self, rs)

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
        return LocalPath(hfapi.snapshot_download(repo_id=self.repo_id))

    @cached_property
    def catalog_name(self):
        psize,parts = self.parse_param_size()
        name = '-'.join(parts)
        return f'{self.architecture}.{psize}b.{name}'.lower()

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
                raise RepositoryNotFoundError(repo_id)
            if instcls := cls.repo_model_type(repo_id):
                if obj := object.__new__(instcls):
                    obj._repo_id = repo_id
                    Model.cache[repo_id] = obj
                    return obj
                else:
                    raise TypeError(f"Failed to create object of type {instcls}")
            else:
                raise TypeError(f"Failed to determine type of {repo_id}")
        else:
            return None

    @staticmethod
    def repo_model_type(repo_id:str) -> type | None:
        return Model.repo_model_type_default(repo_id)

    @staticmethod
    def repo_model_type_default(repo_id:str) -> type | None:
        if repo_id.endswith('-GGUF') or '-GGUF-' in repo_id:
            return QuantModel
        if hfapi.file_exists(repo_id, 'config.json'):
            if any(hfapi.file_exists(repo_id, fn) for fn in ('model.safetensors', 'model.safetensors.index.json', 'pytorch_model.bin.index.json')):
                return SourceModel
        if any(f.casefold().endswith('.gguf') for f in hfapi.list_repo_files(repo_id)):
            return QuantModel
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

class SourceModel(Model):
    @property
    def is_source(self):
        return True

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
    def llm_config(self):
        return (c := self.config) and c.get('llm_config', c)

    @cached_property
    def chat_template(self):
        try:
            ct = self.tokenizer_config.get('chat_template')
            while ct and not isinstance(ct, str):
                if isinstance(ct, list):
                    ct = ct[0]
                elif isinstance(ct, dict) and 'template' in ct:
                    ct = ct['template']
                else:
                    ct = str(ct)
            return ct or ''
        except:
            return '{# error #}'

    @cached_property
    def calculated_params(self):
        if config := self.llm_config:
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
    def context(self): return self.llm_config.get('max_position_embeddings')

    @cached_property
    def architecture(self):
        if (mtype := self.llm_config.get('model_type')) == 'llama':
            return 'llama3' if self.vocab_size > 100*KB else 'llama2'
        else:
            return mtype
        
    @cached_property
    def vocab_size(self): return self.llm_config.get('vocab_size')

    @cached_property
    def num_experts(self): return self.llm_config.get('num_local_experts')

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

        match self.architecture:
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
            return qm.base_model and self.cp.func(qm.base_model)

    @property
    def is_quant(self):
        return True

    @property
    def model_name(self):
        return self.base_model.model_name

    @cached_property
    def base_model(self):
        if (cd := self.card_data) and (bm := cd.base_model):
            try:
                return SourceModel(bm)
            except RepositoryNotFoundError as rnfe:
                print(rnfe)
        return None

    @classmethod
    def __init_proxy__(cls):
        for attrname,bcp in vars(SourceModel).items():
            if isinstance(bcp, cached_property):
                p = cls.proxy_property(bcp)
                qcp = cached_property(p)
                qcp.attrname = attrname
                setattr(cls, attrname, qcp)
