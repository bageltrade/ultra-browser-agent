"""
LLM client — urllib only (stdlib). No openai, httpx, pydantic, or Rust.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


class Message:
    def __init__(self, msg: Dict[str, Any]):
        self.content = msg.get("content")
        self.role = msg.get("role", "assistant")
        self.tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            self.tool_calls.append(
                type("TC", (), {
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": type("Fn", (), {
                        "name": fn.get("name", ""),
                        "arguments": fn.get("arguments") or "{}",
                    })(),
                })()
            )


class LLMResponse:
    def __init__(self, data: Dict[str, Any]):
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        self.choices = [
            type("C", (), {
                "message": Message(msg),
                "finish_reason": choice.get("finish_reason"),
            })()
        ]


class StdlibLLM:
    """OpenAI-compatible chat.completions via urllib."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        extra_body: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> LLMResponse:
        import asyncio

        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
        if extra_body:
            body.update(extra_body)

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ultra-browser-agent/2.5",
            },
            method="POST",
        )

        def _do():
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", errors="replace")[:800]
                raise RuntimeError(f"LLM HTTP {e.code}: {err}") from e

        payload = await asyncio.to_thread(_do)
        return LLMResponse(payload)


def make_llm_client(base_url: str, api_key: str):
    """Always use stdlib urllib on constrained platforms; try openai if forced."""
    if os.environ.get("UBA_USE_OPENAI_SDK", "").lower() in ("1", "true"):
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=base_url, api_key=api_key)

            class _Compat:
                @property
                def chat(self):
                    return type("Ch", (), {"completions": client.chat.completions})()

            return _Compat()
        except ImportError:
            pass

    http = StdlibLLM(base_url, api_key)

    class _Compat:
        @property
        def chat(self):
            return type("Ch", (), {"completions": http})()

    return _Compat()
