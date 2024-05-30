import re
import json
from typing import Any, Callable
from functools import cached_property
import argparse

_re_special_chars_map = {n:u for n,u in re._special_chars_map.items() if chr(n).isprintable()}

def re_escape(s:str) -> str:
    return s.translate(_re_special_chars_map)

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
        if '__init_proxy__' in cls.__dict__:
            cls.__init_proxy__()

    def refresh(self):
        for k in self.__dict__:
            if not k.startswith('_'):
                self.__dict__.pop(k, None)

    def forget(self, *names):
        for k in names:
            if k in self.__dict__:
                self.__dict__.pop(k, None)

def to_json(obj:Any, readable=False):
    dump_opts = {'indent': 4} if readable else { 'separators': (',',':') }
    return json.dumps(obj, ensure_ascii=False, **dump_opts)

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
