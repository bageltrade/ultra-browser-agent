"""
Browser launcher with full Termux support.

Priority:
1. config.cdp_url / CDP_URL env
2. Termux: auto-start system Chromium + pure CDP driver (no Playwright wheel needed)
3. Desktop: standard Playwright Chromium
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Tuple


def is_termux() -> bool:
    if os.environ.get("TERMUX_VERSION") or os.environ.get("PREFIX", "").startswith("/data/data/com.termux"):
        return True
    try:
        if Path("/data/data/com.termux").exists():
            return True
    except Exception:
        pass
    return os.environ.get("UBA_FORCE_TERMUX") == "1"


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


async def launch_browser(config, pw=None) -> Tuple[Any, Any, Any]:
    """
    Returns (browser, context, page).
    On Termux uses pure CDP when Playwright is missing.
    """
    cdp_url = getattr(config, "cdp_url", None) or os.environ.get("CDP_URL")

    # --- Termux / no-Playwright path: pure CDP ---
    use_cdp = (
        is_termux()
        or not playwright_available()
        or os.environ.get("UBA_USE_CDP") == "1"
        or cdp_url
    )

    if use_cdp and (is_termux() or not playwright_available() or cdp_url):
        from .cdp_driver import connect_cdp, ensure_chromium_cdp

        if not cdp_url:
            cdp_url = await ensure_chromium_cdp(port=int(os.environ.get("CDP_PORT", "9222")))
        browser, context, page = await connect_cdp(cdp_url)
        page.set_default_timeout(int(getattr(config, "step_timeout", 60) * 1000))
        return browser, context, page

    # --- Desktop Playwright path ---
    if pw is None:
        from playwright.async_api import async_playwright
        raise RuntimeError("Playwright instance required for desktop launch")

    from playwright.async_api import Browser

    if cdp_url:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        return browser, context, page

    launch_args = {
        "headless": config.headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            f"--window-size={config.viewport_width},{config.viewport_height}",
        ],
    }
    if getattr(config, "slow_mo", 0):
        launch_args["slow_mo"] = config.slow_mo
    if getattr(config, "stealth_mode", True):
        launch_args["args"].append("--disable-features=IsolateOrigins,site-per-process")

    browser = await pw.chromium.launch(**launch_args)
    ctx_args = {
        "viewport": {"width": config.viewport_width, "height": config.viewport_height},
        "locale": getattr(config, "locale", "en-US"),
        "timezone_id": getattr(config, "timezone_id", "UTC"),
        "ignore_https_errors": getattr(config, "ignore_https_errors", True),
        "bypass_csp": getattr(config, "bypass_csp", True),
        "accept_downloads": True,
    }
    if getattr(config, "user_agent", None):
        ctx_args["user_agent"] = config.user_agent
    context = await browser.new_context(**ctx_args)
    if getattr(config, "stealth_mode", True):
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
    page = await context.new_page()
    page.set_default_timeout(int(config.step_timeout * 1000))
    return browser, context, page
