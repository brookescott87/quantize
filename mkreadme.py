import sys
from string import Template
from pathlib import Path, PurePosixPath as RepoPath
import datetime
import json
import huggingface_hub
import argparse

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

parser = argparse.ArgumentParser()
parser.add_argument('model_id', type=str,
                    help='HuggingFace Model ID')
parser.add_argument('--author', '-a', type=str,
                    help='Model author ID')
parser.add_argument('--title', '-t', type=str,
                    help='Model title')
parser.add_argument('--name', '-n', type=str,
                    help='Model name')
parser.add_argument('--context', '-c', type=int,
                    help='Model context size')
parser.add_argument('--date', '-d',
                    type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date(),
                    help='Model creation date')
parser.add_argument('--description', '--desc', '-s', type=str, default='(Add description here)',
                    help='Model description')
parser.add_argument('--print', '-p', action='store_true',
                    help='Print result to standard output')
args = parser.parse_args()

model_info = hfapi.model_info(args.model_id)
card_data = model_info.card_data
repo = RepoPath(args.model_id)
config = json.loads(hfs.cat_file(repo / 'config.json'))

if not card_data.model_name == repo.name:
    sys.stderr.write(f'card_data says model name is {card_data.model_name}\n')
    sys.stderr.write(f'but model_id is {args.model_id}\n')
    raise ValueError('Model name mismatch')

if not args.author:
    args.author = model_info.author
if not args.name:
    args.name = repo.name + '-GGUF'
if not args.title:
    args.title = repo.name.replace('-',' ')
if not args.date:
    args.date = model_info.created_at.date()
if not args.context:
    if context := config.get('max_sequence_length') or config.get('max_position_embeddings'):
        if context > 8192:
            sys.stderr.write(f'Reducing max context from {context} to 8192\n')
            context = 8192
    else:
        sys.stderr.write("Context not specified and couldn't be inferred, defaulting to 4096\n")
        context = 4096
    args.context = context

if args.context % 2048:
    raise ValueError('strange context %d'%(args.context,))

card_data.base_model = args.model_id
card_data.model_name = args.name
card_data.quantized_by = 'brooketh'
card_data.widget = None
card_data.eval_results = None

args.metadata = card_data.to_yaml()

script_dir = Path(__file__).parent
assets_dir = script_dir / 'assets'
with open(assets_dir/'README.md.template','rt',encoding='utf-8') as f:
    template = Template(f.read())

readme = template.substitute(vars(args))
if args.print:
    print(readme)
else:
    with open('README.md', 'wt', encoding='utf-8') as f:
        f.write(readme)
