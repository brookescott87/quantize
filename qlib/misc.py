import sys
import os
import io
import re
import json
from enum import StrEnum
from datetime import datetime as dt, timedelta
from typing import Any, Callable
from functools import cached_property
import dataclasses
import argparse
import torch
import safetensors
import gguf
import numpy
import pathlib

_re_special_chars_map = {n:u for n,u in re._special_chars_map.items() if chr(n).isprintable()}

def re_escape(s:str) -> str:
    return s.translate(_re_special_chars_map)

def badattr(self, attr:str):
    raise AttributeError(f'{repr(self.__class__)} object has no attribute {repr(attr)}')

def is_dataclass_instance(o):
    return dataclasses.is_dataclass(o) and not isinstance(o, type)

def const_property(c:Any = None) -> property:
    return property(lambda _: c)

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
        if '__init_proxy__' in vars(cls):
            cls.__init_proxy__()
        cls.__init_proxy_all__()

    @classmethod
    def __init_proxy_all__(cls):
        pass

    def refresh(self):
        self.forget(*filter(lambda k: not k.startswith('_'), vars(self)))

    def forget(self, *names):
        for k in names:
            vars(self).pop(k, None)

class JSONEncoder(json.JSONEncoder):
    compact_separators = (',',':')
    def __init__(self, *, ensure_ascii=False, indent=None, separators=None, **kwargs):
        match indent:
            case True: indent = 4
            case False:
                indent = None
                if not separators:
                    separators = self.compact_separators
        super().__init__(ensure_ascii=ensure_ascii, indent=indent, separators=separators, **kwargs)

    def default(self, o):
        if is_dataclass_instance(o):
            return vars(o)
        return super().default(o)

def to_json(obj:Any, readable=False):
    return json.dumps(obj, cls=JSONEncoder, indent=bool(readable))

def varname(s:str):
    return s.lower().replace(' ','_')

class BooleanOptionalAction(argparse.BooleanOptionalAction):
    def __init__(self, option_strings, *args, **kwargs):
        _option_strings = []
        self.negators = []
        for opt in option_strings:
            if len(opt) > 1 and opt[0] == '-':
                _option_strings.append(opt)
                if not opt[1] == '-':
                    _option_strings.append(nopt := '-n' + opt[1:])
                    self.negators.append(nopt)
            else:
                raise ValueError(f'invalid option: {opt}')
        super().__init__(_option_strings, *args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string in self.negators:
            setattr(namespace, self.dest, False)
        else:
            super().__call__(parser, namespace, values, option_string)

class KeywordEnum(StrEnum):
    @classmethod
    def _missing_(cls, value):
        return cls._value2member_map_.get(value.lower())

class ConsoleBuffer(io.StringIO):
    def __init__(self):
        super().__init__()
    
    @property
    def cursor(self):
        return self.tell()

    @property
    def chars(self):
        return self.getvalue()

    @property
    def count(self):
        return len(self.getvalue())
    
    @property
    def ahead(self):
        return max(self.count - self.cursor, 0)

    def rewind(self):
        self.seek(0)
        self.truncate(len(self.chars.rstrip()))

    def reset(self):
        self.seek(0)
        self.truncate(0)

    def expandtabs(self, s, tabsize=8):
        if (ofs := self.cursor % 8) > 0:
            return (((' '*ofs)+s).expandtabs(tabsize))[ofs:]
        else:
            return s.expandtabs(tabsize)

class StatusLine:
    def __init__(self):
        self.buffer = ConsoleBuffer()

    def retn(self, linefeed = False):
        self.write(' '*self.buffer.ahead)
        if linefeed:
            sys.stdout.write('\n')
            self.buffer.reset()
        else:
            sys.stdout.write('\r')
            sys.stdout.flush()
            self.buffer.rewind()

    def write(self, text):
        if text:
            self.buffer.write(text)
            sys.stdout.write(text)

    def error(self, text):
        if text:
            saved = self.buffer.chars
            self.retn()
            self.print(text)
            self.retn(True)
            self.print(saved)

    def write(self, text):
        if '\t' in text:
            text = self.buffer.expandtabs(text)
        self.buffer.write(text)
        sys.stdout.write(text)

    def print(self, text):
        *lines,text = text.split('\n')
        for line in lines:
            self.write(line)
            self.retn(True)
        self.write(text)

class ProgressLine(StatusLine):
    max_staleness = timedelta(milliseconds=200)

    def __init__(self, total_amount:int, message:(str | None) = None):
        super().__init__()
        if message is not None:
            self.prefix = message + ': '
        else:
            self.prefix = '    '
        self.total_amount = total_amount
        self.completed = 0
        self.last_update = self.start_time = dt.now()

    def update_progress(self, amount):
        self.completed += amount
        if self.staleness > self.max_staleness:
            progress = self.completed / self.total_amount
            estr = ProgressLine.format_timedelta(elapsed := self.elapsed)
            remaining = elapsed/progress
            rstr = ProgressLine.format_timedelta(remaining)
            self.print(f'{self.prefix}{self.completed:15,} of {self.total_amount:15,} ({progress*100:.1f}%) [{estr}<{rstr}]')
            self.retn()
            self.last_update = dt.now()

    def finish(self, message=None):
        self.retn()
        estr = ProgressLine.format_timedelta(self.elapsed)
        self.print(f'{message or self.prefix}: {self.completed:,} in {estr}\n')

    @property
    def elapsed(self):
        return dt.now() - self.start_time
    
    @property
    def staleness(self):
        return dt.now() - self.last_update

    @staticmethod
    def format_timedelta(delta: timedelta) -> str:
        """Formats a timedelta duration to %H:%M:%S format"""
        seconds = int(delta.total_seconds())

        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

class GGUFMetadataReader(gguf.gguf_reader.GGUFReader):
    class FileMapper:
        def __init__(self, path: os.PathLike[str] | str, mode:str = 'rb',
                     opener:Callable[[os.PathLike[str] | str, str], io.BufferedReader] | None = None):
            assert mode == 'rb'
            self.file = (opener or open)(path, mode = mode)
        
        def __getitem__(self, i):
            return self._getrange(*self._extent(i))
        
        def _getrange(self, offset:int, nbytes:int = 1):
            self.file.seek(offset)
            return numpy.ndarray((nbytes,), dtype=numpy.uint8, buffer=self.file.read(nbytes))

        @staticmethod
        def _extent(i):
            return (i.start, i.stop - i.start) if isinstance(i, slice) else (i,)

    def __init__(self, path: os.PathLike[str] | str, mode:str = 'rb', cls:type = FileMapper,
                 opener:Callable[[os.PathLike[str] | str, str], io.BufferedReader] | None = None):
        super().__init__(path, mode = mode, cls = cls, opener = opener)

    def _build_tensor_info(self, offs: int, count: int) -> tuple[int, list[gguf.gguf_reader.ReaderField]]:
        count = 0
        return super()._build_tensor_info(offs, count)

def torch_type_str(dtype: torch.dtype) -> str:
    return (str(dtype).split('.')[-1]).replace('float','f').replace('uint', 'u').replace('int', 'i').upper()

def guess_model_datatype(model_dir: str | pathlib.Path) -> str:
    model_dir = pathlib.Path(model_dir)
    for f in model_dir.glob('model*.safetensors'):
        # safetensors model
        with safetensors.safe_open(f, framework="pt", device="cpu") as part:
            for name in part.keys():
                data = part.get_slice(name)
                return data.get_dtype()
    for f in model_dir.glob('pytorch_model*.bin'):
        part = torch.load(f, map_location="cpu", mmap=True, weights_only=True)
        for data in part.values():
            return torch_type_str(data.dtype)
    raise ValueError(f'{model_dir} seems to be neither safetensors nor pytorch')
