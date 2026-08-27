#!/usr/bin/env python3
"""
main.py - Entry point for the Ajazz AK820 Max RGB desktop app.

Launches a PyWebView window serving the pre-built Svelte frontend,
and optionally shows a system-tray icon.
"""

import os
import sys

# Force qtpy to use PyQt6 (system-installed), then tell pywebview to use Qt.
# Without QT_API, qtpy defaults to PyQt5 which lacks QtWebChannel on this system.
os.environ.setdefault("QT_API", "pyqt6")
os.environ.setdefault("PYWEBVIEW_GUI", "qt")

# ── locate the built frontend ──────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
UI_DIST = os.path.join(ROOT, "ui", "dist")
INDEX_HTML = os.path.join(UI_DIST, "index.html")

if not os.path.isfile(INDEX_HTML):
    print(
        "[ERROR] Frontend not built.\n"
        "Run:  cd ui && npm install && npm run build",
        file=sys.stderr,
    )
    sys.exit(1)

import webview  # noqa: E402 – import after env check

from app.api import KeyboardAPI
from app.tray import TrayIcon


def main():
    api = KeyboardAPI()

    window = webview.create_window(
        title="Ajazz AK820 RGB",
        url=f"file://{INDEX_HTML}",
        js_api=api,
        width=1000,
        height=680,
        min_size=(800, 560),
        background_color="#0f0f14",
        # frameless=True,   # uncomment for a fully custom titlebar
    )

    tray = TrayIcon(window, api)

    def on_loaded():
        # Kick off a connection attempt right after the UI is ready
        try:
            result = api.connect()
            if result["ok"]:
                window.evaluate_js(
                    f"window.dispatchEvent(new CustomEvent('kb-connected', "
                    f"{{ detail: {result} }}))"
                )
        except Exception:
            pass

    def on_closing():
        api.disconnect()
        tray.stop()

    window.events.loaded += on_loaded
    window.events.closing += on_closing

    # Start tray AFTER Qt's event loop is running to avoid thread conflicts.
    # pywebview's func= runs on the main thread inside the Qt loop.
    def _post_start():
        tray.start()

    webview.start(_post_start, debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
