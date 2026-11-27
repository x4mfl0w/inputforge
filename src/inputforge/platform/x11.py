"""Linux/X11-Implementierung über python-xlib – ohne Root-Rechte.

* Eingaben: XTest (``fake_input``). Kommt in nativen X11-Spielen und Wine/Proton an.
* Hotkeys: XRecord hört alle Geräteereignisse mit. **Unterdrücken ist damit nicht möglich**
  (``can_suppress = False``) – der Trigger erreicht das Spiel immer.
* Eigene Eingaben: XRecord sieht auch XTest-Events. Der :class:`InjectionTracker` merkt sich
  jede selbst gesendete Taste und filtert das passende Echo heraus.
* Fenster: EWMH (``_NET_CLIENT_LIST``, ``_NET_ACTIVE_WINDOW``, ``_NET_WM_NAME``).

Wayland wird nicht unterstützt (keine Fenster-API, Screenshots nur per Portal).

python-xlib ist nicht thread-sicher → jede Komponente hat eine eigene Verbindung + Lock.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any

from Xlib import XK, X, display
from Xlib.error import XError
from Xlib.ext import record, xtest
from Xlib.protocol import event as xevent
from Xlib.protocol import rq

from inputforge.core.keys import VK
from inputforge.platform.base import InputCallback, InputEvent, Rect

log = logging.getLogger(__name__)

XK.load_keysym_group("xf86")
XK.load_keysym_group("xkb")  # ISO_Level3_Shift (AltGr)

# Kanonischer Tastenname → Kandidaten-Keysyms (erster vorhandener gewinnt)
_KEYSYMS: dict[str, tuple[str, ...]] = {
    "backspace": ("BackSpace",), "tab": ("Tab",), "clear": ("Clear",), "enter": ("Return",),
    "pause": ("Pause",), "capslock": ("Caps_Lock",), "esc": ("Escape",), "space": ("space",),
    "pageup": ("Prior",), "pagedown": ("Next",), "end": ("End",), "home": ("Home",),
    "left": ("Left",), "up": ("Up",), "right": ("Right",), "down": ("Down",),
    "printscreen": ("Print",), "insert": ("Insert",), "delete": ("Delete",),
    "shift": ("Shift_L",), "lshift": ("Shift_L",), "rshift": ("Shift_R",),
    "ctrl": ("Control_L",), "lctrl": ("Control_L",), "rctrl": ("Control_R",),
    "alt": ("Alt_L",), "lalt": ("Alt_L",), "ralt": ("ISO_Level3_Shift", "Alt_R"),
    "win": ("Super_L",), "lwin": ("Super_L",), "rwin": ("Super_R",), "apps": ("Menu",),
    "numlock": ("Num_Lock",), "scrolllock": ("Scroll_Lock",),
    "multiply": ("KP_Multiply",), "add": ("KP_Add",), "subtract": ("KP_Subtract",),
    "decimal": ("KP_Decimal", "KP_Separator"), "divide": ("KP_Divide",),
    "semicolon": ("semicolon",), "plus": ("plus", "equal"), "comma": ("comma",),
    "minus": ("minus",), "period": ("period",), "slash": ("slash",), "backtick": ("grave",),
    "lbracket": ("bracketleft",), "backslash": ("backslash",), "rbracket": ("bracketright",),
    "quote": ("apostrophe",), "oem102": ("less",),
    "volumemute": ("XF86AudioMute",), "volumedown": ("XF86AudioLowerVolume",),
    "volumeup": ("XF86AudioRaiseVolume",), "medianext": ("XF86AudioNext",),
    "mediaprev": ("XF86AudioPrev",), "mediastop": ("XF86AudioStop",),
    "mediaplay": ("XF86AudioPlay",),
}  # fmt: skip
_KEYSYMS.update({c: (c,) for c in "abcdefghijklmnopqrstuvwxyz0123456789"})
_KEYSYMS.update({f"f{n}": (f"F{n}",) for n in range(1, 25)})
_KEYSYMS.update({f"numpad{d}": (f"KP_{d}",) for d in range(10)})

# Nicht als Rückabbildung verwenden – seitenspezifische Namen haben Vorrang.
_GENERIC = frozenset({"shift", "ctrl", "alt", "win"})

_BUTTONS = {"left": 1, "middle": 2, "right": 3, "x1": 8, "x2": 9}
_BUTTON_TRIGGERS = {1: "lbutton", 2: "mbutton", 3: "rbutton", 4: "wheelup", 5: "wheeldown",
                    8: "xbutton1", 9: "xbutton2"}  # fmt: skip

RAW_PREFIX = "kc:"
"""Interner Name für rohe Keycodes (z. B. „ü“ beim Tippen), nur innerhalb dieses Backends."""


class KeyMap:
    """Abbildung Tastenname ⇄ X11-Keycode für das aktuelle Layout."""

    def __init__(self, disp: display.Display) -> None:
        self.to_code: dict[str, int] = {}
        self.to_name: dict[int, str] = {}
        for name, candidates in _KEYSYMS.items():
            for sym_name in candidates:
                sym = XK.string_to_keysym(sym_name)
                code = disp.keysym_to_keycode(sym) if sym else 0
                if code:
                    self.to_code[name] = code
                    if name not in _GENERIC:
                        self.to_name.setdefault(code, name)
                    break
        missing = sorted(set(VK) - set(self.to_code))
        if missing:
            log.debug("Ohne Keycode im aktuellen Layout: %s", ", ".join(missing))

    def code(self, name: str) -> int:
        if name.startswith(RAW_PREFIX):
            return int(name[len(RAW_PREFIX) :])
        code = self.to_code.get(name)
        if code is None:
            raise ValueError(f"Taste '{name}' hat im aktuellen Tastaturlayout keinen Keycode")
        return code


class InjectionTracker:
    """Merkt sich selbst gesendete Events, damit der Hook ihr Echo ignoriert.

    Einträge verfallen nach ``ttl`` Sekunden, falls XRecord ein Echo verpasst – sonst würde
    ein später echter Tastendruck fälschlich verschluckt.
    """

    def __init__(self, ttl: float = 1.0) -> None:
        self.ttl = ttl
        self._lock = threading.Lock()
        self._pending: dict[tuple[str, int, bool], deque[float]] = defaultdict(deque)

    def sent(self, kind: str, code: int, down: bool) -> None:
        with self._lock:
            self._pending[(kind, code, down)].append(time.monotonic())

    def is_echo(self, kind: str, code: int, down: bool) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._pending.get((kind, code, down))
            if not q:
                return False
            while q and now - q[0] > self.ttl:
                q.popleft()
            if q:
                q.popleft()
                return True
            return False


def _open_display() -> display.Display:
    return display.Display()


# ======================================================================================
# Eingaben senden
# ======================================================================================
class X11Backend:
    def __init__(self, tracker: InjectionTracker, disp: display.Display | None = None) -> None:
        self._d = disp or _open_display()
        if not self._d.has_extension("XTEST"):
            raise RuntimeError("X-Server ohne XTEST-Erweiterung")
        self._lock = threading.Lock()
        self._tracker = tracker
        self.keymap = KeyMap(self._d)

    def _key(self, key: str, down: bool) -> None:
        code = self.keymap.code(key)
        with self._lock:
            self._tracker.sent("k", code, down)
            xtest.fake_input(self._d, X.KeyPress if down else X.KeyRelease, code)
            self._d.sync()

    def key_down(self, key: str) -> None:
        self._key(key, True)

    def key_up(self, key: str) -> None:
        self._key(key, False)

    def char_chord(self, ch: str) -> list[str] | None:
        if ch == "\n":
            return ["enter"]
        if ch == "\t":
            return ["tab"]
        # Latin-1-Keysyms entsprechen dem Codepoint, alles darüber ist ein Unicode-Keysym.
        sym = ord(ch) if ord(ch) <= 0xFF else 0x01000000 | ord(ch)
        with self._lock:
            code = self._d.keysym_to_keycode(sym)
            if not code:
                return None
            plain = self._d.keycode_to_keysym(code, 0)
            shifted = self._d.keycode_to_keysym(code, 1)
        name = self.keymap.to_name.get(code, f"{RAW_PREFIX}{code}")
        if plain == sym:
            return [name]
        if shifted == sym:
            return ["shift", name]
        return None  # AltGr-Ebenen (z. B. @ auf deutscher Tastatur) – nicht unterstützt

    def mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            xtest.fake_input(self._d, X.MotionNotify, x=x, y=y)
            self._d.sync()

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        with self._lock:
            xtest.fake_input(self._d, X.MotionNotify, detail=True, x=dx, y=dy)
            self._d.sync()

    def _button(self, button: str, down: bool) -> None:
        code = _BUTTONS[button]
        with self._lock:
            self._tracker.sent("b", code, down)
            xtest.fake_input(self._d, X.ButtonPress if down else X.ButtonRelease, code)
            self._d.sync()

    def mouse_down(self, button: str) -> None:
        self._button(button, True)

    def mouse_up(self, button: str) -> None:
        self._button(button, False)

    def cursor_pos(self) -> tuple[int, int]:
        with self._lock:
            p = self._d.screen().root.query_pointer()
        return int(p.root_x), int(p.root_y)


# ======================================================================================
# Hook (XRecord)
# ======================================================================================
class X11Hook:
    """Hört Tastatur/Maus per XRecord mit. Kann nicht unterdrücken."""

    can_suppress = False

    RELEASE_DEBOUNCE_S = 0.03
    """X11-Autorepeat erzeugt Loslassen+Drücken-Paare mit identischem Zeitstempel. Loslassen
    wird kurz zurückgehalten und verworfen, wenn sofort ein Drücken derselben Taste folgt."""

    def __init__(self, tracker: InjectionTracker) -> None:
        self._tracker = tracker
        self._thread: threading.Thread | None = None
        self._ctrl: display.Display | None = None
        self._rec: display.Display | None = None
        self._ctx: Any = None
        self._callback: InputCallback | None = None
        self._mouse = False
        self._keymap: KeyMap | None = None
        self._pending_release: dict[int, tuple[int, threading.Timer]] = {}
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._error: str | None = None

    def start(self, callback: InputCallback, *, mouse: bool) -> None:
        self.stop()
        self._callback = callback
        self._mouse = mouse
        self._ctrl = _open_display()
        self._rec = _open_display()
        if not self._rec.has_extension("RECORD"):
            raise RuntimeError("X-Server ohne RECORD-Erweiterung – Hotkeys nicht möglich")
        self._keymap = KeyMap(self._ctrl)
        last = X.ButtonRelease if mouse else X.KeyRelease
        self._ctx = self._rec.record_create_context(
            0,
            [record.AllClients],
            [
                {
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.KeyPress, last),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="inputforge-xrecord", daemon=True)
        self._thread.start()
        self._ready.wait(1.0)
        if self._error:
            raise RuntimeError(self._error)

    def stop(self) -> None:
        if self._thread is None:
            return
        try:
            assert self._ctrl is not None
            self._ctrl.record_disable_context(self._ctx)
            self._ctrl.flush()
        except XError:
            log.debug("record_disable_context fehlgeschlagen", exc_info=True)
        self._thread.join(2.0)
        self._thread = None
        with self._lock:
            for _, timer in self._pending_release.values():
                timer.cancel()
            self._pending_release.clear()
        for d in (self._rec, self._ctrl):
            if d is not None:
                try:
                    d.close()
                except Exception:
                    log.debug("Display schließen fehlgeschlagen", exc_info=True)
        self._rec = self._ctrl = None

    def _run(self) -> None:
        assert self._rec is not None
        try:
            self._ready.set()
            self._rec.record_enable_context(self._ctx, self._on_reply)
            self._rec.record_free_context(self._ctx)
        except Exception as exc:
            self._error = f"XRecord fehlgeschlagen: {exc}"
            log.exception("XRecord-Thread beendet")
            self._ready.set()

    def _dispatch(self, ev: InputEvent) -> None:
        cb = self._callback
        if cb is None:
            return
        try:
            cb(ev)
        except Exception:
            log.exception("Fehler im Hook-Callback")

    def _on_reply(self, reply: Any) -> None:
        if reply.category != record.FromServer or reply.client_swapped or not reply.data:
            return
        data = reply.data
        assert self._rec is not None
        while data:
            ev, data = rq.EventField(None).parse_binary_value(data, self._rec.display, None, None)
            self._handle(ev)

    def _handle(self, ev: Any) -> None:
        t, code = ev.type, ev.detail
        if t in (X.KeyPress, X.KeyRelease):
            down = t == X.KeyPress
            if self._tracker.is_echo("k", code, down):
                return
            assert self._keymap is not None
            name = self._keymap.to_name.get(code)
            if name is None:
                return
            if down:
                with self._lock:
                    pending = self._pending_release.pop(code, None)
                if pending is not None:
                    pending[1].cancel()
                    if pending[0] == ev.time:
                        return  # Autorepeat: Loslassen + Drücken verwerfen
                    self._dispatch(InputEvent(name, False))
                self._dispatch(InputEvent(name, True))
            else:
                timer = threading.Timer(self.RELEASE_DEBOUNCE_S, self._flush_release, (code, name))
                timer.daemon = True
                with self._lock:
                    old = self._pending_release.pop(code, None)
                    self._pending_release[code] = (ev.time, timer)
                if old is not None:
                    old[1].cancel()
                timer.start()
        elif t in (X.ButtonPress, X.ButtonRelease) and self._mouse:
            down = t == X.ButtonPress
            if self._tracker.is_echo("b", code, down):
                return
            name = _BUTTON_TRIGGERS.get(code)
            if name is None or (name.startswith("wheel") and not down):
                return
            self._dispatch(InputEvent(name, down))

    def _flush_release(self, code: int, name: str) -> None:
        with self._lock:
            if code not in self._pending_release:
                return
            del self._pending_release[code]
        self._dispatch(InputEvent(name, False))


# ======================================================================================
# Fenster (EWMH)
# ======================================================================================
class X11WindowManager:
    def __init__(self, disp: display.Display | None = None) -> None:
        self._d = disp or _open_display()
        self._lock = threading.Lock()
        self._root = self._d.screen().root
        a = self._d.intern_atom
        self._net_client_list = a("_NET_CLIENT_LIST")
        self._net_active = a("_NET_ACTIVE_WINDOW")
        self._net_wm_name = a("_NET_WM_NAME")
        self._utf8 = a("UTF8_STRING")

    def _title(self, win: Any) -> str:
        try:
            prop = win.get_full_property(self._net_wm_name, self._utf8)
            if prop is not None and prop.value:
                v = prop.value
                return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
            name = win.get_wm_name()
            if isinstance(name, bytes):
                return name.decode("latin-1", "replace")
            return name or ""
        except XError:
            return ""

    def _clients(self) -> list[int]:
        prop = self._root.get_full_property(self._net_client_list, X.AnyPropertyType)
        return list(prop.value) if prop is not None else []

    def _active(self) -> int | None:
        prop = self._root.get_full_property(self._net_active, X.AnyPropertyType)
        if prop is None or not prop.value or not prop.value[0]:
            return None
        return int(prop.value[0])

    def find(self, title: str) -> int | None:
        if not title:
            return None
        needle = title.lower()
        with self._lock:
            active = self._active()
            if (
                active
                and needle in self._title(self._d.create_resource_object("window", active)).lower()
            ):
                return active
            for wid in self._clients():
                if needle in self._title(self._d.create_resource_object("window", wid)).lower():
                    return wid
        return None

    def client_rect(self, handle: int) -> Rect | None:
        with self._lock:
            try:
                win = self._d.create_resource_object("window", handle)
                geo = win.get_geometry()
                pos = win.translate_coords(self._root, 0, 0)
            except XError:
                return None
        # translate_coords(root, 0, 0) liefert die Position des Roots relativ zum Fenster.
        return Rect(-int(pos.x), -int(pos.y), int(geo.width), int(geo.height))

    def activate(self, handle: int) -> bool:
        with self._lock:
            try:
                win = self._d.create_resource_object("window", handle)
                ev = xevent.ClientMessage(
                    window=win,
                    client_type=self._net_active,
                    data=(32, [2, X.CurrentTime, 0, 0, 0]),  # 2 = Pager → kein Fokus-Schutz
                )
                self._root.send_event(
                    ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask
                )
                self._d.sync()
            except XError:
                return False
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            with self._lock:
                if self._active() == handle:
                    return True
            time.sleep(0.01)
        return False

    def foreground_title(self) -> str:
        with self._lock:
            active = self._active()
            if not active:
                return ""
            return self._title(self._d.create_resource_object("window", active))

    def list_titles(self) -> list[str]:
        with self._lock:
            titles = {
                self._title(self._d.create_resource_object("window", w)) for w in self._clients()
            }
        return sorted((t for t in titles if t), key=str.lower)
