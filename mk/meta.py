#!/usr/bin/env python3

from pathlib import Path
from gguf.gguf_reader import GGUFReader
import json
import argparse

def convert_num(s:str) -> float|None:
    if s:
        mult = 1
        if (u := s[-1]).isalpha():
            s = s[:-1]
            match u.lower():
                case 'k': mult=1024
                case 'm': mult=1024*1024
                case 'g': mult=1024*1024*1024
                case _:
                    raise ValueError(f'Invalid suffix {u}')
        value = float(s)
        return value * mult
    else:
        return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--description', '-d', type=str, default=None,
                        help='Set description')
    parser.add_argument('--gpu-memory', type=str, default=None,
                        help='amount of memory in the gpu')
    parser.add_argument('json', type=Path,
                        help='File to write meta to')
    parser.add_argument('gguf', type=Path,
                        help='GGUF file to inspect')
    args = parser.parse_args()

    gpu_memory = convert_num(args.gpu_memory)

    if args.json.exists():
        with args.json.open('rt', encoding='utf-8') as f:
            meta = json.load(f)
    else:
        meta = dict()

    if args.description:
        meta['description'] = args.description
    
    input = GGUFReader(args.gguf)
    paramsize = 0
    parambytes = 0
    lastgpublock = None
    for t in input.tensors:
        paramsize += t.n_elements
        parambytes += t.n_bytes
        if t.name.startswith('blk.') and gpu_memory > parambytes:
            lastgpublock = t.name
    meta['paramsize'] = paramsize
    if lastgpublock:
        meta['gpulayers'] = int(lastgpublock.split('.')[1])

    with args.json.open('wt', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()
