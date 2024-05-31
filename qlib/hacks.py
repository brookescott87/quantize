from pathlib import Path

def path_add_str(self: Path, other) -> Path:
    if isinstance(other, str):
        return self.with_name(self.name + other)
    else:
        raise TypeError('Unsupported operand type(s) for +')

if not hasattr(Path, '__add__'):
    Path.__add__ = path_add_str
