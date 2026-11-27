"""Windows-Implementierung über ctypes – ohne Zusatzabhängigkeiten.

* Eingaben: ``SendInput`` mit **Scancodes** (``KEYEVENTF_SCANCODE``). Spiele, die DirectInput
  oder Raw Input lesen, ignorieren reine Virtual-Key-Events – Scancodes kommen an
  (gleiches Verfahren wie AHK ``SendInput``).
* Hotkeys: ``WH_KEYBOARD_LL`` / ``WH_MOUSE_LL`` Hooks in einem eigenen Thread mit
  Message-Loop. Gibt der Callback ``True`` zurück, wird das Ereignis geschluckt.
* Eigene Eingaben werden über ``dwExtraInfo == INJECT_MARKER`` erkannt und ignoriert.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes

from inputforge.core.keys import EXTENDED, VK, VK_TO_NAME
from inputforge.platform.base import INJECT_MARKER, InputCallback, InputEvent, Rect

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

# --- Konstanten -----------------------------------------------------------------------
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP = 0x0080, 0x0100
MOUSEEVENTF_VIRTUALDESK, MOUSEEVENTF_ABSOLUTE = 0x4000, 0x8000
MAPVK_VK_TO_VSC_EX = 4

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_QUIT = 0x0012
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208
WM_MOUSEWHEEL, WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020A, 0x020B, 0x020C
LLKHF_INJECTED, LLMHF_INJECTED = 0x10, 0x01

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
SW_RESTORE = 9


# --- Strukturen -----------------------------------------------------------------------
class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD))


class _INPUTUNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))


class INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("u", _INPUTUNION))


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# --- Signaturen (wichtig für 64 Bit) ---------------------------------------------------
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
user32.VkKeyScanW.restype = ctypes.c_short
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.GetMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
)
user32.PostThreadMessageW.argtypes = (
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.BringWindowToTop.argtypes = (wintypes.HWND,)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def is_admin() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except OSError:
        return False


def set_timer_resolution(ms: int = 1) -> None:
    """Standard-Timerauflösung unter Windows ist ~15,6 ms – für präzise Delays auf 1 ms setzen."""
    try:
        ctypes.WinDLL("winmm").timeBeginPeriod(ms)
    except OSError:
        log.debug("timeBeginPeriod nicht verfügbar")


def enable_dpi_awareness() -> None:
    """Physische Pixelkoordinaten verwenden (nur nötig ohne Qt – Qt6 setzt das selbst)."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            user32.SetProcessDPIAware()


# ======================================================================================
# Eingaben senden
# ======================================================================================
_MOUSE_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 0),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 0),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP, 0),
    "x1": (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, 1),
    "x2": (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, 2),
}

_VK_NAME_BY_CODE = {v: k for k, v in VK.items() if k not in {"shift", "ctrl", "alt", "win"}}


class Win32Backend:
    def __init__(self) -> None:
        self._scan_cache: dict[str, tuple[int, bool]] = {}

    # -- Tastatur --
    def _scan(self, key: str) -> tuple[int, bool]:
        cached = self._scan_cache.get(key)
        if cached is not None:
            return cached
        vk = VK[key]
        sc = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)
        extended = key in EXTENDED or (sc & 0xFF00) in (0xE000, 0xE100)
        result = (sc & 0xFF, extended)
        self._scan_cache[key] = result
        return result

    def _send_key(self, key: str, up: bool) -> None:
        scan, extended = self._scan(key)
        flags = KEYEVENTF_SCANCODE
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        if up:
            flags |= KEYEVENTF_KEYUP
        # wVk zusätzlich setzen: wird bei SCANCODE ignoriert, hilft aber Hooks/Tools beim Lesen.
        ki = KEYBDINPUT(wVk=VK[key], wScan=scan, dwFlags=flags, time=0, dwExtraInfo=INJECT_MARKER)
        _send(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=ki)))

    def key_down(self, key: str) -> None:
        self._send_key(key, up=False)

    def key_up(self, key: str) -> None:
        self._send_key(key, up=True)

    def char_chord(self, ch: str) -> list[str] | None:
        res = user32.VkKeyScanW(ch)
        if res == -1:
            return None
        vk, shift_state = res & 0xFF, (res >> 8) & 0xFF
        name = _VK_NAME_BY_CODE.get(vk)
        if name is None:
            return None
        chord: list[str] = []
        if shift_state & 1:
            chord.append("shift")
        if shift_state & 2:
            chord.append("ctrl")
        if shift_state & 4:
            chord.append("alt")
        chord.append(name)
        return chord

    # -- Maus --
    def mouse_move(self, x: int, y: int) -> None:
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = max(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) - 1, 1)
        vh = max(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) - 1, 1)
        nx = round((x - vx) * 65535 / vw)
        ny = round((y - vy) * 65535 / vh)
        mi = MOUSEINPUT(
            dx=nx,
            dy=ny,
            mouseData=0,
            dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
            time=0,
            dwExtraInfo=INJECT_MARKER,
        )
        _send(INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=mi)))
        # Normierung kann um 1px abweichen → exakt nachziehen.
        user32.SetCursorPos(x, y)

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        mi = MOUSEINPUT(
            dx=dx, dy=dy, mouseData=0, dwFlags=MOUSEEVENTF_MOVE, time=0, dwExtraInfo=INJECT_MARKER
        )
        _send(INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=mi)))

    def _mouse_button(self, button: str, up: bool) -> None:
        down_flag, up_flag, data = _MOUSE_FLAGS[button]
        mi = MOUSEINPUT(
            dx=0,
            dy=0,
            mouseData=data,
            dwFlags=up_flag if up else down_flag,
            time=0,
            dwExtraInfo=INJECT_MARKER,
        )
        _send(INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=mi)))

    def mouse_down(self, button: str) -> None:
        self._mouse_button(button, up=False)

    def mouse_up(self, button: str) -> None:
        self._mouse_button(button, up=True)

    def cursor_pos(self) -> tuple[int, int]:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y


def _send(inp: INPUT) -> None:
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        err = ctypes.get_last_error()
        # Typisch: UIPI blockiert, weil das Spiel mit Adminrechten läuft.
        log.warning("SendInput fehlgeschlagen (Fehler %s) – läuft das Spiel als Admin?", err)


# ======================================================================================
# Hooks
# ======================================================================================
_MOUSE_MSG = {
    WM_LBUTTONDOWN: ("lbutton", True),
    WM_LBUTTONUP: ("lbutton", False),
    WM_RBUTTONDOWN: ("rbutton", True),
    WM_RBUTTONUP: ("rbutton", False),
    WM_MBUTTONDOWN: ("mbutton", True),
    WM_MBUTTONUP: ("mbutton", False),
}


class Win32Hook:
    """Low-Level-Tastatur-/Maushook in eigenem Thread."""

    can_suppress = True

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int = 0
        self._callback: InputCallback | None = None
        self._ready = threading.Event()
        # Referenzen halten, sonst sammelt der GC die Callbacks ein → Absturz.
        self._kb_proc = HOOKPROC(self._kb_handler)
        self._ms_proc = HOOKPROC(self._ms_handler)

    def start(self, callback: InputCallback, *, mouse: bool) -> None:
        if self._thread is not None:
            self.stop()
        self._callback = callback
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, args=(mouse,), name="inputforge-hook", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(2.0):
            raise RuntimeError("Tastatur-Hook konnte nicht installiert werden")

    def stop(self) -> None:
        if self._thread is None:
            return
        user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(2.0)
        self._thread = None

    def _run(self, mouse: bool) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        hmod = kernel32.GetModuleHandleW(None)
        kb = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, hmod, 0)
        ms = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, hmod, 0) if mouse else None
        if not kb:
            log.error("SetWindowsHookExW fehlgeschlagen: %s", ctypes.get_last_error())
            return
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user32.UnhookWindowsHookEx(kb)
            if ms:
                user32.UnhookWindowsHookEx(ms)

    def _dispatch(self, event: InputEvent) -> bool:
        cb = self._callback
        if cb is None:
            return False
        try:
            return cb(event)
        except Exception:  # Hook darf niemals werfen
            log.exception("Fehler im Hook-Callback")
            return False

    def _kb_handler(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code == 0:
            data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if data.dwExtraInfo != INJECT_MARKER:
                name = VK_TO_NAME.get(data.vkCode)
                if name is not None:
                    down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    injected = bool(data.flags & LLKHF_INJECTED)
                    if self._dispatch(InputEvent(name, down, injected)):
                        return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _ms_handler(self, n_code: int, w_param: int, l_param: int) -> int:
        # WM_MOUSEMOVE (0x200) sofort durchreichen – kein Python-Overhead pro Mausbewegung.
        if n_code == 0 and w_param != 0x0200:
            data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            if data.dwExtraInfo != INJECT_MARKER:
                injected = bool(data.flags & LLMHF_INJECTED)
                hi = (data.mouseData >> 16) & 0xFFFF
                event: InputEvent | None = None
                if w_param in _MOUSE_MSG:
                    name, down = _MOUSE_MSG[w_param]
                    event = InputEvent(name, down, injected)
                elif w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                    name = "xbutton1" if hi == 1 else "xbutton2"
                    event = InputEvent(name, w_param == WM_XBUTTONDOWN, injected)
                elif w_param == WM_MOUSEWHEEL:
                    delta = hi - 0x10000 if hi & 0x8000 else hi
                    event = InputEvent("wheelup" if delta > 0 else "wheeldown", True, injected)
                if event is not None and self._dispatch(event):
                    return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)


# ======================================================================================
# Fenster
# ======================================================================================
def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


class Win32WindowManager:
    def _enum(self) -> list[tuple[int, str]]:
        result: list[tuple[int, str]] = []

        def cb(hwnd: int, _lp: int) -> bool:
            if user32.IsWindowVisible(hwnd):
                title = _window_text(hwnd)
                if title:
                    result.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return result

    def find(self, title: str) -> int | None:
        if not title:
            return None
        needle = title.lower()
        fg = user32.GetForegroundWindow()
        if fg and needle in _window_text(fg).lower():
            return int(fg)
        for hwnd, t in self._enum():
            if needle in t.lower():
                return int(hwnd)
        return None

    def client_rect(self, handle: int) -> Rect | None:
        if not user32.IsWindow(handle):
            return None
        rc = wintypes.RECT()
        if not user32.GetClientRect(handle, ctypes.byref(rc)):
            return None
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(handle, ctypes.byref(pt))
        return Rect(pt.x, pt.y, rc.right - rc.left, rc.bottom - rc.top)

    def activate(self, handle: int) -> bool:
        if user32.IsIconic(handle):
            user32.ShowWindow(handle, SW_RESTORE)
        if user32.GetForegroundWindow() == handle:
            return True
        # Windows erlaubt SetForegroundWindow nur eingeschränkt → Thread-Input koppeln.
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        own_thread = kernel32.GetCurrentThreadId()
        attached = bool(
            fg_thread
            and fg_thread != own_thread
            and user32.AttachThreadInput(own_thread, fg_thread, True)
        )
        try:
            user32.BringWindowToTop(handle)
            ok = bool(user32.SetForegroundWindow(handle))
        finally:
            if attached:
                user32.AttachThreadInput(own_thread, fg_thread, False)
        if not ok:
            # Fallback: ALT-Tap entsperrt SetForegroundWindow (bekannter Trick).
            backend = Win32Backend()
            backend.key_down("lalt")
            backend.key_up("lalt")
            ok = bool(user32.SetForegroundWindow(handle))
        return ok

    def foreground_title(self) -> str:
        fg = user32.GetForegroundWindow()
        return _window_text(fg) if fg else ""

    def list_titles(self) -> list[str]:
        return sorted({t for _, t in self._enum()}, key=str.lower)
