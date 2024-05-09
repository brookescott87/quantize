#!/usr/bin/env python3
from pathlib import Path
import hashlib
import iobuffer
import argparse

MAX_BLOB_SIZE = 1_000_000

def hash_file(p: Path) -> str:
    if p.exists() and p.is_file():
        fsize = p.stat().st_size
        with open(p, 'rb') as srcfile:
            if fsize > MAX_BLOB_SIZE:
                h = hashlib.file_digest(srcfile, 'sha256')
            else:
                h = hashlib.sha1(usedforsecurity=False)
                h.update(b'blob %d\0'%(fsize,))
                buffer = iobuffer.iobuffer(MAX_BLOB_SIZE)
                while buffer.readfrom(srcfile):
                    h.update(buffer.bytes)

        return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=Path, help='Name of file to calculate hash of')
    args = parser.parse_args()

    print(hash_file(args.filename))

if __name__ == '__main__':
    main()
