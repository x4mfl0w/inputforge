"""Ausführung eines Makros in einem eigenen Thread."""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from inputforge.config.models import (
    ActivateWindowAction,
    Anchor,
    CoordSpace,
    DelayAction,
    ImageClickAction,
    KeyAction,
    Macro,
    MouseClickAction,
    MouseMoveAction,
    NotFoundPolicy,
    Profile,
    RunMacroAction,
    RunMode,
    SearchArea,
    TypeTextAction,
)
from inputforge.core.events import EngineEvent, EventKind, EventSink
from inputforge.core.keys import parse_chord
from inputforge.i18n import tr
from inputforge.platform.base import InputBackend, Platform, Rect
from inputforge.vision.matcher import Image, TemplateCache, find_template

log = logging.getLogger(__name__)

MAX_NESTING = 8


class Grabber(Protocol):
    def grab(self, rect: Rect | None = None) -> tuple[Image, Rect]: ...


class StopRequested(Exception):
    """Benutzer/Trigger hat den Lauf gestoppt."""


class AbortRun(Exception):
    """Lauf wird wegen eines Fehlers oder einer Abbruch-Policy beendet."""


@dataclass
class RunContext:
    profile: Profile
    base_dir: Path
    platform: Platform
    grabber: Grabber
    templates: TemplateCache
    emit: EventSink


@dataclass
class _Held:
    keys: list[str] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)


class MacroRun(threading.Thread):
    def __init__(
        self,
        macro: Macro,
        ctx: RunContext,
        on_finish: Callable[[MacroRun], None] | None = None,
    ) -> None:
        super().__init__(name=f"macro-{macro.name}", daemon=True)
        self.macro = macro
        self.ctx = ctx
        self._stop_evt = threading.Event()
        self._on_finish = on_finish
        self._held = _Held()
        self.iterations_done = 0
        self.stopped_by_request = False

    @property
    def backend(self) -> InputBackend:
        return self.ctx.platform.backend

    def request_stop(self) -> None:
        self._stop_evt.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_evt.is_set()

    # ------------------------------------------------------------------ Lauf
    def run(self) -> None:
        m = self.macro
        self.ctx.emit(EngineEvent(EventKind.MACRO_STARTED, f"▶ {m.name}", m.id))
        finished = False
        reason = tr("fertig")
        try:
            self._loop()
            finished = True
        except StopRequested:
            self.stopped_by_request = True
            reason = tr("gestoppt")
        except AbortRun as exc:
            reason = tr("abgebrochen: {error}", error=exc)
        except Exception as exc:
            log.exception("Makro %s fehlgeschlagen", m.name)
            reason = tr("Fehler: {error}", error=exc)
            self.ctx.emit(EngineEvent(EventKind.ERROR, f"{m.name}: {exc}", m.id, logging.ERROR))
        finally:
            if not finished:
                self._release_all()
            self.ctx.emit(
                EngineEvent(
                    EventKind.MACRO_STOPPED,
                    f"■ {m.name} ({reason}, {self.iterations_done}×)",
                    m.id,
                )
            )
            if self._on_finish:
                self._on_finish(self)

    def _loop(self) -> None:
        m = self.macro
        if m.mode is RunMode.ONCE:
            limit: float = 1
        else:
            limit = m.repeat_count or math.inf
        deadline = (
            time.monotonic() + m.duration_s
            if m.mode is not RunMode.ONCE and m.duration_s > 0
            else None
        )
        while self.iterations_done < limit:
            self._check_stop()
            self._exec_steps(m, depth=0)
            self.iterations_done += 1
            if self.iterations_done >= limit:
                break
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.sleep_ms(min(m.interval_ms, remaining * 1000))
                if time.monotonic() >= deadline:
                    break
            else:
                self.sleep_ms(m.interval_ms)

    def _exec_steps(self, macro: Macro, depth: int) -> None:
        for step in macro.steps:
            if not step.enabled:
                continue
            self._check_stop()
            self._exec(step, depth)
            if step.post_delay_ms:
                self.sleep_ms(step.post_delay_ms)

    # ------------------------------------------------------------------ Helfer
    def _check_stop(self) -> None:
        if self._stop_evt.is_set():
            raise StopRequested

    def sleep_ms(self, ms: float) -> None:
        if ms <= 0:
            self._check_stop()
            return
        if self._stop_evt.wait(ms / 1000.0):
            raise StopRequested

    def _press(self, key: str) -> None:
        self.backend.key_down(key)
        self._held.keys.append(key)

    def _release(self, key: str) -> None:
        self.backend.key_up(key)
        if key in self._held.keys:
            self._held.keys.remove(key)

    def _tap_chord(self, keys: list[str], hold_ms: int) -> None:
        for k in keys:
            self._press(k)
        try:
            self.sleep_ms(hold_ms)
        finally:
            for k in reversed(keys):
                self._release(k)

    def _button_down(self, button: str) -> None:
        self.backend.mouse_down(button)
        self._held.buttons.append(button)

    def _button_up(self, button: str) -> None:
        self.backend.mouse_up(button)
        if button in self._held.buttons:
            self._held.buttons.remove(button)

    def _click(self, button: str, hold_ms: int) -> None:
        self._button_down(button)
        try:
            self.sleep_ms(hold_ms)
        finally:
            self._button_up(button)

    def _release_all(self) -> None:
        for k in reversed(self._held.keys[:]):
            try:
                self._release(k)
            except Exception:
                log.exception("Taste %s konnte nicht losgelassen werden", k)
        for b in reversed(self._held.buttons[:]):
            try:
                self._button_up(b)
            except Exception:
                log.exception("Maustaste %s konnte nicht losgelassen werden", b)

    def _target_rect(self, required: bool) -> Rect | None:
        title = self.ctx.profile.settings.target_window
        if not title:
            if required:
                raise AbortRun(tr("Kein Zielfenster im Profil konfiguriert"))
            return None
        wm = self.ctx.platform.windows
        handle = wm.find(title)
        rect = wm.client_rect(handle) if handle is not None else None
        if rect is None and required:
            raise AbortRun(tr("Zielfenster '{title}' nicht gefunden", title=title))
        return rect

    def _resolve_point(self, x: int, y: int, space: CoordSpace) -> tuple[int, int]:
        if space is CoordSpace.WINDOW:
            rect = self._target_rect(required=True)
            assert rect is not None
            return rect.x + x, rect.y + y
        return x, y

    # ------------------------------------------------------------------ Aktionen
    def _exec(self, step: object, depth: int) -> None:
        match step:
            case KeyAction():
                self._do_key(step)
            case TypeTextAction():
                self._do_type(step)
            case MouseClickAction():
                self._do_click(step)
            case MouseMoveAction():
                if step.relative:
                    self.backend.mouse_move_relative(step.x, step.y)
                else:
                    self.backend.mouse_move(*self._resolve_point(step.x, step.y, step.space))
            case DelayAction():
                extra = random.randint(0, step.random_ms) if step.random_ms else 0
                self.sleep_ms(step.ms + extra)
            case ImageClickAction():
                self._do_image(step)
            case ActivateWindowAction():
                self._do_activate(step)
            case RunMacroAction():
                self._do_run_macro(step, depth)
            case _:
                raise AbortRun(tr("Unbekannter Schritt: {step}", step=repr(step)))

    def _do_key(self, a: KeyAction) -> None:
        keys = parse_chord(a.keys)
        if a.mode == "tap":
            self._tap_chord(keys, a.hold_ms)
        elif a.mode == "down":
            for k in keys:
                self._press(k)
        else:
            for k in reversed(keys):
                self._release(k)

    def _do_type(self, a: TypeTextAction) -> None:
        for i, ch in enumerate(a.text):
            chord = self.backend.char_chord(ch)
            if chord is None:
                self.ctx.emit(
                    EngineEvent(
                        EventKind.LOG,
                        tr("Zeichen '{ch}' nicht tippbar – übersprungen", ch=ch),
                        self.macro.id,
                        logging.WARNING,
                    )
                )
                continue
            self._tap_chord(chord, a.hold_ms)
            if a.key_delay_ms and i < len(a.text) - 1:
                self.sleep_ms(a.key_delay_ms)

    def _do_click(self, a: MouseClickAction) -> None:
        if a.x is not None and a.y is not None:
            self.backend.mouse_move(*self._resolve_point(a.x, a.y, a.space))
        for i in range(a.clicks):
            self._click(a.button.value, a.hold_ms)
            if i < a.clicks - 1:
                self.sleep_ms(a.interval_ms)

    def _search_rect(self, a: ImageClickAction) -> Rect | None:
        if a.area is SearchArea.SCREEN:
            return None
        win = self._target_rect(required=False)
        if self.ctx.profile.settings.target_window and win is None:
            raise LookupError(
                tr("Zielfenster '{title}' fehlt", title=self.ctx.profile.settings.target_window)
            )
        if a.area is SearchArea.WINDOW:
            return win
        assert a.region is not None
        rx, ry, rw, rh = a.region
        ox, oy = (win.x, win.y) if win else (0, 0)
        return Rect(ox + rx, oy + ry, rw, rh)

    def _do_image(self, a: ImageClickAction) -> None:
        path = Path(a.image)
        if not path.is_absolute():
            path = self.ctx.base_dir / path
        try:
            template = self.ctx.templates.get(path)
        except (OSError, FileNotFoundError) as exc:
            self._image_missing(
                a, tr("Bilddatei fehlt: {name} ({error})", name=path.name, error=exc)
            )
            return

        deadline = time.monotonic() + a.timeout_ms / 1000.0
        match = None
        origin: Rect | None = None
        while True:
            self._check_stop()
            try:
                rect = self._search_rect(a)
                shot, origin = self.ctx.grabber.grab(rect)
                match = find_template(shot, template, a.confidence, grayscale=a.grayscale)
            except (LookupError, ValueError) as exc:
                self._image_missing(a, str(exc))
                return
            if match is not None or time.monotonic() >= deadline:
                break
            self.sleep_ms(a.retry_interval_ms)

        if match is None or origin is None:
            self._image_missing(a, tr("NICHT GEFUNDEN: {name}", name=path.name))
            return

        if a.anchor is Anchor.CENTER:
            px, py = match.center
        else:
            px, py = match.x, match.y
        sx, sy = origin.x + px + a.offset_x, origin.y + py + a.offset_y
        self.ctx.emit(
            EngineEvent(
                EventKind.IMAGE_FOUND,
                tr(
                    "{name} gefunden bei ({x}, {y}), Score {score}",
                    name=path.name,
                    x=sx,
                    y=sy,
                    score=f"{match.score:.3f}",
                ),
                self.macro.id,
                logging.DEBUG,
            )
        )
        self.backend.mouse_move(sx, sy)
        if a.button is not None:
            self._click(a.button.value, a.hold_ms)

    def _image_missing(self, a: ImageClickAction, message: str) -> None:
        notify = a.notify_not_found and self.ctx.profile.settings.show_notifications
        self.ctx.emit(
            EngineEvent(EventKind.IMAGE_NOT_FOUND, message, self.macro.id, logging.WARNING, notify)
        )
        if a.on_not_found is NotFoundPolicy.STOP:
            raise AbortRun(message)

    def _do_activate(self, a: ActivateWindowAction) -> None:
        title = a.title or self.ctx.profile.settings.target_window
        if not title:
            raise AbortRun(tr("Fenster aktivieren: kein Titel und kein Zielfenster gesetzt"))
        wm = self.ctx.platform.windows
        handle = wm.find(title)
        if handle is None or not wm.activate(handle):
            self.ctx.emit(
                EngineEvent(
                    EventKind.LOG,
                    tr("Fenster '{title}' nicht aktivierbar", title=title),
                    self.macro.id,
                    logging.WARNING,
                )
            )
        self.sleep_ms(a.wait_ms)

    def _do_run_macro(self, a: RunMacroAction, depth: int) -> None:
        if depth >= MAX_NESTING:
            raise AbortRun(
                tr("Maximale Verschachtelung ({n}) erreicht – Endlosschleife?", n=MAX_NESTING)
            )
        target = self.ctx.profile.macro_by_id(a.macro_id)
        if target is None:
            raise AbortRun(tr("Makro {id} existiert nicht", id=a.macro_id))
        self._exec_steps(target, depth + 1)
