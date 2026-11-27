"""Datenmodell eines Profils (Makros, Trigger, Aktionen).

Profile werden als JSON gespeichert. Jede Aktion besitzt ein ``type``-Feld, über das
pydantic die passende Klasse auswählt (discriminated union).
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inputforge.core.keys import parse_chord, parse_hotkey
from inputforge.i18n import tr

SCHEMA_VERSION = 1


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class MouseButton(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"
    X1 = "x1"
    X2 = "x2"


class CoordSpace(StrEnum):
    SCREEN = "screen"
    """Absolute Bildschirmkoordinaten (virtueller Desktop, physische Pixel)."""
    WINDOW = "window"
    """Relativ zur linken oberen Ecke des Client-Bereichs des Zielfensters."""


class RunMode(StrEnum):
    ONCE = "once"
    """Ein Druck → Schritte laufen genau einmal."""
    TOGGLE = "toggle"
    """Erster Druck startet eine Schleife, zweiter Druck stoppt sie."""
    HOLD = "hold"
    """Schleife läuft, solange der Trigger gedrückt gehalten wird."""
    REPEAT = "repeat"
    """Ein Druck → N Wiederholungen und/oder für eine feste Dauer (erneuter Druck bricht ab)."""


class SearchArea(StrEnum):
    WINDOW = "window"
    SCREEN = "screen"
    REGION = "region"


class Anchor(StrEnum):
    CENTER = "center"
    TOP_LEFT = "top_left"


class NotFoundPolicy(StrEnum):
    CONTINUE = "continue"
    """Weiter mit dem nächsten Schritt (AHK-Verhalten des Originalskripts)."""
    STOP = "stop"
    """Aktuellen Makrodurchlauf abbrechen."""


# --------------------------------------------------------------------------------------
# Aktionen
# --------------------------------------------------------------------------------------


class _ActionBase(_Base):
    id: str = Field(default_factory=_new_id)
    enabled: bool = True
    comment: str = ""
    post_delay_ms: int = Field(default=0, ge=0, le=600_000)
    """Wartezeit nach Ausführung dieses Schritts."""


class KeyAction(_ActionBase):
    """Taste oder Tastenkombination senden, z. B. ``"1"``, ``"ctrl+shift+a"``."""

    type: Literal["key"] = "key"
    keys: str
    mode: Literal["tap", "down", "up"] = "tap"
    hold_ms: int = Field(default=30, ge=0, le=60_000)
    """Wie lange die Taste(n) beim ``tap`` gehalten werden. Viele Spiele pollen pro Frame –
    0 ms wird dann oft verschluckt. 20–50 ms sind ein guter Wert."""

    @field_validator("keys")
    @classmethod
    def _check_keys(cls, v: str) -> str:
        parse_chord(v)
        return v.strip().lower()


class TypeTextAction(_ActionBase):
    """Eine Folge einzelner Tasten tippen (wie ``SendInput, 12`` in AHK)."""

    type: Literal["type_text"] = "type_text"
    text: str = Field(min_length=1)
    key_delay_ms: int = Field(default=10, ge=0, le=10_000)
    hold_ms: int = Field(default=30, ge=0, le=10_000)


class MouseClickAction(_ActionBase):
    type: Literal["mouse_click"] = "mouse_click"
    button: MouseButton = MouseButton.LEFT
    x: int | None = None
    y: int | None = None
    """Ohne Koordinaten wird an der aktuellen Mausposition geklickt."""
    space: CoordSpace = CoordSpace.SCREEN
    clicks: int = Field(default=1, ge=1, le=100)
    hold_ms: int = Field(default=20, ge=0, le=60_000)
    interval_ms: int = Field(default=40, ge=0, le=10_000)

    @model_validator(mode="after")
    def _xy_pair(self) -> MouseClickAction:
        if (self.x is None) != (self.y is None):
            raise ValueError(tr("x und y müssen beide gesetzt oder beide leer sein"))
        return self


class MouseMoveAction(_ActionBase):
    type: Literal["mouse_move"] = "mouse_move"
    x: int
    y: int
    space: CoordSpace = CoordSpace.SCREEN
    relative: bool = False
    """``True``: x/y sind ein Versatz zur aktuellen Position (Raw-Bewegung, z. B. Kamera)."""


class DelayAction(_ActionBase):
    type: Literal["delay"] = "delay"
    ms: int = Field(ge=0, le=3_600_000)
    random_ms: int = Field(default=0, ge=0, le=60_000)
    """Zusätzliche zufällige Wartezeit 0..random_ms (Humanisierung)."""


class ImageClickAction(_ActionBase):
    """Bild auf dem Bildschirm suchen und (optional) anklicken – Pendant zu ``ImageSearch``."""

    type: Literal["image_click"] = "image_click"
    image: str = Field(min_length=1)
    """Pfad zur Vorlage (PNG). Relative Pfade gelten relativ zur Profildatei."""
    confidence: float = Field(default=0.90, ge=0.5, le=1.0)
    """Mindestähnlichkeit 0.5–1.0 (normierte Kreuzkorrelation)."""
    grayscale: bool = False
    area: SearchArea = SearchArea.WINDOW
    region: tuple[int, int, int, int] | None = None
    """(x, y, Breite, Höhe) – bei ``area=region``; relativ zum Fenster-Client-Bereich."""
    button: MouseButton | None = MouseButton.RIGHT
    """``None`` → nur Maus hinbewegen, nicht klicken."""
    anchor: Anchor = Anchor.CENTER
    offset_x: int = 0
    offset_y: int = 0
    timeout_ms: int = Field(default=0, ge=0, le=600_000)
    """0 = genau ein Suchversuch, sonst wird bis zum Timeout wiederholt gesucht."""
    retry_interval_ms: int = Field(default=100, ge=10, le=10_000)
    on_not_found: NotFoundPolicy = NotFoundPolicy.CONTINUE
    notify_not_found: bool = True
    hold_ms: int = Field(default=20, ge=0, le=10_000)

    @model_validator(mode="after")
    def _region_required(self) -> ImageClickAction:
        if self.area is SearchArea.REGION and self.region is None:
            raise ValueError(tr("area=region benötigt eine region (x, y, w, h)"))
        if self.region is not None and (self.region[2] <= 0 or self.region[3] <= 0):
            raise ValueError(tr("region muss positive Breite und Höhe haben"))
        return self


class ActivateWindowAction(_ActionBase):
    type: Literal["activate_window"] = "activate_window"
    title: str = ""
    """Teil des Fenstertitels. Leer → Zielfenster des Profils."""
    wait_ms: int = Field(default=50, ge=0, le=10_000)


class RunMacroAction(_ActionBase):
    """Ein anderes Makro inline ausführen (wie ``RunBuffs()`` im F2-Hotkey)."""

    type: Literal["run_macro"] = "run_macro"
    macro_id: str


Action = Annotated[
    KeyAction
    | TypeTextAction
    | MouseClickAction
    | MouseMoveAction
    | DelayAction
    | ImageClickAction
    | ActivateWindowAction
    | RunMacroAction,
    Field(discriminator="type"),
]

ACTION_TYPES: dict[str, type[_ActionBase]] = {
    "key": KeyAction,
    "type_text": TypeTextAction,
    "mouse_click": MouseClickAction,
    "mouse_move": MouseMoveAction,
    "delay": DelayAction,
    "image_click": ImageClickAction,
    "activate_window": ActivateWindowAction,
    "run_macro": RunMacroAction,
}


# --------------------------------------------------------------------------------------
# Makro & Profil
# --------------------------------------------------------------------------------------


class Macro(_Base):
    id: str = Field(default_factory=_new_id)
    name: str = "Neues Makro"
    enabled: bool = True
    triggers: list[str] = Field(default_factory=list)
    """Hotkeys, z. B. ``["f1"]``, ``["ctrl+f1", "xbutton1"]``. Leer → nur via run_macro nutzbar."""
    passthrough: bool = False
    """``False``: Trigger wird abgefangen und erreicht das Spiel nicht (AHK-Standard)."""
    wildcard: bool = False
    """``True``: feuert auch, wenn zusätzliche Modifier gedrückt sind (AHK ``*``)."""
    mode: RunMode = RunMode.ONCE
    interval_ms: int = Field(default=100, ge=0, le=3_600_000)
    """Pause zwischen zwei Schleifendurchläufen (toggle/hold/repeat)."""
    repeat_count: int = Field(default=0, ge=0, le=1_000_000)
    """Max. Durchläufe (0 = unbegrenzt). Für ``repeat`` muss count oder duration gesetzt sein."""
    duration_s: float = Field(default=0.0, ge=0.0, le=86_400.0)
    """Max. Laufzeit der Schleife in Sekunden (0 = unbegrenzt)."""
    steps: list[Action] = Field(default_factory=list)

    @field_validator("triggers")
    @classmethod
    def _check_triggers(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            parse_hotkey(t)
            norm = t.strip().lower()
            if norm not in out:
                out.append(norm)
        return out

    @model_validator(mode="after")
    def _repeat_bounds(self) -> Macro:
        if self.mode is RunMode.REPEAT and self.repeat_count == 0 and self.duration_s == 0:
            raise ValueError(tr("Modus 'repeat' benötigt repeat_count > 0 oder duration_s > 0"))
        return self


class ProfileSettings(_Base):
    target_window: str = ""
    """Optional: Teil des Fenstertitels des Spiels/Programms. Leer → kein Zielfenster."""
    require_window_focus: bool = False
    """Hotkeys nur auslösen, wenn das Zielfenster im Vordergrund ist (AHK ``#IfWinActive``)."""
    stop_all_hotkey: str = "ctrl+f12"
    """Notaus: stoppt alle laufenden Makros."""
    arm_toggle_hotkey: str = "ctrl+pause"
    """Schaltet die Hotkey-Erkennung global scharf/unscharf."""
    show_notifications: bool = True

    @field_validator("stop_all_hotkey", "arm_toggle_hotkey")
    @classmethod
    def _check_hotkey(cls, v: str) -> str:
        if v.strip():
            parse_hotkey(v)
        return v.strip().lower()


class Profile(_Base):
    schema_version: int = SCHEMA_VERSION
    name: str = "Neues Profil"
    settings: ProfileSettings = Field(default_factory=ProfileSettings)
    macros: list[Macro] = Field(default_factory=list)

    def macro_by_id(self, macro_id: str) -> Macro | None:
        return next((m for m in self.macros if m.id == macro_id), None)

    @model_validator(mode="after")
    def _check_references(self) -> Profile:
        ids = [m.id for m in self.macros]
        if len(ids) != len(set(ids)):
            raise ValueError(tr("Makro-IDs müssen eindeutig sein"))
        known = set(ids)
        for m in self.macros:
            for s in m.steps:
                if isinstance(s, RunMacroAction) and s.macro_id not in known:
                    raise ValueError(
                        tr(
                            "Makro '{name}' verweist auf unbekanntes Makro '{id}'",
                            name=m.name,
                            id=s.macro_id,
                        )
                    )
        return self
