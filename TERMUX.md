# Termux install (v2.4 — no jiter / no Playwright)

Termux Python often **cannot build** `jiter` (Rust) or install `playwright` wheels.
UBA uses:
- **httpx** for the NVIDIA API (no `openai` package)
- **pure CDP** for Chromium (no Playwright)

## Install

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git which x11-repo chromium

cd ~
git clone https://github.com/bageltrade/ultra-browser-agent.git
# or: cd ~/ultra-browser-agent && git pull

cd ~/ultra-browser-agent

# Do NOT run: pip install -U pip
# Do NOT use: requirements.txt  (desktop only)

pip install -r requirements-termux.txt

export NVIDIA_API_KEY="nvapi-YOUR-KEY"
export UBA_USE_CDP=1
export UBA_HTTPX_LLM=1

python run_web.py
# → http://127.0.0.1:8080
```

One-shot:

```bash
bash scripts/termux_setup.sh
source ~/.uba_env
export NVIDIA_API_KEY="nvapi-YOUR-KEY"
python run_web.py
```

## If you already failed mid-install

```bash
cd ~/ultra-browser-agent
git pull
pip install -r requirements-termux.txt
export UBA_HTTPX_LLM=1
export UBA_USE_CDP=1
export NVIDIA_API_KEY="nvapi-YOUR-KEY"
python run_web.py
```

## CLI test

```bash
python run_agent.py "Extract the main heading" --url https://example.com
```

## Dependencies (Termux only)

| Package | Why |
|---------|-----|
| httpx | NVIDIA API |
| websockets | Chromium CDP |
| fastapi + uvicorn + jinja2 | Chat UI |
| python-dotenv | optional env files |

**Not used on Termux:** openai, jiter, playwright, maturin, rustc
