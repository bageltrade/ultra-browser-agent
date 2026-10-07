"""
Ultra-Advanced Browser Agent — Skyvern-class AI browser automation.
Powered by NVIDIA Nemotron via OpenAI-compatible API.
"""

from .core import BrowserAgent
from .config import AgentConfig

__all__ = ["BrowserAgent", "AgentConfig"]
__version__ = "2.0.0"
