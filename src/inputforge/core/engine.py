"""Engine: verbindet Eingabe-Hook, Hotkey-Erkennung und Makro-Ausführung."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from inputforge.config.models import Macro, Profile, RunMode
from inputforge.core.events import EngineEvent, EventKind, EventSink
from inputforge.core.keys import MODIFIER_OF, Hotkey, is_mouse, parse_hotkey
from inputforge.core.runner import Grabber, MacroRun, RunContext
from inputforge.platform.base import InputEvent, Platform
from inputforge.vision.matcher import TemplateCache

log = logging.getLogger(__name__)

_NO_UP_EVENT = frozenset({"wheelup", "wheeldown"})


@dataclass(frozen=True, slots=True)
class Binding:
    hotkey: Hotkey
    macro: Macro


class Engine:
    """Thread-sicher. ``handle_input`` läuft im Hook-Thread und muss schnell zurückkehren."""

    def __init__(
        self,
        platform: Platform,
        grabber: Grabber | None = None,
        emit: EventSink | None = None,
    ) -> None:
        if grabber is None:
            from inputforge.vision.screen import ScreenGrabber

            grabber = ScreenGrabber()
        self.platform = platform
        self.grabber = grabber
        self._emit_cb = emit
        self.templates = TemplateCache()
        self._lock = threading.RLock()
        self._profile = Profile()
        self._base_dir = Path.cwd()
        self._bindings: list[Binding] = []
        self._stop_hotkey: Hotkey | None = None
        self._arm_hotkey: Hotkey | None = None
        self._runs: dict[str, MacroRun] = {}
        self._hold_owner: dict[str, set[str]] = defaultdict(set)
        self._down: set[str] = set()
        self._suppressed: set[str] = set()
        self._armed = True
        self._hook_running = False

    # ------------------------------------------------------------------ öffentlich
    @property
    def profile(self) -> Profile:
        return self._profile

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def hook_running(self) -> bool:
        return self._hook_running

    def set_emit(self, emit: EventSink | None) -> None:
        self._emit_cb = emit

    def load(self, profile: Profile, base_dir: Path) -> None:
        """Profil übernehmen. Stoppt laufende Makros; startet den Hook bei Bedarf neu."""
        self.stop_all()
        with self._lock:
            self._profile = profile.model_copy(deep=True)
            self._base_dir = base_dir
            self.templates.clear()
            self._bindings = [
                Binding(parse_hotkey(t), m)
                for m in self._profile.macros
                if m.enabled
                for t in m.triggers
            ]
            s = self._profile.settings
            self._stop_hotkey = parse_hotkey(s.stop_all_hotkey) if s.stop_all_hotkey else None
            self._arm_hotkey = parse_hotkey(s.arm_toggle_hotkey) if s.arm_toggle_hotkey else None
        if self._hook_running:
            self.start()  # Maus-Hook ggf. an-/abschalten

    def needs_mouse_hook(self) -> bool:
        keys = [b.hotkey.key for b in self._bindings]
        keys += [h.key for h in (self._stop_hotkey, self._arm_hotkey) if h]
        return any(is_mouse(k) for k in keys)

    def start(self) -> None:
        self.platform.hook.start(self.handle_input, mouse=self.needs_mouse_hook())
        self._hook_running = True
        self._emit(EventKind.LOG, f"Hotkeys aktiv ({len(self._bindings)} Bindungen)")

    def shutdown(self) -> None:
        self.stop_all()
        self.platform.hook.stop()
        self._hook_running = False

    def set_armed(self, armed: bool) -> None:
        self._armed = armed
        if not armed:
            self.stop_all()
        self._emit(EventKind.ARMED, "Scharf" if armed else "Pausiert")

    def stop_all(self) -> None:
        with self._lock:
            runs = list(self._runs.values())
        for r in runs:
            r.request_stop()
        for r in runs:
            r.join(2.0)

    def running_ids(self) -> set[str]:
        with self._lock:
            return set(self._runs)

    def trigger(self, macro_id: str) -> None:
        """Makro wie per Hotkey auslösen (z. B. „Test“-Button in der UI)."""
        macro = self._profile.macro_by_id(macro_id)
        if macro is not None:
            self._fire(macro, key=None)

    def stop_macro(self, macro_id: str) -> None:
        with self._lock:
            run = self._runs.get(macro_id)
        if run:
            run.request_stop()

    # ------------------------------------------------------------------ Hook
    def handle_input(self, ev: InputEvent) -> bool:
        key = ev.key
        if not ev.down:
            return self._handle_up(key)

        repeat = key in self._down
        if key not in _NO_UP_EVENT:
            self._down.add(key)
        if repeat:
            # Autorepeat: nichts auslösen, aber konsistent unterdrücken.
            return key in self._suppressed

        mods = frozenset(MODIFIER_OF[k] for k in self._down if k in MODIFIER_OF)

        if self._stop_hotkey and self._stop_hotkey.matches(key, mods, wildcard=False):
            self._emit(EventKind.LOG, "Notaus – alle Makros gestoppt", notify=True)
            threading.Thread(target=self.stop_all, daemon=True).start()
            return self._mark_suppressed(key)
        if self._arm_hotkey and self._arm_hotkey.matches(key, mods, wildcard=False):
            self.set_armed(not self._armed)
            return self._mark_suppressed(key)

        if not self._armed:
            return False

        matched = [b for b in self._bindings if b.hotkey.matches(key, mods, b.macro.wildcard)]
        if not matched:
            return False
        if not self._focus_ok():
            return False

        suppress = False
        for b in matched:
            self._fire(b.macro, key)
            suppress |= not b.macro.passthrough
        if suppress and self.platform.hook.can_suppress:
            return self._mark_suppressed(key)
        return False

    def _handle_up(self, key: str) -> bool:
        self._down.discard(key)
        with self._lock:
            owners = self._hold_owner.pop(key, set())
            runs = [self._runs[mid] for mid in owners if mid in self._runs]
        for r in runs:
            r.request_stop()
        if key in self._suppressed:
            self._suppressed.discard(key)
            return True
        return False

    def _mark_suppressed(self, key: str) -> bool:
        if not self.platform.hook.can_suppress:
            return False
        if key not in _NO_UP_EVENT:
            self._suppressed.add(key)
        return True

    def _focus_ok(self) -> bool:
        s = self._profile.settings
        if not s.require_window_focus or not s.target_window:
            return True
        return s.target_window.lower() in self.platform.windows.foreground_title().lower()

    # ------------------------------------------------------------------ Ausführung
    def _fire(self, macro: Macro, key: str | None) -> None:
        with self._lock:
            running = self._runs.get(macro.id)
            if running is not None:
                if macro.mode in (RunMode.TOGGLE, RunMode.REPEAT):
                    running.request_stop()
                # ONCE: läuft schon → ignorieren; HOLD: läuft bis zum Loslassen.
                # Manuell ausgelöstes HOLD (key=None) hat kein Loslassen → Stop-Button/Notaus.
                return
            ctx = RunContext(
                profile=self._profile,
                base_dir=self._base_dir,
                platform=self.platform,
                grabber=self.grabber,
                templates=self.templates,
                emit=self._emit_event,
            )
            run = MacroRun(macro, ctx, on_finish=self._on_finish)
            self._runs[macro.id] = run
            if macro.mode is RunMode.HOLD and key is not None:
                self._hold_owner[key].add(macro.id)
        run.start()

    def _on_finish(self, run: MacroRun) -> None:
        with self._lock:
            if self._runs.get(run.macro.id) is run:
                del self._runs[run.macro.id]
            for owners in self._hold_owner.values():
                owners.discard(run.macro.id)

    # ------------------------------------------------------------------ Events
    def _emit_event(self, event: EngineEvent) -> None:
        log.log(event.level, "%s", event.message)
        cb = self._emit_cb
        if cb is not None:
            try:
                cb(event)
            except Exception:
                log.exception("Event-Callback fehlgeschlagen")

    def _emit(self, kind: EventKind, message: str, *, notify: bool = False) -> None:
        self._emit_event(EngineEvent(kind, message, notify=notify))
