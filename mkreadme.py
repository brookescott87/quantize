import sys
from string import Template
from pathlib import Path, PurePosixPath as RepoPath
import datetime
import json
import huggingface_hub
import argparse

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

def get_model_id(p: Path) -> str:
    if not p.exists():
        raise ValueError(f'{p} does not exist')
    if p.is_symlink():
        return get_model_id(p.readlink())
    for s in p.parts:
        if s.startswith('models--'):
            return s[8:].replace('--', '/')
    return None

parser = argparse.ArgumentParser()
parser.add_argument('--file', '-f', action='store_true',
                    help='Model ID is actually a file')
parser.add_argument('--output', '-o', type=Path, default=Path('README.md'),
                    help='Output file')
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
args = parser.parse_args()

if args.file:
    if model_id := get_model_id(Path(args.model_id)):
        args.model_id = model_id
    else:
        raise ValueError(f"Couldn't determine model_id from {args.model_id}")

model_info = hfapi.model_info(args.model_id)
card_data = model_info.card_data
repo = RepoPath(args.model_id)
config = json.loads(hfs.cat_file(repo / 'config.json'))

if not card_data.model_name == repo.name:
    if card_data.model_name:
        sys.stderr.write(f'Warning: card_data says model name is {card_data.model_name}\n')
        sys.stderr.write(f'but model_id is {args.model_id}\n')
        raise ValueError('Model name mismatch')
    else:
        sys.stderr.write("Warning: model name not set in base model's metadata\n")

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
if args.output.name == '-':
    print(readme)
else:
    with args.output.open('wt', encoding='utf-8') as f:
        f.write(readme)
