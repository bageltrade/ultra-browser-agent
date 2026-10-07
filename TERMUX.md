# Termux install v2.5 (stdlib only — no Rust)

Python 3.14 on Android **cannot build** pydantic-core / jiter / maturin.
This release uses:

| Component | Implementation |
|-----------|----------------|
| Web UI | Python **stdlib** `http.server` (no FastAPI/pydantic) |
| LLM API | **urllib** (no openai/httpx) |
| Browser | **pure CDP** + system Chromium (no Playwright) |

## Install

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git which x11-repo chromium

cd ~
git clone https://github.com/bageltrade/ultra-browser-agent.git
# or: cd ultra-browser-agent && git pull

cd ~/ultra-browser-agent

# Optional (pure Python). Skip if it fails — not required:
pip install websockets || true

export NVIDIA_API_KEY="nvapi-YOUR-KEY"
export UBA_USE_CDP=1
export UBA_STDLIB_UI=1

python run_web.py
# open http://127.0.0.1:8080
```

**Do not** run:
- `pip install -U pip`
- `pip install -r requirements.txt` (desktop only)
- anything that pulls pydantic / openai / playwright

## One-shot

```bash
bash scripts/termux_setup.sh
source ~/.uba_env
export NVIDIA_API_KEY="nvapi-YOUR-KEY"
python run_web.py
```

## CLI test

```bash
export NVIDIA_API_KEY="nvapi-YOUR-KEY"
export UBA_USE_CDP=1
python run_agent.py "Extract the main heading" --url https://example.com
```

## If pip still tries to build Rust packages

You may have an old requirements install. Reset:

```bash
cd ~/ultra-browser-agent
git pull
# do not pip install requirements.txt
export UBA_STDLIB_UI=1 UBA_USE_CDP=1
export NVIDIA_API_KEY="nvapi-YOUR-KEY"
python run_web.py
```

The UI and agent run with **only** the Python standard library + system Chromium.
