"""Menschenlesbare Beschreibungen für Aktionen/Enums (Qt-frei, testbar)."""

from __future__ import annotations

from inputforge.config.models import (
    ActivateWindowAction,
    Anchor,
    CoordSpace,
    DelayAction,
    ImageClickAction,
    KeyAction,
    MouseButton,
    MouseClickAction,
    MouseMoveAction,
    NotFoundPolicy,
    Profile,
    RunMacroAction,
    RunMode,
    SearchArea,
    TypeTextAction,
)

ACTION_LABELS: dict[str, str] = {
    "key": "Taste / Kombination",
    "type_text": "Tastenfolge tippen",
    "mouse_click": "Mausklick",
    "mouse_move": "Maus bewegen",
    "delay": "Warten",
    "image_click": "Bild suchen & klicken",
    "activate_window": "Fenster aktivieren",
    "run_macro": "Anderes Makro ausführen",
}

MODE_LABELS: dict[RunMode, str] = {
    RunMode.ONCE: "Einmal ausführen",
    RunMode.TOGGLE: "Schleife – Toggle (an/aus)",
    RunMode.HOLD: "Schleife – solange gehalten",
    RunMode.REPEAT: "Schleife – N-mal / Dauer",
}

BUTTON_LABELS: dict[MouseButton, str] = {
    MouseButton.LEFT: "Links",
    MouseButton.RIGHT: "Rechts",
    MouseButton.MIDDLE: "Mitte",
    MouseButton.X1: "Maus 4 (Zurück)",
    MouseButton.X2: "Maus 5 (Vor)",
}

CLICK_LABELS: dict[MouseButton, str] = {
    MouseButton.LEFT: "Linksklick",
    MouseButton.RIGHT: "Rechtsklick",
    MouseButton.MIDDLE: "Mittelklick",
    MouseButton.X1: "Maus-4-Klick",
    MouseButton.X2: "Maus-5-Klick",
}

SPACE_LABELS: dict[CoordSpace, str] = {
    CoordSpace.SCREEN: "Bildschirm (absolut)",
    CoordSpace.WINDOW: "Zielfenster (relativ)",
}

AREA_LABELS: dict[SearchArea, str] = {
    SearchArea.WINDOW: "Zielfenster",
    SearchArea.SCREEN: "Ganzer Bildschirm",
    SearchArea.REGION: "Bereich im Fenster",
}

ANCHOR_LABELS: dict[Anchor, str] = {
    Anchor.CENTER: "Bildmitte",
    Anchor.TOP_LEFT: "Obere linke Ecke",
}

NOT_FOUND_LABELS: dict[NotFoundPolicy, str] = {
    NotFoundPolicy.CONTINUE: "Weiter mit nächstem Schritt",
    NotFoundPolicy.STOP: "Makro abbrechen",
}


def _space(space: CoordSpace) -> str:
    return "Fenster" if space == CoordSpace.WINDOW else "Bildschirm"


def describe(action: object, profile: Profile | None = None) -> str:
    match action:
        case KeyAction(keys=k, mode=mode, hold_ms=h):
            verb = {"tap": "Drücke", "down": "Halte", "up": "Lasse los"}[mode]
            extra = f" ({h} ms)" if mode == "tap" else ""
            text = f"{verb} {k.upper()}{extra}"
        case TypeTextAction(text=t):
            text = f'Tippe "{t}"'
        case MouseClickAction(button=b, x=x, y=y, space=s, clicks=c):
            where = f" bei ({x}, {y}) [{_space(s)}]" if x is not None else " an Mausposition"
            times = f" {c}×" if c > 1 else ""
            text = f"{CLICK_LABELS[b]}{times}{where}"
        case MouseMoveAction(x=x, y=y, relative=True):
            text = f"Maus um ({x:+d}, {y:+d}) bewegen"
        case MouseMoveAction(x=x, y=y, space=s):
            text = f"Maus nach ({x}, {y}) [{_space(s)}]"
        case DelayAction(ms=ms, random_ms=r):
            text = f"Warte {ms} ms" + (f" (+0–{r} ms zufällig)" if r else "")
        case ImageClickAction(image=img, confidence=c, button=b, timeout_ms=t):
            act = CLICK_LABELS[b] if b is not None else "Maus hin"
            wait = f", warte bis {t} ms" if t else ""
            text = f"Suche {img} (≥{c:.2f}) → {act}{wait}"
        case ActivateWindowAction(title=t):
            text = f'Aktiviere Fenster "{t or "<Zielfenster>"}"'
        case RunMacroAction(macro_id=mid):
            target = profile.macro_by_id(mid) if profile else None
            text = f"Führe Makro aus: {target.name if target else mid}"
        case _:
            text = repr(action)
    post = getattr(action, "post_delay_ms", 0)
    if post:
        text += f"  ⏱ {post} ms"
    comment = getattr(action, "comment", "")
    if comment:
        text += f"   // {comment}"
    return text
