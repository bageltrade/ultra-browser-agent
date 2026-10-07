"""
Ultra Browser Agent — Web Chat UI
Mobile-first chat panel (Ask-style interface).
Works on Termux (Python + pip) and desktop.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure package root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from agent import BrowserAgent, AgentConfig

app = FastAPI(title="Ultra Browser Agent", version="2.1.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# In-memory session store (fine for single-user / Termux)
SESSIONS: Dict[str, Dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str
    url: Optional[str] = None
    max_steps: int = Field(default=80, ge=1, le=300)
    session_id: Optional[str] = None
    headless: bool = True


def _default_config(max_steps: int = 80, headless: bool = True) -> AgentConfig:
    return AgentConfig(
        api_key=os.getenv("NVIDIA_API_KEY", ""),
        api_base=os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1"),
        model=os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
        headless=headless,
        max_steps=max_steps,
        verbose=False,
        save_traces=True,
        capture_screenshots=False,
        reflection_every_n_steps=6,
        max_tokens=8192,
        temperature=0.05,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "has_api_key": bool(os.getenv("NVIDIA_API_KEY")),
        "model": os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Synchronous-style chat endpoint (runs agent to completion)."""
    if not os.getenv("NVIDIA_API_KEY"):
        return JSONResponse(
            {"error": "NVIDIA_API_KEY not set. export NVIDIA_API_KEY=nvapi-..."},
            status_code=400,
        )

    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {"messages": [], "created": time.time()}

    SESSIONS[session_id]["messages"].append({"role": "user", "content": req.message})

    config = _default_config(max_steps=req.max_steps, headless=req.headless)
    start = time.time()
    try:
        async with BrowserAgent(config) as agent:
            result = await agent.run_task(
                prompt=req.message,
                url=req.url,
                max_steps=req.max_steps,
                use_planner=True,
            )
    except Exception as e:
        result = {"success": False, "message": str(e), "data": None, "steps": 0}

    duration = round(time.time() - start, 2)
    assistant_msg = {
        "role": "assistant",
        "content": result.get("message") or "Done.",
        "success": result.get("success"),
        "data": result.get("data"),
        "steps": result.get("steps"),
        "duration_sec": duration,
        "plan": result.get("plan"),
    }
    SESSIONS[session_id]["messages"].append(assistant_msg)

    return {
        "session_id": session_id,
        "reply": assistant_msg,
        "result": {
            "success": result.get("success"),
            "message": result.get("message"),
            "data": result.get("data"),
            "steps": result.get("steps"),
            "duration_sec": duration,
        },
    }


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """Streaming-style progress over WebSocket (step updates)."""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            message = payload.get("message", "").strip()
            url = payload.get("url")
            max_steps = int(payload.get("max_steps", 80))

            if not message:
                await websocket.send_json({"type": "error", "text": "Empty message"})
                continue
            if not os.getenv("NVIDIA_API_KEY"):
                await websocket.send_json({
                    "type": "error",
                    "text": "NVIDIA_API_KEY not set on the server",
                })
                continue

            await websocket.send_json({"type": "status", "text": "Starting agent…"})

            config = _default_config(max_steps=max_steps, headless=True)
            # Monkey-patch a lightweight progress callback via history
            try:
                async with BrowserAgent(config) as agent:
                    await websocket.send_json({
                        "type": "status",
                        "text": f"Navigating / planning (max {max_steps} steps)…",
                    })
                    result = await agent.run_task(
                        prompt=message,
                        url=url,
                        max_steps=max_steps,
                        use_planner=True,
                    )
                await websocket.send_json({
                    "type": "result",
                    "success": result.get("success"),
                    "message": result.get("message"),
                    "data": result.get("data"),
                    "steps": result.get("steps"),
                    "duration_sec": result.get("duration_sec"),
                    "plan": result.get("plan"),
                })
            except Exception as e:
                await websocket.send_json({"type": "error", "text": str(e)})
    except WebSocketDisconnect:
        return


def main():
    import uvicorn
    host = os.getenv("UBA_HOST", "0.0.0.0")
    port = int(os.getenv("UBA_PORT", "8080"))
    print(f"Ultra Browser Agent UI → http://{host}:{port}")
    print("Set NVIDIA_API_KEY before starting.")
    uvicorn.run("web.app:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
