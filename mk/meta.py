#!/usr/bin/env python3

from pathlib import Path
from gguf.gguf_reader import GGUFReader
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('gguf', type=Path,
                        help='GGUF file to inspect')
    parser.add_argument('outfile', type=Path,
                        help='File to write meta to')
    args = parser.parse_args()

    input = GGUFReader(args.gguf)
    paramsize = sum(t.n_elements for t in input.tensors)

    with args.outfile.open('wt') as output:
        output.write(f'''# generated from {args.gguf}

model_paramsize := {paramsize}

# end of metadata
''')

if __name__ == '__main__':
    main()
