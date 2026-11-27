"""Null-Backend für Umgebungen ohne Eingabezugriff (Wayland, Headless/CI, macOS).

UI und Profilbearbeitung funktionieren, es werden aber keine Eingaben gesendet oder erkannt.
"""

from __future__ import annotations

import logging

from inputforge.core.keys import char_to_chord
from inputforge.platform.base import InputCallback, Rect

log = logging.getLogger(__name__)


class NullWindowManager:
    def find(self, title: str) -> int | None:
        return None

    def client_rect(self, handle: int) -> Rect | None:
        return None

    def activate(self, handle: int) -> bool:
        return False

    def foreground_title(self) -> str:
        return ""

    def list_titles(self) -> list[str]:
        return []


class NullBackend:
    """Sendet nichts, protokolliert nur auf DEBUG-Ebene."""

    def key_down(self, key: str) -> None:
        log.debug("key_down %s", key)

    def key_up(self, key: str) -> None:
        log.debug("key_up %s", key)

    def char_chord(self, ch: str) -> list[str] | None:
        return char_to_chord(ch)

    def mouse_move(self, x: int, y: int) -> None:
        log.debug("mouse_move %s %s", x, y)

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        log.debug("mouse_move_relative %s %s", dx, dy)

    def mouse_down(self, button: str) -> None:
        log.debug("mouse_down %s", button)

    def mouse_up(self, button: str) -> None:
        log.debug("mouse_up %s", button)

    def cursor_pos(self) -> tuple[int, int]:
        return 0, 0


class NullHook:
    can_suppress = False

    def start(self, callback: InputCallback, *, mouse: bool) -> None:
        log.warning("Kein Eingabe-Hook verfügbar – Hotkeys sind deaktiviert")

    def stop(self) -> None:
        pass
