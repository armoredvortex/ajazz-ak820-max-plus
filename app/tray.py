"""
tray.py - System-tray icon using pystray.

Gracefully no-ops if pystray is unavailable or if the desktop
has no tray support (e.g. Wayland compositors without a StatusNotifier).
"""

import threading
import logging

log = logging.getLogger(__name__)

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


def _make_icon_image(size: int = 64) -> "Image.Image":
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(4, 14), (size - 4, size - 14)], radius=6, fill=(30, 30, 40))
    colors = [(220, 50, 50), (50, 200, 50), (50, 100, 220)]
    for row, c in enumerate(colors):
        y = 22 + row * 10
        draw.rectangle([(8, y), (size - 8, y + 7)], fill=c)
    return img


class TrayIcon:
    def __init__(self, window, api):
        self._window = window
        self._api = api
        self._icon = None
        self._thread: threading.Thread | None = None

    def start(self):
        if not PYSTRAY_AVAILABLE:
            log.info("pystray not available — tray icon disabled")
            return

        try:
            self._start_icon()
        except Exception as e:
            log.info("Tray icon unavailable (%s) — continuing without it", e)

    def _start_icon(self):
        def on_show(icon, item):
            try:
                self._window.show()
            except Exception:
                pass

        def on_hide(icon, item):
            try:
                self._window.hide()
            except Exception:
                pass

        def on_off(icon, item):
            try:
                self._api.turn_off()
            except Exception:
                pass

        def on_quit(icon, item):
            try:
                icon.stop()
            except Exception:
                pass
            try:
                self._window.destroy()
            except Exception:
                pass

        menu = pystray.Menu(
            pystray.MenuItem("Show", on_show, default=True),
            pystray.MenuItem("Hide", on_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Turn off keyboard", on_off),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )

        self._icon = pystray.Icon(
            "ajazz-ak820",
            _make_icon_image(),
            "Ajazz AK820 RGB",
            menu,
        )

        self._thread = threading.Thread(
            target=self._run_icon,
            daemon=True,
            name="TrayIcon",
        )
        self._thread.start()

    def _run_icon(self):
        try:
            self._icon.run()
        except Exception as e:
            log.info("Tray icon stopped: %s", e)

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
