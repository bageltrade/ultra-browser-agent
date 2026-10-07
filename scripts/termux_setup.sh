#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "== Ultra Browser Agent — Termux setup =="

pkg update -y
pkg install -y python git x11-repo which
pkg install -y chromium || pkg install -y chromium-browser || true

pip install -U pip
pip install -r requirements.txt

export PLAYWRIGHT_BROWSERS_PATH=0
CHROME=$(which chromium-browser 2>/dev/null || which chromium 2>/dev/null || true)
if [ -n "$CHROME" ]; then
  echo "Chromium found: $CHROME"
  echo "export CHROMIUM_PATH=$CHROME" >> "$HOME/.uba_env"
  echo "export PLAYWRIGHT_BROWSERS_PATH=0" >> "$HOME/.uba_env"
  echo "Wrote $HOME/.uba_env — run: source ~/.uba_env"
else
  echo "WARNING: Chromium not found. Try: pkg install x11-repo && pkg install chromium"
fi

echo ""
echo "Set your API key:"
echo "  export NVIDIA_API_KEY=nvapi-..."
echo "Start UI:"
echo "  python run_web.py"
