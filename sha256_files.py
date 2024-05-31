#!/usr/bin/env python3

from pathlib import Path
import hashlib
import qlib
import argparse

def hash_path(p):
    return p.with_name(p.name + '.sha256')

def needs_hash(p):
    hp = hash_path(p)
    return p.stat().st_mtime > hp.stat().st_mtime if hp.exists() else True

def hash_file(p, message):
    hp = hash_path(p)
    hp.unlink(missing_ok = True)
    fsize = p.stat().st_size
    pl = qlib.misc.ProgressLine(fsize, message)
    with p.open('rb') as f:
        h = hashlib.sha256(usedforsecurity=False)
        buffer = qlib.IOBuffer(1024*1024)
        while nbytes := buffer.readfrom(f):
            h.update(buffer.bytes)
            pl.update_progress(nbytes)
        pl.finish()
        with hp.open('wt') as hf:
            hf.write(h.hexdigest()+'\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', type=Path, nargs='+',
                        help='Files to hash')
    args = parser.parse_args()

    files = [p for p in args.files if needs_hash(p)]
    fstr = 'file' if (fnum := len(files)) == 1 else 'files'
    print(f'Hashing {fnum} {fstr}')
    fctr = 0
    for f in files:
        fctr += 1
        hash_file(f, f'{fctr}/{fnum} {f.name}')

if __name__ == '__main__':
    main()
