#!/usr/bin/env python
import os
import re
from datetime import datetime as dt
from tzlocal import get_localzone
from pathlib import Path
import subprocess
import clear_screen
import huggingface_hub
from huggingface_hub.hf_api import RepoFile
import argparse

MAX_UPLOAD_SIZE = 50_000_000_000
TOASTER = Path(os.environ['TOASTER_ROOT'])
gguf_split_exe = TOASTER/'bin'/'gguf-split'

hfapi = huggingface_hub.HfApi()

split_rx = re.compile('.*-split-\d{5}-of-\d{5}\.gguf$')

def timestamp():
    return dt.strftime(dt.now(get_localzone()), '%Y/%m/%d-%H:%M:%S(%Z)')

def print_object(p, obj):
    try:
        with open(p, 'at', encoding='utf-8') as errfile:
            errfile.write(f'{timestamp()} {str(obj)}\n')
    except:
        print(f'Failed to write {type(obj).__name__} to {p}')
    else:
        print(f'Wrote {type(obj).__name__} to {p}')

def next_file(dirp):
    for g in ('README.md','*.png','*.imatrix','*.gguf'):
        for f in sorted(dirp.glob(g),key=lambda p: p.stat().st_size):
            if f.is_file() and not f.is_symlink():
                return f
    return None

def gguf_split(p: Path):
    result = subprocess.run([gguf_split_exe, '--split-max-size', '50G', p])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')
    remove_file(p)

def upload_file(repo_id: str, p: Path, new_name:str = None) -> bool:
    name = new_name or p.name
    print(f'{timestamp()} ### Uploading {p.name} to {repo_id}/{name}')
    try:
        v = hfapi.upload_file(path_or_fileobj=p, repo_id=repo_id, path_in_repo=name,
                              commit_message=f'Upload {name}')
        print_object(p.with_suffix('.log'), v)
    except KeyboardInterrupt as k:
        raise(k)
    except Exception as e:
        print_object(p.with_suffix('.err'), e)
        print(f'\n{p.name} failed due to {type(e).__name__}')
    else:
        print(f'{timestamp()} {p.name} succeeded')
        return True
    return False

def remove_file(p:Path, destroy:bool=False):
    if destroy:
        print(f'Removing {p.name}')
        p.unlink()
    else:
        dname = p.name + '.dead'
        pdead = p.with_name(dname)
        num = 0
        while pdead.exists():
            num += 1
            pdead = p.with_name(dname + str(num))
        print(f'Renaming {p.name} to {pdead.name}')
        p.rename(pdead)

def get_path_info(repo_id : str, path : str) -> RepoFile:
    result = hfapi.get_paths_info(repo_id, path, expand=True)
    for rf in result:
        if rf.path == path:
            return rf
    return None

def get_file_info(repo_id : str, f : Path) -> RepoFile:
    return get_path_info(repo_id, f.name)

def file_is_newer(repo_id : str, f : Path):
    if rf := get_file_info(repo_id, f):
        lf = f.stat()
        if lf.st_size == rf.size and lf.st_mtime < rf.last_commit.date.timestamp():
            return False
    return True

def main():
    if (hf_key := 'HF_HUB_ENABLE_HF_TRANSFER') in os.environ:
        del os.environ[hf_key]

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', '-d', type=Path,
                        help='Directory for source files')
    parser.add_argument('--remove', '-r', action='store_true',
                        help='Remove files after successful upload')
    args = parser.parse_args()

    if args.dir:
        os.chdir(args.dir)

    cwd = Path('.')
    acwd = cwd.absolute()
    repo = acwd.name
    owner = acwd.parent.name
    repo_id = f'{owner}/{repo}'

    clear_screen.clear()
    while f := next_file(cwd):
        if f.stat().st_size > MAX_UPLOAD_SIZE:
            gguf_split(f)
        elif file_is_newer(repo_id, f):
            upload_file(repo_id, f)
        else:
            remove_file(f, args.remove)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n*** Keyboard interrupt ***')
    print()
