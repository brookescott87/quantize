import re
from dataclasses import dataclass,field
from typing import Dict

link_rx = re.compile('\[(.*?)]\(((https://[^/]+/)([^/]+/.*))\)$')
ctx_rx = re.compile('(\d+) tokens$')

@dataclass
class InfoBlock:
    metadata: str
    title: str
    vars: Dict[str,str] = field(default_factory=dict)


def extract_info(text: str) -> dict:
    meta_text,info_text = text.split('\n***\n')[:2]
    try:
        meta_block = meta_text.split('---\n')[1]
    except Exception:
        meta_block = ''
    info_block = info_text.split('\n\n##')[0]
    title,*info_vars = info_block.split('\n- ')
    info = InfoBlock(meta_block, title[2:])
    for entry in info_vars:
        kv = re.sub(r'^\*\*([^:]+:)\*\* ', r'\1', entry)
        k,v = kv.split(':',1)
        info.vars[k] = v
    return info

def extract_vars(text: str) -> dict:
    blocks = text.split('\n***\n')
    if len(blocks) > 1:
        info_block = blocks[1]
