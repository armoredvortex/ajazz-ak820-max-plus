#!/usr/bin/env bash
# run.sh - Launch the Ajazz AK820 RGB desktop app.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/venv"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    exit 1
fi

if [ ! -f "$ROOT/ui/dist/index.html" ]; then
    echo "Frontend not built. Run ./install.sh first."
    exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

# Force qtpy → PyQt6 so pywebview's Qt backend loads the right bindings
export QT_API=pyqt6
export PYWEBVIEW_GUI=qt

# Pass --debug to enable WebKit inspector (right-click → Inspect)
exec python "$ROOT/main.py" "$@"
