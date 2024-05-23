#!/usr/bin/env python

from string import Template
import re
from pathlib import Path
import huggingface_hub
import argparse

script_dir = Path(__file__).parent
assets_dir = script_dir / 'assets'

TEMPLATE = 'README.new.md.template'
GROUP = 'BackyardAI'

meta_rx = re.compile('---\n(.*?)\n---\n.*?\n\*\*\*\n# ((?-s:.*))\n(- \*\*.*?)\n\s*\n#', re.S)
info_rx = re.compile('^- \*\*(.*?:)\*\* (.*)$', re.M)
link_rx = re.compile('\[(.*?)]\(((https://[^/]+/)([^/]+/.*))\)$')
ctx_rx = re.compile('(\d+) tokens$')

var_rx = re.compile('\*\*([^:]+):\*\* (.*)$')

with open(assets_dir/TEMPLATE,'rt',encoding='utf-8') as f:
    template = Template(f.read())

hfapi = huggingface_hub.HfApi()
hfs = huggingface_hub.HfFileSystem()

def extract_info(text: str) -> dict:
    meta_text,info_text = text.split('\n***\n')[:2]
    try:
        meta_block = meta_text.split('---\n')[1]
    except Exception:
        meta_block = ''
    info_block = info_text.split('\n\n##')[0]
    title,*info_vars = info_block.split('\n- ')
    info = {'metadata': meta_block, 'title': title[2:]}
    for entry in info_vars:
        kv = re.sub(r'^\*\*([^:]+:)\*\* ', r'\1', entry)
        k,v = kv.split(':',1)
        try:
            match k:
                case 'Creator':
                    mm = link_rx.match(v)
                    info['author'] = mm.group(1)
                case 'Original':
                    mm = link_rx.match(v)
                    info['model_id'] = mm.group(4)
                case 'Date Created':
                    info['date'] = v
                case 'Trained Context':
                    mm = ctx_rx.match(v)
                    info['context'] = mm.group(1)
                case 'Description':
                    info['description'] = v
                case _:
                    print(f"Warning: unmatched key {k}")
        except:
            print(f"Couldn't get vars for key '{k}' and value '{v}'")
    return info

def qualify_repo(repo_id: str) -> str:
    return repo_id if '/' in repo_id else GROUP + '/' + repo_id

def readme_file(repo_id: str) -> str:
    return qualify_repo(repo_id) + '/' + 'README.md'

def update_readme(repo_id: str) -> str:
    path = repo_id + '/README.md'
    text = hfs.read_text(path, encoding='utf-8')

    if m := meta_rx.match(text):
        info = { 'metadata': m.group(1), 'title': m.group(2) }
        for kv in [s.split(':', 1) for s in re.sub(info_rx, r'\1\2', m.group(3)).split('\n')]:
            try:
                k,v = kv
            except:
                print(f"Can't split {kv}")
                return
            match k:
                case 'Creator':
                    mm = link_rx.match(v)
                    info['author'] = mm.group(1)
                case 'Original':
                    mm = link_rx.match(v)
                    info['model_id'] = mm.group(4)
                case 'Date Created':
                    info['date'] = v
                case 'Trained Context':
                    mm = ctx_rx.match(v)
                    info['context'] = mm.group(1)
                case 'Description':
                    info['description'] = v
        
        return template.substitute(info)
    else:
        raise ValueError('Malformed README.md')
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repo_id', type=str, nargs='*', help='Repository to update the README for')
    parser.add_argument('--all', '-a', action='store_true', help='Do for all repositories')
    parser.add_argument('--print-vars', '-v', action='store_true', help='Just print the extracted vars')
    parser.add_argument('--write', '-w', action='store_true', help='Write the updated file back to the repo')
    args = parser.parse_args()

    if (args.all or not len(args.repo_id) == 1) and not args.write:
        raise ValueError('multiple repo ids can only be given with --write')
    if args.all:
        repo_list = [mi.id for mi in hfapi.list_models(author='backyardai') if not mi.private]
    else:
        repo_list = args.repo_id

    for repo_id in repo_list:
        readme = readme_file(repo_id)
        old_text = hfs.read_text(readme, encoding='utf-8')
        low_text = old_text.lower()
        if 'faraday' in low_text:
            try:
                info = extract_info(old_text)
            except Exception as e:
                print(e)
                print(f'{repo_id} failed')
                continue
            if args.print_vars:
                print('Metadata:')
                for line in info['metadata'].split('\n'):
                    print('    '+line)
                del info['metadata']
                print('Info:')
                for k,v in info.items():
                    print(f'    {k}: {v}')
                return
        
            new_text = template.substitute(info)

            if args.write:
                hfs.write_text(readme, new_text, commit_message = 'Update README.md')
                print(f'Updated {repo_id}')
            else:
                print(new_text)
        elif 'backyard' in low_text:
            print(f'{repo_id} was already updated')
        else:
            print(f'{repo_id} is messed up')

if __name__ == '__main__':
    main()
