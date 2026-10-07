#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "=========================================="
echo " Ultra Browser Agent — Termux setup v2.5"
echo "=========================================="

pkg update -y
pkg install -y python git which x11-repo
pkg install -y chromium || pkg install -y chromium-browser || {
  echo "ERROR: chromium install failed"; exit 1
}

echo ""
echo "Installing optional pure-Python deps (safe to skip if fails)..."
# NEVER pip install -U pip
pip install websockets 2>/dev/null || echo "(websockets optional — skipped)"

# requirements-termux is optional; stdlib UI needs zero pip packages
if [ -f requirements-termux.txt ]; then
  pip install -r requirements-termux.txt 2>/dev/null || true
fi

CHROME=$(which chromium-browser 2>/dev/null || which chromium 2>/dev/null || true)
[ -n "$CHROME" ] || { echo "ERROR: chromium binary missing"; exit 1; }
echo "Chromium: $CHROME"

cat > "$HOME/.uba_env" << ENV
export UBA_USE_CDP=1
export UBA_HTTPX_LLM=1
export UBA_STDLIB_UI=1
export PLAYWRIGHT_BROWSERS_PATH=0
export CHROMIUM_PATH=$CHROME
export CDP_PORT=9222
# export NVIDIA_API_KEY=nvapi-YOUR-KEY
ENV

echo ""
echo "OK — zero Rust deps. Next:"
echo "  source ~/.uba_env"
echo "  export NVIDIA_API_KEY=nvapi-YOUR-KEY"
echo "  python run_web.py"
