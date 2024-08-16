#!/usr/bin/env python
import sys
from string import Template
from pathlib import Path, PurePosixPath as RepoPath
import shutil
import datetime
import json
import huggingface_hub
import argparse

script_dir = Path(__file__).parent
assets_dir = script_dir / 'assets'

image_files = (assets_dir / 'BackyardAI_Banner.png',
               assets_dir / 'BackyardAI_Logo.png')

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

default_description='See original model.'

def get_model_id(p: Path) -> RepoPath:
    if not p.exists():
        raise ValueError(f'{p} does not exist')
    if p.is_symlink():
        return get_model_id(p.readlink())
    for s in p.parts:
        if s.startswith('models--'):
            return RepoPath(s[8:].replace('--', '/'))
    raise ValueError(f'{p} does not resolve to a repository')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', action='store_true',
                        help='Model ID is actually a file')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file')
    parser.add_argument('--update', '-u', action='store_true',
                        help='Update existing file')
    parser.add_argument('model_id', type=str,
                        help='HuggingFace Model ID')
    parser.add_argument('--author', '-a', type=str,
                        help='Model author ID')
    parser.add_argument('--title', '-t', type=str,
                        help='Model title')
    # parser.add_argument('--name', '-n', type=str,
    #                     help='Model name')
    parser.add_argument('--context', '-c', type=int,
                        help='Model context size')
    parser.add_argument('--mistral', '-M', action='store_true',
                        help='Mistral compatibility switch')
    parser.add_argument('--date', '-d',
                        type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date(),
                        help='Model creation date')
    parser.add_argument('--description', '--desc', '-s', type=str,
                        help='Model description')
    parser.add_argument('--paramsize', '-p', type=int,
                        help='Number of parameters in the model')
    parser.add_argument('--standalone', '-S', action='store_true',
                        help='Not a HuggingFace model')
    parser.add_argument('--meta', '-m', type=Path,
                        help='meta file')
    args = parser.parse_args()

    if args.file:
        args.model_id = repo = get_model_id(model_id := Path(args.model_id))
    else:
        repo = model_id = RepoPath(args.model_id)
    quant_name = model_id.name + '-GGUF'

    if not args.output:
        args.output = Path(repo.name + '.info.md')

    if not args.output.name == '-':
        output_dir = args.output.parent if args.output.suffix == '.md' else args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        if args.output.is_dir() and not args.output == script_dir:
            for srcimg in image_files:
                dstimg = args.output / srcimg.name
                if not dstimg.exists():
                    shutil.copy(srcimg, dstimg)
            args.output = args.output / 'README.md'
        if args.output.exists() and not args.update:
            sys.exit()

    if args.standalone:
        card_data = huggingface_hub.repocard_data.ModelCardData(model_name = repo.name)
        model_info = huggingface_hub.hf_api.ModelInfo(
            id = str(repo), private = True, downloads = 0, likes = 0, tags = [], author=repo.parent, card_data = card_data,
            created_at = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
        config = {}
    else:
        model_info = hfapi.model_info(str(repo))
        card_data = model_info.card_data or huggingface_hub.repocard_data.ModelCardData(model_name = repo.name)
        config = json.loads(hfs.cat_file(repo / 'config.json'))

        if not card_data.model_name == repo.name:
            if card_data.model_name:
                sys.stderr.write(f'Warning: card_data says model name is {card_data.model_name}\n')
                sys.stderr.write(f'but model_id is {str(repo)}\n')
                raise ValueError('Model name mismatch')
            else:
                sys.stderr.write("Warning: model name not set in base model's metadata\n")

    if args.meta:
        with args.meta.open('rt', encoding='utf-8') as f:
            meta = json.load(f)
        argsd = vars(args)
        for k,v in meta.items():
            if v and k in argsd and not argsd[k]:
                argsd[k] = v

    if not args.description:
        args.description = default_description

    if not args.author:
        args.author = model_info.author
    # if not args.name:
    #     args.name = model_id.name + '-GGUF'
    if not args.title:
        args.title = model_id.name.replace('-',' ')
    if not args.date:
        args.date = model_info.created_at.date()
    if not args.context:
        if context := config.get('max_sequence_length') or config.get('max_position_embeddings'):
            if args.mistral and context > 8192:
                sys.stderr.write(f'Reducing max context from {context} to 8192\n')
                context = 8192
        else:
            sys.stderr.write("Context not specified and couldn't be inferred, defaulting to 4096\n")
            context = 4096
        args.context = context

#    if args.context % 2048:
#        raise ValueError('strange context %d'%(args.context,))

    card_data.base_model = str(repo)
    card_data.model_name = quant_name
    card_data.quantized_by = 'brooketh'
    card_data.widget = None
    card_data.eval_results = None
    if args.paramsize:
        card_data.parameter_count = args.paramsize

    args.metadata = card_data.to_yaml()

    with open(assets_dir/'README.md.template','rt',encoding='utf-8') as f:
        template = Template(f.read())

    readme = template.substitute(vars(args))
    if args.output.name == '-':
        print(readme)
    else:
        with args.output.open('wt', encoding='utf-8') as f:
            f.write(readme)
            sys.stdout.write(f'Wrote {args.output}\n')

if __name__ == '__main__':
    main()
