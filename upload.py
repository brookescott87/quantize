import os
import re
from datetime import datetime as dt
from tzlocal import get_localzone
from pathlib import Path
import huggingface_hub
import argparse

MAX_UPLOAD_SIZE = 50_000_000_000
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

if (hf_key := 'HF_HUB_ENABLE_HF_TRANSFER') in os.environ:
    del os.environ[hf_key]

parser = argparse.ArgumentParser()
parser.add_argument('--all', '-a', action='store_true',
                    help='All images, even splits')
args = parser.parse_args()

hfapi = huggingface_hub.HfApi()

cwd = Path('.')
acwd = cwd.absolute()
repo = acwd.name
owner = acwd.parent.name
repo_id = f'{owner}/{repo}'

while True:
    active = False
    for f in cwd.glob('*.gguf'):
        if f.is_file() and not f.is_symlink():
            if args.all or not split_rx.match(f.name):
                if f.stat().st_size <= MAX_UPLOAD_SIZE:
                    try:
                        if not hfapi.file_exists(repo_id, f.name):
                            active = True
                            print(f'Uploading {f.name} to {repo_id}/{f.name}')
                            v = hfapi.upload_file(path_or_fileobj=f, repo_id=repo_id, path_in_repo=f.name,
                                                commit_message=f'Upload {f.name}')
                            print(f'{f.name} succeeded')
                            print_object(f.with_suffix('.log'), v)
                    except Exception as ex:
                        print(f'\n{f.name} failed due to {type(ex).__name__}')
                        print_object(f.with_suffix('.err'), ex)
    if active:
        print("Re-looping...")
    else:
        break