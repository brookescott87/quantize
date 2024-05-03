#!/usr/bin/env python
import os
from pathlib import Path
import huggingface_hub
import argparse

parser = argparse.ArgumentParser(prog=os.getenv('PROGRAM'))
parser.add_argument('repo_id', type=str,
                    help='Repo id of model to retrieve')
parser.add_argument('destdir', type=Path, default=Path('models'), nargs='?',
                    help='Directory into which a link to the model will be put')
args = parser.parse_args()

if not '/' in args.repo_id:
    raise ValueError('repo_id must be of the form owner/model')
owner, model = args.repo_id.split('/')

if not args.destdir.is_dir():
    if args.destdir.exists():
        raise ValueError('%s is not a directory'%(args.destdir,))
    args.destdir.mkdir()
model_path = args.destdir / model

hfapi = huggingface_hub.HfApi()

cache_path = Path(hfapi.snapshot_download(repo_id=args.repo_id))
model_path.symlink_to(cache_path, True)
print(f'\n\n\n\n\n\nModel downloaded to: {model_path.absolute()}')