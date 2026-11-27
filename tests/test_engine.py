import time

import cv2

from inputforge.config.models import (
    ActivateWindowAction,
    Anchor,
    CoordSpace,
    DelayAction,
    ImageClickAction,
    KeyAction,
    Macro,
    MouseButton,
    MouseClickAction,
    NotFoundPolicy,
    Profile,
    ProfileSettings,
    RunMacroAction,
    RunMode,
    SearchArea,
    TypeTextAction,
)
from inputforge.core.events import EventKind


def _profile(*macros: Macro, **settings) -> Profile:
    return Profile(macros=list(macros), settings=ProfileSettings(**settings))


def test_once_runs_steps_in_order_and_suppresses(harness):
    m = Macro(
        triggers=["f1"],
        steps=[
            KeyAction(keys="1", hold_ms=0),
            TypeTextAction(text="2", hold_ms=0, key_delay_ms=0),
            MouseClickAction(button=MouseButton.RIGHT, x=5, y=6, hold_ms=0),
        ],
    )
    harness.load(_profile(m))
    assert harness.hook.tap("f1") is True  # erreicht das Spiel nicht
    harness.wait_idle()
    assert harness.backend.snapshot() == [
        ("down", "1"),
        ("up", "1"),
        ("down", "2"),
        ("up", "2"),
        ("move", 5, 6),
        ("mdown", "right"),
        ("mup", "right"),
    ]


def test_passthrough_and_unbound_keys_not_suppressed(harness):
    m = Macro(triggers=["f1"], passthrough=True, steps=[])
    harness.load(_profile(m))
    assert harness.hook.tap("f1") is False
    assert harness.hook.tap("f5") is False


def test_once_ignores_retrigger_while_running(harness):
    m = Macro(triggers=["f1"], steps=[DelayAction(ms=150), KeyAction(keys="a", hold_ms=0)])
    harness.load(_profile(m))
    harness.hook.tap("f1")
    harness.hook.tap("f1")
    harness.wait_idle()
    assert harness.backend.count("down", "a") == 1


def test_autorepeat_does_not_retrigger(harness):
    m = Macro(triggers=["f1"], steps=[KeyAction(keys="a", hold_ms=0)])
    harness.load(_profile(m))
    harness.hook.press("f1")
    harness.wait_idle()
    assert harness.hook.press("f1") is True  # Repeat bleibt unterdrückt …
    assert harness.hook.release("f1") is True  # … ebenso das Loslassen
    harness.wait_idle()
    assert harness.backend.count("down", "a") == 1


def test_toggle_loop_start_stop(harness):
    m = Macro(
        triggers=["f3"], mode=RunMode.TOGGLE, interval_ms=10, steps=[KeyAction(keys="3", hold_ms=0)]
    )
    harness.load(_profile(m))
    harness.hook.tap("f3")
    harness.wait_for(lambda: harness.backend.count("down", "3") >= 3)
    harness.hook.tap("f3")
    harness.wait_idle()
    n = harness.backend.count("down", "3")
    time.sleep(0.05)
    assert harness.backend.count("down", "3") == n
    assert harness.backend.count("up", "3") == n  # nichts bleibt gedrückt


def test_hold_loop_stops_on_release(harness):
    m = Macro(
        triggers=["xbutton1"], mode=RunMode.HOLD, interval_ms=5, steps=[MouseClickAction(hold_ms=0)]
    )
    harness.load(_profile(m))
    assert harness.hook.mouse is True  # Maus-Hook nur bei Maus-Triggern
    harness.hook.press("xbutton1")
    harness.wait_for(lambda: harness.backend.count("mdown", "left") >= 2)
    harness.hook.release("xbutton1")
    harness.wait_idle()


def test_repeat_count_and_duration(harness):
    by_count = Macro(
        triggers=["f4"],
        mode=RunMode.REPEAT,
        repeat_count=4,
        interval_ms=1,
        steps=[KeyAction(keys="4", hold_ms=0)],
    )
    by_time = Macro(
        triggers=["f5"],
        mode=RunMode.REPEAT,
        duration_s=0.15,
        interval_ms=20,
        steps=[KeyAction(keys="5", hold_ms=0)],
    )
    harness.load(_profile(by_count, by_time))
    harness.hook.tap("f4")
    harness.wait_idle()
    assert harness.backend.count("down", "4") == 4
    start = time.monotonic()
    harness.hook.tap("f5")
    harness.wait_idle()
    elapsed = time.monotonic() - start
    assert 0.1 < elapsed < 0.6
    assert 3 <= harness.backend.count("down", "5") <= 10


def test_one_key_many_bindings_and_chords(harness):
    a = Macro(triggers=["f6"], steps=[KeyAction(keys="ctrl+1+2", hold_ms=0)])
    b = Macro(triggers=["f6"], steps=[KeyAction(keys="9", hold_ms=0)])
    harness.load(_profile(a, b))
    harness.hook.tap("f6")
    harness.wait_idle()
    calls = harness.backend.snapshot()
    chord = [c for c in calls if c[1] != "9"]
    assert chord == [
        ("down", "ctrl"),
        ("down", "1"),
        ("down", "2"),
        ("up", "2"),
        ("up", "1"),
        ("up", "ctrl"),
    ]
    assert ("down", "9") in calls


def test_modifier_matching(harness):
    exact = Macro(triggers=["ctrl+f1"], steps=[KeyAction(keys="a", hold_ms=0)])
    wild = Macro(triggers=["f2"], wildcard=True, steps=[KeyAction(keys="b", hold_ms=0)])
    harness.load(_profile(exact, wild))
    harness.hook.tap("f1")
    harness.hook.press("lshift")
    harness.hook.tap("f2")
    harness.hook.release("lshift")
    harness.hook.press("rctrl")
    harness.hook.tap("f1")
    harness.hook.release("rctrl")
    harness.wait_idle()
    assert harness.backend.count("down", "a") == 1
    assert harness.backend.count("down", "b") == 1


def test_global_stop_and_arm_toggle(harness):
    loop = Macro(
        triggers=["f3"], mode=RunMode.TOGGLE, interval_ms=5, steps=[KeyAction(keys="3", hold_ms=0)]
    )
    harness.load(_profile(loop, stop_all_hotkey="f12", arm_toggle_hotkey="pause"))
    harness.hook.tap("f3")
    harness.wait_for(lambda: harness.engine.running_ids() != set())
    assert harness.hook.tap("f12") is True
    harness.wait_idle()

    harness.hook.tap("pause")
    assert harness.engine.armed is False
    assert harness.hook.tap("f3") is False  # pausiert → durchlassen, nichts starten
    assert harness.engine.running_ids() == set()
    harness.hook.tap("pause")
    assert harness.engine.armed is True


def test_require_focus(harness):
    m = Macro(triggers=["f1"], steps=[KeyAction(keys="a", hold_ms=0)])
    harness.load(_profile(m, target_window="Grim Dawn", require_window_focus=True))
    harness.windows.foreground = "Browser"
    assert harness.hook.tap("f1") is False
    harness.windows.foreground = "Grim Dawn v1.2"
    assert harness.hook.tap("f1") is True
    harness.wait_idle()
    assert harness.backend.count("down", "a") == 1


def test_run_macro_nesting_and_recursion_guard(harness):
    inner = Macro(name="inner", steps=[KeyAction(keys="i", hold_ms=0)])
    outer = Macro(
        triggers=["f2"], steps=[KeyAction(keys="o", hold_ms=0), RunMacroAction(macro_id=inner.id)]
    )
    loop = Macro(id="loop", triggers=["f9"], steps=[RunMacroAction(macro_id="loop")])
    harness.load(_profile(inner, outer, loop))
    harness.hook.tap("f2")
    harness.wait_idle()
    assert [c[1] for c in harness.backend.snapshot() if c[0] == "down"] == ["o", "i"]
    harness.hook.tap("f9")
    harness.wait_idle()
    stopped = [e for e in harness.events if e.kind is EventKind.MACRO_STOPPED]
    assert "Verschachtelung" in stopped[-1].message


def test_stop_releases_held_keys(harness):
    m = Macro(
        triggers=["f1"],
        mode=RunMode.TOGGLE,
        steps=[KeyAction(keys="w", mode="down"), DelayAction(ms=5000)],
    )
    harness.load(_profile(m))
    harness.hook.tap("f1")
    harness.wait_for(lambda: harness.backend.count("down", "w") == 1)
    harness.engine.stop_all()
    assert harness.backend.count("up", "w") == 1


def test_window_relative_click_and_activation(harness):
    m = Macro(
        triggers=["f1"],
        steps=[
            ActivateWindowAction(wait_ms=0),
            MouseClickAction(x=10, y=20, space=CoordSpace.WINDOW, hold_ms=0),
        ],
    )
    harness.load(_profile(m, target_window="grim"))
    harness.hook.tap("f1")
    harness.wait_idle()
    assert harness.windows.activated == [0]
    assert ("move", 110, 70) in harness.backend.snapshot()  # Fenster bei (100, 50)


def _write_png(path, img):
    ok, buf = cv2.imencode(".png", img)
    assert ok
    path.write_bytes(buf.tobytes())


def test_image_click_in_window(harness, screen):
    (harness.base_dir / "assets").mkdir()
    _write_png(harness.base_dir / "assets" / "scroll.png", screen[200:230, 300:330])
    m = Macro(
        triggers=["f1"],
        steps=[
            ImageClickAction(
                image="assets/scroll.png",
                confidence=0.95,
                anchor=Anchor.TOP_LEFT,
                offset_x=5,
                offset_y=5,
                button=MouseButton.RIGHT,
                hold_ms=0,
            ),
        ],
    )
    harness.load(_profile(m, target_window="Grim Dawn"))
    harness.hook.tap("f1")
    harness.wait_idle()
    assert harness.grabber.grabs[-1] == harness.windows.windows["Grim Dawn"]
    assert harness.backend.snapshot() == [("move", 305, 205), ("mdown", "right"), ("mup", "right")]


def test_image_region_and_center(harness, screen):
    _write_png(harness.base_dir / "i.png", screen[200:230, 300:330])
    m = Macro(
        triggers=["f1"],
        steps=[
            ImageClickAction(
                image="i.png", area=SearchArea.REGION, region=(150, 100, 200, 200), button=None
            ),
        ],
    )
    harness.load(_profile(m, target_window="Grim Dawn"))
    harness.hook.tap("f1")
    harness.wait_idle()
    assert harness.backend.snapshot() == [("move", 315, 215)]


def test_image_not_found_policies(harness, screen):
    _write_png(harness.base_dir / "i.png", screen[0:20, 0:20])  # außerhalb des Fensters
    cont = Macro(
        triggers=["f1"], steps=[ImageClickAction(image="i.png"), KeyAction(keys="a", hold_ms=0)]
    )
    stop = Macro(
        triggers=["f2"],
        steps=[
            ImageClickAction(
                image="i.png", on_not_found=NotFoundPolicy.STOP, timeout_ms=60, retry_interval_ms=20
            ),
            KeyAction(keys="b", hold_ms=0),
        ],
    )
    missing = Macro(triggers=["f3"], steps=[ImageClickAction(image="nope.png")])
    harness.load(_profile(cont, stop, missing, target_window="Grim Dawn"))
    harness.hook.tap("f1")
    harness.wait_idle()
    harness.hook.tap("f2")
    harness.wait_idle()
    harness.hook.tap("f3")
    harness.wait_idle()
    assert harness.backend.count("down", "a") == 1
    assert harness.backend.count("down", "b") == 0
    nf = [e for e in harness.events if e.kind is EventKind.IMAGE_NOT_FOUND]
    assert len(nf) == 3 and all(e.notify for e in nf)
    assert len(harness.grabber.grabs) >= 1 + 2  # f2 hat wiederholt gesucht


def test_missing_target_window_aborts_window_click(harness):
    m = Macro(triggers=["f1"], steps=[MouseClickAction(x=1, y=1, space=CoordSpace.WINDOW)])
    harness.load(_profile(m, target_window="Not running"))
    harness.hook.tap("f1")
    harness.wait_idle()
    assert harness.backend.snapshot() == []
    assert "nicht gefunden" in harness.events[-1].message


def test_manual_trigger_and_reload_stops_runs(harness):
    m = Macro(
        triggers=[], mode=RunMode.TOGGLE, interval_ms=5, steps=[KeyAction(keys="x", hold_ms=0)]
    )
    p = _profile(m)
    harness.load(p)
    harness.engine.trigger(m.id)
    harness.wait_for(lambda: harness.backend.count("down", "x") >= 1)
    harness.engine.load(p, harness.base_dir)
    assert harness.engine.running_ids() == set()
