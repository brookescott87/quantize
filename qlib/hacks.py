from pathlib import Path

def path_add_str(self: Path, other) -> Path:
    if isinstance(other, str):
        return self.with_name(self.name + other)
    else:
        raise TypeError('Unsupported operand type(s) for +')

if not hasattr(Path, '__add__'):
    setattr(Path, '__add__', path_add_str)

def path_size(self: Path, *args, **kwargs):
    return self.stat(*args, **kwargs).st_size

if not hasattr(Path, 'size'):
    setattr(Path, 'size', path_size)
