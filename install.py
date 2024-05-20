#!/usr/bin/env python
import sys
import os
from pathlib import Path
import datetime
import argparse
import qlib.iobuffer as iobuffer

class statusline(object):
    def __init__(self, stream=sys.stdout):
        self.out = stream
        self.pos = 0
        self.line = 0

    def retn(self, linefeed = False):
        if (pad := self.line - self.pos) > 0:
            self.out.write(' '*pad)
        if linefeed:
            self.out.write('\n')
            self.line = 0
        else:
            self.out.write('\r')
            self.out.flush()
            self.line = self.pos
        self.pos = 0

    def print(self, text):
        self.pos += self.out.write(text)

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
            buffer = iobuffer.IOBuffer(1024*1024)
            statln = statusline()
            copied = 0
            start_time = datetime.datetime.now()
            while buffer.readfrom(srcfile):
                copied += buffer.writeto(destfile)
                progress = copied/filesize
                elapsed = datetime.datetime.now() - start_time
                estr = format_timedelta(elapsed)
                remaining = elapsed/progress
                rstr = format_timedelta(remaining)
                statln.print(f'Wrote {copied:15,} of {filesize:15,} ({progress*100:.1f}%) [{estr}<{rstr}]')
                statln.retn()
            statln.retn(True)
            stop_time = datetime.datetime.now()
            sys.stdout.write(f'Copied {copied:,} bytes in {format_timedelta(stop_time - start_time)}\n')

if sys.platform == 'win32':
    nulldev = Path('nul')
else:
    nulldev = Path('/dev/null')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=Path,
                        help='File to install')
    parser.add_argument('destdir', type=Path,
                        help='directory to install to')
    parser.add_argument('--name', '-n', type=str,
                        help='Different name to give file at destination')
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
    dest = args.destdir / (args.name or args.file.name)
    if not dest.parent == args.destdir:
        raise ValueError(f'Invalid destination name: {args.name}')
    if dest.exists():
        if not dest.is_file() or dest.is_symlink():
            raise ValueError(f'{dest} is not a regular file')
        if args.force:
            dest.unlink()
        else:
            raise ValueError(f'{dest} already exists and --force not given')
        
    tmp = dest.with_suffix(dest.suffix + '.tmp')
    copy_file(args.file, tmp)

    if args.mode:
        tmp.chmod(args.mode)
    tmp.rename(dest)
    if not args.keep:
        args.file.unlink(missing_ok=True)
        args.file.symlink_to(nulldev)

if __name__ == '__main__':
    main()
