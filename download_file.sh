#/usr/bin/env bash

if [ $# -ne 2 ]; then
	echo "usage: $0 REPO-ID FILENAME" >&2
	exit 255
fi

huggingface-cli download --local-dir . --local-dir-use-symlinks False $1 $2 
