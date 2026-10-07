"""
Ultra-Advanced Browser Agent
============================
Hierarchical Planner → Actor → Validator loop with:
- Reflection & self-correction
- Episodic memory
- Rich observation (a11y + forms + dialogs)
- 17 tools (tabs, downloads, JS, credentials, …)
- Trace persistence & screenshots
- NVIDIA Nemotron tool-calling
"""

from __future__ import annotations

import asyncio
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from rich.console import Console
from rich.panel import Panel

from .config import AgentConfig
from .observation import get_page_observation, observation_to_prompt
from .tools import TOOL_SCHEMAS, ToolExecutor
from .browser_launcher import launch_browser, is_termux

console = Console()


SYSTEM_PROMPT = """You are an elite browser automation agent (Skyvern-class).
You accomplish complex multi-step goals on real websites using only the tools provided.

You receive at every step:
1. The current URL + title
2. A numbered accessibility tree of interactive & semantic elements
3. Form field state, dialog warnings, and visible text sample
4. Your previous actions and any reflections

Core strategy:
- Prefer the shortest reliable path.
- Always target elements by their numeric accessibility id.
- After significant actions (navigation, form submit, search) re-observe before extracting.
- If you notice you are repeating the same action without progress, call `reflect` and change strategy.
- When the goal is data extraction, call `extract_data` with clean JSON that matches any schema the user requested.
- When the overall goal is finished (or impossible), call `done`.
- Never invent element ids that do not appear in the current tree.
- Never invent credentials; only use `fill_credential` with a stored profile name.

Respond ONLY by calling tools. Parallel tool calls are allowed when independent.
"""


PLANNER_PROMPT = """You are the PLANNER sub-agent.
Given a high-level user goal, produce a concise ordered list of 3–8 concrete sub-goals that a browser agent can execute.
Also list success criteria and likely failure modes.
Return pure JSON:
{
  "subgoals": ["...", "..."],
  "success_criteria": ["..."],
  "risks": ["..."]
}
"""


class EpisodicMemory:
    """Lightweight memory of past successful patterns and failures."""

    def __init__(self):
        self.episodes: List[Dict[str, Any]] = []
        self.failures: List[str] = []

    def add(self, goal: str, success: bool, summary: str, steps: int):
        self.episodes.append({
            "goal": goal[:200],
            "success": success,
            "summary": summary[:300],
            "steps": steps,
            "ts": time.time(),
        })
        if not success:
            self.failures.append(summary[:200])

    def context_snippet(self) -> str:
        if not self.episodes:
            return ""
        recent = self.episodes[-5:]
        lines = ["Recent episodes:"]
        for e in recent:
            mark = "✓" if e["success"] else "✗"
            lines.append(f"  {mark} ({e['steps']} steps) {e['goal'][:80]} → {e['summary'][:80]}")
        return "\n".join(lines)


class BrowserAgent:
    """
    Full-featured ultra-advanced AI browser agent.

    Example
    -------
    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            "Search Wikipedia for Alan Turing and extract the first sentence",
            url="https://en.wikipedia.org",
            data_schema={"first_sentence": "string"},
        )
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.config.validate()
        self.client = AsyncOpenAI(
            base_url=self.config.api_base,
            api_key=self.config.api_key,
        )
        self._pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.history: List[Dict[str, Any]] = []
        self.memory = EpisodicMemory()
        self.trace_dir: Optional[Path] = None
        self.screenshot_dir: Optional[Path] = None
        self.current_plan: Optional[Dict[str, Any]] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def start(self):
        """Launch browser — auto-detects Termux system Chromium / CDP / desktop Playwright."""
        self._pw = await async_playwright().start()
        self.browser, self.context, self.page = await launch_browser(self.config, self._pw)

        if self.config.save_traces:
            self.trace_dir = Path(self.config.trace_dir)
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            self.screenshot_dir = self.trace_dir / "screenshots"
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        Path(self.config.download_dir).mkdir(parents=True, exist_ok=True)

        if self.config.verbose:
            mode = "Termux" if is_termux() else "desktop"
            cdp = getattr(self.config, "cdp_url", None) or os.environ.get("CDP_URL")
            extra = f" CDP={cdp}" if cdp else ""
            console.print(
                f"[bold green]Ultra BrowserAgent started[/bold green] "
                f"(mode={mode}, headless={self.config.headless}, model={self.config.model}{extra})"
            )

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        if self.config.verbose:
            console.print("[green]BrowserAgent closed[/green]")

    # ── LLM helpers ────────────────────────────────────────────────────────

    async def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools is not None:
            kwargs["tools"] = tools
        if self.config.extra_body:
            kwargs["extra_body"] = self.config.extra_body

        last_err = None
        for attempt in range(4):
            try:
                return await self.client.chat.completions.create(**kwargs)
            except Exception as e:
                last_err = e
                if self.config.verbose:
                    console.print(f"[yellow]LLM retry {attempt+1}: {e}[/yellow]")
                await asyncio.sleep(1.2 * (attempt + 1))
        raise last_err  # type: ignore

    async def _create_plan(self, goal: str, url: Optional[str]) -> Dict[str, Any]:
        """High-level planner call (no tools)."""
        user = f"Goal: {goal}\nStarting URL: {url or '(none — agent will navigate)'}"
        mem = self.memory.context_snippet()
        if mem:
            user += "\n\n" + mem
        try:
            resp = await self._call_llm(
                [
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": user},
                ],
                tools=None,
                temperature=0.2,
            )
            text = resp.choices[0].message.content or "{}"
            # extract JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                plan = json.loads(text[start:end])
            else:
                plan = {"subgoals": [goal], "success_criteria": [], "risks": []}
        except Exception as e:
            plan = {"subgoals": [goal], "success_criteria": [], "risks": [str(e)]}
        self.current_plan = plan
        if self.config.verbose:
            console.print(Panel(
                json.dumps(plan, indent=2)[:800],
                title="[cyan]PLAN[/cyan]",
                border_style="cyan",
            ))
        return plan

    def _trim_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.config.keep_full_message_history:
            return messages
        if len(messages) <= self.config.max_history_messages:
            return messages
        # keep system + first user + last N
        head = messages[:2]
        tail = messages[-(self.config.max_history_messages - 2):]
        return head + [{"role": "user", "content": "[older turns summarized / truncated for context length]"}] + tail

    def _log(self, step: int, content: str, style: str = "cyan"):
        if self.config.verbose:
            console.print(Panel(content, title=f"Step {step}", border_style=style))

    # ── Main task loop ─────────────────────────────────────────────────────

    async def run_task(
        self,
        prompt: str,
        url: Optional[str] = None,
        data_schema: Optional[Dict[str, Any]] = None,
        max_steps: Optional[int] = None,
        use_planner: bool = True,
    ) -> Dict[str, Any]:
        if not self.page:
            await self.start()

        max_steps = max_steps or self.config.max_steps
        start_ts = time.time()
        self.history = []

        if url:
            if self.config.verbose:
                console.print(f"[blue]→ {url}[/blue]")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(0.7)

        plan = None
        if use_planner:
            plan = await self._create_plan(prompt, url)

        schema_hint = ""
        if data_schema:
            schema_hint = (
                "\n\nWhen extracting, produce JSON conforming to:\n```json\n"
                + json.dumps(data_schema, indent=2)
                + "\n```"
            )

        plan_hint = ""
        if plan:
            plan_hint = "\n\nHigh-level plan:\n" + "\n".join(
                f"  {i+1}. {sg}" for i, sg in enumerate(plan.get("subgoals", []))
            )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"GOAL:\n{prompt}{schema_hint}{plan_hint}\n\nBegin. Observe the page and take the first useful action.",
            },
        ]

        final: Dict[str, Any] = {
            "success": False,
            "message": "Max steps reached without completion",
            "data": None,
            "steps": 0,
            "history": [],
            "plan": plan,
            "reflections": [],
            "duration_sec": 0.0,
        }

        executor: Optional[ToolExecutor] = None

        for step in range(1, max_steps + 1):
            # ── Observe ────────────────────────────────────────────────────
            obs = await get_page_observation(
                self.page,
                max_a11y_nodes=self.config.max_a11y_nodes,
                max_visible_text=self.config.max_visible_text_chars,
                screenshot_dir=self.screenshot_dir if self.config.capture_screenshots else None,
                step=step,
            )
            obs_text = observation_to_prompt(obs, self.config.include_aria_raw_fallback)

            messages.append({
                "role": "user",
                "content": f"CURRENT PAGE STATE (step {step}/{max_steps}):\n\n{obs_text}",
            })
            messages = self._trim_messages(messages)

            self._log(step, f"URL: {obs['url']}\nTitle: {obs['title']}\nNodes: {obs['node_count']}")

            # ── Periodic forced reflection ─────────────────────────────────
            if (
                step > 1
                and self.config.reflection_every_n_steps > 0
                and step % self.config.reflection_every_n_steps == 0
            ):
                messages.append({
                    "role": "user",
                    "content": (
                        "REFLECTION CHECKPOINT: Call the `reflect` tool now to assess progress, "
                        "detect if you are stuck, and revise strategy if needed. Then continue."
                    ),
                })

            # ── LLM decide ─────────────────────────────────────────────────
            try:
                response = await self._call_llm(messages, tools=TOOL_SCHEMAS)
            except Exception as e:
                final["message"] = f"LLM error: {e}"
                break

            choice = response.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None) or []

            assistant_entry: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_entry)

            if not tool_calls:
                messages.append({
                    "role": "user",
                    "content": "You must call at least one tool. Choose the next best action toward the goal.",
                })
                continue

            # ── Execute tools ──────────────────────────────────────────────
            executor = ToolExecutor(
                self.page,
                obs["a11y_nodes"],
                context=self.context,
                download_dir=self.config.download_dir,
                credentials=self.config.credentials,
            )
            # keep page reference in sync if tabs change
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                if self.config.verbose:
                    console.print(f"  [magenta]→ {name}({json.dumps(args)[:140]})[/magenta]")

                result_str = await executor.execute(name, args)

                # if tab switched, update our page handle
                if name in ("new_tab", "switch_tab") and executor.page:
                    self.page = executor.page

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

                self.history.append({
                    "step": step,
                    "tool": name,
                    "args": args,
                    "result": result_str,
                    "url": self.page.url if self.page else "",
                })

                if self.config.verbose:
                    console.print(f"  [green]← {result_str[:220]}[/green]")

                if executor.finished:
                    final.update({
                        "success": executor.final_result.get("success", True),
                        "message": executor.final_result.get("message", ""),
                        "data": executor.final_result.get("data") or executor.last_extracted,
                        "steps": step,
                    })
                    break

            if executor and executor.reflection_log:
                final["reflections"].extend(executor.reflection_log)

            if executor and executor.finished:
                break

            await asyncio.sleep(0.35)

        final["history"] = self.history
        final["duration_sec"] = round(time.time() - start_ts, 2)
        final["steps"] = final.get("steps") or len({h["step"] for h in self.history})

        # memory
        self.memory.add(prompt, final["success"], final["message"], final["steps"])

        # persist trace
        if self.trace_dir:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            trace_path = self.trace_dir / f"run_{ts}.json"
            with open(trace_path, "w") as f:
                json.dump(
                    {
                        "prompt": prompt,
                        "url": url,
                        "plan": plan,
                        "result": {k: v for k, v in final.items() if k != "history"},
                        "history": self.history,
                        "reflections": final.get("reflections"),
                    },
                    f,
                    indent=2,
                    default=str,
                )
            if self.config.verbose:
                console.print(f"[dim]Trace → {trace_path}[/dim]")

        if self.config.verbose:
            status = "[bold green]SUCCESS[/bold green]" if final["success"] else "[bold red]FAILED[/bold red]"
            console.print(Panel(
                f"{status}\n{final['message']}\n"
                f"Data: {json.dumps(final.get('data'), indent=2, default=str)[:900]}\n"
                f"Steps: {final['steps']} | Duration: {final['duration_sec']}s",
                title="Final Result",
                border_style="green" if final["success"] else "red",
            ))

        return final

    # ── Skyvern-style convenience API ──────────────────────────────────────

    async def act(self, prompt: str, max_steps: int = 10) -> Dict[str, Any]:
        return await self.run_task(prompt, max_steps=max_steps, use_planner=False)

    async def extract(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Any:
        result = await self.run_task(
            f"Extract from the current page: {prompt}",
            data_schema=schema,
            max_steps=8,
            use_planner=False,
        )
        return result.get("data")

    async def goto(self, url: str):
        await self.page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(0.4)

    async def run_workflow(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute a list of pre-defined steps (Skyvern-style block chain).
        Each step: {"type": "task"|"goto"|"extract", "prompt": ..., "url": ..., "schema": ...}
        """
        results = []
        for i, step in enumerate(steps):
            stype = step.get("type", "task")
            if stype == "goto":
                await self.goto(step["url"])
                results.append({"step": i, "type": "goto", "url": step["url"]})
            elif stype == "extract":
                data = await self.extract(step.get("prompt", "extract data"), step.get("schema"))
                results.append({"step": i, "type": "extract", "data": data})
            else:
                r = await self.run_task(
                    step["prompt"],
                    url=step.get("url"),
                    data_schema=step.get("schema"),
                    max_steps=step.get("max_steps", 15),
                    use_planner=step.get("use_planner", True),
                )
                results.append({"step": i, "type": "task", "result": r})
        return results
