#!/usr/bin/env python3
"""Launch the Ultra Browser Agent web chat UI."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    os.chdir(ROOT)
    from web.app import main
    main()
