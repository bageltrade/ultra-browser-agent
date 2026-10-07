# Termux install (real browsing, no Playwright wheel)

Official `playwright` packages **do not publish Android wheels**.  
UBA uses a **pure CDP driver** + system Chromium instead.

## Quick install

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git which x11-repo chromium

cd ~
git clone https://github.com/bageltrade/ultra-browser-agent.git
cd ultra-browser-agent

# IMPORTANT: do NOT run  pip install -U pip
pip install -r requirements-termux.txt

export NVIDIA_API_KEY="nvapi-YOUR-KEY"
export UBA_USE_CDP=1
export PLAYWRIGHT_BROWSERS_PATH=0

python run_web.py
# open http://127.0.0.1:8080
```

Or:

```bash
bash scripts/termux_setup.sh
source ~/.uba_env
export NVIDIA_API_KEY="nvapi-YOUR-KEY"
python run_web.py
```

## Why the old error happened

| Command | Problem |
|---------|---------|
| `pip install -U pip` | Forbidden — breaks Termux `python-pip` |
| `pip install playwright` | No wheel for Android → "No matching distribution" |

Use **`requirements-termux.txt`** only on Termux.

## Verify

```bash
which chromium-browser || which chromium
python -c "import openai, fastapi, websockets; print('python ok')"

# Start agent CLI test
export NVIDIA_API_KEY="nvapi-..."
export UBA_USE_CDP=1
python run_agent.py "Extract the main heading" --url https://example.com
```

## How browsing works

```
UBA Python
  → pure CDP driver (agent/cdp_driver.py)
    → Chromium (--remote-debugging-port=9222)
      → real websites
```

No Playwright package required on the phone.

## Permanent env

```bash
echo 'export NVIDIA_API_KEY="nvapi-YOUR-KEY"' >> ~/.bashrc
echo 'export UBA_USE_CDP=1' >> ~/.bashrc
echo 'export PLAYWRIGHT_BROWSERS_PATH=0' >> ~/.bashrc
source ~/.bashrc
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| Installing pip is forbidden | Skip `pip install -U pip` |
| No matching distribution for playwright | Use `requirements-termux.txt` |
| Chromium not found | `pkg install x11-repo chromium` |
| CDP port failed | `pkill -f remote-debugging-port` then retry |
| websockets missing | `pip install websockets` |
