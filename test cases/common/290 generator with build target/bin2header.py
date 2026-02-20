#!/usr/bin/env python3
import sys
with open(sys.argv[1], 'rb') as f:
    data = f.read()
with open(sys.argv[2], 'w') as f:
    f.write('unsigned char fw[] = {')
    f.write(', '.join(f'0x{b:02x}' for b in data))
    f.write('};\n')
