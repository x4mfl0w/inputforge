"""Wiederverwendbare Widgets: Hotkey-Eingabe, Toast, Log, App-Icon."""

from __future__ import annotations

import html
import logging
import sys

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from inputforge.core.events import EngineEvent
from inputforge.core.keys import VK_TO_NAME, KeyParseError, parse_chord, parse_hotkey


# --------------------------------------------------------------------------------------
# Icon
# --------------------------------------------------------------------------------------
def app_icon(active: bool = True) -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#2d7ff9") if active else QColor("#777777"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)
    p.setPen(QColor("white"))
    f = QFont()
    f.setBold(True)
    f.setPixelSize(30)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "IF")
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------------------
# Hotkey-Aufnahme
# --------------------------------------------------------------------------------------
def _kv(k: object) -> int:
    """Qt-Enum oder int → int (PySide6-Enums sind je nach Version Enum oder IntEnum)."""
    return int(getattr(k, "value", k))  # type: ignore[call-overload]


_QT_KEYS_RAW: dict[object, str] = {
    Qt.Key.Key_Escape: "esc",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Insert: "insert",
    Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Pause: "pause",
    Qt.Key.Key_Print: "printscreen",
    Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Down: "down",
    Qt.Key.Key_PageUp: "pageup",
    Qt.Key.Key_PageDown: "pagedown",
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_CapsLock: "capslock",
    Qt.Key.Key_NumLock: "numlock",
    Qt.Key.Key_ScrollLock: "scrolllock",
    Qt.Key.Key_Menu: "apps",
    Qt.Key.Key_Minus: "minus",
    Qt.Key.Key_Comma: "comma",
    Qt.Key.Key_Period: "period",
    Qt.Key.Key_Plus: "plus",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Alt: "alt",
    Qt.Key.Key_Meta: "win",
    Qt.Key.Key_AltGr: "ralt",
}
_QT_KEYS: dict[int, str] = {_kv(k): v for k, v in _QT_KEYS_RAW.items()}
for _i in range(1, 25):
    _QT_KEYS[_kv(Qt.Key.Key_F1) + _i - 1] = f"f{_i}"
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    _QT_KEYS[ord(_c)] = _c.lower()

_MODIFIER_QT = {
    _kv(k) for k in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta)
}


def key_name_from_event(ev: QKeyEvent) -> str | None:
    key = _kv(ev.key())
    if key in _MODIFIER_QT:
        return _QT_KEYS[key]
    if sys.platform == "win32":
        name = VK_TO_NAME.get(ev.nativeVirtualKey())
        if name:
            return name
    name = _QT_KEYS.get(key)
    if name and name.isdigit() and ev.modifiers() & Qt.KeyboardModifier.KeypadModifier:
        return f"numpad{name}"
    return name


def modifiers_from_event(ev: QKeyEvent | QMouseEvent | QWheelEvent) -> list[str]:
    m = ev.modifiers()
    out = []
    if m & Qt.KeyboardModifier.ControlModifier:
        out.append("ctrl")
    if m & Qt.KeyboardModifier.AltModifier:
        out.append("alt")
    if m & Qt.KeyboardModifier.ShiftModifier:
        out.append("shift")
    if m & Qt.KeyboardModifier.MetaModifier:
        out.append("win")
    return out


class _CaptureFilter(QObject):
    captured = Signal(str)
    cancelled = Signal()

    def __init__(self, allow_mouse: bool) -> None:
        super().__init__()
        self.allow_mouse = allow_mouse
        self._pending_modifier: str | None = None

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        t = ev.type()
        if t == QEvent.Type.KeyPress:
            assert isinstance(ev, QKeyEvent)
            if ev.isAutoRepeat():
                return True
            name = key_name_from_event(ev)
            if name is None:
                return True
            if _kv(ev.key()) in _MODIFIER_QT:
                self._pending_modifier = name
                return True
            if name == "esc" and not ev.modifiers():
                self.cancelled.emit()
                return True
            mods = modifiers_from_event(ev)
            self._pending_modifier = None
            self.captured.emit("+".join([*mods, name]))
            return True
        if t == QEvent.Type.KeyRelease:
            assert isinstance(ev, QKeyEvent)
            if self._pending_modifier and _kv(ev.key()) in _MODIFIER_QT:
                # Nur ein Modifier gedrückt und losgelassen → Modifier selbst ist der Hotkey.
                name, self._pending_modifier = self._pending_modifier, None
                self.captured.emit(name)
            return True
        if self.allow_mouse and t == QEvent.Type.MouseButtonPress:
            assert isinstance(ev, QMouseEvent)
            names = {
                Qt.MouseButton.MiddleButton: "mbutton",
                Qt.MouseButton.BackButton: "xbutton1",
                Qt.MouseButton.ForwardButton: "xbutton2",
            }
            name = names.get(ev.button())
            if name:
                self.captured.emit("+".join([*modifiers_from_event(ev), name]))
                return True
        if self.allow_mouse and t == QEvent.Type.Wheel:
            assert isinstance(ev, QWheelEvent)
            name = "wheelup" if ev.angleDelta().y() > 0 else "wheeldown"
            self.captured.emit("+".join([*modifiers_from_event(ev), name]))
            return True
        return False


class HotkeyEdit(QWidget):
    """Textfeld + „Aufnehmen“-Button. ``chord=True`` → Tastenkombination zum Senden."""

    changed = Signal(str)
    recording_changed = Signal(bool)

    def __init__(self, text: str = "", *, chord: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.chord = chord
        self.edit = QLineEdit(text)
        self.edit.setPlaceholderText(
            "z. B. ctrl+shift+1" if chord else "z. B. f1, ctrl+f2, xbutton1"
        )
        self.button = QPushButton("Aufnehmen")
        self.button.setCheckable(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.button)
        self._filter: _CaptureFilter | None = None
        self.button.toggled.connect(self._toggle_record)
        self.edit.textChanged.connect(self._on_text)

    def text(self) -> str:
        return self.edit.text().strip().lower()

    def setText(self, text: str) -> None:
        self.edit.setText(text)

    def is_valid(self) -> bool:
        t = self.text()
        if not t:
            return False
        try:
            (parse_chord if self.chord else parse_hotkey)(t)
        except KeyParseError:
            return False
        return True

    def _on_text(self, _t: str) -> None:
        ok = self.is_valid() or not self.text()
        self.edit.setStyleSheet("" if ok else "QLineEdit { background: #5a1e1e; color: white; }")
        if ok:
            self.changed.emit(self.text())

    def _toggle_record(self, on: bool) -> None:
        app = QApplication.instance()
        assert app is not None
        if on:
            self._filter = _CaptureFilter(allow_mouse=not self.chord)
            self._filter.captured.connect(self._on_captured)
            self._filter.cancelled.connect(lambda: self.button.setChecked(False))
            app.installEventFilter(self._filter)
            self.button.setText("Taste drücken… (Esc)")
            self.edit.setFocus()
        else:
            if self._filter is not None:
                app.removeEventFilter(self._filter)
                self._filter = None
            self.button.setText("Aufnehmen")
        self.recording_changed.emit(on)

    def _on_captured(self, text: str) -> None:
        self.edit.setText(text)
        self.button.setChecked(False)


# --------------------------------------------------------------------------------------
# Toast (nicht-fokussierende Einblendung, wie AHK-ToolTip)
# --------------------------------------------------------------------------------------
class Toast(QLabel):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "QLabel { background: rgba(20,20,20,220); color: #ffd166; padding: 8px 14px;"
            " border: 1px solid #ffd166; border-radius: 6px; font-size: 13px; }"
        )
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, ms: int = 1500) -> None:
        self.setText(text)
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(QPoint(geo.center().x() - self.width() // 2, geo.top() + 40))
        self.show()
        self.raise_()
        self._timer.start(ms)


# --------------------------------------------------------------------------------------
# Log
# --------------------------------------------------------------------------------------
_LEVEL_COLORS = {
    logging.DEBUG: "#8a8a8a",
    logging.INFO: "#d0d0d0",
    logging.WARNING: "#ffb347",
    logging.ERROR: "#ff6b6b",
}


class LogPanel(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(2000)
        self.setStyleSheet(
            "QPlainTextEdit { background: #151515; font-family: Consolas, monospace; }"
        )
        self.show_debug = False

    def add(self, event: EngineEvent) -> None:
        if event.level < logging.INFO and not self.show_debug:
            return
        from datetime import datetime

        color = _LEVEL_COLORS.get(event.level, "#d0d0d0")
        ts = datetime.now().strftime("%H:%M:%S")
        self.appendHtml(
            f'<span style="color:#666">{ts}</span> '
            f'<span style="color:{color}">{html.escape(event.message)}</span>'
        )


def ms_spin(maximum: int = 600_000, minimum: int = 0, suffix: str = " ms") -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimum, maximum)
    s.setSuffix(suffix)
    s.setSingleStep(10)
    s.setAccelerated(True)
    return s
