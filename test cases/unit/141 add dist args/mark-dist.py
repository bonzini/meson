#!/usr/bin/env python3

import os
from pathlib import Path

Path(os.environ['MESON_DIST_ROOT'], 'distcheck.txt').touch()
