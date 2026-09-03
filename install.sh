#!/usr/bin/env bash
# install.sh - One-shot setup for the Ajazz AK820 RGB desktop app.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── colour helpers ──────────────────────────────────────────────────────
green() { printf '\e[32m%s\e[0m\n' "$*"; }
blue()  { printf '\e[34m%s\e[0m\n' "$*"; }
red()   { printf '\e[31m%s\e[0m\n' "$*"; }

# ── 1. Python virtual environment ───────────────────────────────────────
blue "→ Setting up Python virtual environment…"
# --system-site-packages lets the venv inherit gi (GTK) and PyQt* from the
# system Python, which cannot be installed via pip.
if [ ! -d "$ROOT/venv" ]; then
    python3 -m venv --system-site-packages "$ROOT/venv"
else
    # Recreate if it was built without system-site-packages
    if ! grep -q "include-system-site-packages = true" "$ROOT/venv/pyvenv.cfg" 2>/dev/null; then
        blue "  Recreating venv with --system-site-packages…"
        rm -rf "$ROOT/venv"
        python3 -m venv --system-site-packages "$ROOT/venv"
    fi
fi
# shellcheck source=/dev/null
source "$ROOT/venv/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$ROOT/requirements.txt"
green "  Python deps installed."

# ── 2. Node / npm ────────────────────────────────────────────────────────
blue "→ Checking for Node.js…"
if ! command -v node &>/dev/null; then
    red "Node.js not found. Install it from https://nodejs.org/ (v18+) and re-run."
    exit 1
fi
NODE_VER=$(node -e "process.stdout.write(process.version)")
blue "  Node ${NODE_VER} found."

# ── 3. Frontend dependencies ─────────────────────────────────────────────
blue "→ Installing frontend dependencies…"
cd "$ROOT/ui"
npm install --silent
green "  npm packages installed."

# ── 4. Build the frontend ────────────────────────────────────────────────
blue "→ Building Svelte frontend…"
npm run build
green "  Frontend built → ui/dist/"

cd "$ROOT"

# ── 5. udev rule (hidraw permissions) ────────────────────────────────────
UDEV_FILE="/etc/udev/rules.d/99-ajazz-ak820.rules"
UDEV_RULE_USB='SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1a2c", ATTRS{idProduct}=="8fff", MODE="0660", GROUP="input"'
UDEV_RULE_24G='SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1a2c", ATTRS{idProduct}=="a036", MODE="0660", GROUP="input"'

if [ ! -f "$UDEV_FILE" ]; then
    blue "→ Installing udev rule for keyboard access…"
    printf '%s\n%s\n' "$UDEV_RULE_USB" "$UDEV_RULE_24G" | sudo tee "$UDEV_FILE" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    sudo usermod -aG input "$USER"
    green "  udev rule installed (USB + 2.4 GHz). Log out and back in for group membership to take effect."
else
    green "  udev rule already present, skipping."
fi

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
green "✓ Installation complete."
echo "  Run the app with:  ./run.sh"
