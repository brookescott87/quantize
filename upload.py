#!/usr/bin/env python
import os
import re
from datetime import datetime as dt
from tzlocal import get_localzone
from pathlib import Path
import subprocess
import clear_screen
import huggingface_hub
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
    result = subprocess.run([gguf_split_exe, '--split-max-size', str(MAX_UPLOAD_SIZE), p])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')
    p.rename(p.with_suffix('.dead'))

def upload_file(p: Path, repo_id: str, new_name:str = None) -> bool:
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

def main():
    if (hf_key := 'HF_HUB_ENABLE_HF_TRANSFER') in os.environ:
        del os.environ[hf_key]

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', '-d', type=Path,
                        help='Directory for source files')
    parser.add_argument('--keep', '-k', action='store_true',
                        help='Do not delete files.')
    parser.add_argument
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
        else:
            try:
                if hfapi.file_exists(repo_id, f.name):
                    if args.keep:
                        print(f'Renaming {f.name}')
                        f.rename(f.with_suffix('.dead'))
                    else:
                        print(f'Removing {f.name}')
                        f.unlink()
                else:
                    upload_file(f, repo_id)
            except KeyboardInterrupt:
                print('\n*** Keyboard interrupt ***')
                break
        print()

if __name__ == '__main__':
    main()
