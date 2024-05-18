#!/usr/bin/env python

import os
from pathlib import Path
from datetime import datetime as dt
import subprocess
import clear_screen
import huggingface_hub
import argparse

MAX_UPLOAD_SIZE = 50_000_000_000
TOASTER = Path(os.environ['TOASTER_ROOT'])
gguf_split_exe = TOASTER/'bin'/'gguf-split'

hfapi = huggingface_hub.HfApi()

def oversize_ggufs(d: Path) -> list[Path]:
    return [f for f in d.iterdir() if f.suffix == '.gguf' and f.stat().st_size > MAX_UPLOAD_SIZE]

def gguf_split(p: Path, keep=False):
    result = subprocess.run([gguf_split_exe, '--split-max-size', str(MAX_UPLOAD_SIZE), p])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')
    if keep:
        p.rename(p.with_suffix('.dead'))
    else:
        p.unlink()

def check_quant(qdir, keep_oversize=False):
    qbig = oversize_ggufs(qdir)
    for f in qbig:
        gguf_split(f, keep_oversize)
    if oversize_ggufs(qdir):
        raise RuntimeError(f'"{qdir}" still has oversize ggufs')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path, help='Directory containing quant.')
    parser.add_argument('--initialize', '-i', action='store_true', help="Create new if doesn't exist") 
    parser.add_argument('--retries', '-r', type=int, default=0, help='Number of times to retry')
    parser.add_argument('--no-ggufs', '-g', action='store_true', help='Exclude GGUFs from upload')
    parser.add_argument('--no-upload', '-u', action='store_true', help='Do not upload any files')
    parser.add_argument('--keep-oversize', '--keep', '-k', action='store_true', help='Keep oversize GGUFs after splitting')
    args = parser.parse_args()

    upload_patterns = [
        'README.md',
        '*.png',
        '*.imatrix'
    ]

    qdir = args.directory.absolute()

    if not qdir.is_dir():
        raise ValueError(f'"{qdir}" is not a directory.')

    if not args.no_ggufs:
        upload_patterns.append('*.gguf')
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
        print(f'Uploading {repo_id}')

        running = True
        retries = 0
        start_time = dt.now()

        while running and retries <= args.retries:
            try:
                hfapi.upload_folder(repo_id=repo_id, folder_path=qdir, commit_message=f'Upload {repo}.',
                                    repo_type='model', allow_patterns=upload_patterns)
                running = False
            except RuntimeError:
                retries += 1
                print(f'Upload failed (retries = {retries})')

        elapsed = dt.now() - start_time
        result = 'failed' if running else 'succeeded'
        clear_screen.clear()
        print(f"# Upload {result} after {elapsed} and {retries} retr{'y' if retries == 1 else 'ies'}.")

if __name__ == '__main__':
    main()
