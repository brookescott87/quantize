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
    bytesperblock = sum(t.n_bytes for t in input.tensors if t.name.startswith('blk.0.'))
    gpulayers = int(bytesperblock / 22683222016)

    with args.outfile.open('wt') as output:
        output.write(f'''# generated from {args.gguf}

model_paramsize := {paramsize}
model_bytesperblock := {bytesperblock}
model_gpulayers := {gpulayers}

# end of metadata
''')

if __name__ == '__main__':
    main()
