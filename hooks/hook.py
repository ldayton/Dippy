#!/usr/bin/env python3
"""Plugin hook entry point — delegates to dippy.dippy.main()."""
import os
import sys

sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "src"))
from dippy.dippy import main

main()
