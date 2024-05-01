#!/usr/bin/env python
import sys
from pathlib import Path

toastlib = str(Path('C:/Apps/Toaster/lib/python'))

if toastlib not in sys.path:
    sys.path.insert(0, toastlib)

from gguf import GGUFReader

def model_name(model):
    try:
        gguf = GGUFReader(model, 'r')
        return str(bytes(gguf.fields['general.name'].parts[-1]), encoding='utf-8')
    except:
        return '?'

models = sys.argv[1:]
for m in models:
    print('%s: "%s"'%(m, model_name(m)))
