"""
Ultra-advanced page observation.
- Playwright aria_snapshot (YAML a11y)
- Numbered interactive element index for reliable targeting
- Visible text + form state
- Dialog / overlay detection
- Optional screenshot paths
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page


INTERESTING_ROLES = {
    "button", "link", "textbox", "searchbox", "combobox", "listbox",
    "option", "checkbox", "radio", "switch", "tab", "menuitem",
    "slider", "spinbutton", "heading", "img", "cell", "row",
    "listitem", "article", "navigation", "main", "form", "dialog",
    "alert", "table", "columnheader", "rowheader", "gridcell",
    "menuitemcheckbox", "menuitemradio", "treeitem", "tabpanel",
    "banner", "contentinfo", "complementary", "status",
}


def _parse_aria_snapshot_to_nodes(snapshot: str, max_nodes: int = 350) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    if not snapshot:
        return nodes

    pattern = re.compile(
        r'^\s*-\s*(?P<role>[\w-]+)(?:\s+"(?P<name>[^"]*)")?(?P<rest>.*)$',
        re.MULTILINE,
    )
    for m in pattern.finditer(snapshot):
        role = (m.group("role") or "").lower()
        name = (m.group("name") or "").strip()
        rest = (m.group("rest") or "").strip()

        if role not in INTERESTING_ROLES and not name:
            continue
        if role in ("paragraph", "text", "generic", "group", "none") and not name:
            continue

        entry: Dict[str, Any] = {
            "id": len(nodes) + 1,
            "role": role,
            "name": name[:160],
        }
        if "checked" in rest.lower():
            entry["checked"] = True
        if "disabled" in rest.lower() or "unavailable" in rest.lower():
            entry["disabled"] = True
        if "expanded" in rest.lower():
            entry["expanded"] = True
        nodes.append(entry)
        if len(nodes) >= max_nodes:
            break
    return nodes


def format_nodes_for_llm(nodes: List[Dict[str, Any]]) -> str:
    lines = []
    for n in nodes:
        parts = [f"[{n['id']}]", n["role"]]
        if n.get("name"):
            parts.append(f'"{n["name"]}"')
        flags = []
        for k in ("checked", "disabled", "expanded", "focused", "selected"):
            if n.get(k):
                flags.append(k)
        if flags:
            parts.append("(" + ",".join(flags) + ")")
        lines.append(" ".join(parts))
    return "\n".join(lines)


async def get_aria_snapshot(page: Page) -> str:
    try:
        return (await page.locator("body").aria_snapshot()) or ""
    except Exception as e:
        return f"(aria_snapshot failed: {e})"


async def get_visible_text(page: Page, max_chars: int = 4000) -> str:
    try:
        text = await page.evaluate(
            """(maxChars) => {
                const parts = [];
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: (node) => {
                            const t = (node.textContent || "").trim();
                            if (!t || t.length < 2) return NodeFilter.FILTER_REJECT;
                            const p = node.parentElement;
                            if (!p) return NodeFilter.FILTER_REJECT;
                            const s = window.getComputedStyle(p);
                            if (s.display === "none" || s.visibility === "hidden" || s.opacity === "0")
                                return NodeFilter.FILTER_REJECT;
                            const tag = p.tagName.toLowerCase();
                            if (["script","style","noscript","svg"].includes(tag))
                                return NodeFilter.FILTER_REJECT;
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                let n;
                while ((n = walker.nextNode())) {
                    const t = n.textContent.trim();
                    if (t) parts.push(t);
                }
                return parts.join(" | ").slice(0, maxChars);
            }""",
            max_chars,
        )
        return text or ""
    except Exception as e:
        return f"(visible_text failed: {e})"


async def get_form_state(page: Page) -> str:
    try:
        data = await page.evaluate(
            """() => {
                const fields = [];
                document.querySelectorAll("input, textarea, select").forEach((el, i) => {
                    if (i > 40) return;
                    const tag = el.tagName.toLowerCase();
                    const type = (el.type || tag).toLowerCase();
                    if (["hidden","submit","button","image","reset"].includes(type)) return;
                    const name = el.name || el.id || el.getAttribute("aria-label") || el.placeholder || "";
                    let val = "";
                    if (tag === "select") {
                        val = el.options[el.selectedIndex]?.text || "";
                    } else if (type === "checkbox" || type === "radio") {
                        val = el.checked ? "checked" : "unchecked";
                    } else {
                        val = (el.value || "").slice(0, 80);
                    }
                    fields.push({type, name: name.slice(0,60), value: val});
                });
                return fields;
            }"""
        )
        if not data:
            return ""
        lines = [f'  - {f["type"]}: "{f["name"]}" = "{f["value"]}"' for f in data]
        return "Form fields:\n" + "\n".join(lines)
    except Exception:
        return ""


async def detect_dialogs(page: Page) -> str:
    try:
        count = await page.locator('[role="dialog"], [aria-modal="true"], .modal, .popup, [class*="overlay"]').count()
        if count:
            return f"⚠ {count} dialog/modal/overlay element(s) detected — may need to dismiss or interact."
        return ""
    except Exception:
        return ""


async def get_page_observation(
    page: Page,
    max_a11y_nodes: int = 350,
    max_visible_text: int = 4000,
    screenshot_dir: Optional[Path] = None,
    step: int = 0,
) -> Dict[str, Any]:
    url = page.url
    title = await page.title()
    aria_raw = await get_aria_snapshot(page)
    nodes = _parse_aria_snapshot_to_nodes(aria_raw, max_nodes=max_a11y_nodes)
    visible = await get_visible_text(page, max_visible_text)
    forms = await get_form_state(page)
    dialogs = await detect_dialogs(page)

    screenshot_path = None
    if screenshot_dir is not None:
        try:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = str(screenshot_dir / f"step_{step:03d}_{int(time.time())}.png")
            await page.screenshot(path=screenshot_path, full_page=False)
        except Exception:
            screenshot_path = None

    return {
        "url": url,
        "title": title,
        "accessibility_tree": format_nodes_for_llm(nodes) if nodes else "",
        "a11y_nodes": nodes,
        "aria_raw": aria_raw[:5000],
        "visible_text_sample": visible,
        "form_state": forms,
        "dialog_info": dialogs,
        "node_count": len(nodes),
        "screenshot_path": screenshot_path,
    }


def observation_to_prompt(obs: Dict[str, Any], include_raw_fallback: bool = True) -> str:
    parts = [
        f"URL: {obs['url']}",
        f"Title: {obs['title']}",
        f"Numbered interactive / semantic elements ({obs['node_count']}):",
        "```",
        obs["accessibility_tree"] or "(none detected — rely on visible text)",
        "```",
    ]
    if include_raw_fallback and obs["node_count"] < 8 and obs.get("aria_raw"):
        parts.append("Full ARIA snapshot (context):\n```\n" + obs["aria_raw"][:2200] + "\n```")
    if obs.get("form_state"):
        parts.append(obs["form_state"])
    if obs.get("dialog_info"):
        parts.append(obs["dialog_info"])
    if obs.get("visible_text_sample"):
        parts.append("Visible text sample:\n" + obs["visible_text_sample"][:2000])
    return "\n".join(parts)
