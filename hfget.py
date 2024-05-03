#!/usr/bin/env python

import huggingface_hub
from pathlib import Path
import argparse

urlprefix = 'https://huggingface.co/'
hfapi = huggingface_hub.HfApi()

parser = argparse.ArgumentParser()
parser.add('--directory', '--dir', '-d', type=Path, default=Path('.'), help='Download directory')
parser.add('--create', '-c', action='store_true', help='Create download directory')
parser.add('url', type=str, help='Url to download')
args = parser.parse_args()

if not args.url.startswith(urlprefix):
    raise ValueError(f'url must start with "{urlprefix}"')

parts = args.url.removeprefix(urlprefix).split('/')

if len(parts) < 5 or not len[2:4] == ['blob','main']:
    raise ValueError('strangely formed url')

repo_id = '/'.join(parts[:2])
filename = '/'.join(parts[4:])

if args.directory.exists():
    if not args.directory.is_dir():
        raise ValueError(f'"{args.directory}" is not a directory')
elif args.create:
    args.directory.mkdir(parents=True)
else:
    raise ValueError(f'"{args.directory}" does not exist and --create not given')

res = hfapi.hf_hub_download(repo_id, filename, local_dir=args.directory, local_dir_use_symlinks=False)
if res:
    print(f'File downloaded to {res}')
