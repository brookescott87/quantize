#!/usr/bin/env python
import sys
import os
from os.path import relpath
from pathlib import Path
import argparse
import qlib

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

    if qbr := os.getenv('QUANTIZE_BUILD_ROOT'):
        quantize_build_root = Path(qbr)
    else:
        quantize_build_root = top/'build'

    parser = argparse.ArgumentParser(prog=os.getenv('PROGRAM'))
    parser.add_argument('basemodel', type=str,
                        help='Base model to be quantized')
    parser.add_argument('--build-root', '-b', type=Path, default=quantize_build_root,
                        help=f'Build directory (default="{quantize_build_root}")')
    parser.add_argument('--name', '-n', type=str,
                        help='Model name override')
    parser.add_argument('--affix', '-a', type=str, default='',
                        help='Local affix to model name')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force overwrite existing files')
    parser.add_argument('--description', '--desc', '-s', type=str, default=None,
                        help='Description of the model')
    parser.add_argument('--llama-bpe', '-L', action='store_true',
                        help='Use llama-bpe pretokenizer')
    parser.add_argument('--ftype', '-F', type=str.upper, choices=('F32', 'F16', 'BF16'),
                        help='Floating point type of base model'),
    parser.add_argument('--requant', '-R', action='store_true',
                        help='Model is a requant')
    parser.add_argument('--test', action='store_true',
                        help='Test mode')
    args = parser.parse_args()

    if args.affix and not args.affix.startswith('-'):
        args.affix = '-' + args.affix

    if not '/' in (baserepo := args.basemodel.removeprefix(qlib.hf_url_prefix)):
        raise ValueError('basemodel must be of the form owner/model')
    
    basemodel = qlib.SourceModel(baserepo)

    quantmodel = (args.name or basemodel.model_name) + args.affix
    quantmodel_dir = args.build_root / (quantmodel + '-GGUF')
    makefile = quantmodel_dir / 'GNUmakefile'

    mk_dir = top / 'mk'
    defs_mk = mk_dir/'defs.mk'
    if quantmodel_dir.is_absolute():
        defs_mk = defs_mk.absolute()
    else:
        defs_mk = relpath(defs_mk, quantmodel_dir)
    basemodel_dir = quantmodel_dir / 'basemodel'
    basemodel_id = basemodel_dir / 'model-id.txt'
    basemodel_link = basemodel_dir / basemodel.model_name

    basemodel_dir.mkdir(parents=True, exist_ok=True)
    if not args.test:
        cache_path = basemodel.download()

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

    ftype = args.ftype or qlib.guess_model_datatype(basemodel_link)

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
        if args.llama_bpe:
            defvar(f, 'PRETOKENIZER', 'llama-bpe')
        defvar(f, 'AUTHOR', basemodel.owner)
        defvar(f, 'BASEMODEL', basemodel.model_name)
        defvar(f, 'CATNAME', basemodel.catalog_name)
        defvar(f, 'FULLNAME', basemodel.formal_name)
        if args.requant:
            defvar(f, 'REQUANT', str(1))
        else:
            defvar(f, 'DESCRIPTION', args.description)
        defvar(f, 'FTYPE', ftype)
        f.write(f'\ninclude {defs_mk}\n\n')

    print(f'Makefile in {makefile}')

if __name__ == '__main__':
    main()
