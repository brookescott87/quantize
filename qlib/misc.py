import json
from typing import Any, Callable
from functools import cached_property

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
    def __default_instantiator__(cls, *_, **__):
        return cls
    
    @classmethod
    def __init_subclass__(cls):
        if '__instantiator__' not in cls.__dict__:
            cls.__instantiator__ = cls.__default_instantiator__
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
