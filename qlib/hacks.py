from pathlib import Path

def path_add_str(self: Path, other) -> Path:
    if isinstance(other, str):
        return self.with_name(self.name + other)
    else:
        raise TypeError(f'Unsupported operand type(s) for +: {repr(type(self))} and {repr(type(other))}')

if not hasattr(Path, '__add__'):
    setattr(Path, '__add__', path_add_str)

@property
def path_size(self: Path):
    return self.stat().st_size

if not hasattr(Path, 'size'):
    setattr(Path, 'size', path_size)
