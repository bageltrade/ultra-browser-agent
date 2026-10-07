# Ultra Browser Agent (UBA) v2.1

**Skyvern-class hierarchical AI browser automation** with a **mobile-first chat UI**.

Powered by NVIDIA Nemotron-3-Super-120B-A12B.

## Highlights

- **Chat UI** — Ask-style panel (mobile + desktop), quick chips, settings sheet
- **High step budget** — default **120** steps (configurable up to 300 in UI)
- **Planner → Actor → Validator** with reflection & episodic memory
- **17 tools** — click, type, tabs, downloads, JS, credentials, reflect…
- **Termux-friendly** — pure Python web UI; remote CDP for browser on Android
- Accessibility-tree targeting (survives UI changes)

## Install

```bash
git clone https://github.com/bageltrade/ultra-browser-agent.git
cd ultra-browser-agent
pip install -r requirements.txt
playwright install chromium   # skip on Termux — see TERMUX.md
export NVIDIA_API_KEY="nvapi-..."
```

## Web chat UI (recommended)

```bash
python run_web.py
# → http://127.0.0.1:8080
```

Mobile-style interface: type a goal, optional start URL, adjust max steps (10–200), get structured results.

## CLI

```bash
python run_agent.py "Extract top 5 HN titles with points" --url https://news.ycombinator.com
```

## Python API

```python
import asyncio, os
from agent import BrowserAgent, AgentConfig

async def main():
    cfg = AgentConfig(
        api_key=os.environ["NVIDIA_API_KEY"],
        max_steps=120,
        headless=True,
    )
    async with BrowserAgent(cfg) as agent:
        result = await agent.run_task(
            "Search Wikipedia for Ada Lovelace and extract the first sentence",
            url="https://en.wikipedia.org",
        )
        print(result)

asyncio.run(main())
```

## Termux (real on-device browsing)

Do **not** install desktop `requirements.txt` or upgrade pip.

```bash
pkg install -y python git x11-repo chromium
pip install -r requirements-termux.txt   # NOT requirements.txt
export NVIDIA_API_KEY="nvapi-..."
export UBA_USE_CDP=1
python run_web.py
```

Full guide: [TERMUX.md](TERMUX.md).


## Architecture

```
User (Chat UI / CLI)
        │
        ▼
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   PLANNER    │────▶│   ACTOR LOOP    │────▶│  VALIDATOR   │
│  subgoals +  │     │ observe → LLM → │     │ extract/done │
│  risks       │     │ tools → reflect │     │              │
└──────────────┘     └─────────────────┘     └──────────────┘
```

## License

MIT
