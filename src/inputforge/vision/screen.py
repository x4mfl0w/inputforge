"""Bildschirmaufnahme via mss (DXGI/GDI unter Windows, sehr schnell)."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from inputforge.platform.base import Rect
from inputforge.vision.matcher import Image


class ScreenGrabber:
    """mss-Instanzen sind an den erzeugenden Thread gebunden → eine pro Thread."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _sct(self) -> Any:
        sct = getattr(self._local, "sct", None)
        if sct is None:
            import mss

            sct = mss.mss()
            self._local.sct = sct
        return sct

    def virtual_screen(self) -> Rect:
        mon = self._sct().monitors[0]
        return Rect(mon["left"], mon["top"], mon["width"], mon["height"])

    def grab(self, rect: Rect | None = None) -> tuple[Image, Rect]:
        """BGR-Bild des Bereichs (Standard: gesamter virtueller Desktop) + tatsächlicher Bereich."""
        screen = self.virtual_screen()
        r = rect or screen
        # Auf den Desktop zuschneiden – mss wirft sonst bei Bereichen außerhalb.
        x1, y1 = max(r.x, screen.x), max(r.y, screen.y)
        x2, y2 = min(r.right, screen.right), min(r.bottom, screen.bottom)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Suchbereich {r} liegt außerhalb des Bildschirms")
        clipped = Rect(x1, y1, x2 - x1, y2 - y1)
        shot = self._sct().grab(
            {"left": clipped.x, "top": clipped.y, "width": clipped.w, "height": clipped.h}
        )
        bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        return np.ascontiguousarray(bgra[:, :, :3]), clipped
