from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from inputforge.config.models import Profile
from inputforge.core.engine import Engine
from inputforge.core.events import EngineEvent
from inputforge.platform.base import InputCallback, InputEvent, Platform, Rect


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.lock = threading.Lock()
        self.pos = (0, 0)

    def _rec(self, *call: object) -> None:
        with self.lock:
            self.calls.append(call)

    def key_down(self, key: str) -> None:
        self._rec("down", key)

    def key_up(self, key: str) -> None:
        self._rec("up", key)

    def char_chord(self, ch: str) -> list[str] | None:
        from inputforge.core.keys import char_to_chord

        return char_to_chord(ch)

    def mouse_move(self, x: int, y: int) -> None:
        self.pos = (x, y)
        self._rec("move", x, y)

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        self._rec("rel", dx, dy)

    def mouse_down(self, button: str) -> None:
        self._rec("mdown", button)

    def mouse_up(self, button: str) -> None:
        self._rec("mup", button)

    def cursor_pos(self) -> tuple[int, int]:
        return self.pos

    def snapshot(self) -> list[tuple]:
        with self.lock:
            return list(self.calls)

    def count(self, *call: object) -> int:
        return sum(1 for c in self.snapshot() if c == call)


class FakeHook:
    can_suppress = True

    def __init__(self) -> None:
        self.callback: InputCallback | None = None
        self.mouse = False

    def start(self, callback: InputCallback, *, mouse: bool) -> None:
        self.callback = callback
        self.mouse = mouse

    def stop(self) -> None:
        self.callback = None

    def press(self, key: str) -> bool:
        assert self.callback is not None
        return self.callback(InputEvent(key, True))

    def release(self, key: str) -> bool:
        assert self.callback is not None
        return self.callback(InputEvent(key, False))

    def tap(self, key: str) -> bool:
        suppressed = self.press(key)
        self.release(key)
        return suppressed


class FakeWindows:
    def __init__(self) -> None:
        self.windows: dict[str, Rect] = {"Grim Dawn": Rect(100, 50, 800, 600)}
        self.foreground = "Grim Dawn"
        self.activated: list[int] = []

    def _titles(self) -> list[str]:
        return list(self.windows)

    def find(self, title: str) -> int | None:
        for i, t in enumerate(self._titles()):
            if title.lower() in t.lower():
                return i
        return None

    def client_rect(self, handle: int) -> Rect | None:
        titles = self._titles()
        return self.windows[titles[handle]] if 0 <= handle < len(titles) else None

    def activate(self, handle: int) -> bool:
        self.activated.append(handle)
        return True

    def foreground_title(self) -> str:
        return self.foreground

    def list_titles(self) -> list[str]:
        return self._titles()


class FakeGrabber:
    """Liefert ein Ausschnitt eines festen virtuellen 'Bildschirms'."""

    def __init__(self, screen: np.ndarray) -> None:
        self.screen = screen
        self.grabs: list[Rect | None] = []

    def grab(self, rect: Rect | None = None) -> tuple[np.ndarray, Rect]:
        self.grabs.append(rect)
        h, w = self.screen.shape[:2]
        r = rect or Rect(0, 0, w, h)
        x1, y1 = max(r.x, 0), max(r.y, 0)
        x2, y2 = min(r.right, w), min(r.bottom, h)
        return self.screen[y1:y2, x1:x2].copy(), Rect(x1, y1, x2 - x1, y2 - y1)


@pytest.fixture
def screen() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, size=(800, 1200, 3), dtype=np.uint8)


class Harness:
    def __init__(self, tmp_path: Path, screen: np.ndarray) -> None:
        self.backend = FakeBackend()
        self.hook = FakeHook()
        self.windows = FakeWindows()
        self.grabber = FakeGrabber(screen)
        self.events: list[EngineEvent] = []
        self.platform = Platform("fake", self.backend, self.hook, self.windows, game_ready=True)
        self.engine = Engine(self.platform, grabber=self.grabber, emit=self.events.append)
        self.base_dir = tmp_path

    def load(self, profile: Profile) -> None:
        self.engine.load(profile, self.base_dir)
        self.engine.start()

    def wait_idle(self, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while self.engine.running_ids():
            if time.monotonic() > deadline:
                raise AssertionError(f"Makros laufen noch: {self.engine.running_ids()}")
            time.sleep(0.005)

    def wait_for(self, cond: Callable[[], bool], timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while not cond():
            if time.monotonic() > deadline:
                raise AssertionError("Bedingung nicht erfüllt")
            time.sleep(0.005)


@pytest.fixture
def harness(tmp_path: Path, screen: np.ndarray):
    h = Harness(tmp_path, screen)
    yield h
    h.engine.shutdown()
