#!/usr/bin/env python
import sys
import os

winner_name = ''
winner_size = 0
target = 64 * 1024 ** 3

try:
    model_list = sys.argv[1:]
except:
    model_list = []

try:
    for model in model_list:
        fn = os.path.normpath(model)
        size = abs(target - os.path.getsize(fn))
        if not winner_name or size < winner_size:
            winner_name = model
            winner_size = size

    print(winner_name)

except Exception:
    print('???')