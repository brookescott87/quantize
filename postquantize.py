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

def split_or_link(xguf: Path, dest: Path):
    if xguf.size > qlib.MAX_UPLOAD_SIZE:
        outp = dest.with_suffix('') + '-split'
        gguf_split(xguf, outp)
        for p in xguf.parent.glob(outp.name + '*.gguf'):
            yield(p)
    else:
        dest.hardlink_to(xguf)
        yield(dest)

def purge(p, srcp=None):
    if srcp and p.is_newer_than(srcp):
        raise PurgeFailed(p, srcp)
    p.unlink(missing_ok = True)

def purge_all(dirp, pattern, srcp=None):
    for p in list(dirp.glob(pattern)):
        purge(p, srcp)
    for p in list(dirp.glob(pattern + '.sha256')):
        purge(p)

def validate(args):
    args.rename = False
    for p in (args.infile, args.outfile):
        if p and p.suffix == '.gguf':
            raise ValueError(f"{p} can't have .gguf suffix")
    if not args.infile.is_file:
        raise ValueError(f"{args.infile} is not an existing file")
    if args.outfile:
        if not args.outfile == args.infile:
            purge(args.outfile, args.infile)
            args.rename = True
    else:
        args.outfile = args.infile
    return args

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('infile', type=Path, help='Name of gguf file to operate on')
    parser.add_argument('outfile', type=Path, nargs='?', help='Name of gguf file to operate on')
    args = validate(parser.parse_args())
    init_paths()
    dirp = args.outfile.parent
    stem = args.outfile.stem
    purge_all(dirp, stem + '*.gguf', args.infile)
    for outp in split_or_link(args.infile, args.outfile.with_suffix('.gguf')):
        hash_file(outp)
    if args.rename:
        args.infile.rename(args.outfile)

def run_main():
    try:
        main()
    except PurgeFailed as nfe:
        print(f"{nfe.path} is up to date")

if __name__ == '__main__':
    run_main()
