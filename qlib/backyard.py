import re
from dataclasses import dataclass
from functools import cached_property
from typing import List,Tuple
from datetime import datetime as dt, UTC
import requests
from . import hfutil
from . import misc

link_rx = re.compile('\[(.*?)]\(((https://[^/]+/)([^/]+/.*))\)$')
ctx_rx = re.compile('(\d+) tokens$')

class InfoBlock:
    class Field:
        def __init__(self, name, value):
            self.name = name
            self.var = misc.varname(name)
            self.value = value

        @property
        def value(self): return self._value
        @value.setter
        def value(self, value):
            if re.fullmatch('(.|\n\n)+', value := value.strip()):
                self._value = value
            else:
                raise TypeError(f'Malformed value: {repr(value)}')

    delim = '\n***\n'
    delim_rx = re.compile(misc.re_escape(delim))
    var_rx = re.compile('(?:\n- \*\*(?P<key>[A-Z][^:]*):\*\* (?P<value>(?:.|\n\n)+))')
    info_rx = re.compile(f'# (?P<title>.+)(?P<vars>{var_rx.pattern}*)')
    rx = re.compile(delim_rx.pattern + info_rx.pattern + delim_rx.pattern)

    def __init__(self, title:str, vars:List[Tuple[str,str]]):
        self.__dict__.update({
            'title': title,
            '_vars': [InfoBlock.Field(k,v) for (k,v) in vars]
        })

    def __getattr__(self, name:str) -> str:
        if not name.startswith('_'):
            return self._lookup_var(name).value
        self._badattr(name)
    
    def __setattr__(self, name:str, value:str):
        if not name.startswith('_'):
            self._lookup_var(name).value = value
        self._badattr(name)
    
    def __contains__(self, name:str) -> bool:
        return bool(self._lookup_name(name), quiet=True)
            
    def __getitem__(self, name:str) -> str:
        return self._lookup_name(name).value
    
    def __setitem__(self, name:str, value:str):
        self._lookup_name(name).value = value
    
    def __len__(self) -> int:
        return len(self._vars)

    def __iter__(self):
        for f in self._vars:
            yield (f.name, f.value)

    def _lookup_var(self, var:str, quiet:bool = False) -> Field|None:
        for f in self._vars:
            if f.var == var:
                return f
        if quiet:
            return None
        self._badattr(var)

    def _lookup_name(self, name:str, quiet:bool = False) -> Field|None:
        for f in self._vars:
            if f.name == name:
                return f
        if quiet:
            return None
        raise KeyError(repr(name))
    
    def _badattr(self, var:str):
        raise AttributeError(f'{repr(self.__class__)} object has no attribute {repr(var)}')

    @cached_property
    def fields(self):
        return [f.name for f in self._vars]

    @cached_property
    def vars(self):
        return [f.var for f in self._vars]

    @classmethod
    def parse(cls, text: str):
        if m := InfoBlock.info_rx.fullmatch(text):
            return cls(title=m.group('title'),
                       vars=cls.var_rx.findall(m.group('vars')))

@dataclass
class MetaInfo:
    metadata: str|None
    info: InfoBlock

def extract_info(text: str) -> MetaInfo:
    meta_block = None
    meta_text,info_text = text.split('\n***\n')[:2]
    if meta_text.startswith('---\n'):
        try:
            meta_block = meta_text.split('---\n')[1]
        except Exception:
            pass
    info_block = InfoBlock.parse(info_text)
    return MetaInfo(metadata=meta_block,info=info_block)

def read_description(model: hfutil.Model) -> str:
    if model.readme:
        ib = extract_info(model.readme)
        if 'Description' in ib:
            return ib.description
    return None

def timestamp(t: dt=None):
    return dt.strftime(t or dt.now(tz=UTC),'%Y-%m-%dT%H:%M:%S.%f')[:-3]


class Manifest:
    file_format:str = 'gguf_v2'

    def __init__(self, model:hfutil.QuantModel, recommended:bool=None, description:str = None, prompt_format:str = None):
        self.model = model
        if recommended is not None:
            self.recommended = recommended
        if description is not None:
            self.description = description
        if prompt_format is not None:
            self.prompt_format = prompt_format
    
    @cached_property
    def recommended(self): return False

    @cached_property
    def description(self):
        if (desc := extract_info(self.model.readme).info.description):
            if not desc == '(Add description here)':
                return desc
        misc.badattr(self, 'description')

    @cached_property
    def prompt_format(self):
        return self.model.base_model.guess_prompt_format()

    def files(self):
        for mf in self.model.iterfiles(lambda fn: fn.endswith('.gguf')):
            qtype = mf.name.split('.')[-2]
            if '-split-' not in qtype:
                lname = f'{self.model.catalog_name}.{self.file_format}.{qtype.lower()}'
                yield {
                    'commitHash': self.model.model_info.sha,
                    'isDeprecated': False,
                    'displayLink' : self.model.url + '/',
                    'hfPathFromRoot': mf.name,
                    'fileFormat': self.file_format,
                    'hfRepo': self.model.repo_id,
                    'localFilename': lname + '.gguf',
                    'size': mf.size,
                    'displayName': f'{self.model.formal_name} ({qtype})',
                    'name': lname,
                    'cloudCtxSize': None
                }

    def generate(self) -> dict:
        ts = timestamp()
        
        return {
            'modelFamily': {
                'ctxSize': self.model.context,
                'description': self.description,
                'displayName': self.model.formal_name,
                'name': self.model.catalog_name,
                'recommended': self.recommended,
                'files': list(self.files()),
                'featureToNewUsers': False,
                'updatedAt': ts,
                'createdAt': ts,
                'promptFormat': self.prompt_format or 'general',
                'isDefault': True
            }
        }
    
    def json(self, readable = False):
        return misc.to_json(self.generate(), readable)
    
    def show(self, readable = True):
        print(self.json(readable))

class Requestor:
    uuid_rx = re.compile('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
    cookie_name = '__Secure-next-auth.session-token'
    server = 'hub-uploader-private.faraday.dev'

    def __init__(self, token:str):
        if self.uuid_rx.fullmatch(token):
            self.token = token
        else:
            raise ValueError('This is not a valid UUID')
        self.cookie_jar = requests.cookies.RequestsCookieJar()
        cookie = requests.cookies.create_cookie(self.cookie_name, token, domain=self.server,
                                                secure=True, discard=False,
                                                expires=int(dt.now().timestamp()) + 3600*24*30)
        self.cookie_jar.set_cookie(cookie)

    def request(self, command, data):
        if isinstance(data,dict):
            data = misc.to_json(data)
        payload = '{"0":{"json":%s}}'%(data,)
        url = f'https://{self.server}/api/trpc/models.{command}?batch=1'
        r = requests.post(url, payload, cookies=self.cookie_jar)
        if r.ok:
            return r.json()
        raise RuntimeError(f'Request failed: {r.reason}')
    
    def get_last_commit(self, model_id):
        data = {'url': f'https://huggingface.co/{model_id}'}
        return self.request('getLastCommit', data)

    def submit(self, manifest: Manifest):
        return self.request('addPendingApproval', manifest.json())
