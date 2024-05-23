#!/usr/bin/env python
import sys
import os
from os.path import relpath
from pathlib import Path
import huggingface_hub
import argparse

hfapi = huggingface_hub.HfApi()

def defvar(f, name:str, value:str=None, disable=False):
    if disable or value is None:
        f.write('#')
        value = value or ''
    if ' ' in value:
        value = f'"{value}"'
    f.write(f'export {name} := {value}\n')

def main():
    script_path = Path(sys.argv[0])
    top = script_path.parent

    parser = argparse.ArgumentParser(prog=os.getenv('PROGRAM'))
    parser.add_argument('basemodel', type=str,
                        help='Base model to be quantized')
    parser.add_argument('--build-root', '-b', type=Path, default=top/'build',
                        help='Build directory')
    parser.add_argument('--affix', '-a', type=str, default='',
                        help='Local affix to model name')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force overwrite existing files')
    args = parser.parse_args()

    if args.affix and not args.affix.startswith('-'):
        args.affix = '-' + args.affix


    if not '/' in (baserepo := args.basemodel.removeprefix('https://huggingface.co/')):
        raise ValueError('basemodel must be of the form owner/model')
    author,basemodel = baserepo.split('/')[:2]
    quantmodel = basemodel + args.affix + '-GGUF'
    quantmodel_dir = args.build_root / quantmodel
    makefile = quantmodel_dir / 'GNUmakefile'

    mk_dir = top / 'mk'
    defs_mk = relpath(mk_dir/'defs.mk', quantmodel_dir)
    basemodel_dir = quantmodel_dir / 'basemodel'
    basemodel_id = basemodel_dir / 'model-id.txt'
    basemodel_link = basemodel_dir / basemodel

    basemodel_dir.mkdir(parents=True, exist_ok=True)
    cache_path = Path(hfapi.snapshot_download(repo_id=baserepo))

    if basemodel_link.is_symlink():
        tgt = basemodel_link.readlink()
        if tgt.samefile(cache_path):
            cache_path = None
        elif not tgt.exists():
            args.force = True

    if cache_path:
        if basemodel_link.exists():
            if args.force:
                basemodel_link.unlink()
            else:
                raise RuntimeError(f'{basemodel_link} exists and --force not given')
        basemodel_link.symlink_to(cache_path, target_is_directory=True)

    with basemodel_id.open('wt') as f:
        f.write(baserepo)
        f.write('\n')
    print(f'\n\n\n\n\n\nModel downloaded to: {basemodel_link.absolute()}')

    if makefile.exists() and not args.force:
        print(f'{makefile} exists and --force not given')
        return

    with makefile.open('wt', encoding='utf-8') as f:
        defvar(f, 'TOASTER_ROOT', os.getenv('TOASTER_ROOT'))
        defvar(f, 'BASEREPO', baserepo)
        defvar(f, 'QUANTMODEL', quantmodel)
        defvar(f, 'AUTHOR', author)
        defvar(f, 'BASEMODEL', basemodel)
        f.write(f'\n\ninclude {defs_mk}\n')

    print(f'Makefile in {makefile}')

if __name__ == '__main__':
    main()
