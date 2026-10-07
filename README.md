# Ultra Browser Agent (UBA) v2

**Skyvern-class hierarchical AI browser automation** powered by NVIDIA Nemotron-3-Super-120B-A12B.

Planner → Actor → Validator loop with reflection, episodic memory, 17 tools, multi-tab, downloads, credential vault, and full traces.

## Features

| Capability | Status |
|------------|--------|
| Hierarchical planning (sub-goals + risks) | ✅ |
| Reflection & self-correction | ✅ |
| Episodic memory | ✅ |
| Accessibility-tree targeting (UI-change resilient) | ✅ |
| 17 tools (click, type, JS, tabs, downloads, credentials…) | ✅ |
| Structured JSON extraction | ✅ |
| Multi-tab support | ✅ |
| File downloads | ✅ |
| Stealth mode | ✅ |
| Workflow chaining (`run_workflow`) | ✅ |
| Full JSON traces + screenshots | ✅ |

## Install

```bash
git clone https://github.com/poachdarling/ultra-browser-agent.git
cd ultra-browser-agent
pip install -r requirements.txt
playwright install chromium
export NVIDIA_API_KEY="nvapi-..."
```

## Quick start

```bash
python run_agent.py "Extract the top 5 Hacker News titles with points" \
  --url https://news.ycombinator.com
```

## Python API

```python
import asyncio
from agent import BrowserAgent, AgentConfig

async def main():
    cfg = AgentConfig(
        api_key="nvapi-...",           # or set NVIDIA_API_KEY
        model="nvidia/nemotron-3-super-120b-a12b",
        headless=True,
        max_steps=25,
    )
    async with BrowserAgent(cfg) as agent:
        result = await agent.run_task(
            "Search Wikipedia for Ada Lovelace and extract the first sentence",
            url="https://en.wikipedia.org",
            data_schema={"first_sentence": "string", "url": "string"},
        )
        print(result)

asyncio.run(main())
```

## Architecture

```
User Goal
    │
    ▼
┌──────────┐     ┌─────────────────┐     ┌──────────────┐
│ PLANNER  │────▶│  ACTOR LOOP     │────▶│  VALIDATOR   │
│ subgoals │     │ observe→LLM→    │     │ extract/done │
│ + risks  │     │ tools→reflect   │     │              │
└──────────┘     └─────────────────┘     └──────────────┘
                       │  ▲
                       ▼  │
              Episodic Memory + Traces
```

## Tools available to the model

`click` · `type_text` · `select_option` · `scroll` · `goto` · `wait` · `press_key` · `hover` · `go_back` · `new_tab` · `switch_tab` · `execute_js` · `download_file` · `fill_credential` · `extract_data` · `done` · `reflect`

## Configuration highlights

See `agent/config.py` for full options: max steps, reflection frequency, stealth, viewport, credentials vault, download dir, etc.

## License

MIT
