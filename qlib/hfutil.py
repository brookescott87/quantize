import sys
import os
import re
from pathlib import Path
import datetime
import json
import clear_screen
import huggingface_hub
from typing import List

organization = os.getenv('HF_DEFAULT_ORGANIZATION')

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

paramsize_rx = re.compile('(\d+x)?(\d{1,3}(\.\d)?)b$')

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

class Model:
    cache = dict()
    aliases = {
        'microsoft/WizardLM-2-8x22B': 'alpindale/WizardLM-2-8x22B'
    }

    def xattr(self, name):
        match(name):
            case 'model_info':
                return hfapi.model_info(self.repo_id, files_metadata=False)
            case 'files':
                return hfapi.model_info(self.repo_id, files_metadata=True).siblings
            case 'card_data':
                return self.model_info.card_data
            case 'owner':
                return self.repo_id.split('/')[0]
            case 'model_name':
                return self.repo_id.split('/')[-1]
            case 'base_model':
                return self.card_data and Model(self.card_data.base_model)
            case 'config':
                if self.repo_id.endswith('-GGUF') and self.base_model:
                    return self.base_model.config
                elif hfs.isfile(path := self.repo_id + '/config.json'):
                    return json.loads(hfs.read_text(path))
                else:
                    raise RuntimeError(f'Base model {self.model_name} lacks a config.json')
            case 'num_params':
                return self.config and Model.calc_params_from_config(self.config)
            case 'context':
                return self.config.get('max_position_embeddings')
            case 'model_type':
                return self.config.get('model_type')
            case 'vocab_size':
                return self.config.get('vocab_size')
            case 'num_experts':
                return self.config.get('num_local_experts')
        return self.__getattribute__(name)

    def refresh(self):
        for k in [k for k in self.__dict__ if not k[0] == '_']:
            self.__dict__.pop(k, None)

    def is_llama3(self):
        try:
            return self.model_type == 'llama' and self.vocab_size > 100000
        except:
            return None
    
    @staticmethod
    def parse_param_size(parts, nparams, nexperts=None):
        if nexperts:
            nexperts = f'{nexperts}x'
        nparams = nparams / 1e9
        bparams = round(nparams)
        perr = nparams / 10
        pstr = (nexperts or '') + str(bparams) + 'b'
        for p in parts:
            if m := paramsize_rx.match(p):
                if not m.group(0) == pstr:
                    if m.group(1) == nexperts:
                        if nerr := abs(nparams - float(m.group(2))) < perr:
                            perr = nerr
                            pstr = m.group(0)
        return pstr

    def catalog_name(self):
        catname = self.model_name.lower().removesuffix('-gguf')
        if (mtype := self.model_type) == 'llama':
            mtype = 'llama3' if self.vocab_size > 100000 else 'llama2'
        parts = catname.split('-')
        psize = Model.parse_param_size(parts, self.num_params, self.num_experts)
        return '.'.join([mtype, psize, '-'.join(filter(lambda s: s != psize, parts))])

    def download(self):
        return Path(hfapi.snapshot_download(repo_id=self.repo_id))

    def __getattr__(self, name):
        value = self.xattr(name)
        setattr(self, name, value)
        return value

    def __new__(cls, repo_id:str):
        if repo_id:
            if (repo_id := Model.aliases.get(repo_id,repo_id)) in Model.cache:
                return Model.cache[repo_id]
            if not hfapi.repo_exists(repo_id):
                raise ValueError(f'Repository {repo_id} does not exist')
            obj = object.__new__(cls)
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
    
    @staticmethod
    def canonize_paramsize(nparams):
        bpsize = nparams / 1e9
        if round(bpsize,1) == 10.7:
            psize = '10.7'
        else:
            bpsize = round()