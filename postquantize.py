#!/usr/bin/env python3
import os
from pathlib import Path
from typing import Iterable
import qlib
import hashlib
import subprocess
import argparse

class PurgeFailed(Exception):
    def __init__(self, path: Path):
        self.path = path

def init_paths():
    def chk(p:Path) -> Path:
        if not p.exists():
            raise FileNotFoundError("'{p}' not found")
        return p

    global toaster_root, gguf_split_exe
    if toaster_root := os.getenv('TOASTER_ROOT'):
        toaster_root = Path(toaster_root)
    else:
        raise RuntimeError('TOASTER_ROOT environment variable is not set')
    bin = chk(toaster_root / 'bin')
    gguf_split_exe = chk(bin / 'gguf-split')

def hash_file(p: Path):
    if p.exists() and p.is_file():
        outp = p.with_name(p.name + '.sha256')
        outp.unlink(missing_ok = True)
        fsize = p.stat().st_size
        with open(p, 'rb') as srcfile:
            if fsize > qlib.MAX_BLOB_SIZE:
                h = hashlib.file_digest(srcfile, 'sha256')
                with outp.open('wt') as outfile:
                    outfile.write(h.hexdigest())

def gguf_split(xguf, outp):
    result = subprocess.run([gguf_split_exe, '--split-max-size', '50G', str(xguf), str(outp)])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')

def split_or_link(xguf: Path):
    if xguf.size > qlib.MAX_UPLOAD_SIZE:
        outp = xguf.with_suffix('') + '-split'
        gguf_split(xguf, outp)
        for p in xguf.parent.glob(outp.name + '*.gguf'):
            yield(p)
    else:
        outp = xguf.with_suffix('.gguf')
        outp.hardlink_to(xguf)
        yield(outp)

def purge(p, srcp=None):
    if srcp and p.is_newer_than(srcp):
        raise PurgeFailed(p, srcp)
    p.unlink(missing_ok = True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('xguf', type=Path, help='Name of xguf file to operate on')
    args = parser.parse_args()
    init_paths()
    dirp = (xguf := args.xguf).parent
    if xguf.suffix == '.gguf':
        raise ValueError(f"{xguf} can't have .gguf suffix")
    stem = xguf.stem
    any(map(purge, dirp.glob(stem + '*.gguf'), xguf))
    any(map(purge, dirp.glob(stem + '*.gguf.sha256')))
    for outp in split_or_link(xguf):
        hash_file(outp)

def run_main():
    try:
        main()
    except PurgeFailed as nfe:
        print(f"{nfe.path} is up to date")

if __name__ == '__main__':
    run_main()
