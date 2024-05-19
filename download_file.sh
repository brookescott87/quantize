#!/usr/bin/env bash

if [ $# -lt 2 -o $# -gt 3 ]; then
    echo "usage: $0 REPO-ID FILENAME [DIR]" >&2
	exit 255
fi

repo_id="$1"
filename="$2"

if [ $# -eq 3 ]; then
    local_dir="$3"
else
    local_dir=.
fi

exec huggingface-cli download --local-dir "$local_dir" --local-dir-use-symlinks False "$repo_id" "$filename"
