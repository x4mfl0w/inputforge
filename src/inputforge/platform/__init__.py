"""Wählt die passende Plattform-Implementierung.

* Windows → :mod:`inputforge.platform.win32` (SendInput/Scancodes, Low-Level-Hooks)
* Linux/X11 → :mod:`inputforge.platform.x11` (XTest/XRecord/EWMH, ohne Root)
* sonst (Wayland, Headless, macOS) → Null-Backend: nur Bearbeiten, keine Eingaben
"""

from __future__ import annotations

import logging
import os
import sys

from inputforge.i18n import tr
from inputforge.platform.base import (
    INJECT_MARKER,
    InputBackend,
    InputEvent,
    InputHook,
    Platform,
    Rect,
    WindowManager,
)

log = logging.getLogger(__name__)


def _null(name: str, reason: str) -> Platform:
    from inputforge.platform import fallback

    log.warning("%s – Eingaben deaktiviert", reason)
    return Platform(
        name=tr("{name} (ohne Eingabe)", name=name),
        backend=fallback.NullBackend(),
        hook=fallback.NullHook(),
        windows=fallback.NullWindowManager(),
        game_ready=False,
        limitations=[reason],
    )


def create_platform() -> Platform:
    if sys.platform == "win32":
        from inputforge.platform import win32

        win32.set_timer_resolution(1)
        return Platform(
            name="Windows",
            backend=win32.Win32Backend(),
            hook=win32.Win32Hook(),
            windows=win32.Win32WindowManager(),
            game_ready=True,
            is_admin=win32.is_admin(),
        )

    if sys.platform.startswith("linux"):
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session == "wayland":
            return _null("Linux/Wayland", tr("Wayland wird nicht unterstützt – bitte X11-Sitzung"))
        if not os.environ.get("DISPLAY"):
            return _null("Linux", tr("Kein X11-Display (DISPLAY nicht gesetzt)"))
        try:
            from inputforge.platform import x11

            tracker = x11.InjectionTracker()
            return Platform(
                name="Linux/X11",
                backend=x11.X11Backend(tracker),
                hook=x11.X11Hook(tracker),
                windows=x11.X11WindowManager(),
                game_ready=True,
                is_admin=os.geteuid() == 0,
                limitations=[
                    tr("Trigger werden nicht abgefangen – das Spiel erhält die Taste ebenfalls"),
                ],
            )
        except Exception as exc:
            return _null("Linux", tr("X11 nicht nutzbar: {error}", error=exc))

    return _null(sys.platform, tr("Plattform {name} wird nicht unterstützt", name=sys.platform))


__all__ = [
    "INJECT_MARKER",
    "InputBackend",
    "InputEvent",
    "InputHook",
    "Platform",
    "Rect",
    "WindowManager",
    "create_platform",
]
