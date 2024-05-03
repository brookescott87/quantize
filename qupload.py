#!/usr/bin/env python

import os
from pathlib import Path
import subprocess
import huggingface_hub
import argparse

MAX_UPLOAD_SIZE = 50_000_000_000
TOASTER = Path(os.environ['TOASTER'])

upload_patterns = [
    'README.md',
    '*.png',
    '*.imatrix',
    '*.gguf'
]

qsuffixes = ('.gguf', '.imatrix', '.md', '.png')
gguf_split_exe = TOASTER/'bin'/'gguf-split'

def oversize_ggufs(d: Path) -> list[Path]:
    return [f for f in d.iterdir() if f.suffix == '.gguf' and f.stat().st_size > MAX_UPLOAD_SIZE]

def gguf_split(p: Path):
    result = subprocess.run([gguf_split_exe, '--split-max-size', str(MAX_UPLOAD_SIZE), p])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')
    p.rename(p.with_suffix('.dead'))

def check_quant(qdir):
    qbig = oversize_ggufs(qdir)
    for f in qbig:
        gguf_split(f)
    if oversize_ggufs(qdir):
        raise RuntimeError(f'"{qdir}" still has oversize ggufs')
    
parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path, help='Directory containing quant.')
parser.add_argument('--initialize', '-i', action='store_true', help="Create new if doesn't exist") 
parser.add_argument('--retries', '-r', type=int, help='Number of times to retry')
args = parser.parse_args()

qdir = args.directory.absolute()

if not qdir.is_dir():
    raise ValueError(f'"{qdir}" is not a directory.')

check_quant(qdir)

repo = qdir.name
owner = qdir.parent.name
repo_id = f'{owner}/{repo}'

hfapi = huggingface_hub.HfApi()

if not hfapi.repo_exists(repo_id):
    if args.initialize:
        print(f'Initializing repository {repo_id}')
        hfapi.create_repo(repo_id, private = True, repo_type = 'model')
    else:
        raise ValueError(f'Repository {repo_id} does not exist and --initialize not given')

print(f'Uploading {repo_id}')

retries = 0

while retries <= args.retries:
    try:
        hfapi.upload_folder(repo_id=repo_id, folder_path=qdir, commit_message=f'Upload {repo}.',
                            repo_type='model', allow_patterns=upload_patterns)
    except RuntimeError:
        retries += 1
        print(f'Upload failed (retries = {retries})')
    else:
        break