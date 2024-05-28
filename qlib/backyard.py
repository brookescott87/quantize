import re
from dataclasses import dataclass,field
from typing import Dict
from datetime import datetime as dt, UTC
from . import hfutil
from . import misc
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

def timestamp(t: dt=None):
    return dt.strftime(t or dt.now(tz=UTC),'%Y-%m-%dT%H:%M:%S.%f')[:-3]

class Manifest:
    @staticmethod
    def files(qm: hfutil.QuantModel, file_format:str = 'gguf_v2'):
        for mf in qm.files(lambda fn: fn.endswith('.gguf')):
            qtype = mf.name.split('.')[-2]
            lname = f'{mf.catalog_name}.{file_format}{qtype.lower()}'
            yield {
                'commitHash': qm.model_info.sha,
                'isDeprecated': False,
                'displayLink' : qm.url + '/',
                'hfPathFromRoot': mf.name,
                'fileFormat': file_format,
                'hfRepo': qm.repo_id,
                'localFilename': lname + '.gguf',
                'size': mf.size,
                'displayName': f'{mf.formal_name} ({qtype})',
                'name': lname,
                'cloudCtxSize': None
            }

    @staticmethod
    def generate(qm: hfutil.QuantModel, recommended = False, prompt_format = False, readable = False) -> str:
        if buf := qm.readme:
            info = extract_info(buf)
            if not (description := info.vars.get('Description')):
                raise ValueError("Can't extract description from infovar block")
            if description == '(Add description here)':
                raise ValueError('Description must be set')
        if prompt_format is False:
            prompt_format = qm.base_model.guess_prompt_format()
        ts = timestamp()
        
        return misc.to_json({
            'ctxSize': qm.context,
            'description': description,
            'displayName': qm.formal_name,
            'name': qm.catalog_name,
            'recommended': recommended,
            'files': list(Manifest.files(qm)),
            'featureToNewUsers': False,
            'updatedAt': ts,
            'createdAt': ts,
            'promptFormat': prompt_format or 'general',
            'isDefault': True
        }, readable)

    def show(qm: hfutil.QuantModel, readable = True, **kwargs):
        print(Manifest.generate(qm, readable = readable, **kwargs))
