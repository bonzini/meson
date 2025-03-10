#! /usr/bin/env python3

import sys
for fname in sys.argv[1:]:
    with open(fname, 'rb') as f:
        sys.stdout.buffer.write(f.read())
