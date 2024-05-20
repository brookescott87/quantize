#!/usr/bin/env python

import os
import re
from pathlib import Path
from typing import Iterator
import subprocess
import clear_screen
import argparse
import qlib

MAX_UPLOAD_SIZE = 50_000_000_000
TOASTER = Path(os.environ['TOASTER_ROOT'])
gguf_split_exe = TOASTER/'bin'/'gguf-split'
shard_rx = re.compile('.*-split-\d{5}-of-\d{5}$')

def oversize_ggufs(d: Path) -> Iterator[Path]:
    return (f for f in d.iterdir() if f.suffix == '.gguf' and f.stat().st_size > MAX_UPLOAD_SIZE)

def gguf_split(p: Path, keep=False):
    result = subprocess.run([gguf_split_exe, '--split-max-size', str(MAX_UPLOAD_SIZE), p])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')
    if keep:
        p.rename(p.with_suffix('.dead'))
    else:
        p.unlink()

def check_quant(qdir, keep_oversize=False):
    qbig = list(oversize_ggufs(qdir))
    for f in qbig:
        if shard_rx.match(f.stem):
            raise RuntimeError(f'GGUF shard "{f}" is oversize!')
        gguf_split(f, keep_oversize)
    if any(oversize_ggufs(qdir)):
        raise RuntimeError(f'"{qdir}" still has oversize ggufs')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path, help='Directory containing quant.')
    parser.add_argument('--initialize', '-i', action='store_true', help="Create new if doesn't exist") 
    parser.add_argument('--retries', '-r', type=int, default=0, help='Number of times to retry')
    parser.add_argument('--only_shards', '-S', action='store_true', help='Only shards')
    parser.add_argument('--no-ggufs', '-g', action='store_true', help='Exclude GGUFs from upload')
    parser.add_argument('--no-upload', '-u', action='store_true', help='Do not upload any files')
    parser.add_argument('--keep-oversize', '--keep', '-k', action='store_true', help='Keep oversize GGUFs after splitting')
    args = parser.parse_args()

    allow_patterns = [
        'README.md',
        '*.png',
        '*.imatrix'
    ]

    gguf_pattern = '*.gguf'
    shard_pattern = '*-split-?????-of-?????.gguf'

    ignore_patterns = []
    
    qdir = args.directory.absolute()

    if not qdir.is_dir():
        raise ValueError(f'"{qdir}" is not a directory.')

    if not args.no_ggufs:
        allow_patterns.append(gguf_pattern)
        ignore_patterns.append(shard_pattern)
        check_quant(qdir, args.keep_oversize)

    repo = qdir.name
    owner = qdir.parent.name
    repo_id = f'{owner}/{repo}'

    if not args.no_upload:
        uploader = qlib.Uploader(repo_id, qdir, args.retries)

        if (success := uploader.upload(f'Upload {repo}', allow_patterns, ignore_patterns, skip=args.only_shards)):
            if not args.no_ggufs:
                if any(qdir.glob(shard_pattern)):
                    success = uploader.upload('Upload shards', [shard_pattern], [])

        clear_screen.clear()
        print('# Upload %s after %s and %d retr%s.'%('succeeded' if success else 'failed',
                                                     uploader.elapsed,
                                                     retries := uploader.total_retries,
                                                     'y' if retries == 1 else 'ies'))

if __name__ == '__main__':
    main()
