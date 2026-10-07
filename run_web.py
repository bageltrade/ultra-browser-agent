#!/usr/bin/env python3
"""Launch Ultra Browser Agent web UI (stdlib on Termux, FastAPI if available)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

def main():
    use_stdlib = (
        os.environ.get("UBA_STDLIB_UI", "").lower() in ("1", "true", "yes")
        or os.environ.get("TERMUX_VERSION")
        or os.environ.get("PREFIX", "").startswith("/data/data/com.termux")
    )
    if not use_stdlib:
        try:
            import fastapi  # noqa: F401
            import uvicorn  # noqa: F401
        except ImportError:
            use_stdlib = True

    if use_stdlib:
        from web.stdlib_app import main as stdlib_main
        stdlib_main()
    else:
        from web.app import main as fastapi_main
        fastapi_main()

if __name__ == "__main__":
    main()
