"""Windows-spezifische Tests (laufen in der Windows-CI). Senden keine echten Eingaben."""

import ctypes
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="nur Windows")


def test_struct_sizes_match_win32_abi():
    from inputforge.platform import win32

    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(win32.INPUT) == expected


def test_scancodes_and_layout_mapping():
    from inputforge.platform.win32 import Win32Backend

    b = Win32Backend()
    scan, ext = b._scan("a")
    assert scan != 0 and not ext
    assert b._scan("up")[1] is True  # Pfeiltasten sind Extended Keys
    assert b.char_chord("a") == ["a"]
    assert b.char_chord("A") == ["shift", "a"]


def test_window_manager_and_hook_lifecycle():
    from inputforge.platform.win32 import Win32Hook, Win32WindowManager, is_admin

    wm = Win32WindowManager()
    assert isinstance(wm.list_titles(), list)
    assert isinstance(wm.foreground_title(), str)
    assert wm.find("§§ gibt es nicht §§") is None
    assert isinstance(is_admin(), bool)

    hook = Win32Hook()
    hook.start(lambda _ev: False, mouse=True)
    hook.stop()


def test_create_platform_is_game_ready():
    from inputforge.platform import create_platform

    p = create_platform()
    assert p.game_ready and p.hook.can_suppress
