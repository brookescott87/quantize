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
split_rx = re.compile('.*-split-\d{5}-of-\d{5}\.gguf$')

TOASTER = Path(os.environ['TOASTER'])
gguf_split_exe = TOASTER/'bin'/'gguf-split'

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
        for f in dirp.glob(g):
            if f.is_file() and not f.is_symlink():
                return f
    return None

def gguf_split(p: Path):
    result = subprocess.run([gguf_split_exe, '--split-max-size', str(MAX_UPLOAD_SIZE), p])
    if result.returncode:
        raise RuntimeError(f'gguf-split returned {result.returncode}')
    p.rename(p.with_suffix('.dead'))

if (hf_key := 'HF_HUB_ENABLE_HF_TRANSFER') in os.environ:
    del os.environ[hf_key]

parser = argparse.ArgumentParser()
parser.add_argument('--dir', '-d', type=Path,
                    help='Directory for source files')
parser.add_argument
args = parser.parse_args()

hfapi = huggingface_hub.HfApi()

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
                print(f'Removing {f.name}')
                f.unlink()
            else:
                print(f'Uploading {f.name} to {repo_id}/{f.name}')
                v = hfapi.upload_file(path_or_fileobj=f, repo_id=repo_id, path_in_repo=f.name,
                                    commit_message=f'Upload {f.name}')
                print(f'{f.name} succeeded')
                print_object(f.with_suffix('.log'), v)
        except Exception as ex:
            print(f'\n{f.name} failed due to {type(ex).__name__}')
            print_object(f.with_suffix('.err'), ex)
