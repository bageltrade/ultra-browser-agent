from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class AgentConfig:
    """Ultra-advanced configuration for the Browser Agent."""

    # ── LLM (NVIDIA Nemotron) ──────────────────────────────────────────────
    api_base: str = "https://integrate.api.nvidia.com/v1"
    api_key: str = field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", ""))
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    temperature: float = 0.05
    max_tokens: int = 8192
    extra_body: Dict[str, Any] = field(default_factory=dict)

    # ── Agent loop ─────────────────────────────────────────────────────────
    max_steps: int = 40
    max_plan_revisions: int = 4
    reflection_every_n_steps: int = 4
    step_timeout: float = 45.0
    timeout_seconds: float = 2400.0
    allow_parallel_tools: bool = True

    # ── Browser ────────────────────────────────────────────────────────────
    headless: bool = True
    viewport_width: int = 1440
    viewport_height: int = 900
    user_agent: Optional[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    slow_mo: int = 0
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    geolocation: Optional[Dict[str, float]] = None
    permissions: List[str] = field(default_factory=lambda: ["geolocation", "notifications"])
    bypass_csp: bool = True
    ignore_https_errors: bool = True
    stealth_mode: bool = True

    # ── Observation ────────────────────────────────────────────────────────
    max_a11y_nodes: int = 350
    max_visible_text_chars: int = 4000
    include_aria_raw_fallback: bool = True
    capture_screenshots: bool = True
    screenshot_on_error: bool = True

    # ── Memory & history ───────────────────────────────────────────────────
    keep_full_message_history: bool = False
    max_history_messages: int = 28
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
