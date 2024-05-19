#!/usr/bin/env python

import sys
import os
import re
from pathlib import Path
from datetime import datetime as dt
from typing import Iterator,List
import subprocess
import clear_screen
import huggingface_hub
import argparse

MAX_UPLOAD_SIZE = 50_000_000_000
TOASTER = Path(os.environ['TOASTER_ROOT'])
gguf_split_exe = TOASTER/'bin'/'gguf-split'
shard_rx = re.compile('.*-split-\d{5}-of-\d{5}$')

hfapi = huggingface_hub.HfApi()

class Uploader(object):
    def __init__(self, repo_id: str, folder_path: Path, max_retries:int = 0):
        self.repo_id = repo_id
        self.folder_path = folder_path
        self.max_retries = max_retries
        self.total_retries = 0
        self.start_time = dt.now()

    @property
    def elapsed(self):
        return dt.now() - self.start_time
        
    def upload(self, message: str, allow_patterns:List[str], ignore_patterns:List[str], skip=False):
        if skip:
            return True
        retries = 0
        finished = False

        while not (finished or (self.max_retries and retries > self.max_retries)):
            clear_screen.clear()
            sys.stdout.write(message)

            if retries:
                sys.stdout.write(f' (retry {retries}')
                if self.max_retries:
                    sys.stdout.write(f' of {self.max_retries}')
                    sys.stdout.write(')')
            sys.stdout.write('\n')
            try:
                hfapi.upload_folder(repo_id=self.repo_id, folder_path=self.folder_path, commit_message=message,
                                    repo_type='model', allow_patterns=allow_patterns, ignore_patterns=ignore_patterns)
                finished = True
            except KeyboardInterrupt:
                print('\n*** Keyboard interrupt ***')
                break
            except RuntimeError:
                retries += 1
                print('Upload failed')

        self.total_retries += retries
        return finished

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

    if not hfapi.repo_exists(repo_id):
        if args.initialize:
            print(f'Initializing repository {repo_id}')
            hfapi.create_repo(repo_id, private = True, repo_type = 'model')
        else:
            raise ValueError(f'Repository {repo_id} does not exist and --initialize not given')

    if not args.no_upload:
        uploader = Uploader(repo_id, qdir, args.retries)

        if (success := uploader.upload(f'Upload {repo}', allow_patterns, ignore_patterns, args.only_shards)):
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
