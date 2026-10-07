from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class AgentConfig:
    """Ultra-advanced configuration for the Browser Agent (Termux + server friendly)."""

    # ── LLM (NVIDIA Nemotron / OpenAI-compatible) ──────────────────────────
    api_base: str = "https://integrate.api.nvidia.com/v1"
    api_key: str = field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", ""))
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    temperature: float = 0.05
    max_tokens: int = 8192
    extra_body: Dict[str, Any] = field(default_factory=dict)

    # ── Agent loop (much higher defaults) ──────────────────────────────────
    max_steps: int = 120                    # was 40 — complex workflows need room
    max_plan_revisions: int = 6
    reflection_every_n_steps: int = 6
    step_timeout: float = 60.0
    timeout_seconds: float = 7200.0         # 2 hours for long runs
    allow_parallel_tools: bool = True

    # ── Browser ────────────────────────────────────────────────────────────
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: Optional[str] = (
        "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
    )
    slow_mo: int = 0
    locale: str = "en-US"
    timezone_id: str = "UTC"
    geolocation: Optional[Dict[str, float]] = None
    permissions: List[str] = field(default_factory=lambda: ["geolocation"])
    bypass_csp: bool = True
    ignore_https_errors: bool = True
    stealth_mode: bool = True
    # Termux / constrained environments: set to True to skip launching a local browser
    # and only use the planning/extract path (or connect to a remote CDP endpoint).
    dry_run: bool = False
    cdp_url: Optional[str] = None          # e.g. "http://127.0.0.1:9222" for remote Chrome

    # ── Observation ────────────────────────────────────────────────────────
    max_a11y_nodes: int = 350
    max_visible_text_chars: int = 4500
    include_aria_raw_fallback: bool = True
    capture_screenshots: bool = False      # off by default to save disk on Termux
    screenshot_on_error: bool = True

    # ── Memory & history ───────────────────────────────────────────────────
    keep_full_message_history: bool = False
    max_history_messages: int = 32
    enable_episodic_memory: bool = True

    # ── Safety / observability ─────────────────────────────────────────────
    save_traces: bool = True
    trace_dir: str = "./traces"
    download_dir: str = "./downloads"
    verbose: bool = True
    log_level: str = "INFO"

    # ── Credentials (simple vault) ─────────────────────────────────────────
    credentials: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError(
                "NVIDIA_API_KEY is required. "
                "Set via environment or AgentConfig(api_key=...)."
            )
