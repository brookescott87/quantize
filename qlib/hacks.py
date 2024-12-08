from typing import Any
import pathlib
import math

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
