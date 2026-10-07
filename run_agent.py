#!/usr/bin/env python3
"""CLI for the Ultra-Advanced Browser Agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import BrowserAgent, AgentConfig


async def main():
    parser = argparse.ArgumentParser(description="Ultra-Advanced AI Browser Agent")
    parser.add_argument("prompt", nargs="?", help="Natural language goal")
    parser.add_argument("--url", default=None)
    parser.add_argument("--schema", default=None, help="JSON schema file or inline JSON")
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--no-planner", action="store_true")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default="nvidia/nemotron-3-super-120b-a12b")
    args = parser.parse_args()

    if not args.prompt:
        print('Usage: python run_agent.py "goal" [--url https://...]')
        sys.exit(1)

    api_key = args.api_key or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("ERROR: set NVIDIA_API_KEY or pass --api-key")
        sys.exit(1)

    schema = None
    if args.schema:
        if os.path.isfile(args.schema):
            with open(args.schema) as f:
                schema = json.load(f)
        else:
            schema = json.loads(args.schema)

    config = AgentConfig(
        api_key=api_key,
        model=args.model,
        headless=not args.headed,
        max_steps=args.max_steps,
        verbose=True,
        save_traces=True,
        capture_screenshots=True,
        trace_dir="./traces",
    )

    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            prompt=args.prompt,
            url=args.url,
            data_schema=schema,
            use_planner=not args.no_planner,
        )
        print("\n=== JSON RESULT ===")
        print(json.dumps({k: v for k, v in result.items() if k != "history"}, indent=2, default=str))
        return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
