# Running on Termux (Android)

## 1. Packages

```bash
pkg update && pkg upgrade
pkg install python git
pip install -r requirements.txt
```

## 2. Browser on Termux

Full Playwright Chromium **does not run natively** on Termux.
Options:

| Option | How |
|--------|-----|
| **A. Remote Chrome (recommended)** | Run Chrome/Chromium on a PC or VPS with `--remote-debugging-port=9222`, then set `AgentConfig(cdp_url="http://IP:9222")` |
| **B. Proot / UserLAnd** | Install a full Linux userspace and run Playwright there |
| **C. UI-only** | Use the web chat UI to talk to a server that has the browser |

## 3. Start the chat UI on device

```bash
export NVIDIA_API_KEY="nvapi-..."
python run_web.py
# open http://127.0.0.1:8080 in your phone browser
```

Or expose on LAN:

```bash
UBA_HOST=0.0.0.0 UBA_PORT=8080 python run_web.py
```

## 4. Env vars

- `NVIDIA_API_KEY` — required
- `NVIDIA_API_BASE` — default `https://integrate.api.nvidia.com/v1`
- `NVIDIA_MODEL` — default `nvidia/nemotron-3-super-120b-a12b`
- `UBA_HOST` / `UBA_PORT` — web server bind
