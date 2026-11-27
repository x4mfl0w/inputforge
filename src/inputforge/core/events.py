from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class EventKind(StrEnum):
    LOG = "log"
    MACRO_STARTED = "macro_started"
    MACRO_STOPPED = "macro_stopped"
    IMAGE_FOUND = "image_found"
    IMAGE_NOT_FOUND = "image_not_found"
    ARMED = "armed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    kind: EventKind
    message: str
    macro_id: str | None = None
    level: int = logging.INFO
    notify: bool = False
    """UI soll eine Einblendung (Toast) zeigen – entspricht dem AHK-ToolTip."""


EventSink = Callable[[EngineEvent], None]
