# Ultra Browser Agent on Termux — Real Browsing

Full **on-device** Chromium automation inside Termux (no PC required).

## One-shot install

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git x11-repo
pkg install -y chromium
pip install -r requirements.txt

# Optional (extra Termux Playwright helpers)
# pip install termux-playwright && termux-playwright-install

export NVIDIA_API_KEY="nvapi-YOUR-KEY"
export PLAYWRIGHT_BROWSERS_PATH=0
```

Or run the helper:

```bash
bash scripts/termux_setup.sh
```

## How real browsing works on Termux

The agent **auto-detects Termux** and:

1. Finds system Chromium (`pkg install chromium` from x11-repo)
2. Starts it headless with `--remote-debugging-port=9222` (CDP)
3. Connects Playwright over CDP — **real page load, JS, clicks, extraction**

You can also point at any CDP endpoint:

```bash
export CDP_URL="http://127.0.0.1:9222"
```

## Verify Chromium

```bash
which chromium-browser || which chromium
chromium-browser --version   # or: chromium --version

# Manual CDP test
chromium-browser --headless --no-sandbox --disable-gpu \
  --remote-debugging-port=9222 --user-data-dir=$HOME/.config/uba-chromium about:blank &
curl -s http://127.0.0.1:9222/json/version
```

## Run the agent

### Web chat UI (recommended on phone)

```bash
export NVIDIA_API_KEY="nvapi-..."
export PLAYWRIGHT_BROWSERS_PATH=0
python run_web.py
# open http://127.0.0.1:8080 in your browser
```

### CLI

```bash
export NVIDIA_API_KEY="nvapi-..."
export PLAYWRIGHT_BROWSERS_PATH=0
python run_agent.py "Extract top 5 HN titles with points" --url https://news.ycombinator.com
```

### Python

```python
import asyncio, os
from agent import BrowserAgent, AgentConfig

async def main():
    cfg = AgentConfig(
        api_key=os.environ["NVIDIA_API_KEY"],
        max_steps=80,
        headless=True,
        # cdp_url="http://127.0.0.1:9222",  # optional override
    )
    async with BrowserAgent(cfg) as agent:
        r = await agent.run_task(
            "Go to example.com and extract the main heading",
            url="https://example.com",
        )
        print(r)

asyncio.run(main())
```

## Env vars

| Variable | Meaning |
|----------|---------|
| `NVIDIA_API_KEY` | Required |
| `PLAYWRIGHT_BROWSERS_PATH=0` | Required on Termux (skip bundled browsers) |
| `CHROMIUM_PATH` | Override Chromium binary path |
| `CDP_URL` | Connect to existing Chrome/Chromium CDP |
| `UBA_AUTO_CDP=0` | Disable auto-start of local CDP Chromium |
| `UBA_FORCE_TERMUX=1` | Force Termux launch path on any platform |
| `UBA_HOST` / `UBA_PORT` | Web UI bind (default 0.0.0.0:8080) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No browser available on Termux` | `pkg install x11-repo chromium` |
| Playwright Android platform error | `export PLAYWRIGHT_BROWSERS_PATH=0` |
| Chromium crashes / OOM | Close other apps; lower `max_steps`; keep headless |
| Slow SPA pages | Normal on mobile CPU; agent uses `--js-flags=--jitless` |
| Port 9222 in use | Kill old Chromium: `pkill -f remote-debugging-port` |

## Architecture on device

```
Termux Python (UBA)
       │
       ▼
Playwright ──CDP──▶ Chromium (pkg install chromium)
                       │
                       ▼
                 Real websites
```
