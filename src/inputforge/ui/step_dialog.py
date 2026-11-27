"""Dialog zum Anlegen/Bearbeiten eines einzelnen Makro-Schritts."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from inputforge.config.models import (
    ACTION_TYPES,
    CoordSpace,
    ImageClickAction,
    MouseButton,
    Profile,
    SearchArea,
)
from inputforge.i18n import N_, tr
from inputforge.platform.base import Platform, Rect
from inputforge.ui.describe import (
    ACTION_LABELS,
    ANCHOR_LABELS,
    AREA_LABELS,
    BUTTON_LABELS,
    NOT_FOUND_LABELS,
    SPACE_LABELS,
)
from inputforge.ui.picker import bgr_to_qimage, pick_from_screen
from inputforge.ui.widgets import HotkeyEdit, ms_spin
from inputforge.vision.matcher import find_template, load_template
from inputforge.vision.screen import ScreenGrabber


@dataclass
class EditorContext:
    profile: Profile
    profile_path: Path | None
    platform: Platform
    assets_fallback: Path
    pause_hotkeys: Callable[[bool], None]

    @property
    def base_dir(self) -> Path:
        return self.profile_path.parent if self.profile_path else self.assets_fallback.parent

    def assets_dir(self) -> Path:
        if self.profile_path:
            return self.profile_path.parent / "assets"
        return self.assets_fallback


def _combo(items: dict[Any, str], current: Any) -> QComboBox:
    c = QComboBox()
    for value, label in items.items():
        c.addItem(tr(label), value)
    idx = c.findData(current)
    c.setCurrentIndex(max(idx, 0))
    return c


def _spin(lo: int, hi: int, val: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    return s


class StepDialog(QDialog):
    def __init__(self, kind: str, action: Any | None, ctx: EditorContext, parent: QWidget | None):
        super().__init__(parent)
        self.kind = kind
        self.ctx = ctx
        self.model_cls = ACTION_TYPES[kind]
        self.action = action if action is not None else self._default()
        self.result_action: Any | None = None
        self._getters: dict[str, Callable[[], Any]] = {}

        self.setWindowTitle(tr("Schritt: {name}", name=tr(ACTION_LABELS[kind])))
        self.setMinimumWidth(520)
        root = QVBoxLayout(self)
        self.form = QFormLayout()
        root.addLayout(self.form)

        getattr(self, f"_build_{kind}")()

        common = QGroupBox(tr("Allgemein"))
        cf = QFormLayout(common)
        self.post_delay = ms_spin()
        self.post_delay.setValue(self.action.post_delay_ms)
        cf.addRow(tr("Warten danach"), self.post_delay)
        self.comment = QLineEdit(self.action.comment)
        cf.addRow(tr("Kommentar"), self.comment)
        root.addWidget(common)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _default(self) -> Any:
        defaults: dict[str, dict[str, Any]] = {
            "key": {"keys": "1"},
            "type_text": {"text": "12"},
            "mouse_move": {"x": 0, "y": 0},
            "delay": {"ms": 100},
            "image_click": {"image": "assets/icon.png"},
            "run_macro": {
                "macro_id": self.ctx.profile.macros[0].id if self.ctx.profile.macros else "?"
            },
        }
        return self.model_cls(**defaults.get(self.kind, {}))

    def _bind(self, name: str, getter: Callable[[], Any]) -> None:
        self._getters[name] = getter

    # ------------------------------------------------------------------ Typen
    def _build_key(self) -> None:
        a = self.action
        self.keys = HotkeyEdit(a.keys, chord=True)
        self.keys.recording_changed.connect(lambda on: self.ctx.pause_hotkeys(on))
        self.form.addRow(tr("Taste(n)"), self.keys)
        self.form.addRow("", QLabel(tr("Mehrere Tasten gleichzeitig mit + verbinden, z. B. 1+2+3")))
        mode = _combo(
            {
                "tap": N_("Drücken & loslassen"),
                "down": N_("Nur drücken (halten)"),
                "up": N_("Nur loslassen"),
            },
            a.mode,
        )
        self.form.addRow(tr("Art"), mode)
        hold = ms_spin(60_000)
        hold.setValue(a.hold_ms)
        self.form.addRow(tr("Haltedauer"), hold)
        self._bind("keys", self.keys.text)
        self._bind("mode", mode.currentData)
        self._bind("hold_ms", hold.value)

    def _build_type_text(self) -> None:
        a = self.action
        text = QLineEdit(a.text)
        self.form.addRow(tr("Text"), text)
        delay = ms_spin(10_000)
        delay.setValue(a.key_delay_ms)
        hold = ms_spin(10_000)
        hold.setValue(a.hold_ms)
        self.form.addRow(tr("Pause zwischen Tasten"), delay)
        self.form.addRow(tr("Haltedauer je Taste"), hold)
        self._bind("text", text.text)
        self._bind("key_delay_ms", delay.value)
        self._bind("hold_ms", hold.value)

    def _coords_row(self, x: int | None, y: int | None, space: CoordSpace, optional: bool) -> None:
        self.use_pos = QCheckBox(tr("An aktueller Mausposition"))
        self.pos_x = _spin(-100_000, 100_000, x or 0)
        self.pos_y = _spin(-100_000, 100_000, y or 0)
        self.space = _combo(SPACE_LABELS, space)
        pick = QPushButton(tr("Vom Bildschirm wählen…"))
        pick.clicked.connect(self._pick_point)
        row = QHBoxLayout()
        row.addWidget(QLabel("X"))
        row.addWidget(self.pos_x)
        row.addWidget(QLabel("Y"))
        row.addWidget(self.pos_y)
        row.addWidget(pick)
        w = QWidget()
        w.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        if optional:
            self.form.addRow("", self.use_pos)

            def _toggle(on: bool) -> None:
                w.setDisabled(on)
                self.space.setDisabled(on)

            self.use_pos.toggled.connect(_toggle)
            self.use_pos.setChecked(x is None)
        self.form.addRow(tr("Position"), w)
        self.form.addRow(tr("Koordinaten"), self.space)

    def _pick_point(self) -> None:
        res = pick_from_screen(
            self, self.ctx.platform.windows, self.ctx.profile.settings.target_window, mode="point"
        )
        if res is None:
            return
        if self.space.currentData() == CoordSpace.WINDOW:
            rel = res.relative_to_window()
            if rel is None:
                QMessageBox.warning(
                    self,
                    tr("Zielfenster"),
                    tr("Zielfenster nicht gefunden – nutze Bildschirmkoordinaten."),
                )
                self.space.setCurrentIndex(self.space.findData(CoordSpace.SCREEN))
                self.pos_x.setValue(res.rect.x)
                self.pos_y.setValue(res.rect.y)
                return
            self.pos_x.setValue(rel[0])
            self.pos_y.setValue(rel[1])
        else:
            self.pos_x.setValue(res.rect.x)
            self.pos_y.setValue(res.rect.y)

    def _build_mouse_click(self) -> None:
        a = self.action
        button = _combo(BUTTON_LABELS, a.button)
        self.form.addRow(tr("Taste"), button)
        self._coords_row(a.x, a.y, a.space, optional=True)
        clicks = _spin(1, 100, a.clicks)
        hold = ms_spin(60_000)
        hold.setValue(a.hold_ms)
        interval = ms_spin(10_000)
        interval.setValue(a.interval_ms)
        self.form.addRow(tr("Anzahl Klicks"), clicks)
        self.form.addRow(tr("Haltedauer"), hold)
        self.form.addRow(tr("Pause zwischen Klicks"), interval)
        self._bind("button", button.currentData)
        self._bind("x", lambda: None if self.use_pos.isChecked() else self.pos_x.value())
        self._bind("y", lambda: None if self.use_pos.isChecked() else self.pos_y.value())
        self._bind("space", self.space.currentData)
        self._bind("clicks", clicks.value)
        self._bind("hold_ms", hold.value)
        self._bind("interval_ms", interval.value)

    def _build_mouse_move(self) -> None:
        a = self.action
        self._coords_row(a.x, a.y, a.space, optional=False)
        relative = QCheckBox(
            tr("Relativ zur aktuellen Position (Raw-Bewegung, z. B. Kamera drehen)")
        )
        relative.setChecked(a.relative)
        self.form.addRow("", relative)
        self._bind("x", self.pos_x.value)
        self._bind("y", self.pos_y.value)
        self._bind("space", self.space.currentData)
        self._bind("relative", relative.isChecked)

    def _build_delay(self) -> None:
        a = self.action
        ms = ms_spin(3_600_000)
        ms.setValue(a.ms)
        rnd = ms_spin(60_000)
        rnd.setValue(a.random_ms)
        self.form.addRow(tr("Dauer"), ms)
        self.form.addRow(tr("+ zufällig bis"), rnd)
        self._bind("ms", ms.value)
        self._bind("random_ms", rnd.value)

    def _build_activate_window(self) -> None:
        a = self.action
        title = QComboBox()
        title.setEditable(True)
        title.addItems(["", *self.ctx.platform.windows.list_titles()])
        title.setCurrentText(a.title)
        title_edit = title.lineEdit()
        assert title_edit is not None
        title_edit.setPlaceholderText(tr("leer = Zielfenster des Profils"))
        wait = ms_spin(10_000)
        wait.setValue(a.wait_ms)
        self.form.addRow(tr("Fenstertitel enthält"), title)
        self.form.addRow(tr("Warten danach"), wait)
        self._bind("title", title.currentText)
        self._bind("wait_ms", wait.value)

    def _build_run_macro(self) -> None:
        a = self.action
        combo = QComboBox()
        for m in self.ctx.profile.macros:
            combo.addItem(m.name, m.id)
        combo.setCurrentIndex(max(combo.findData(a.macro_id), 0))
        self.form.addRow(tr("Makro"), combo)
        self.form.addRow(
            "", QLabel(tr("Die Schritte des Makros laufen einmal inline (ohne Schleife)."))
        )
        self._bind("macro_id", combo.currentData)

    def _build_image_click(self) -> None:
        a: ImageClickAction = self.action
        self.image = QLineEdit(a.image)
        browse = QPushButton("…")
        browse.clicked.connect(self._browse_image)
        capture = QPushButton(tr("Vom Bildschirm ausschneiden…"))
        capture.clicked.connect(self._capture_image)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.image, 1)
        row.addWidget(browse)
        rw = QWidget()
        rw.setLayout(row)
        self.form.addRow(tr("Bild"), rw)
        self.form.addRow("", capture)
        self.preview = QLabel()
        self.preview.setMinimumHeight(48)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.addRow(tr("Vorschau"), self.preview)
        self.image.textChanged.connect(self._update_preview)
        self._update_preview()

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.5, 1.0)
        self.confidence.setSingleStep(0.01)
        self.confidence.setDecimals(2)
        self.confidence.setValue(a.confidence)
        self.form.addRow(tr("Mindest-Übereinstimmung"), self.confidence)
        gray = QCheckBox(tr("Graustufen (robuster bei Farbeffekten, etwas ungenauer)"))
        gray.setChecked(a.grayscale)
        self.form.addRow("", gray)

        self.area = _combo(AREA_LABELS, a.area)
        self.form.addRow(tr("Suchbereich"), self.area)
        rx, ry, rw_, rh = a.region or (0, 0, 400, 300)
        self.rx, self.ry = _spin(-100_000, 100_000, rx), _spin(-100_000, 100_000, ry)
        self.rw, self.rh = _spin(1, 100_000, rw_), _spin(1, 100_000, rh)
        pick_region = QPushButton(tr("Wählen…"))
        pick_region.clicked.connect(self._pick_region)
        rrow = QHBoxLayout()
        rrow.setContentsMargins(0, 0, 0, 0)
        for label, w in (("X", self.rx), ("Y", self.ry), (tr("B"), self.rw), (tr("H"), self.rh)):
            rrow.addWidget(QLabel(label))
            rrow.addWidget(w)
        rrow.addWidget(pick_region)
        region_w = QWidget()
        region_w.setLayout(rrow)
        self.form.addRow(tr("Bereich"), region_w)
        self.area.currentIndexChanged.connect(
            lambda: region_w.setEnabled(self.area.currentData() == SearchArea.REGION)
        )
        region_w.setEnabled(a.area == SearchArea.REGION)

        buttons: dict[MouseButton | None, str] = {None: N_("Nicht klicken (nur Maus hinbewegen)")}
        for btn, label in BUTTON_LABELS.items():
            buttons[btn] = label
        button = _combo(buttons, a.button)
        self.form.addRow(tr("Klick"), button)
        anchor = _combo(ANCHOR_LABELS, a.anchor)
        self.form.addRow(tr("Klickpunkt"), anchor)
        ox, oy = _spin(-10_000, 10_000, a.offset_x), _spin(-10_000, 10_000, a.offset_y)
        orow = QHBoxLayout()
        orow.setContentsMargins(0, 0, 0, 0)
        orow.addWidget(QLabel("X"))
        orow.addWidget(ox)
        orow.addWidget(QLabel("Y"))
        orow.addWidget(oy)
        ow = QWidget()
        ow.setLayout(orow)
        self.form.addRow(tr("Versatz"), ow)
        hold = ms_spin(10_000)
        hold.setValue(a.hold_ms)
        self.form.addRow(tr("Klick-Haltedauer"), hold)

        timeout = ms_spin(600_000)
        timeout.setValue(a.timeout_ms)
        timeout.setSpecialValueText(tr("einmal suchen"))
        self.form.addRow(tr("Warten bis sichtbar"), timeout)
        retry = ms_spin(10_000, 10)
        retry.setValue(a.retry_interval_ms)
        self.form.addRow(tr("Suchintervall"), retry)
        not_found = _combo(NOT_FOUND_LABELS, a.on_not_found)
        self.form.addRow(tr("Wenn nicht gefunden"), not_found)
        notify = QCheckBox(tr("Einblendung „NICHT GEFUNDEN“ anzeigen"))
        notify.setChecked(a.notify_not_found)
        self.form.addRow("", notify)

        test = QPushButton(tr("Jetzt testen (3 s Verzögerung)"))
        test.clicked.connect(self._test_image)
        self.test_result = QLabel()
        self.form.addRow(test, self.test_result)

        self._bind("image", lambda: self.image.text().strip())
        self._bind("confidence", self.confidence.value)
        self._bind("grayscale", gray.isChecked)
        self._bind("area", self.area.currentData)
        self._bind(
            "region",
            lambda: (
                (self.rx.value(), self.ry.value(), self.rw.value(), self.rh.value())
                if self.area.currentData() == SearchArea.REGION
                else None
            ),
        )
        self._bind("button", button.currentData)
        self._bind("anchor", anchor.currentData)
        self._bind("offset_x", ox.value)
        self._bind("offset_y", oy.value)
        self._bind("hold_ms", hold.value)
        self._bind("timeout_ms", timeout.value)
        self._bind("retry_interval_ms", retry.value)
        self._bind("on_not_found", not_found.currentData)
        self._bind("notify_not_found", notify.isChecked)

    # ------------------------------------------------------------------ Bild-Helfer
    def _image_path(self) -> Path:
        p = Path(self.image.text().strip())
        return p if p.is_absolute() else self.ctx.base_dir / p

    def _update_preview(self) -> None:
        path = self._image_path()
        pm = QPixmap(str(path)) if path.is_file() else QPixmap()
        if pm.isNull():
            self.preview.setText(tr("<i>Bild nicht gefunden</i>"))
            return
        if pm.height() > 64:
            pm = pm.scaledToHeight(64, Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(pm)

    def _browse_image(self) -> None:
        start = str(self.ctx.assets_dir())
        file, _ = QFileDialog.getOpenFileName(
            self, tr("Bild wählen"), start, tr("Bilder (*.png *.bmp *.jpg)")
        )
        if file:
            self.image.setText(self._relativize(Path(file)))

    def _relativize(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.ctx.base_dir.resolve()).as_posix()
        except ValueError:
            return str(path)

    def _capture_image(self) -> None:
        res = pick_from_screen(
            self, self.ctx.platform.windows, self.ctx.profile.settings.target_window, mode="region"
        )
        if res is None:
            return
        assets = self.ctx.assets_dir()
        assets.mkdir(parents=True, exist_ok=True)
        default = assets / f"icon_{time.strftime('%Y%m%d_%H%M%S')}.png"
        file, _ = QFileDialog.getSaveFileName(
            self, tr("Vorlage speichern"), str(default), "PNG (*.png)"
        )
        if not file:
            return
        ok, buf = cv2.imencode(".png", res.crop)
        if not ok:
            QMessageBox.critical(self, tr("Fehler"), tr("PNG konnte nicht kodiert werden"))
            return
        Path(file).write_bytes(buf.tobytes())
        self.image.setText(self._relativize(Path(file)))

    def _pick_region(self) -> None:
        res = pick_from_screen(
            self, self.ctx.platform.windows, self.ctx.profile.settings.target_window, mode="region"
        )
        if res is None:
            return
        rel = res.relative_to_window()
        x, y = rel if rel is not None else (res.rect.x, res.rect.y)
        self.rx.setValue(x)
        self.ry.setValue(y)
        self.rw.setValue(res.rect.w)
        self.rh.setValue(res.rect.h)

    def _test_image(self) -> None:
        try:
            template = load_template(self._image_path())
        except (OSError, FileNotFoundError) as exc:
            self.test_result.setText(f"❌ {exc}")
            return
        res_holder: dict[str, Any] = {}

        def grab_after_countdown() -> None:
            from inputforge.ui.picker import _Countdown

            _Countdown(3).exec()
            rect: Rect | None = None
            wm = self.ctx.platform.windows
            title = self.ctx.profile.settings.target_window
            area = self.area.currentData()
            if area != SearchArea.SCREEN and title:
                h = wm.find(title)
                rect = wm.client_rect(h) if h is not None else None
                if area == SearchArea.REGION and rect is not None:
                    rect = Rect(
                        rect.x + self.rx.value(),
                        rect.y + self.ry.value(),
                        self.rw.value(),
                        self.rh.value(),
                    )
            shot, origin = ScreenGrabber().grab(rect)
            res_holder["shot"], res_holder["origin"] = shot, origin

        self.setWindowOpacity(0.0)
        try:
            grab_after_countdown()
        finally:
            self.setWindowOpacity(1.0)
        shot, origin = res_holder["shot"], res_holder["origin"]
        # Mit Schwelle 0 suchen, um den besten Score immer anzeigen zu können.
        best = find_template(shot, template, 0.0)
        if best is None:
            self.test_result.setText(tr("❌ Vorlage größer als Suchbereich"))
            return
        ok = best.score >= self.confidence.value()
        sx, sy = origin.x + best.center[0], origin.y + best.center[1]
        mark = tr("✅ Gefunden") if ok else tr("❌ Zu unsicher")
        self.test_result.setText(
            tr(
                "{mark}: Score {score} bei ({x}, {y})",
                mark=mark,
                score=f"{best.score:.3f}",
                x=sx,
                y=sy,
            )
        )
        if not ok:
            return
        thumb = shot[best.y : best.y + best.h, best.x : best.x + best.w]
        self.preview.setPixmap(QPixmap.fromImage(bgr_to_qimage(thumb)))

    # ------------------------------------------------------------------ OK
    def _accept(self) -> None:
        data = {name: getter() for name, getter in self._getters.items()}
        data.update(
            type=self.kind,
            id=self.action.id,
            enabled=self.action.enabled,
            comment=self.comment.text(),
            post_delay_ms=self.post_delay.value(),
        )
        try:
            self.result_action = self.model_cls.model_validate(data)
        except ValidationError as exc:
            msgs = "\n".join(f"• {'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            QMessageBox.warning(self, tr("Ungültige Eingabe"), msgs)
            return
        self.accept()


def edit_step(kind: str, action: Any | None, ctx: EditorContext, parent: QWidget | None) -> Any:
    dlg = StepDialog(kind, action, ctx, parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.result_action
    return None


__all__ = ["EditorContext", "StepDialog", "edit_step"]
