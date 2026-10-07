#!/data/data/com.termux/files/usr/bin/bash
# Ultra Browser Agent — Termux installer (no pip upgrade, no Playwright wheel)
set -e
echo "=========================================="
echo " Ultra Browser Agent — Termux setup"
echo "=========================================="

pkg update -y
pkg install -y python git which x11-repo
pkg install -y chromium || pkg install -y chromium-browser || {
  echo "ERROR: could not install chromium"
  exit 1
}

echo ""
echo "Installing Python packages (Termux set, no Playwright)..."
# Do NOT run: pip install -U pip  (forbidden on Termux)
pip install -r requirements-termux.txt

CHROME=$(which chromium-browser 2>/dev/null || which chromium 2>/dev/null || true)
if [ -z "$CHROME" ]; then
  echo "ERROR: chromium binary not found after install"
  exit 1
fi
echo "Chromium: $CHROME"

ENVFILE="$HOME/.uba_env"
cat > "$ENVFILE" << ENV
export PLAYWRIGHT_BROWSERS_PATH=0
export UBA_USE_CDP=1
export CHROMIUM_PATH=$CHROME
export CDP_PORT=9222
# export NVIDIA_API_KEY=nvapi-YOUR-KEY
ENV

echo ""
echo "Wrote $ENVFILE"
echo ""
echo "Next steps:"
echo "  1. source ~/.uba_env"
echo "  2. export NVIDIA_API_KEY=nvapi-YOUR-KEY"
echo "  3. cd ~/ultra-browser-agent"
echo "  4. python run_web.py"
echo "  5. Open http://127.0.0.1:8080"
echo ""
echo "CLI test:"
echo "  python run_agent.py \"Extract heading from example.com\" --url https://example.com"
