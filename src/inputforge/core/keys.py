"""Kanonische Tastennamen, Windows-Virtual-Key-Codes und Hotkey-Parser.

Dieses Modul ist plattformunabhängig und hat keine Abhängigkeiten, damit Konfiguration
und Tests überall laufen.

Hotkey-Syntax:  ``[modifier+]...taste``   z. B. ``f1``, ``ctrl+shift+a``, ``alt+xbutton1``
Chord-Syntax :  ``taste[+taste]...``      z. B. ``1``, ``ctrl+c``, ``1+2+3`` (gleichzeitig)
"""

from __future__ import annotations

import string
from dataclasses import dataclass

MODIFIERS: frozenset[str] = frozenset({"ctrl", "shift", "alt", "win"})

# Seitenspezifische Modifier → generischer Modifier
MODIFIER_OF: dict[str, str] = {
    "ctrl": "ctrl",
    "lctrl": "ctrl",
    "rctrl": "ctrl",
    "shift": "shift",
    "lshift": "shift",
    "rshift": "shift",
    "alt": "alt",
    "lalt": "alt",
    "ralt": "alt",
    "win": "win",
    "lwin": "win",
    "rwin": "win",
}

VK: dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "clear": 0x0C,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "lwin": 0x5B,
    "rwin": 0x5C,
    "win": 0x5B,
    "apps": 0x5D,
    "multiply": 0x6A,
    "add": 0x6B,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "lshift": 0xA0,
    "rshift": 0xA1,
    "lctrl": 0xA2,
    "rctrl": 0xA3,
    "lalt": 0xA4,
    "ralt": 0xA5,
    "volumemute": 0xAD,
    "volumedown": 0xAE,
    "volumeup": 0xAF,
    "medianext": 0xB0,
    "mediaprev": 0xB1,
    "mediastop": 0xB2,
    "mediaplay": 0xB3,
    "semicolon": 0xBA,
    "plus": 0xBB,
    "comma": 0xBC,
    "minus": 0xBD,
    "period": 0xBE,
    "slash": 0xBF,
    "backtick": 0xC0,
    "lbracket": 0xDB,
    "backslash": 0xDC,
    "rbracket": 0xDD,
    "quote": 0xDE,
    "oem102": 0xE2,  # <>|-Taste auf deutschen Tastaturen
}
VK.update({str(d): 0x30 + d for d in range(10)})
VK.update({c: ord(c.upper()) for c in string.ascii_lowercase})
VK.update({f"numpad{d}": 0x60 + d for d in range(10)})
VK.update({f"f{n}": 0x6F + n for n in range(1, 25)})

# Tasten, die mit KEYEVENTF_EXTENDEDKEY gesendet werden müssen
EXTENDED: frozenset[str] = frozenset(
    {
        "rctrl",
        "ralt",
        "insert",
        "delete",
        "home",
        "end",
        "pageup",
        "pagedown",
        "left",
        "up",
        "right",
        "down",
        "numlock",
        "divide",
        "printscreen",
        "lwin",
        "rwin",
        "win",
        "apps",
    }
)

MOUSE_TRIGGERS: frozenset[str] = frozenset(
    {"lbutton", "rbutton", "mbutton", "xbutton1", "xbutton2", "wheelup", "wheeldown"}
)

ALIASES: dict[str, str] = {
    "escape": "esc",
    "return": "enter",
    "control": "ctrl",
    "strg": "ctrl",
    "lcontrol": "lctrl",
    "rcontrol": "rctrl",
    "altgr": "ralt",
    "del": "delete",
    "entf": "delete",
    "ins": "insert",
    "einfg": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "bs": "backspace",
    "windows": "win",
    "super": "win",
    "menu": "apps",
    "break": "pause",
    "prtsc": "printscreen",
    "mouse4": "xbutton1",
    "mouse5": "xbutton2",
    "middle": "mbutton",
    "num0": "numpad0",
    "num1": "numpad1",
    "num2": "numpad2",
    "num3": "numpad3",
    "num4": "numpad4",
    "num5": "numpad5",
    "num6": "numpad6",
    "num7": "numpad7",
    "num8": "numpad8",
    "num9": "numpad9",
}

VK_TO_NAME: dict[int, str] = {}
for _name, _vk in VK.items():
    # Generische Modifier-VKs und "win" nicht als Rückabbildung verwenden – der
    # Low-Level-Hook liefert immer die seitenspezifischen Codes.
    if _name in {"shift", "ctrl", "alt", "win"}:
        continue
    VK_TO_NAME.setdefault(_vk, _name)


class KeyParseError(ValueError):
    pass


def normalize_key(name: str) -> str:
    n = name.strip().lower()
    n = ALIASES.get(n, n)
    if n not in VK and n not in MOUSE_TRIGGERS:
        raise KeyParseError(f"Unbekannte Taste: '{name}'")
    return n


def is_mouse(name: str) -> bool:
    return name in MOUSE_TRIGGERS


@dataclass(frozen=True, slots=True)
class Hotkey:
    key: str
    modifiers: frozenset[str] = frozenset()

    def __str__(self) -> str:
        order = ["ctrl", "alt", "shift", "win"]
        return "+".join([m for m in order if m in self.modifiers] + [self.key])

    def matches(self, key: str, held_modifiers: frozenset[str], wildcard: bool) -> bool:
        """``key`` ist der kanonische Name der gerade gedrückten Taste."""
        own_mod = MODIFIER_OF.get(key)
        if key != self.key and not (own_mod is not None and own_mod == self.key):
            return False
        # Die Trigger-Taste selbst zählt nicht als gehaltener Modifier.
        held = held_modifiers - {own_mod} if own_mod else held_modifiers
        if wildcard:
            return self.modifiers <= held
        return self.modifiers == held


def _split(text: str) -> list[str]:
    if not text.strip():
        raise KeyParseError("Leere Tastenangabe")
    parts = [s.strip() for s in text.split("+")]
    if not all(parts):
        raise KeyParseError(f"Ungültige Angabe '{text}' (für die Plus-Taste 'plus' schreiben)")
    return parts


def parse_hotkey(text: str) -> Hotkey:
    parts = [normalize_key(p) for p in _split(text)]
    *mods, key = parts
    norm_mods: set[str] = set()
    for m in mods:
        generic = MODIFIER_OF.get(m)
        if generic is None:
            raise KeyParseError(
                f"'{m}' ist kein Modifier – nur ctrl/shift/alt/win dürfen vor der Taste stehen"
            )
        norm_mods.add(generic)
    return Hotkey(key=key, modifiers=frozenset(norm_mods))


def parse_chord(text: str) -> list[str]:
    """Liste von Tastaturtasten, die nacheinander gedrückt und rückwärts losgelassen werden."""
    keys = [normalize_key(p) for p in _split(text)]
    for k in keys:
        if is_mouse(k):
            raise KeyParseError(f"Maustaste '{k}' ist in einer Tastenaktion nicht erlaubt")
    return keys


_SHIFTED_US = {
    ")": "0",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
}
_CHAR_KEYS = {" ": "space", "\n": "enter", "\t": "tab", "-": "minus", ",": "comma", ".": "period"}


def char_to_chord(ch: str) -> list[str] | None:
    """Plattformunabhängiger Fallback (US-Layout) – das Windows-Backend nutzt VkKeyScanW."""
    if ch in string.ascii_lowercase or ch in string.digits:
        return [ch]
    if ch in string.ascii_uppercase:
        return ["shift", ch.lower()]
    if ch in _CHAR_KEYS:
        return [_CHAR_KEYS[ch]]
    if ch in _SHIFTED_US:
        return ["shift", _SHIFTED_US[ch]]
    return None


def all_key_names() -> list[str]:
    return sorted(set(VK) | MOUSE_TRIGGERS)
