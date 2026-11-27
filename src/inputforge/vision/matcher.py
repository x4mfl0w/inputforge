"""Template-Matching (Pendant zu AHK ``ImageSearch``) mit OpenCV.

Statt der AHK-Toleranz ``*n`` (0–255 Farbabweichung pro Kanal) wird eine Ähnlichkeit
``confidence`` (0.5–1.0, ``TM_CCOEFF_NORMED``) verwendet. Faustregel für Umsteiger:
``*0`` ≈ 0.99, ``*50`` ≈ 0.92, ``*100`` ≈ 0.85.

Transparenz: Hat die Vorlage einen Alphakanal, werden transparente Pixel per Maske
ignoriert (wie ``*Trans`` in AHK).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class Match:
    x: int
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


@dataclass(frozen=True, slots=True)
class Template:
    bgr: Image
    gray: Image
    mask: Image | None

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.bgr.shape[:2]
        return w, h


def load_template(path: Path) -> Template:
    # np.fromfile + imdecode statt imread → funktioniert mit Umlauten im Pfad (Windows).
    raw = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED) if raw.size else None
    if img is None:
        raise FileNotFoundError(f"Bild nicht lesbar: {path}")
    return template_from_array(img)


def template_from_array(img: NDArray[Any]) -> Template:
    mask: Image | None = None
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        alpha = img[:, :, 3]
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        if int(alpha.min()) < 255:
            mask = np.asarray(cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)[1], np.uint8)
    else:
        bgr = img
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return Template(
        bgr=np.ascontiguousarray(bgr, dtype=np.uint8),
        gray=np.asarray(gray, dtype=np.uint8),
        mask=mask,
    )


class TemplateCache:
    """Thread-sicherer Cache; lädt Dateien neu, wenn sie sich ändern (mtime)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[Path, tuple[float, Template]] = {}

    def get(self, path: Path) -> Template:
        mtime = path.stat().st_mtime
        with self._lock:
            hit = self._items.get(path)
            if hit and hit[0] == mtime:
                return hit[1]
        tpl = load_template(path)
        with self._lock:
            self._items[path] = (mtime, tpl)
        return tpl

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


def find_template(
    haystack_bgr: Image,
    template: Template,
    confidence: float,
    *,
    grayscale: bool = False,
) -> Match | None:
    """Bestes Vorkommen von ``template`` in ``haystack_bgr`` oder ``None``."""
    tw, th = template.size
    hh, hw = haystack_bgr.shape[:2]
    if tw > hw or th > hh:
        return None

    if grayscale:
        hay = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY)
        needle = template.gray
    else:
        hay = haystack_bgr
        needle = template.bgr

    if template.mask is not None:
        # Mit Maske ist CCORR_NORMED stabil (CCOEFF_NORMED liefert bei Masken oft inf/nan).
        mask = template.mask if grayscale else cv2.merge([template.mask] * 3)
        result = cv2.matchTemplate(hay, needle, cv2.TM_CCORR_NORMED, mask=mask)
    else:
        result = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)

    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < confidence:
        return None
    return Match(x=int(max_loc[0]), y=int(max_loc[1]), w=tw, h=th, score=float(max_val))
