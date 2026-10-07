"""
Zero-dependency (stdlib) web chat UI for Termux.
Optional: websockets package for future live updates (not required).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATIC = Path(__file__).parent / "static"
TEMPLATES = Path(__file__).parent / "templates"

SESSIONS: Dict[str, Any] = {}


def _read_index() -> bytes:
    html_path = TEMPLATES / "index.html"
    html = html_path.read_text(encoding="utf-8")
    # Point assets to /static/
    return html.encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any):
        data = json.dumps(obj, default=str).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send(200, _read_index())
            return

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            fpath = (STATIC / rel).resolve()
            if not str(fpath).startswith(str(STATIC.resolve())) or not fpath.is_file():
                self._send(404, b"not found")
                return
            ctype = "text/plain"
            if rel.endswith(".css"):
                ctype = "text/css; charset=utf-8"
            elif rel.endswith(".js"):
                ctype = "application/javascript; charset=utf-8"
            elif rel.endswith(".png"):
                ctype = "image/png"
            self._send(200, fpath.read_bytes(), ctype)
            return

        if path == "/api/health":
            self._json(200, {
                "status": "ok",
                "has_api_key": bool(os.getenv("NVIDIA_API_KEY")),
                "model": os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
                "backend": "stdlib",
            })
            return

        self._send(404, b"not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self._send(404, b"not found")
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid JSON"})
            return

        api_key = os.getenv("NVIDIA_API_KEY", "")
        if not api_key:
            self._json(400, {"error": "NVIDIA_API_KEY not set. export NVIDIA_API_KEY=nvapi-..."})
            return

        message = (req.get("message") or "").strip()
        if not message:
            self._json(400, {"error": "Empty message"})
            return

        url = req.get("url") or None
        max_steps = int(req.get("max_steps") or 80)
        max_steps = max(1, min(max_steps, 200))
        session_id = req.get("session_id") or str(uuid.uuid4())
        headless = bool(req.get("headless", True))

        # Run agent in a fresh event loop (handler is threaded)
        try:
            result = asyncio.run(_run_agent(message, url, max_steps, headless, api_key))
        except Exception as e:
            result = {
                "success": False,
                "message": str(e),
                "data": None,
                "steps": 0,
                "duration_sec": 0,
            }

        assistant = {
            "role": "assistant",
            "content": result.get("message") or "Done.",
            "success": result.get("success"),
            "data": result.get("data"),
            "steps": result.get("steps"),
            "duration_sec": result.get("duration_sec"),
        }
        self._json(200, {
            "session_id": session_id,
            "reply": assistant,
            "result": result,
        })


async def _run_agent(message: str, url: Optional[str], max_steps: int, headless: bool, api_key: str):
    from agent import BrowserAgent, AgentConfig

    config = AgentConfig(
        api_key=api_key,
        api_base=os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1"),
        model=os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
        headless=headless,
        max_steps=max_steps,
        verbose=False,
        save_traces=True,
        capture_screenshots=False,
        reflection_every_n_steps=6,
        max_tokens=4096,
        temperature=0.05,
    )
    start = time.time()
    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            prompt=message,
            url=url,
            max_steps=max_steps,
            use_planner=True,
        )
    result["duration_sec"] = round(time.time() - start, 2)
    return {
        "success": result.get("success"),
        "message": result.get("message"),
        "data": result.get("data"),
        "steps": result.get("steps"),
        "duration_sec": result.get("duration_sec"),
        "plan": result.get("plan"),
    }


def main():
    host = os.getenv("UBA_HOST", "0.0.0.0")
    port = int(os.getenv("UBA_PORT", "8080"))
    # Ensure static/templates exist
    STATIC.mkdir(parents=True, exist_ok=True)
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    print(f"Ultra Browser Agent (stdlib) → http://{host}:{port}")
    print("Set NVIDIA_API_KEY before using chat.")
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
