#!/usr/bin/env python
import os
from pathlib import Path
import huggingface_hub
import argparse

hfapi = huggingface_hub.HfApi()

def main():
    parser = argparse.ArgumentParser(prog=os.getenv('PROGRAM'))
    parser.add_argument('repo_id', type=str,
                        help='Repo id of model to retrieve')
    parser.add_argument('destdir', type=Path, nargs='?',
                        help='Directory into which a link to the model will be put')
    parser.add_argument('--affix', '-a', type=str, default='',
                        help='Local affix to model name')
    args = parser.parse_args()

    if args.affix and not args.affix.startswith('-'):
        args.affix = '-' + args.affix

    if not '/' in args.repo_id:
        raise ValueError('repo_id must be of the form owner/model')
    owner, model = args.repo_id.split('/')

    if not args.destdir:
        if model.upper().endswith('-GGUF'):
            args.destdir = Path('models/ref')
            model = model[:-5] + args.affix + '-GGUF'
        else:
            args.destdir = Path('models/base')
            model = model + args.affix

    if not args.destdir.is_dir():
        if args.destdir.exists():
            raise ValueError('%s is not a directory'%(args.destdir,))
        args.destdir.mkdir(parents=True)
    model_path = args.destdir / model

    cache_path = Path(hfapi.snapshot_download(repo_id=args.repo_id))
    model_path.symlink_to(cache_path, True)
    print(f'\n\n\n\n\n\nModel downloaded to: {model_path.absolute()}')

if __name__ == '__main__':
    main()
