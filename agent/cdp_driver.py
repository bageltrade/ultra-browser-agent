"""
Pure CDP browser driver for Termux / Android.
No Playwright package required — talks to Chromium over Chrome DevTools Protocol.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class CDPError(Exception):
    pass


class CDPConnection:
    """Minimal async CDP client over WebSocket."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._ws = None
        self._id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_handlers: Dict[str, List] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self):
        try:
            import websockets
        except ImportError as e:
            raise RuntimeError(
                "websockets package required for CDP. Install with:\n"
                "  pip install websockets\n"
                "(pure Python — no Rust/compiler needed)"
            ) from e
        self._ws = await websockets.connect(
            self.ws_url,
            max_size=32 * 1024 * 1024,
            ping_interval=20,
        )
        self._reader_task = asyncio.create_task(self._reader())

    async def close(self):
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _reader(self):
        assert self._ws
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if "id" in msg and msg["id"] in self._pending:
                fut = self._pending.pop(msg["id"])
                if "error" in msg:
                    fut.set_exception(CDPError(str(msg["error"])))
                else:
                    fut.set_result(msg.get("result", {}))
            elif "method" in msg:
                for h in self._event_handlers.get(msg["method"], []):
                    try:
                        h(msg.get("params", {}))
                    except Exception:
                        pass

    async def call(self, method: str, params: Optional[Dict] = None, timeout: float = 30.0) -> Dict:
        assert self._ws
        self._id += 1
        msg_id = self._id
        payload = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        await self._ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=timeout)

    def on(self, event: str, handler):
        self._event_handlers.setdefault(event, []).append(handler)


class CDPPage:
    """Page-like API used by the agent (subset of Playwright Page)."""

    def __init__(self, conn: CDPConnection, target_id: str, session_id: Optional[str] = None):
        self.conn = conn
        self.target_id = target_id
        self.session_id = session_id
        self._url = "about:blank"
        self._default_timeout = 30000

    def set_default_timeout(self, ms: int):
        self._default_timeout = ms

    async def _session_call(self, method: str, params: Optional[Dict] = None, timeout: float = 30.0) -> Dict:
        if self.session_id:
            # Target session via Target.sendMessageToTarget is legacy; prefer flat session
            return await self.conn.call(method, params, timeout=timeout)
        return await self.conn.call(method, params, timeout=timeout)

    @property
    def url(self) -> str:
        return self._url

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000):
        await self.conn.call("Page.enable")
        await self.conn.call("Runtime.enable")
        await self.conn.call("DOM.enable")
        result = await self.conn.call(
            "Page.navigate",
            {"url": url},
            timeout=timeout / 1000.0 + 5,
        )
        # wait briefly for load
        await asyncio.sleep(0.8)
        self._url = url
        try:
            info = await self.conn.call("Target.getTargetInfo", {"targetId": self.target_id})
            self._url = info.get("targetInfo", {}).get("url", url)
        except Exception:
            pass
        return result

    async def title(self) -> str:
        r = await self.conn.call("Runtime.evaluate", {
            "expression": "document.title",
            "returnByValue": True,
        })
        return (r.get("result") or {}).get("value") or ""

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        # Support simple function form from Playwright-style evaluate
        if arg is not None:
            expr = f"({expression})({json.dumps(arg)})"
        else:
            expr = expression if not expression.strip().startswith("()") else f"({expression})()"
            if expression.strip().startswith("(") or "=>" in expression or expression.strip().startswith("function"):
                expr = f"({expression})()"
            else:
                expr = expression
        r = await self.conn.call("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if "exceptionDetails" in r:
            raise CDPError(str(r["exceptionDetails"]))
        return (r.get("result") or {}).get("value")

    async def content(self) -> str:
        return await self.evaluate("document.documentElement.outerHTML")

    async def click_selector(self, selector: str, timeout: float = 10.0):
        js = """(sel) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('not found: ' + sel);
            el.scrollIntoView({block: 'center'});
            el.click();
            return true;
        }"""
        await self.evaluate(js, selector)

    async def fill_selector(self, selector: str, text: str):
        js = """(args) => {
            const el = document.querySelector(args.sel);
            if (!el) throw new Error('not found');
            el.focus();
            el.value = '';
            el.value = args.text;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }"""
        await self.evaluate(js, {"sel": selector, "text": text})

    async def press(self, key: str):
        # CDP Input
        key_map = {
            "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
            "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
            "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
        }
        k = key_map.get(key, {"key": key, "code": key})
        await self.conn.call("Input.dispatchKeyEvent", {"type": "keyDown", **k})
        await self.conn.call("Input.dispatchKeyEvent", {"type": "keyUp", **k})

    async def type_text(self, text: str):
        await self.conn.call("Input.insertText", {"text": text})

    async def mouse_click(self, x: float, y: float):
        for t in ("mousePressed", "mouseReleased"):
            await self.conn.call("Input.dispatchMouseEvent", {
                "type": t, "x": x, "y": y, "button": "left", "clickCount": 1,
            })

    async def wheel(self, delta_y: int):
        await self.conn.call("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": 100, "y": 100,
            "deltaX": 0, "deltaY": delta_y,
        })

    async def screenshot(self, path: str, full_page: bool = False):
        r = await self.conn.call("Page.captureScreenshot", {"format": "png"})
        import base64
        data = base64.b64decode(r.get("data", ""))
        Path(path).write_bytes(data)

    async def wait_for_load_state(self, state: str = "domcontentloaded", timeout: int = 8000):
        await asyncio.sleep(min(timeout / 1000.0, 2.0))

    async def go_back(self, wait_until: str = "domcontentloaded", timeout: int = 15000):
        await self.evaluate("window.history.back()")
        await asyncio.sleep(0.8)

    async def bring_to_front(self):
        pass

    # --- Playwright-compatible helpers used by tools/observation ---

    def locator(self, selector: str):
        return CDPLocator(self, selector)

    def get_by_role(self, role: str, name: Optional[str] = None, exact: bool = False):
        return CDPRoleLocator(self, role, name, exact)

    def get_by_text(self, text: str, exact: bool = False):
        return CDPTextLocator(self, text, exact)

    def get_by_placeholder(self, text: str, exact: bool = False):
        return CDPPlaceholderLocator(self, text, exact)

    @property
    def keyboard(self):
        return CDPKeyboard(self)

    @property
    def mouse(self):
        return CDPMouse(self)

    @property
    def accessibility(self):
        return CDPAccessibility(self)


class CDPLocator:
    def __init__(self, page: CDPPage, selector: str):
        self.page = page
        self.selector = selector
        self.first = self

    async def click(self, timeout: int = 10000):
        await self.page.click_selector(self.selector)

    async def fill(self, text: str):
        await self.page.fill_selector(self.selector, text)

    async def press(self, key: str):
        await self.page.press(key)

    async def hover(self, timeout: int = 8000):
        js = """(sel) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('not found');
            el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
            return true;
        }"""
        await self.page.evaluate(js, self.selector)

    async def scroll_into_view_if_needed(self):
        await self.page.evaluate(
            "(sel) => { const el = document.querySelector(sel); if (el) el.scrollIntoView({block:'center'}); }",
            self.selector,
        )

    async def select_option(self, label: str = None, value: str = None, timeout: int = 8000):
        js = """(args) => {
            const el = document.querySelector(args.sel);
            if (!el) throw new Error('not found');
            if (args.value != null) el.value = args.value;
            if (args.label != null) {
                for (const o of el.options) {
                    if (o.text === args.label || o.label === args.label) { el.value = o.value; break; }
                }
            }
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }"""
        await self.page.evaluate(js, {"sel": self.selector, "label": label, "value": value})

    def count(self):
        return 1


class CDPRoleLocator(CDPLocator):
    def __init__(self, page: CDPPage, role: str, name: Optional[str], exact: bool):
        # Build a CSS/ARIA selector approximation
        sel = f'[role="{role}"]'
        if name:
            sel = f'[role="{role}"][aria-label*="{name}"], [role="{role}"]:has-text("{name}")'
        # Prefer JS query for role+name
        super().__init__(page, sel)
        self.role = role
        self.name = name or ""
        self.exact = exact

    async def click(self, timeout: int = 10000):
        js = """(args) => {
            const role = args.role, name = args.name, exact = args.exact;
            const all = Array.from(document.querySelectorAll('*'));
            const match = all.find(el => {
                const r = (el.getAttribute('role') || el.tagName || '').toLowerCase();
                const roleMap = {a:'link', button:'button', input:'textbox', select:'combobox', textarea:'textbox'};
                const resolved = el.getAttribute('role') || roleMap[el.tagName.toLowerCase()] || '';
                if (resolved.toLowerCase() !== role && el.tagName.toLowerCase() !== role) {
                    if (!(role === 'link' && el.tagName === 'A')) return false;
                    if (!(role === 'button' && (el.tagName === 'BUTTON' || el.type === 'submit'))) return false;
                    if (!(role === 'textbox' && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA'))) return false;
                }
                const label = (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || '').trim();
                if (!name) return true;
                return exact ? label === name : label.toLowerCase().includes(name.toLowerCase());
            });
            if (!match) throw new Error('role not found: ' + role + ' ' + name);
            match.scrollIntoView({block:'center'});
            match.click();
            return true;
        }"""
        await self.page.evaluate(js, {"role": self.role, "name": self.name, "exact": self.exact})

    async def fill(self, text: str):
        js = """(args) => {
            const role = args.role, name = args.name, text = args.text;
            const inputs = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'));
            const el = inputs.find(el => {
                const label = (el.getAttribute('aria-label') || el.placeholder || el.name || el.id || '').trim();
                if (!name) return true;
                return label.toLowerCase().includes(name.toLowerCase());
            }) || inputs[0];
            if (!el) throw new Error('textbox not found');
            el.focus();
            if (el.value !== undefined) { el.value = ''; el.value = text; }
            else { el.innerText = text; }
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }"""
        await self.page.evaluate(js, {"role": self.role, "name": self.name, "text": text})


class CDPTextLocator(CDPLocator):
    def __init__(self, page: CDPPage, text: str, exact: bool):
        super().__init__(page, f"text={text}")
        self.text = text
        self.exact = exact

    async def click(self, timeout: int = 10000):
        js = """(args) => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
            let n;
            while (n = walker.nextNode()) {
                const t = (n.innerText || '').trim();
                if (!t) continue;
                const ok = args.exact ? t === args.text : t.toLowerCase().includes(args.text.toLowerCase());
                if (ok && n.children.length < 5) { n.scrollIntoView({block:'center'}); n.click(); return true; }
            }
            throw new Error('text not found');
        }"""
        await self.page.evaluate(js, {"text": self.text, "exact": self.exact})


class CDPPlaceholderLocator(CDPLocator):
    def __init__(self, page: CDPPage, text: str, exact: bool):
        super().__init__(page, f"[placeholder*='{text}']")
        self.text = text

    async def fill(self, text: str):
        await self.page.fill_selector(f"[placeholder*='{self.text}']", text)

    async def click(self, timeout: int = 10000):
        await self.page.click_selector(f"[placeholder*='{self.text}']")


class CDPKeyboard:
    def __init__(self, page: CDPPage):
        self.page = page

    async def press(self, key: str):
        await self.page.press(key)


class CDPMouse:
    def __init__(self, page: CDPPage):
        self.page = page

    async def wheel(self, dx: int, dy: int):
        await self.page.wheel(dy)


class CDPAccessibility:
    def __init__(self, page: CDPPage):
        self.page = page

    async def snapshot(self, interesting_only: bool = True) -> Optional[Dict]:
        # Build a simplified a11y-like tree via JS
        js = """() => {
            const roles = new Set(['button','link','textbox','searchbox','checkbox','radio',
                'combobox','listbox','option','heading','img','navigation','main','form',
                'dialog','tab','menuitem','switch','article','listitem','cell','row']);
            const nodes = [];
            function walk(el, depth) {
                if (!el || depth > 12 || nodes.length > 200) return;
                const tag = (el.tagName || '').toLowerCase();
                if (['script','style','noscript','svg'].includes(tag)) return;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return;
                let role = el.getAttribute('role') || '';
                if (!role) {
                    if (tag === 'a') role = 'link';
                    else if (tag === 'button') role = 'button';
                    else if (tag === 'input') role = el.type === 'checkbox' ? 'checkbox' : (el.type === 'radio' ? 'radio' : 'textbox');
                    else if (tag === 'textarea') role = 'textbox';
                    else if (tag === 'select') role = 'combobox';
                    else if (/^h[1-6]$/.test(tag)) role = 'heading';
                    else if (tag === 'img') role = 'img';
                    else if (tag === 'nav') role = 'navigation';
                }
                const name = (el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
                    (role === 'textbox' ? '' : (el.innerText || '')).split('\\n')[0] ||
                    el.getAttribute('name') || el.getAttribute('alt') || '').trim().slice(0, 120);
                if (role && (roles.has(role) || name)) {
                    nodes.push({role, name, depth});
                }
                for (const c of el.children || []) walk(c, depth + 1);
            }
            walk(document.body, 0);
            // Convert to nested-ish structure for compatibility
            function nest(list) {
                if (!list.length) return null;
                const root = {role: 'RootWebArea', name: document.title, children: []};
                for (const n of list) {
                    root.children.push({role: n.role, name: n.name, children: []});
                }
                return root;
            }
            return nest(nodes);
        }"""
        return await self.page.evaluate(js)


class CDPBrowser:
    def __init__(self, conn: CDPConnection, browser_ws: str):
        self.conn = conn
        self.browser_ws = browser_ws
        self.contexts: List[CDPContext] = []

    async def close(self):
        await self.conn.close()

    async def new_context(self, **kwargs) -> "CDPContext":
        ctx = CDPContext(self)
        self.contexts.append(ctx)
        return ctx


class CDPContext:
    def __init__(self, browser: CDPBrowser):
        self.browser = browser
        self.pages: List[CDPPage] = []
        self._page: Optional[CDPPage] = None

    async def new_page(self) -> CDPPage:
        # Use existing page from browser target list or create
        page = await attach_default_page(self.browser.conn)
        self.pages.append(page)
        self._page = page
        return page

    async def add_init_script(self, script: str):
        try:
            await self.browser.conn.call("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        except Exception:
            pass

    async def close(self):
        pass


async def get_browser_ws(cdp_http: str) -> str:
    url = cdp_http.rstrip("/") + "/json/version"
    loop = asyncio.get_event_loop()

    def fetch():
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
            return data["webSocketDebuggerUrl"]

    return await loop.run_in_executor(None, fetch)


async def attach_default_page(conn: CDPConnection) -> CDPPage:
    # List targets, prefer page type
    try:
        targets = await conn.call("Target.getTargets")
        pages = [t for t in targets.get("targetInfos", []) if t.get("type") == "page"]
        if pages:
            tid = pages[0]["targetId"]
            return CDPPage(conn, tid)
    except Exception:
        pass
    return CDPPage(conn, "default")


async def connect_cdp(cdp_http: str) -> tuple:
    """Connect to Chromium CDP and return (browser, context, page)."""
    ws_url = await get_browser_ws(cdp_http)
    conn = CDPConnection(ws_url)
    await conn.connect()
    await conn.call("Target.setDiscoverTargets", {"discover": True})
    browser = CDPBrowser(conn, ws_url)
    context = CDPContext(browser)
    browser.contexts.append(context)
    page = await context.new_page()
    await conn.call("Page.enable")
    await conn.call("Runtime.enable")
    await conn.call("DOM.enable")
    await conn.call("Network.enable")
    return browser, context, page


def find_chromium() -> Optional[str]:
    import shutil
    for c in [
        os.environ.get("CHROMIUM_PATH"),
        shutil.which("chromium-browser"),
        shutil.which("chromium"),
        "/data/data/com.termux/files/usr/bin/chromium-browser",
        "/data/data/com.termux/files/usr/bin/chromium",
    ]:
        if c and Path(c).exists():
            return c
    return None


async def ensure_chromium_cdp(port: int = 9222) -> str:
    cdp = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(cdp + "/json/version", timeout=2) as r:
            if r.status == 200:
                return cdp
    except Exception:
        pass

    exe = find_chromium()
    if not exe:
        raise RuntimeError(
            "Chromium not found. Install with:\n"
            "  pkg install x11-repo\n"
            "  pkg install chromium"
        )

    udd = str(Path.home() / ".config" / "uba-chromium")
    Path(udd).mkdir(parents=True, exist_ok=True)
    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={udd}",
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-first-run",
        "--js-flags=--jitless",
        "about:blank",
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(30):
        await asyncio.sleep(0.5)
        try:
            with urllib.request.urlopen(cdp + "/json/version", timeout=1) as r:
                if r.status == 200:
                    return cdp
        except Exception:
            continue
    raise RuntimeError("Chromium started but CDP port did not open")
