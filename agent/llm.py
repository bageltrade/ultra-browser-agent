"""
LLM client for NVIDIA / OpenAI-compatible APIs.
Uses the official openai SDK when available; otherwise pure httpx
(required on Termux / Android where jiter has no wheels).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def _openai_available() -> bool:
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


class LLMResponse:
    """Minimal stand-in for openai ChatCompletion response."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        self.choices = [type("C", (), {"message": Message(msg), "finish_reason": choice.get("finish_reason")})()]


class Message:
    def __init__(self, msg: Dict[str, Any]):
        self.content = msg.get("content")
        self.role = msg.get("role", "assistant")
        raw_tools = msg.get("tool_calls") or []
        self.tool_calls = []
        for tc in raw_tools:
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


class HttpxLLM:
    """OpenAI-compatible chat.completions via httpx (no native deps)."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 180.0):
        import httpx
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

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
        # strip None
        body = {k: v for k, v in body.items() if v is not None}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = await self._client.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text[:800]}")
        return LLMResponse(r.json())


class OpenAILLM:
    """Wrapper around official AsyncOpenAI."""

    def __init__(self, base_url: str, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    @property
    def chat(self):
        return self._client.chat

    @property
    def completions(self):
        return self._client.chat.completions


def make_llm_client(base_url: str, api_key: str):
    """
    Prefer official openai SDK; fall back to httpx on Termux / missing wheels.
    Returns object with .chat.completions.create(...)
    """
    force_httpx = os.environ.get("UBA_HTTPX_LLM", "").lower() in ("1", "true", "yes")
    if not force_httpx and _openai_available():
        client = OpenAILLM(base_url, api_key)

        class _Compat:
            def __init__(self, c):
                self._c = c

            @property
            def chat(self):
                return type("Ch", (), {"completions": self._c.completions})()

        return _Compat(client)

    http = HttpxLLM(base_url, api_key)

    class _CompatHttp:
        def __init__(self, h: HttpxLLM):
            self._h = h

        @property
        def chat(self):
            return type("Ch", (), {"completions": self._h})()

    return _CompatHttp(http)
