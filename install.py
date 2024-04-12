import sys
import os
from pathlib import Path
import datetime
import argparse

class iobuffer(object):
    def __init__(self, capacity):
        self.capacity = capacity
        self.buffer = bytearray(capacity)
        self.length = 0

    @property
    def bytes(self):
        if self.length < self.capacity:
            return self.buffer[0:self.length]
        else:
            return self.buffer

    def readfrom(self, f):
        self.length = f.readinto(self.buffer)
        return self.length
    
    def writeto(self, f):
        return f.write(self.bytes) if self.length else 0

def format_timedelta(delta: datetime.timedelta) -> str:
    """Formats a timedelta duration to %H:%M:%S format"""
    seconds = int(delta.total_seconds())

    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def copy_file(srcpath: Path, destpath: Path):
    filesize = srcpath.stat().st_size

    with open(destpath, 'wb', buffering=0) as destfile:
        with open(srcpath, 'rb', buffering=0) as srcfile:
            buffer = iobuffer(1024*1024)
            copied = 0
            start_time = datetime.datetime.now()
            while buffer.readfrom(srcfile):
                copied += buffer.writeto(destfile)
                sys.stdout.write(f"\rWrote {copied} of {filesize}")
                sys.stdout.flush()
            sys.stdout.write('\n')
            stop_time = datetime.datetime.now()
            sys.stdout.write(f'Copied {copied} bytes in {format_timedelta(stop_time - start_time)}')

parser = argparse.ArgumentParser()
parser.add_argument('file', type=Path,
                    help='File to install')
parser.add_argument('destdir', type=Path,
                    help='directory to install to')
parser.add_argument('--force', '-f', action='store_true',
                    help='Overwrite existing file')
parser.add_argument('--keep', '-k', action='store_true',
                    help='Keep source file.')
parser.add_argument('--mode', '-m', type=lambda m: int(m, 8),
                    help='Installed file mode in octal')
args = parser.parse_args()
if not args.file.exists():
    raise ValueError(f'{args.file} does not exist')
if not args.file.is_file() or args.file.is_symlink():
    raise ValueError(f'{args.file} is not a regular file')
if args.destdir.exists():
    if not args.destdir.is_dir():
        raise ValueError(f'{args.destdir} is not a directory')
else:
    args.destdir.mkdir(parents=True)
dest = args.destdir / args.file.name
if dest.exists():
    if args.force:
        dest.unlink()
    else:
        raise ValueError(f'{dest} already exists and --force not given')
    
tmp = dest.with_suffix(args.file.suffix + '.tmp')
copy_file(args.file, tmp)

if args.mode:
    tmp.chmod(args.mode)
tmp.rename(dest)
if not args.keep:
    args.file.unlink(missing_ok=True)
    args.file.symlink_to(dest)
