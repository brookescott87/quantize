from pathlib import Path
import math

def initattr(obj, name, value):
    if not hasattr(obj, name):
        setattr(obj, name, value)

def path_add_str(self: Path, other) -> Path:
    if isinstance(other, str):
        return self.with_name(self.name + other)
    else:
        raise TypeError(f'Unsupported operand type(s) for +: {repr(type(self))} and {repr(type(other))}')
initattr(Path, '__add__', path_add_str)

initattr(Path, 'size', property(lambda self: self.stat().st_size))
initattr(Path, 'mtime',
         property(lambda self: self.lstat().st_mtime if self.exists(follow_symlinks=False) else None))
# For the purpose of comparison, nonexistent file is treated as though it were infinitely old
initattr(Path, 'is_newer_than', lambda self, other: (self.mtime or -math.inf) > (other.mtime or -math.inf))
initattr(Path, 'is_older_than', lambda self, other: (self.mtime or -math.inf) < (other.mtime or -math.inf))
