"""
Ultra-advanced browser tools for the agent.
Includes click, type, select, scroll, navigation, tabs, files, JS, credentials, extract, done, reflect.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout, Download


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element by its numbered accessibility id. Prefer this for buttons, links, checkboxes, tabs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer", "description": "Numeric id from the accessibility tree, e.g. 12"},
                    "reason": {"type": "string"},
                    "double": {"type": "boolean", "default": False},
                },
                "required": ["element_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Clear and type text into an input/textarea identified by accessibility id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer"},
                    "text": {"type": "string"},
                    "press_enter": {"type": "boolean", "default": False},
                    "clear_first": {"type": "boolean", "default": True},
                    "reason": {"type": "string"},
                },
                "required": ["element_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "select_option",
            "description": "Select an option in a <select> or listbox by visible label or value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer"},
                    "value": {"type": "string", "description": "Visible text or value of the option"},
                    "reason": {"type": "string"},
                },
                "required": ["element_id", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page or bring an element into view.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "top", "bottom", "left", "right"]},
                    "amount": {"type": "integer", "default": 700},
                    "element_id": {"type": "integer", "description": "Optional: scroll this element into view first"},
                    "reason": {"type": "string"},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "goto",
            "description": "Navigate to an absolute URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait for network idle, a selector, or a fixed number of seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "default": 1.5},
                    "for_network_idle": {"type": "boolean", "default": False},
                    "reason": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a keyboard key (Enter, Escape, Tab, ArrowDown, Control+a, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hover",
            "description": "Hover over an element (useful for menus that appear on hover).",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["element_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "Navigate back in browser history.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "new_tab",
            "description": "Open a new tab (optionally navigate to a URL) and switch to it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_tab",
            "description": "Switch to a tab by zero-based index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_js",
            "description": "Run a short JavaScript snippet in the page context and return the result. Use for advanced extraction or state inspection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "JS expression or IIFE that returns a JSON-serializable value"},
                    "reason": {"type": "string"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_file",
            "description": "Click an element that triggers a file download and wait for it to complete. Returns the saved path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["element_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_credential",
            "description": "Fill username/password fields using a stored credential profile name. Never invent credentials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile": {"type": "string", "description": "Key in the credentials vault"},
                    "username_element_id": {"type": "integer"},
                    "password_element_id": {"type": "integer"},
                    "submit_element_id": {"type": "integer", "description": "Optional submit button id"},
                    "reason": {"type": "string"},
                },
                "required": ["profile", "username_element_id", "password_element_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "Extract structured data from the CURRENT page. Call when you have the information needed. After this the task is usually complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "Extracted data matching any requested schema"},
                    "summary": {"type": "string"},
                },
                "required": ["data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Signal that the overall goal is finished (success or definitive failure).",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "result": {"type": "object"},
                },
                "required": ["success", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reflect",
            "description": "Internal reflection: assess progress toward the goal, detect stuck loops, and optionally revise the plan. Call every few steps or when stuck.",
            "parameters": {
                "type": "object",
                "properties": {
                    "progress_summary": {"type": "string"},
                    "is_stuck": {"type": "boolean"},
                    "next_strategy": {"type": "string"},
                    "revised_subgoals": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["progress_summary"],
            },
        },
    },
]


class ToolExecutor:
    """Maps LLM tool calls → Playwright actions with robust element resolution."""

    def __init__(
        self,
        page: Page,
        a11y_nodes: List[Dict[str, Any]],
        context=None,
        download_dir: str = "./downloads",
        credentials: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        self.page = page
        self.context = context
        self.a11y_nodes = {n["id"]: n for n in a11y_nodes}
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.credentials = credentials or {}
        self.last_extracted: Optional[Dict[str, Any]] = None
        self.finished = False
        self.final_result: Optional[Dict[str, Any]] = None
        self.reflection_log: List[Dict[str, Any]] = []

    def _find_locator(self, element_id: int):
        node = self.a11y_nodes.get(element_id)
        if not node:
            raise ValueError(f"No accessibility node with id={element_id}. Use only ids from the current tree.")

        role = (node.get("role") or "").lower()
        name = node.get("name") or ""

        role_map = {
            "textbox": "textbox", "searchbox": "searchbox", "button": "button",
            "link": "link", "checkbox": "checkbox", "radio": "radio",
            "combobox": "combobox", "listbox": "listbox", "option": "option",
            "heading": "heading", "tab": "tab", "menuitem": "menuitem",
            "switch": "switch", "slider": "slider", "spinbutton": "spinbutton",
            "img": "img", "cell": "cell", "row": "row", "gridcell": "gridcell",
            "listitem": "listitem", "dialog": "dialog",
        }
        pw_role = role_map.get(role, role if role else None)

        # Strategy cascade
        if pw_role and name:
            loc = self.page.get_by_role(pw_role, name=name, exact=False)
            try:
                if loc.count() and awaitable_count(loc):
                    return loc
            except Exception:
                pass
            return loc
        if name:
            try:
                loc = self.page.get_by_placeholder(name, exact=False)
                return loc
            except Exception:
                pass
            return self.page.get_by_text(name, exact=False)
        if pw_role:
            return self.page.get_by_role(pw_role)
        raise ValueError(f"Cannot locate element id={element_id} (role={role}, name={name})")

    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        try:
            if name == "click":
                loc = self._find_locator(int(arguments["element_id"]))
                if arguments.get("double"):
                    await loc.first.dblclick(timeout=12000)
                else:
                    await loc.first.click(timeout=12000)
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
                return f"Clicked element [{arguments['element_id']}] successfully."

            elif name == "type_text":
                loc = self._find_locator(int(arguments["element_id"]))
                text = arguments["text"]
                await loc.first.click(timeout=8000)
                if arguments.get("clear_first", True):
                    await loc.first.fill("")
                await loc.first.fill(text)
                if arguments.get("press_enter"):
                    await loc.first.press("Enter")
                    try:
                        await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                return f"Typed into element [{arguments['element_id']}]: '{text[:60]}{'...' if len(text)>60 else ''}'."

            elif name == "select_option":
                loc = self._find_locator(int(arguments["element_id"]))
                value = arguments["value"]
                try:
                    await loc.first.select_option(label=value, timeout=8000)
                except Exception:
                    await loc.first.select_option(value=value, timeout=8000)
                return f"Selected '{value}' on element [{arguments['element_id']}]."

            elif name == "scroll":
                direction = arguments.get("direction", "down")
                amount = int(arguments.get("amount", 700))
                if arguments.get("element_id") is not None:
                    loc = self._find_locator(int(arguments["element_id"]))
                    await loc.first.scroll_into_view_if_needed()
                if direction == "down":
                    await self.page.mouse.wheel(0, amount)
                elif direction == "up":
                    await self.page.mouse.wheel(0, -amount)
                elif direction == "left":
                    await self.page.mouse.wheel(-amount, 0)
                elif direction == "right":
                    await self.page.mouse.wheel(amount, 0)
                elif direction == "top":
                    await self.page.evaluate("window.scrollTo(0, 0)")
                elif direction == "bottom":
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.35)
                return f"Scrolled {direction}."

            elif name == "goto":
                url = arguments["url"]
                await self.page.goto(url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(0.6)
                return f"Navigated to {url}."

            elif name == "wait":
                secs = float(arguments.get("seconds", 1.5))
                secs = max(0.3, min(secs, 12.0))
                if arguments.get("for_network_idle"):
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=int(secs * 1000))
                    except Exception:
                        await asyncio.sleep(secs)
                else:
                    await asyncio.sleep(secs)
                return f"Waited {secs}s."

            elif name == "press_key":
                key = arguments["key"]
                await self.page.keyboard.press(key)
                await asyncio.sleep(0.25)
                return f"Pressed '{key}'."

            elif name == "hover":
                loc = self._find_locator(int(arguments["element_id"]))
                await loc.first.hover(timeout=8000)
                await asyncio.sleep(0.4)
                return f"Hovered element [{arguments['element_id']}]."

            elif name == "go_back":
                await self.page.go_back(wait_until="domcontentloaded", timeout=15000)
                return "Navigated back."

            elif name == "new_tab":
                if not self.context:
                    return "Error: no browser context available for new tabs."
                new_page = await self.context.new_page()
                url = arguments.get("url")
                if url:
                    await new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self.page = new_page
                return f"Opened new tab{' and navigated to ' + url if url else ''}. Now active."

            elif name == "switch_tab":
                if not self.context:
                    return "Error: no browser context."
                pages = self.context.pages
                idx = int(arguments["index"])
                if idx < 0 or idx >= len(pages):
                    return f"Invalid tab index {idx}. Available: 0..{len(pages)-1}"
                self.page = pages[idx]
                await self.page.bring_to_front()
                return f"Switched to tab {idx} ({self.page.url})."

            elif name == "execute_js":
                code = arguments["code"]
                result = await self.page.evaluate(code)
                try:
                    out = json.dumps(result)[:1500]
                except Exception:
                    out = str(result)[:1500]
                return f"JS result: {out}"

            elif name == "download_file":
                loc = self._find_locator(int(arguments["element_id"]))
                async with self.page.expect_download(timeout=30000) as di:
                    await loc.first.click(timeout=10000)
                download: Download = await di.value
                dest = self.download_dir / download.suggested_filename
                await download.save_as(str(dest))
                return f"Downloaded file → {dest}"

            elif name == "fill_credential":
                profile = arguments["profile"]
                creds = self.credentials.get(profile)
                if not creds:
                    return f"No credentials stored for profile '{profile}'. Available: {list(self.credentials.keys())}"
                user_loc = self._find_locator(int(arguments["username_element_id"]))
                pass_loc = self._find_locator(int(arguments["password_element_id"]))
                await user_loc.first.fill(creds.get("username", ""))
                await pass_loc.first.fill(creds.get("password", ""))
                if arguments.get("submit_element_id") is not None:
                    sub = self._find_locator(int(arguments["submit_element_id"]))
                    await sub.first.click()
                    try:
                        await self.page.wait_for_load_state("domcontentloaded", timeout=12000)
                    except Exception:
                        pass
                return f"Filled credentials for profile '{profile}'."

            elif name == "extract_data":
                data = arguments.get("data", {})
                summary = arguments.get("summary", "Data extracted.")
                self.last_extracted = data
                self.finished = True
                self.final_result = {"success": True, "data": data, "message": summary}
                return f"Data extracted: {json.dumps(data)[:600]}"

            elif name == "done":
                self.finished = True
                self.final_result = {
                    "success": bool(arguments.get("success", True)),
                    "message": arguments.get("message", ""),
                    "result": arguments.get("result"),
                    "data": arguments.get("result"),
                }
                return f"Task marked done (success={self.final_result['success']})."

            elif name == "reflect":
                entry = {
                    "progress": arguments.get("progress_summary"),
                    "stuck": arguments.get("is_stuck", False),
                    "strategy": arguments.get("next_strategy"),
                    "subgoals": arguments.get("revised_subgoals"),
                }
                self.reflection_log.append(entry)
                return (
                    f"Reflection recorded. Progress: {entry['progress'][:200]}. "
                    f"Stuck={entry['stuck']}. Next: {entry.get('strategy') or 'continue'}."
                )

            else:
                return f"Unknown tool: {name}"

        except PlaywrightTimeout as e:
            return f"Timeout while executing {name}: {e}"
        except Exception as e:
            return f"Error executing {name}: {type(e).__name__}: {e}"


def awaitable_count(loc) -> bool:
    """Helper placeholder — count is sync in some versions."""
    try:
        return True
    except Exception:
        return True
