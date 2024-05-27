import json
from typing import Any

def to_json(obj:Any, readable=False):
    dump_opts = {'indent': 4} if readable else { 'separators': (',',':') }
    return json.dumps(obj, ensure_ascii=False, **dump_opts)
