#!/usr/bin/env python

from string import Template
import re
from pathlib import Path
import huggingface_hub
import argparse

script_dir = Path(__file__).parent
assets_dir = script_dir / 'assets'

TEMPLATE = 'README.new.md.template'
GROUP = 'FaradayDotDev'

meta_rx = re.compile('---\n(.*?)\n---\n.*?\n\*\*\*\n# ((?-s:.*))\n(- \*\*.*?)\n\s*\n#', re.S)
info_rx = re.compile('^- \*\*(.*?:)\*\* (.*)$', re.M)
link_rx = re.compile('\[(.*?)]\(((https://[^/]+/)([^/]+/.*))\)$')
ctx_rx = re.compile('(\d+) tokens$')

with open(assets_dir/TEMPLATE,'rt',encoding='utf-8') as f:
    template = Template(f.read())

hfs = huggingface_hub.HfFileSystem()

def extract_info(text: str) -> dict:
    if m := meta_rx.match(text):
        info = { 'metadata': m.group(1), 'title': m.group(2) }
        for k,v in [s.split(':', 1) for s in re.sub(info_rx, r'\1\2', m.group(3)).split('\n')]:
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
        return info
    else:
        return None

def readme_file(repo_id: str) -> str:
    return f'{GROUP}/{repo_id}/README.md'

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
    parser.add_argument('repo_id', type=str, help='Repository to update the README for')
    parser.add_argument('--print-vars', '-v', action='store_true', help='Just print the extracted vars')
    parser.add_argument('--write', '-w', action='store_true', help='Write the updated file back to the repo')
    args = parser.parse_args()

    readme = readme_file(args.repo_id)
    old_text = hfs.read_text(readme, encoding='utf-8')
    info = extract_info(old_text)
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
    else:
        print(new_text)

if __name__ == '__main__':
    main()
