#!/usr/bin/env python3
"""
End-to-end tests for the Advanced Browser Agent using NVIDIA Nemotron.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import BrowserAgent, AgentConfig

API_KEY = os.getenv("NVIDIA_API_KEY") or "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"
MODEL = "nvidia/nemotron-3-super-120b-a12b"
BASE = "https://integrate.api.nvidia.com/v1"


def make_config(**kwargs) -> AgentConfig:
    defaults = dict(
        api_key=API_KEY,
        api_base=BASE,
        model=MODEL,
        headless=True,
        max_steps=12,
        verbose=True,
        save_traces=True,
        trace_dir="/home/workdir/artifacts/advanced_browser_agent/traces",
        temperature=0.1,
        max_tokens=4096,
    )
    defaults.update(kwargs)
    return AgentConfig(**defaults)


async def test_simple_extract():
    """Test 1: Extract heading from example.com"""
    print("\n" + "=" * 60)
    print("TEST 1: Extract main heading from example.com")
    print("=" * 60)

    config = make_config(max_steps=6)
    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            prompt="Extract the main heading (h1) text and the first paragraph text from this page.",
            url="https://example.com",
            data_schema={
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "paragraph": {"type": "string"},
                },
                "required": ["heading"],
            },
        )
    print("RESULT:", json.dumps(result, indent=2, default=str)[:1000])
    assert result.get("success") or result.get("data"), "Should have extracted something"
    print("✓ TEST 1 PASSED (or partially succeeded)")
    return result


async def test_navigation_and_extract():
    """Test 2: Navigate Hacker News and get top stories"""
    print("\n" + "=" * 60)
    print("TEST 2: Hacker News top stories")
    print("=" * 60)

    config = make_config(max_steps=10)
    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            prompt=(
                "You are on Hacker News. Extract the titles of the top 3 stories "
                "currently listed on the front page. Return them as a list."
            ),
            url="https://news.ycombinator.com",
            data_schema={
                "type": "object",
                "properties": {
                    "stories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rank": {"type": "integer"},
                                "title": {"type": "string"},
                            },
                        },
                    }
                },
            },
        )
    print("RESULT:", json.dumps(result, indent=2, default=str)[:1200])
    print("✓ TEST 2 completed")
    return result


async def test_form_interaction():
    """Test 3: Interact with a simple form (httpbin forms)"""
    print("\n" + "=" * 60)
    print("TEST 3: Simple page interaction (Wikipedia search)")
    print("=" * 60)

    config = make_config(max_steps=12)
    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            prompt=(
                "Go to the Wikipedia main page. Use the search box to search for 'Artificial intelligence'. "
                "After the results or article loads, extract the title of the page you land on."
            ),
            url="https://en.wikipedia.org/wiki/Main_Page",
            data_schema={
                "type": "object",
                "properties": {
                    "page_title": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        )
    print("RESULT:", json.dumps(result, indent=2, default=str)[:1200])
    print("✓ TEST 3 completed")
    return result


async def run_all():
    results = {}
    try:
        results["test1"] = await test_simple_extract()
    except Exception as e:
        print(f"TEST 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results["test1"] = {"error": str(e)}

    try:
        results["test2"] = await test_navigation_and_extract()
    except Exception as e:
        print(f"TEST 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results["test2"] = {"error": str(e)}

    try:
        results["test3"] = await test_form_interaction()
    except Exception as e:
        print(f"TEST 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results["test3"] = {"error": str(e)}

    print("\n\n========== SUMMARY ==========")
    for k, v in results.items():
        success = v.get("success") if isinstance(v, dict) else False
        print(f"{k}: success={success}  message={v.get('message', v.get('error', ''))[:80] if isinstance(v, dict) else v}")
    return results


if __name__ == "__main__":
    asyncio.run(run_all())
