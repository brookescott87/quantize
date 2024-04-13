from string import Template
from pathlib import Path
import datetime
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('model_id', type=str,
                    help='HuggingFace Model ID')
parser.add_argument('--author', '-a', type=str,
                    help='Model author ID')
parser.add_argument('--name', '-n', type=str,
                    help='Model name')
parser.add_argument('--context', '-c', type=int, default='4096',
                    help='Model context size')
parser.add_argument('--date', '-t',
                    type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date(),
                    default=datetime.date.today(),
                    help='Model creation date')
parser.add_argument('--description', '--desc', '-d', type=str, default='(Add description here)',
                    help='Model description')
parser.add_argument('--print', '-p', action='store_true',
                    help='Print result to standard output')
args = parser.parse_args()

author,model = args.model_id.split('/')
if not args.author:
    args.author = author
if not args.name:
    args.name = model.replace('-',' ')
if args.context % 2048:
    raise ValueError('strange context %d'%(args.context,))

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
