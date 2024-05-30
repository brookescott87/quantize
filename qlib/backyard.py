import re
from dataclasses import dataclass
from functools import cached_property
from typing import List,Tuple
from datetime import datetime as dt, UTC
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
    @staticmethod
    def files(qm: hfutil.QuantModel, file_format:str = 'gguf_v2'):
        for mf in qm.iterfiles(lambda fn: fn.endswith('.gguf')):
            qtype = mf.name.split('.')[-2]
            lname = f'{qm.catalog_name}.{file_format}{qtype.lower()}'
            yield {
                'commitHash': qm.model_info.sha,
                'isDeprecated': False,
                'displayLink' : qm.url + '/',
                'hfPathFromRoot': mf.name,
                'fileFormat': file_format,
                'hfRepo': qm.repo_id,
                'localFilename': lname + '.gguf',
                'size': mf.size,
                'displayName': f'{qm.formal_name} ({qtype})',
                'name': lname,
                'cloudCtxSize': None
            }

    @staticmethod
    def generate(qm: hfutil.QuantModel, recommended = False, description = None, prompt_format = False, readable = False) -> str:
        if not description:
            description = extract_info(qm.readme).info.description
        if not description or description == '(Add description here)':
            raise ValueError('Description must be set')
        if prompt_format is False:
            prompt_format = qm.base_model.guess_prompt_format()
        ts = timestamp()
        
        return misc.to_json({
            'ctxSize': qm.context,
            'description': description,
            'displayName': qm.formal_name,
            'name': qm.catalog_name,
            'recommended': recommended,
            'files': list(Manifest.files(qm)),
            'featureToNewUsers': False,
            'updatedAt': ts,
            'createdAt': ts,
            'promptFormat': prompt_format or 'general',
            'isDefault': True
        }, readable)

    def show(qm: hfutil.QuantModel, readable = True, **kwargs):
        print(Manifest.generate(qm, readable = readable, **kwargs))
