"""X11-Backend.

* Unit-Tests (ohne X-Server): Echo-Filter, Autorepeat-Entprellung, Keymap.
* Integrationstests: nur mit ``INPUTFORGE_X11_TESTS=1`` auf einem *Wegwerf*-X-Server
  (CI: ``xvfb-run``). Sie senden echte Eingaben – niemals auf dem eigenen Desktop ausführen!
"""

import os
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="nur Linux")
x11 = pytest.importorskip("inputforge.platform.x11")

from Xlib import X  # noqa: E402

from inputforge.platform.base import InputEvent  # noqa: E402


def test_tracker_filters_echo_once_and_expires():
    t = x11.InjectionTracker(ttl=0.05)
    t.sent("k", 38, True)
    assert t.is_echo("k", 38, True)
    assert not t.is_echo("k", 38, True)  # nur einmal
    assert not t.is_echo("k", 38, False)
    t.sent("b", 1, True)
    time.sleep(0.08)
    assert not t.is_echo("b", 1, True)  # verfallen → echter Klick geht durch


class _FakeDisplay:
    def __init__(self, mapping):
        self.mapping = mapping

    def keysym_to_keycode(self, sym):
        return self.mapping.get(sym, 0)


def test_keymap_prefers_side_specific_names_and_raw_codes():
    from Xlib import XK

    disp = _FakeDisplay({XK.XK_Shift_L: 50, XK.XK_a: 38, XK.XK_F1: 67})
    km = x11.KeyMap(disp)
    assert km.code("a") == 38
    assert km.code("shift") == km.code("lshift") == 50
    assert km.to_name[50] == "lshift"
    assert km.code("kc:47") == 47
    with pytest.raises(ValueError):
        km.code("f2")


def _hook_with(events):
    hook = x11.X11Hook(x11.InjectionTracker())
    hook._keymap = SimpleNamespace(to_name={38: "a", 67: "f1"})
    hook._callback = lambda e: events.append(e) or False
    hook._mouse = True
    return hook


def _ev(t, code, time_ms):
    return SimpleNamespace(type=t, detail=code, time=time_ms)


def test_hook_debounces_x11_autorepeat():
    events: list[InputEvent] = []
    hook = _hook_with(events)
    hook._handle(_ev(X.KeyPress, 67, 100))
    # Autorepeat: Loslassen + Drücken mit identischem Zeitstempel
    hook._handle(_ev(X.KeyRelease, 67, 200))
    hook._handle(_ev(X.KeyPress, 67, 200))
    hook._handle(_ev(X.KeyRelease, 67, 300))
    time.sleep(hook.RELEASE_DEBOUNCE_S * 3)
    assert events == [InputEvent("f1", True), InputEvent("f1", False)]


def test_hook_fast_retap_is_two_presses():
    events: list[InputEvent] = []
    hook = _hook_with(events)
    hook._handle(_ev(X.KeyPress, 38, 100))
    hook._handle(_ev(X.KeyRelease, 38, 150))
    hook._handle(_ev(X.KeyPress, 38, 160))  # anderer Zeitstempel → echter neuer Druck
    hook._handle(_ev(X.KeyRelease, 38, 200))
    time.sleep(hook.RELEASE_DEBOUNCE_S * 3)
    assert [e.down for e in events] == [True, False, True, False]


def test_hook_ignores_own_echo_and_maps_buttons():
    events: list[InputEvent] = []
    hook = _hook_with(events)
    hook._tracker.sent("k", 38, True)
    hook._handle(_ev(X.KeyPress, 38, 1))
    hook._handle(_ev(X.ButtonPress, 8, 2))
    hook._handle(_ev(X.ButtonPress, 4, 3))
    hook._handle(_ev(X.ButtonRelease, 4, 4))  # Rad hat kein Loslassen
    assert events == [InputEvent("xbutton1", True), InputEvent("wheelup", True)]


# --------------------------------------------------------------------------------------
# Integration (nur auf Wegwerf-X-Server)
# --------------------------------------------------------------------------------------
integration = pytest.mark.skipif(
    os.environ.get("INPUTFORGE_X11_TESTS") != "1",
    reason="setzt INPUTFORGE_X11_TESTS=1 + xvfb-run voraus (sendet echte Eingaben)",
)


@integration
def test_send_receive_roundtrip():
    tracker = x11.InjectionTracker()
    backend = x11.X11Backend(tracker)
    hook = x11.X11Hook(tracker)
    events: list[InputEvent] = []
    hook.start(lambda e: events.append(e) or False, mouse=True)
    try:
        time.sleep(0.2)
        backend.key_down("a")
        backend.key_up("a")
        backend.mouse_down("left")
        backend.mouse_up("left")
        time.sleep(0.2)
        assert events == []  # eigene Eingaben lösen nichts aus

        subprocess.run(["xdotool", "key", "F1"], check=True)
        time.sleep(0.3)
        assert InputEvent("f1", True) in events and InputEvent("f1", False) in events
    finally:
        hook.stop()

    backend.mouse_move(123, 45)
    assert backend.cursor_pos() == (123, 45)
    backend.mouse_move_relative(10, 5)
    assert backend.cursor_pos() == (133, 50)


@integration
def test_window_manager_without_wm_is_empty_but_safe():
    wm = x11.X11WindowManager()
    assert isinstance(wm.list_titles(), list)
    assert wm.find("gibt es nicht") is None
    assert isinstance(wm.foreground_title(), str)
