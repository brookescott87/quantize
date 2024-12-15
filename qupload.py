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
HF_DEFAULT_ORGANIZATION = os.getenv('HF_DEFAULT_ORGANIZATION')
gguf_split_exe = TOASTER/'bin'/'llama-gguf-split'
shard_rx = re.compile('.*-split-\d{5}-of-\d{5}$')

def oversize_ggufs(d: Path) -> Iterator[Path]:
    return (f for f in d.iterdir() if f.suffix == '.gguf' and f.size > qlib.MAX_UPLOAD_SIZE)

def gguf_split(p: Path, keep=False):
    result = subprocess.run([gguf_split_exe, '--split-max-size', '50G', p])
    if result.returncode:
        raise RuntimeError(f'llama-gguf-split returned {result.returncode}')
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
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('directory', type=Path, help='Directory containing quant')
    parser.add_argument('--organization', '-o', type=str, default=HF_DEFAULT_ORGANIZATION, help='Organization to upload to')
    parser.add_argument('--repository', '-n', '-R', type=str, help='Repository name')
    parser.add_argument('--initialize', '-i', action='store_true', help="Create new if doesn't exist") 
    parser.add_argument('--retries', '-r', type=int, default=0, help='Number of times to retry')
    parser.add_argument('--only_shards', '-S', action='store_true', help='Only shards')
    parser.add_argument('--everything', '-E', action='store_true', help='Upload everything (USE WITH CAUTION!)')
    parser.add_argument('--ggufs', '-g', action=qlib.misc.BooleanOptionalAction, default=True, help='Include GGUFs in upload')
    parser.add_argument('--upload', '-u', action=qlib.misc.BooleanOptionalAction, default=True, help='Perform the upload')
    parser.add_argument('--keep-oversize', '--keep', '-k', action='store_true', help='Keep oversize GGUFs after splitting')
    parser.add_argument('--publish', '-p', action='store_true', help='Make repository public after upload')
    args = parser.parse_args()

    allow_patterns = [
        'README.md',
        '*.png',
        '*.imatrix'
    ]

    gguf_pattern = '*.gguf'
    shard_pattern = '*-split-?????-of-?????.gguf'

    ignore_patterns = [
        '*.sha256',
        '_*'
    ]
    
    qdir = args.directory.absolute()

    if not qdir.is_dir():
        raise ValueError(f'"{qdir}" is not a directory.')

    if args.everything:
        allow_patterns = [ '*' ]

    if args.ggufs:
        if args.only_shards:
            gguf_pattern = shard_pattern
        else:
            check_quant(qdir, args.keep_oversize)
        allow_patterns.append(gguf_pattern)

    if not (owner := args.organization):
        raise ValueError('either HF_DEFAULT_ORGANIZATION must be set or --organization must be given')

    repo = args.repository or qdir.name
    repo_id = f'{owner}/{repo}'

    if args.upload:
        uploader = qlib.Uploader(repo_id, qdir, args.retries)

        success = uploader.upload(f'Upload {repo}', allow_patterns, ignore_patterns)

        clear_screen.clear()
        print('# Upload %s after %s and %d retr%s.'%('succeeded' if success else 'failed',
                                                     uploader.elapsed,
                                                     retries := uploader.total_retries,
                                                     'y' if retries == 1 else 'ies'))
        if not success:
            return

    if args.publish:
        ri = qlib.hfapi.repo_info(repo_id)
        if ri.private:
            qlib.hfapi.update_repo_visibility(repo_id, private = False)
    print(f'Model is at {qlib.hf_url_prefix + repo_id}')

if __name__ == '__main__':
    main()
