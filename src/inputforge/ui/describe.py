"""Menschenlesbare Beschreibungen für Aktionen/Enums (Qt-frei, testbar).

Die Label-Tabellen enthalten deutsche Quelltexte; an der Verwendungsstelle mit ``tr`` übersetzen.
"""

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
from inputforge.i18n import N_, tr

ACTION_LABELS: dict[str, str] = {
    "key": N_("Taste / Kombination"),
    "type_text": N_("Tastenfolge tippen"),
    "mouse_click": N_("Mausklick"),
    "mouse_move": N_("Maus bewegen"),
    "delay": N_("Warten"),
    "image_click": N_("Bild suchen & klicken"),
    "activate_window": N_("Fenster aktivieren"),
    "run_macro": N_("Anderes Makro ausführen"),
}

MODE_LABELS: dict[RunMode, str] = {
    RunMode.ONCE: N_("Einmal ausführen"),
    RunMode.TOGGLE: N_("Schleife – Toggle (an/aus)"),
    RunMode.HOLD: N_("Schleife – solange gehalten"),
    RunMode.REPEAT: N_("Schleife – N-mal / Dauer"),
}

BUTTON_LABELS: dict[MouseButton, str] = {
    MouseButton.LEFT: N_("Links"),
    MouseButton.RIGHT: N_("Rechts"),
    MouseButton.MIDDLE: N_("Mitte"),
    MouseButton.X1: N_("Maus 4 (Zurück)"),
    MouseButton.X2: N_("Maus 5 (Vor)"),
}

CLICK_LABELS: dict[MouseButton, str] = {
    MouseButton.LEFT: N_("Linksklick"),
    MouseButton.RIGHT: N_("Rechtsklick"),
    MouseButton.MIDDLE: N_("Mittelklick"),
    MouseButton.X1: N_("Maus-4-Klick"),
    MouseButton.X2: N_("Maus-5-Klick"),
}

SPACE_LABELS: dict[CoordSpace, str] = {
    CoordSpace.SCREEN: N_("Bildschirm (absolut)"),
    CoordSpace.WINDOW: N_("Zielfenster (relativ)"),
}

AREA_LABELS: dict[SearchArea, str] = {
    SearchArea.WINDOW: N_("Zielfenster"),
    SearchArea.SCREEN: N_("Ganzer Bildschirm"),
    SearchArea.REGION: N_("Bereich im Fenster"),
}

ANCHOR_LABELS: dict[Anchor, str] = {
    Anchor.CENTER: N_("Bildmitte"),
    Anchor.TOP_LEFT: N_("Obere linke Ecke"),
}

NOT_FOUND_LABELS: dict[NotFoundPolicy, str] = {
    NotFoundPolicy.CONTINUE: N_("Weiter mit nächstem Schritt"),
    NotFoundPolicy.STOP: N_("Makro abbrechen"),
}


def _space(space: CoordSpace) -> str:
    return tr("Fenster") if space == CoordSpace.WINDOW else tr("Bildschirm")


def describe(action: object, profile: Profile | None = None) -> str:
    match action:
        case KeyAction(keys=k, mode=mode, hold_ms=h):
            if mode == "tap":
                text = tr("Drücke {keys} ({ms} ms)", keys=k.upper(), ms=h)
            elif mode == "down":
                text = tr("Halte {keys}", keys=k.upper())
            else:
                text = tr("Lasse {keys} los", keys=k.upper())
        case TypeTextAction(text=t):
            text = tr('Tippe "{text}"', text=t)
        case MouseClickAction(button=b, x=x, y=y, space=s, clicks=c):
            where = (
                tr(" bei ({x}, {y}) [{space}]", x=x, y=y, space=_space(s))
                if x is not None
                else tr(" an Mausposition")
            )
            times = f" {c}×" if c > 1 else ""
            text = f"{tr(CLICK_LABELS[b])}{times}{where}"
        case MouseMoveAction(x=x, y=y, relative=True):
            text = tr("Maus um ({x}, {y}) bewegen", x=f"{x:+d}", y=f"{y:+d}")
        case MouseMoveAction(x=x, y=y, space=s):
            text = tr("Maus nach ({x}, {y}) [{space}]", x=x, y=y, space=_space(s))
        case DelayAction(ms=ms, random_ms=r):
            text = tr("Warte {ms} ms", ms=ms)
            if r:
                text += tr(" (+0–{ms} ms zufällig)", ms=r)
        case ImageClickAction(image=img, confidence=c, button=b, timeout_ms=t):
            act = tr(CLICK_LABELS[b]) if b is not None else tr("Maus hin")
            wait = tr(", warte bis {ms} ms", ms=t) if t else ""
            text = tr("Suche {image} (≥{conf}) → {action}", image=img, conf=f"{c:.2f}", action=act)
            text += wait
        case ActivateWindowAction(title=t):
            text = tr('Aktiviere Fenster "{title}"', title=t or tr("<Zielfenster>"))
        case RunMacroAction(macro_id=mid):
            target = profile.macro_by_id(mid) if profile else None
            text = tr("Führe Makro aus: {name}", name=target.name if target else mid)
        case _:
            text = repr(action)
    post = getattr(action, "post_delay_ms", 0)
    if post:
        text += f"  ⏱ {post} ms"
    comment = getattr(action, "comment", "")
    if comment:
        text += f"   // {comment}"
    return text
