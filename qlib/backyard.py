import re
from pathlib import Path
import json
from dataclasses import dataclass
from functools import cached_property
from operator import attrgetter
from typing import List,Tuple
from datetime import datetime as dt, UTC
import requests
from . import hfutil
from . import misc
from .misc import singleton

link_rx = re.compile('\[(.*?)]\(((https://[^/]+/)([^/]+/.*))\)$')
ctx_rx = re.compile('(\d+) tokens$')

@singleton
class Backyard:
    @cached_property
    def backyard_dir(self):
        if (d := Path('~/.cache/backyard').expanduser()).exists():
            if not d.is_dir():
                raise RuntimeError(f'{d} is not a directory')
        else:
            d.mkdir(parents = True)
        return d

    @cached_property
    def cookie_jar(self):
        cookie_jar_path = self.backyard_dir / 'cookie.jar'
        if cookie_jar_path.exists():
            with cookie_jar_path.open('rt') as f:
                jar = requests.cookies.cookiejar_from_dict(json.load(f))
        else:
            jar = requests.cookies.RequestsCookieJar()
        jar.save_file = cookie_jar_path

        return jar

def save_cookie_jar(jar):
    with jar.save_file.open('wt', encoding='utf-8') as f:
        f.write(misc.to_json(jar.get_dict()))

requests.cookies.RequestsCookieJar.save = save_cookie_jar

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
    return dt.strftime(t or dt.now(tz=UTC),'%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


class Manifest:
    file_format:str = 'gguf_v2'

    def __init__(self, model:hfutil.QuantModel, recommended:bool=None, description:str = None, prompt_format:str = None,
                 catalog_name=None, formal_name=None):
        self.model = model
        if recommended is not None:
            self.recommended = recommended
        if description is not None:
            self.description = description
        if prompt_format is not None:
            self.prompt_format = prompt_format
        if catalog_name:
            self.catalog_name = catalog_name
        if formal_name:
            self.formal_name = formal_name
    
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
    
    @cached_property
    def catalog_name(self):
        return self.model.catalog_name
    
    @cached_property
    def formal_name(self):
        return self.model.formal_name
    
    @cached_property
    def context_size(self):
        return self.model.context

    def nonsplitggufs(self):
        for mf in self.model.files:
            if mf.name.endswith('.gguf'):
                qtype = mf.name.split('.')[-2]
                if '-split-' not in qtype:
                    mf.qtype = qtype
                    yield mf

    def files1(self):
        filter = ('Q3_K_L', 'Q3_K_M', 'Q4_K_M', 'Q4_K_S', 'Q5_K_M', 'Q5_K_S', 'Q6_K')
        flist = sorted([mf for mf in self.nonsplitggufs() if mf.qtype in filter], key=attrgetter('qtype'))
        for mf in flist:
            lname = f'{self.catalog_name}.{self.file_format}.{mf.qtype.lower()}'
            yield {
                'commitHash': self.model.model_info.sha,
                'isDeprecated': False,
                'displayLink' : self.model.url + '/',
                'hfPathFromRoot': mf.name,
                'fileFormat': self.file_format,
                'hfRepo': self.model.repo_id,
                'localFilename': lname + '.gguf',
                'size': mf.size,
                'displayName': f'{self.formal_name} ({mf.qtype})',
                'name': lname,
                'cloudCtxSize': None,
                'cloudPlan': None
            }

    def files(self):
        flist = sorted(self.nonsplitggufs(), key=attrgetter('size'))
        for filter in ('Q','IQ','F','BF'):
            for mf in flist:
                if mf.qtype.startswith(filter):
                    lname = f'{self.catalog_name}.{self.file_format}.{mf.qtype.lower()}'
                    yield {
                        'commitHash': self.model.model_info.sha,
                        'isDeprecated': False,
                        'displayLink' : self.model.url + '/',
                        'hfPathFromRoot': mf.name,
                        'fileFormat': self.file_format,
                        'hfRepo': self.model.repo_id,
                        'localFilename': lname + '.gguf',
                        'size': mf.size,
                        'displayName': f'{self.formal_name} ({mf.qtype})',
                        'name': lname,
                        'cloudCtxSize': None,
                        'cloudPlan': None
                    }

    def generate(self, summary=False) -> dict:
        ts = timestamp()
        
        return {
            'modelFamily': {
                'ctxSize': self.context_size,
                'description': self.description,
                'displayName': self.formal_name,
                'name': self.catalog_name,
                'recommended': self.recommended,
                'files': [] if summary else list(self.files()),
                'featureToNewUsers': False,
                'updatedAt': ts,
                'createdAt': ts,
                'promptFormat': self.prompt_format or 'general'
            },
            'isUpdate': False
        }
    
    def register(self, summary=False) -> dict:
        return {'json': self.generate(summary)}
    
    def json(self, readable = False, summary = False) -> str:
        return misc.to_json(self.generate(summary), readable)
    
    def jsonr(self, readable = False, summary = False) -> str:
        return misc.to_json(self.register(summary), readable)
    
    def show(self, readable = True, summary = False):
        print(self.jsonr(readable, summary))

    def summary(self, readable = True):
        self.show(readable, True)

class RequestFailed(Exception):
    def __init__(self, request):
        self.request = request
        super().__init__(f'Request failed: {request.reason}')

class Requestor:
    uuid_rx = re.compile('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
    cookie_name = '__Secure-next-auth.session-token'
    server = 'backyard.ai'
    target = 'hub.modelUploader'

    def __init__(self, token:str=None):
        self.cookie_jar = Backyard.cookie_jar
        self.r = None

        if token:
            if not self.uuid_rx.fullmatch(token):
                raise ValueError('This is not a valid UUID')
            self.cookie_jar.clear()
            cookie = requests.cookies.create_cookie(self.cookie_name, token, domain=self.server,
                                                    secure=True, discard=False,
                                                    expires=int(dt.now().timestamp()) + 3600*24*30)
            self.cookie_jar.set_cookie(cookie)
            self.cookie_jar.save()

    def request(self, command, params=None, get=None, post=None, **kwargs_):
        kwargs = {'params': {}, 'cookies': self.cookie_jar}
        if params:
            kwargs['params'].update(params)
        kwargs.update(kwargs_)

        if bool(get) ^ bool(post):
            if isinstance(data := get or post, dict):
                data = {'json': get or post}
                if get:
                    func = requests.get
                    kwargs['params']['input'] = misc.to_json(data)
                else:
                    func = requests.post
                    kwargs['json'] = data
            else:
                raise ValueError('get or post parameter must be a dict')
        else:
            raise ValueError('cannot specify both get and post')

        url = f'https://{self.server}/api/trpc/{self.target}.{command}'
        self.r = r = func(url, **kwargs)
        if r.ok:
            self.cookie_jar.save()
            return r.json()
        raise RequestFailed(r)
    
    def get_models(self, only_non_gguf:bool):
        return self.request('getModels', get={'onlyNonGGUF': only_non_gguf})

    def get_last_commit(self, model_id):
        data = {'url': f'https://huggingface.co/{model_id}'}
        return self.request('getLastCommit', post=data)

    def submit(self, manifest: Manifest):
        return self.request('addPendingApproval', post=manifest.generate())
