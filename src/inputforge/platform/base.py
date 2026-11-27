"""Plattform-Abstraktionen: Eingabe senden, Eingabe abfangen, Fenster verwalten."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

# Markiert von InputForge selbst erzeugte Eingaben (dwExtraInfo), damit der eigene Hook
# sie ignoriert und Makros sich nicht gegenseitig/selbst auslösen.
INJECT_MARKER = 0x1F0F_1F0F


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom


@dataclass(frozen=True, slots=True)
class InputEvent:
    key: str
    """Kanonischer Name (siehe :mod:`inputforge.core.keys`), inkl. Maustasten wie ``xbutton1``."""
    down: bool
    injected: bool = False
    """Von einem *anderen* Programm synthetisch erzeugt (eigene Eingaben kommen gar nicht an)."""


InputCallback = Callable[[InputEvent], bool]
"""Rückgabe ``True`` → Ereignis unterdrücken (erreicht das Spiel nicht)."""


class InputBackend(Protocol):
    def key_down(self, key: str) -> None: ...
    def key_up(self, key: str) -> None: ...
    def char_chord(self, ch: str) -> list[str] | None:
        """Tasten (inkl. Modifier), die das Zeichen im aktuellen Layout erzeugen."""
        ...

    def mouse_move(self, x: int, y: int) -> None: ...
    def mouse_move_relative(self, dx: int, dy: int) -> None: ...
    def mouse_down(self, button: str) -> None: ...
    def mouse_up(self, button: str) -> None: ...
    def cursor_pos(self) -> tuple[int, int]: ...


class InputHook(Protocol):
    def start(self, callback: InputCallback, *, mouse: bool) -> None: ...
    def stop(self) -> None: ...
    @property
    def can_suppress(self) -> bool: ...


class WindowManager(Protocol):
    def find(self, title: str) -> int | None:
        """Handle des ersten sichtbaren Fensters, dessen Titel ``title`` enthält."""
        ...

    def client_rect(self, handle: int) -> Rect | None: ...
    def activate(self, handle: int) -> bool: ...
    def foreground_title(self) -> str: ...
    def list_titles(self) -> list[str]: ...


@dataclass(slots=True)
class Platform:
    name: str
    backend: InputBackend
    hook: InputHook
    windows: WindowManager
    game_ready: bool
    """``True``, wenn Eingaben gesendet und Hotkeys erkannt werden können."""
    is_admin: bool = False
    limitations: list[str] = field(default_factory=list)
    """Plattformbedingte Einschränkungen, die die UI anzeigt."""
