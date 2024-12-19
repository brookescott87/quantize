import os
import io
from typing import Callable
import gguf
import numpy

__exclude__ = set(locals())
class GGUFReader(gguf.gguf_reader.GGUFReader):
    def _build_fields(self, offs: int, count: int) -> int:
        self.tensor_info_offset = offs = super()._build_fields(offs, count)
        return offs

class GGUFMetadataReader(GGUFReader):
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

__all__ = [ sym for sym in locals() if not (sym in __exclude__ or sym.startswith('_'))]
del __exclude__
