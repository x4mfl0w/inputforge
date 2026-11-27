"""Editor für ein einzelnes Makro: Trigger, Laufmodus, Schritte."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from inputforge.config.models import Macro, RunMode
from inputforge.i18n import tr
from inputforge.ui.describe import ACTION_LABELS, MODE_LABELS, describe
from inputforge.ui.step_dialog import EditorContext, edit_step
from inputforge.ui.widgets import HotkeyEdit, ms_spin


class _HotkeyDialog(QDialog):
    def __init__(self, ctx: EditorContext, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Trigger hinzufügen"))
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("Taste, Kombination oder Maustaste (Mitte/4/5/Rad) drücken:")))
        self.edit = HotkeyEdit()
        self.edit.recording_changed.connect(ctx.pause_hotkeys)
        lay.addWidget(self.edit)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        QTimer.singleShot(0, lambda: self.edit.button.setChecked(True))

    def _ok(self) -> None:
        if self.edit.is_valid():
            self.accept()
        else:
            QMessageBox.warning(self, tr("Ungültig"), tr("Unbekannte Taste oder Kombination."))


class MacroEditor(QWidget):
    changed = Signal()
    test_requested = Signal(str)

    def __init__(self, ctx_provider: Callable[[], EditorContext], parent: QWidget | None = None):
        super().__init__(parent)
        self._ctx = ctx_provider
        self.macro: Macro | None = None
        self._loading = False

        root = QVBoxLayout(self)

        # --- Grunddaten / Trigger --------------------------------------------------
        top = QGroupBox(tr("Makro"))
        f = QFormLayout(top)
        self.name = QLineEdit()
        f.addRow(tr("Name"), self.name)
        self.enabled = QCheckBox(tr("Aktiv"))
        f.addRow("", self.enabled)

        trig_row = QHBoxLayout()
        self.triggers = QListWidget()
        self.triggers.setMaximumHeight(70)
        trig_buttons = QVBoxLayout()
        self.add_trigger = QPushButton(tr("+ Trigger"))
        self.add_trigger.setToolTip(tr("Neuen Trigger (Hotkey) für dieses Makro hinzufügen"))
        self.del_trigger = QPushButton(tr("Entfernen"))
        trig_buttons.addWidget(self.add_trigger)
        trig_buttons.addWidget(self.del_trigger)
        trig_buttons.addStretch()
        trig_row.addWidget(self.triggers, 1)
        trig_row.addLayout(trig_buttons)
        f.addRow(tr("Trigger"), trig_row)
        self.passthrough = QCheckBox(tr("Trigger an das Spiel durchlassen"))
        self.wildcard = QCheckBox(
            tr("Auch mit zusätzlich gehaltenen Modifiern auslösen (Shift/Strg/…)")
        )
        f.addRow("", self.passthrough)
        f.addRow("", self.wildcard)
        root.addWidget(top)

        # --- Laufmodus -------------------------------------------------------------
        run = QGroupBox(tr("Ausführung"))
        rf = QFormLayout(run)
        self.mode = QComboBox()
        for mode, label in MODE_LABELS.items():
            self.mode.addItem(tr(label), mode)
        rf.addRow(tr("Modus"), self.mode)
        self.interval = ms_spin(3_600_000)
        rf.addRow(tr("Pause zwischen Durchläufen"), self.interval)
        self.repeat = QSpinBox()
        self.repeat.setRange(0, 1_000_000)
        self.repeat.setSpecialValueText(tr("unbegrenzt"))
        rf.addRow(tr("Max. Durchläufe"), self.repeat)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0, 86_400)
        self.duration.setDecimals(1)
        self.duration.setSuffix(" s")
        self.duration.setSpecialValueText(tr("unbegrenzt"))
        rf.addRow(tr("Max. Dauer"), self.duration)
        self.mode_hint = QLabel()
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setStyleSheet("color: #999")
        rf.addRow("", self.mode_hint)
        root.addWidget(run)

        # --- Schritte --------------------------------------------------------------
        steps = QGroupBox(tr("Schritte"))
        sl = QVBoxLayout(steps)
        self.steps = QListWidget()
        self.steps.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.steps.setAlternatingRowColors(True)
        sl.addWidget(self.steps, 1)
        bar = QHBoxLayout()
        self.add_step = QToolButton()
        self.add_step.setText(tr("+ Schritt"))
        self.add_step.setToolTip(tr("Neuen Schritt zu diesem Makro hinzufügen"))
        self.add_step.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        for kind, label in ACTION_LABELS.items():
            act = QAction(tr(label), menu)
            act.triggered.connect(lambda _=False, k=kind: self._add_step(k))
            menu.addAction(act)
        self.add_step.setMenu(menu)
        self.edit_step_btn = QPushButton(tr("Bearbeiten"))
        self.edit_step_btn.setToolTip(tr("Ausgewählten Schritt bearbeiten"))
        self.dup_step = QPushButton(tr("Duplizieren"))
        self.dup_step.setToolTip(tr("Ausgewählten Schritt duplizieren"))
        self.up_step = QPushButton("▲")
        self.down_step = QPushButton("▼")
        self.del_step = QPushButton(tr("Löschen"))
        self.del_step.setToolTip(tr("Ausgewählten Schritt löschen"))
        self.up_step.setToolTip(tr("Schritt nach oben"))
        self.down_step.setToolTip(tr("Schritt nach unten"))
        self.test_btn = QPushButton(tr("▶ Testen (3 s)"))
        for w in (
            self.add_step,
            self.edit_step_btn,
            self.dup_step,
            self.up_step,
            self.down_step,
            self.del_step,
        ):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.test_btn)
        sl.addLayout(bar)
        root.addWidget(steps, 1)

        # --- Signale ---------------------------------------------------------------
        self.name.textEdited.connect(lambda t: self._set("name", t or tr("Unbenannt")))
        self.enabled.toggled.connect(lambda v: self._set("enabled", v))
        self.passthrough.toggled.connect(lambda v: self._set("passthrough", v))
        self.wildcard.toggled.connect(lambda v: self._set("wildcard", v))
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.interval.valueChanged.connect(lambda v: self._set("interval_ms", v))
        self.repeat.valueChanged.connect(lambda v: self._set_loop("repeat_count", v))
        self.duration.valueChanged.connect(lambda v: self._set_loop("duration_s", float(v)))
        self.add_trigger.clicked.connect(self._add_trigger)
        self.del_trigger.clicked.connect(self._del_trigger)
        self.steps.itemDoubleClicked.connect(lambda _i: self._edit_step())
        self.steps.itemChanged.connect(self._step_check_changed)
        self.steps.model().rowsMoved.connect(self._steps_reordered)
        self.edit_step_btn.clicked.connect(self._edit_step)
        self.dup_step.clicked.connect(self._duplicate_step)
        self.up_step.clicked.connect(lambda: self._move_step(-1))
        self.down_step.clicked.connect(lambda: self._move_step(1))
        self.del_step.clicked.connect(self._delete_step)
        self.test_btn.clicked.connect(self._test)

        self.setEnabled(False)

    # ------------------------------------------------------------------ Laden
    def set_macro(self, macro: Macro | None) -> None:
        self.macro = macro
        self.setEnabled(macro is not None)
        if macro is None:
            return
        self._loading = True
        try:
            self.name.setText(macro.name)
            self.enabled.setChecked(macro.enabled)
            self.passthrough.setChecked(macro.passthrough)
            can_suppress = self._ctx().platform.hook.can_suppress
            self.passthrough.setEnabled(can_suppress)
            self.passthrough.setToolTip(
                ""
                if can_suppress
                else tr(
                    "Auf dieser Plattform nicht möglich – der Trigger erreicht das Spiel immer."
                )
            )
            self.wildcard.setChecked(macro.wildcard)
            self.mode.setCurrentIndex(self.mode.findData(macro.mode))
            self.interval.setValue(macro.interval_ms)
            self.repeat.setValue(macro.repeat_count)
            self.duration.setValue(macro.duration_s)
            self._refresh_triggers()
            self._refresh_steps()
            self._update_mode_ui()
        finally:
            self._loading = False

    def _refresh_triggers(self) -> None:
        assert self.macro is not None
        self.triggers.clear()
        for t in self.macro.triggers:
            self.triggers.addItem(t)
        if not self.macro.triggers:
            item = QListWidgetItem(tr("(kein Trigger – nur über „Anderes Makro ausführen“)"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.triggers.addItem(item)

    def _refresh_steps(self, select: int | None = None) -> None:
        assert self.macro is not None
        self._loading = True
        try:
            self.steps.clear()
            profile = self._ctx().profile
            for i, step in enumerate(self.macro.steps):
                item = QListWidgetItem(f"{i + 1:>2}. {describe(step, profile)}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if step.enabled else Qt.CheckState.Unchecked
                )
                item.setData(Qt.ItemDataRole.UserRole, step.id)
                self.steps.addItem(item)
            if select is not None and 0 <= select < self.steps.count():
                self.steps.setCurrentRow(select)
        finally:
            self._loading = False

    # ------------------------------------------------------------------ Setzen
    def _set(self, field: str, value: object) -> None:
        if self._loading or self.macro is None:
            return
        try:
            setattr(self.macro, field, value)
        except ValidationError as exc:
            QMessageBox.warning(self, tr("Ungültig"), str(exc.errors()[0]["msg"]))
            return
        self.changed.emit()

    def _set_loop(self, field: str, value: object) -> None:
        """repeat_count/duration_s: Bei Modus 'repeat' muss mindestens eines > 0 sein."""
        if self._loading or self.macro is None:
            return
        m = self.macro
        if m.mode == RunMode.REPEAT:
            other = m.duration_s if field == "repeat_count" else m.repeat_count
            if not value and not other:
                return  # ungültigen Zwischenzustand nicht übernehmen
        self._set(field, value)

    def _mode_changed(self) -> None:
        if self._loading or self.macro is None:
            return
        mode = self.mode.currentData()
        if mode == RunMode.REPEAT and not self.macro.repeat_count and not self.macro.duration_s:
            # Sinnvollen Startwert setzen, sonst wäre das Modell ungültig.
            self.macro.repeat_count = 10
            self._loading = True
            self.repeat.setValue(10)
            self._loading = False
        self._set("mode", mode)
        self._update_mode_ui()

    def _update_mode_ui(self) -> None:
        mode = self.mode.currentData()
        looping = mode != RunMode.ONCE
        for w in (self.interval, self.repeat, self.duration):
            w.setEnabled(looping)
        hints = {
            RunMode.ONCE: tr(
                "Trigger drücken → Schritte laufen einmal. Während des Laufs wird "
                "ein erneuter Druck ignoriert."
            ),
            RunMode.TOGGLE: tr(
                "1. Druck startet die Schleife, 2. Druck stoppt sie. Ideal für "
                "„alle X ms Taste drücken“ (Pause zwischen Durchläufen = Intervall)."
            ),
            RunMode.HOLD: tr("Schleife läuft, solange der Trigger gehalten wird."),
            RunMode.REPEAT: tr(
                "Ein Druck → bis zu „Max. Durchläufe“ bzw. „Max. Dauer“. Erneuter Druck bricht ab."
            ),
        }
        self.mode_hint.setText(hints[mode])

    # ------------------------------------------------------------------ Trigger
    def _add_trigger(self) -> None:
        assert self.macro is not None
        dlg = _HotkeyDialog(self._ctx(), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        t = dlg.edit.text()
        if t and t not in self.macro.triggers:
            self.macro.triggers = [*self.macro.triggers, t]
            self._refresh_triggers()
            self.changed.emit()

    def _del_trigger(self) -> None:
        assert self.macro is not None
        item = self.triggers.currentItem()
        if item and item.text() in self.macro.triggers:
            self.macro.triggers = [t for t in self.macro.triggers if t != item.text()]
            self._refresh_triggers()
            self.changed.emit()

    # ------------------------------------------------------------------ Schritte
    def _add_step(self, kind: str) -> None:
        assert self.macro is not None
        step = edit_step(kind, None, self._ctx(), self)
        if step is None:
            return
        row = self.steps.currentRow()
        idx = row + 1 if row >= 0 else len(self.macro.steps)
        self.macro.steps.insert(idx, step)
        self._refresh_steps(select=idx)
        self.changed.emit()

    def _edit_step(self) -> None:
        assert self.macro is not None
        row = self.steps.currentRow()
        if row < 0:
            return
        old = self.macro.steps[row]
        new = edit_step(old.type, old, self._ctx(), self)
        if new is None:
            return
        self.macro.steps[row] = new
        self._refresh_steps(select=row)
        self.changed.emit()

    def _duplicate_step(self) -> None:
        assert self.macro is not None
        row = self.steps.currentRow()
        if row < 0:
            return
        from inputforge.config.models import _new_id

        copy = self.macro.steps[row].model_copy(update={"id": _new_id()}, deep=True)
        self.macro.steps.insert(row + 1, copy)
        self._refresh_steps(select=row + 1)
        self.changed.emit()

    def _move_step(self, delta: int) -> None:
        assert self.macro is not None
        row = self.steps.currentRow()
        new = row + delta
        if row < 0 or not 0 <= new < len(self.macro.steps):
            return
        s = self.macro.steps
        s[row], s[new] = s[new], s[row]
        self._refresh_steps(select=new)
        self.changed.emit()

    def _delete_step(self) -> None:
        assert self.macro is not None
        row = self.steps.currentRow()
        if row < 0:
            return
        del self.macro.steps[row]
        self._refresh_steps(select=min(row, len(self.macro.steps) - 1))
        self.changed.emit()

    def _step_check_changed(self, item: QListWidgetItem) -> None:
        if self._loading or self.macro is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        for s in self.macro.steps:
            if s.id == sid:
                s.enabled = item.checkState() == Qt.CheckState.Checked
                self.changed.emit()
                return

    def _steps_reordered(self, *_args: object) -> None:
        if self._loading or self.macro is None:
            return
        by_id = {s.id: s for s in self.macro.steps}
        order = [
            self.steps.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.steps.count())
        ]
        self.macro.steps[:] = [by_id[i] for i in order if i in by_id]
        row = self.steps.currentRow()
        QTimer.singleShot(0, lambda: self._refresh_steps(select=row))
        self.changed.emit()

    def _test(self) -> None:
        if self.macro is not None:
            self.test_requested.emit(self.macro.id)
