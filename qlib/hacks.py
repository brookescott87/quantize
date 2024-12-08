from typing import Any
import pathlib
import math

def PurePath___set_parts(self, drv, root, parts):
    self._drv = drv
    self._root = root
    self._parts = [p for p in parts if not p == '.']
    if not root:
        self._parts.insert(0, '.')
    return self

pathlib.PurePath._set_parts = PurePath___set_parts

@classmethod
def PurePath___from_parts(cls, args):
    # We need to call _parse_args on the instance, so as to get the
    # right flavour.
    self = object.__new__(cls)
    return self._set_parts(*self._parse_args(args))

pathlib.PurePath._from_parts = PurePath___from_parts

@classmethod
def PurePath___from_parsed_parts(cls, drv, root, parts):
    return object.__new__(cls)._set_parts(drv, root, parts)

pathlib.PurePath._from_parsed_parts = PurePath___from_parsed_parts

def initattr(obj, name, value):
    if not hasattr(obj, name):
        setattr(obj, name, value)

def path_add_str(self: pathlib.Path, other) -> pathlib.Path:
    if isinstance(other, str):
        return self.with_name(self.name + other)
    else:
        raise TypeError(f'Unsupported operand type(s) for +: {repr(type(self))} and {repr(type(other))}')
initattr(pathlib.Path, '__add__', path_add_str)

initattr(pathlib.Path, 'size', property(lambda self: self.stat().st_size))
# initattr(pathlib.Path, 'mtime',
#          property(lambda self: self.lstat().st_mtime if self.exists(follow_symlinks=False) else None))
initattr(pathlib.Path, 'mtime',
         property(lambda self: self.lstat().st_mtime if self.exists() else None))
# For the purpose of comparison, nonexistent file is treated as though it were infinitely old
initattr(pathlib.Path, 'is_newer_than', lambda self, other: (self.mtime or -math.inf) > (other.mtime or -math.inf))
initattr(pathlib.Path, 'is_older_than', lambda self, other: (self.mtime or -math.inf) < (other.mtime or -math.inf))

import numpy
import gguf

def ndarray_tostring(nda:numpy.ndarray) -> str:
    return nda.tobytes().decode('utf-8')

def ndarray_toscalar(nda:numpy.ndarray) -> Any:
    return nda.item()

def gguf_ReaderField_decode(self:gguf.gguf_reader.ReaderField) -> Any:
    if self.types[-1] == gguf.GGUFValueType.STRING:
        fdec = ndarray_tostring
    else:
        fdec = ndarray_toscalar
    gen=(fdec(self.parts[i]) for i in self.data)
    if self.types[0] == gguf.GGUFValueType.ARRAY:
        return list(gen)
    else:
        return next(gen,None)

gguf.gguf_reader.ReaderField.decode = gguf_ReaderField_decode
