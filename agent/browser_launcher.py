"""
Browser launcher with full Termux / Android support.

Priority:
1. config.cdp_url  → connect over CDP
2. Termux system Chromium (x11-repo) via executablePath
3. termux-playwright if installed
4. Standard Playwright Chromium (desktop Linux/macOS/Windows)
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


def is_termux() -> bool:
    """Detect Termux / Android environment."""
    if os.environ.get("TERMUX_VERSION") or os.environ.get("PREFIX", "").startswith("/data/data/com.termux"):
        return True
    # Android often reports as Linux but with specific paths
    try:
        if Path("/data/data/com.termux").exists():
            return True
    except Exception:
        pass
    return False


def find_termux_chromium() -> Optional[str]:
    """Locate Termux-packaged Chromium binary."""
    candidates = [
        os.environ.get("CHROMIUM_PATH"),
        shutil.which("chromium-browser"),
        shutil.which("chromium"),
        "/data/data/com.termux/files/usr/bin/chromium-browser",
        "/data/data/com.termux/files/usr/bin/chromium",
        str(Path(os.environ.get("PREFIX", "")) / "bin" / "chromium-browser"),
        str(Path(os.environ.get("PREFIX", "")) / "bin" / "chromium"),
    ]
    for c in candidates:
        if c and Path(c).exists() and os.access(c, os.X_OK):
            return c
    return None


def termux_chromium_args(headless: bool = True) -> list:
    args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
        "--js-flags=--jitless",  # more stable on mobile CPUs
    ]
    if headless:
        args.append("--headless=new")
    return args


async def ensure_local_cdp(
    port: int = 9222,
    chromium_path: Optional[str] = None,
    user_data_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Start Termux Chromium with remote debugging if not already running.
    Returns cdp_url or None.
    """
    import urllib.request

    cdp = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(f"{cdp}/json/version", timeout=2) as r:
            if r.status == 200:
                return cdp
    except Exception:
        pass

    exe = chromium_path or find_termux_chromium()
    if not exe:
        return None

    udd = user_data_dir or str(Path.home() / ".config" / "uba-chromium")
    Path(udd).mkdir(parents=True, exist_ok=True)

    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={udd}",
        *termux_chromium_args(headless=True),
        "about:blank",
    ]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # wait for CDP to come up
        for _ in range(20):
            await asyncio.sleep(0.5)
            try:
                with urllib.request.urlopen(f"{cdp}/json/version", timeout=1) as r:
                    if r.status == 200:
                        return cdp
            except Exception:
                continue
    except Exception:
        return None
    return None


async def launch_browser(
    config,
    pw: Playwright,
) -> Tuple[Browser, BrowserContext, Page]:
    """
    Launch or connect a browser according to config + environment.
    Returns (browser, context, page).
    """
    # 1) Explicit CDP
    cdp_url = getattr(config, "cdp_url", None) or os.environ.get("CDP_URL")
    if cdp_url:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        return browser, context, page

    # 2) Termux path
    if is_termux() or os.environ.get("UBA_FORCE_TERMUX") == "1":
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

        chromium = find_termux_chromium()
        # Prefer connect via local CDP (more stable on Android)
        auto_cdp = os.environ.get("UBA_AUTO_CDP", "1") != "0"
        if auto_cdp:
            local = await ensure_local_cdp(chromium_path=chromium)
            if local:
                browser = await pw.chromium.connect_over_cdp(local)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()
                return browser, context, page

        if chromium:
            launch_args: Dict[str, Any] = {
                "executable_path": chromium,
                "headless": config.headless,
                "args": termux_chromium_args(config.headless),
            }
            if config.slow_mo:
                launch_args["slow_mo"] = config.slow_mo
            browser = await pw.chromium.launch(**launch_args)
        else:
            # Last resort: try termux_playwright package
            try:
                from termux_playwright import async_playwright_termux, launch as tp_launch  # type: ignore
                # Caller already has pw — fallback message
                raise RuntimeError(
                    "Termux Chromium not found. Run: pkg install x11-repo chromium\n"
                    "Or: pip install termux-playwright && termux-playwright-install"
                )
            except ImportError:
                raise RuntimeError(
                    "No browser available on Termux.\n"
                    "Install with:\n"
                    "  pkg install x11-repo\n"
                    "  pkg install chromium\n"
                    "See TERMUX.md for full setup."
                )

        ctx_args: Dict[str, Any] = {
            "viewport": {"width": config.viewport_width, "height": config.viewport_height},
            "locale": config.locale,
            "timezone_id": config.timezone_id,
            "ignore_https_errors": config.ignore_https_errors,
            "bypass_csp": getattr(config, "bypass_csp", True),
            "accept_downloads": True,
        }
        if config.user_agent:
            ctx_args["user_agent"] = config.user_agent
        context = await browser.new_context(**ctx_args)
        if config.stealth_mode:
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
        page = await context.new_page()
        page.set_default_timeout(int(config.step_timeout * 1000))
        return browser, context, page

    # 3) Standard desktop launch
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
    if config.slow_mo:
        launch_args["slow_mo"] = config.slow_mo
    if config.stealth_mode:
        launch_args["args"].append("--disable-features=IsolateOrigins,site-per-process")

    browser = await pw.chromium.launch(**launch_args)
    ctx_args = {
        "viewport": {"width": config.viewport_width, "height": config.viewport_height},
        "locale": config.locale,
        "timezone_id": config.timezone_id,
        "ignore_https_errors": config.ignore_https_errors,
        "bypass_csp": getattr(config, "bypass_csp", True),
        "permissions": getattr(config, "permissions", []),
        "accept_downloads": True,
    }
    if config.user_agent:
        ctx_args["user_agent"] = config.user_agent
    if getattr(config, "geolocation", None):
        ctx_args["geolocation"] = config.geolocation

    context = await browser.new_context(**ctx_args)
    if config.stealth_mode:
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
    page = await context.new_page()
    page.set_default_timeout(int(config.step_timeout * 1000))
    return browser, context, page
