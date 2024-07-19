#!/usr/bin/env python3

import struct
from pathlib import Path
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('from_file', metavar='from-file', type=Path, help='Filename to rename')
    parser.add_argument('to_file', metavar='to-file', type=Path, help='Destination filename')
    parser.add_argument('--dataset', '-s', help='Dataset URL or filename')
    parser.add_argument('--force', '-f', help='Remove destination file')
    args = parser.parse_args()

    if args.from_file.exists() and args.from_file.is_file() and not args.from_file.is_symlink():
        if args.to_file.exists():
            if args.force:
                args.to_file.unlink()
            else:
                raise ValueError(f'File "{args.to_file}" exists and --force not given')
        if args.dataset:
            with args.from_file.open('rb') as f:
                filebuf = f.read()
            fnidx = filebuf.rindex(0) + 1
            fnlen = len(filebuf) - fnidx
            if fnlen < 1 or fnlen > 32767:
                raise RuntimeError(f'Improbable dataset name length of {fnlen}')
            olddataset = str(filebuf[fnidx:],'utf-8')
            print(f'Old dataset name ({fnlen} bytes): {olddataset}')
            lenidx = fnidx - 4
            (lenval,) = struct.unpack('I', filebuf[lenidx:fnidx])
            if lenval == fnlen:
                newdataset = bytes(args.dataset, 'utf-8')
                lenval = len(newdataset)
                with args.to_file.open('wb') as f:
                    f.write(filebuf[0:lenidx])
                    f.write(struct.pack('I', lenval))
                    f.write(newdataset)
                if args.force:
                    args.from_file.unlink()
            else:
                raise RuntimeError(f'Dataset length mismatch, read {lenval} from file')
        else:
            args.from_file.rename(args.to_file)

if __name__ == '__main__':
    main()

