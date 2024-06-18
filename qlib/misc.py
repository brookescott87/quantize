import sys
import re
import json
from datetime import datetime as dt, timedelta
from typing import Any, Callable
from functools import cached_property
import dataclasses
import argparse

_re_special_chars_map = {n:u for n,u in re._special_chars_map.items() if chr(n).isprintable()}

def re_escape(s:str) -> str:
    return s.translate(_re_special_chars_map)

def badattr(self, attr:str):
    raise AttributeError(f'{repr(self.__class__)} object has no attribute {repr(attr)}')

def is_dataclass_instance(o):
    return dataclasses.is_dataclass(o) and not isinstance(o, type)

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

class StatusLine:
    def __init__(self, stream=sys.stdout):
        self.out = stream
        self.pos = 0
        self.line = 0

    def retn(self, linefeed = False):
        if (pad := self.line - self.pos) > 0:
            self.out.write(' '*pad)
        if linefeed:
            self.out.write('\n')
            self.line = 0
        else:
            self.out.write('\r')
            self.out.flush()
            self.line = self.pos
        self.pos = 0

    def print(self, text):
        self.pos += self.out.write(text)

class ProgressLine(StatusLine):
    max_staleness = timedelta(milliseconds=200)

    def __init__(self, total_amount:int, message:str, stream=sys.stdout):
        super().__init__(stream)
        self.message = message
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
            self.print(f'{self.message}: {self.completed:15,} of {self.total_amount:15,} ({progress*100:.1f}%) [{estr}<{rstr}]')
            self.retn()
            self.last_update = dt.now()

    def finish(self, message=None):
        self.retn()
        estr = ProgressLine.format_timedelta(self.elapsed)
        self.print(f'{message or self.message}: {self.completed:,} in {estr}\n')

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

