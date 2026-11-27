"""Hauptfenster."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from inputforge import APP_NAME, __version__
from inputforge.config.models import Macro, Profile, RunMacroAction, _new_id
from inputforge.config.storage import (
    AppSettings,
    ProfileError,
    ProfileStore,
    load_profile,
    save_profile,
)
from inputforge.core.engine import Engine
from inputforge.core.events import EngineEvent, EventKind
from inputforge.platform.base import Platform
from inputforge.ui.describe import MODE_LABELS
from inputforge.ui.macro_editor import MacroEditor
from inputforge.ui.step_dialog import EditorContext
from inputforge.ui.widgets import HotkeyEdit, LogPanel, Toast, app_icon

log = logging.getLogger(__name__)


class EventBridge(QObject):
    """Leitet Engine-Events (beliebiger Thread) in den GUI-Thread."""

    received = Signal(object)


class SettingsPanel(QWidget):
    changed = Signal()

    def __init__(
        self,
        platform: Platform,
        pause_hotkeys: Callable[[bool], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.platform = platform
        self.profile: Profile | None = None
        self._loading = False
        f = QFormLayout(self)
        self.name = QComboBox()
        self.name.setEditable(True)
        f.addRow("Profilname", self.name)

        row = QHBoxLayout()
        self.window_combo = QComboBox()
        self.window_combo.setEditable(True)
        line = self.window_combo.lineEdit()
        assert line is not None
        line.setPlaceholderText("optional – Teil des Fenstertitels des Spiels")
        refresh = QPushButton("↻")
        refresh.setToolTip("Offene Fenster neu einlesen")
        refresh.clicked.connect(self._refresh_windows)
        row.addWidget(self.window_combo, 1)
        row.addWidget(refresh)
        f.addRow("Zielfenster", row)
        self.focus = QCheckBox("Hotkeys nur auslösen, wenn das Zielfenster aktiv ist")
        f.addRow("", self.focus)
        self.stop_key = HotkeyEdit()
        self.stop_key.recording_changed.connect(pause_hotkeys)
        f.addRow("Notaus (alle stoppen)", self.stop_key)
        self.arm_key = HotkeyEdit()
        self.arm_key.recording_changed.connect(pause_hotkeys)
        f.addRow("Hotkeys an/aus", self.arm_key)
        self.notify = QCheckBox("Einblendungen anzeigen (z. B. „NICHT GEFUNDEN“)")
        f.addRow("", self.notify)

        name_edit = self.name.lineEdit()
        assert name_edit is not None
        name_edit.textEdited.connect(self._apply)
        self.window_combo.currentTextChanged.connect(self._apply)
        self.focus.toggled.connect(self._apply)
        self.stop_key.changed.connect(self._apply)
        self.arm_key.changed.connect(self._apply)
        self.notify.toggled.connect(self._apply)

    def _refresh_windows(self) -> None:
        current = self.window_combo.currentText()
        was_loading, self._loading = self._loading, True
        try:
            self.window_combo.clear()
            self.window_combo.addItems(self.platform.windows.list_titles())
            self.window_combo.setCurrentText(current)
        finally:
            self._loading = was_loading

    def set_profile(self, profile: Profile) -> None:
        self.profile = profile
        self._loading = True
        s = profile.settings
        self.name.setCurrentText(profile.name)
        self._refresh_windows()
        self.window_combo.setCurrentText(s.target_window)
        self.focus.setChecked(s.require_window_focus)
        self.stop_key.setText(s.stop_all_hotkey)
        self.arm_key.setText(s.arm_toggle_hotkey)
        self.notify.setChecked(s.show_notifications)
        self._loading = False

    def _apply(self, *_args: object) -> None:
        if self._loading or self.profile is None:
            return
        p = self.profile
        p.name = self.name.currentText().strip() or "Profil"
        s = p.settings
        s.target_window = self.window_combo.currentText().strip()
        s.require_window_focus = self.focus.isChecked()
        if self.stop_key.is_valid() or not self.stop_key.text():
            s.stop_all_hotkey = self.stop_key.text()
        if self.arm_key.is_valid() or not self.arm_key.text():
            s.arm_toggle_hotkey = self.arm_key.text()
        s.show_notifications = self.notify.isChecked()
        self.changed.emit()


class MainWindow(QMainWindow):
    def __init__(self, platform: Platform, engine: Engine, store: ProfileStore) -> None:
        super().__init__()
        self.platform = platform
        self.engine = engine
        self.store = store
        self.app_settings: AppSettings = store.load_settings()
        self.profile = Profile()
        self.profile_path: Path | None = None
        self.dirty = False
        self._quitting = False
        self._paused_for_recording = False

        self.bridge = EventBridge()
        self.bridge.received.connect(self._on_event)
        engine.set_emit(self.bridge.received.emit)

        self.toast = Toast()
        self.setWindowIcon(app_icon())
        self.resize(1100, 760)

        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(400)
        self._apply_timer.timeout.connect(self._apply_to_engine)

        self._build_ui()
        self._build_tray()
        self._load_initial_profile()
        self.engine.start()
        self._update_status()

        if self.app_settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(self.app_settings.window_geometry.encode()))

    # ------------------------------------------------------------------ Aufbau
    def _build_ui(self) -> None:
        tb = QToolBar("Werkzeuge")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.act_new = QAction("Neu", self, shortcut=QKeySequence(QKeySequence.StandardKey.New))
        self.act_open = QAction(
            "Öffnen…", self, shortcut=QKeySequence(QKeySequence.StandardKey.Open)
        )
        self.act_save = QAction(
            "Speichern", self, shortcut=QKeySequence(QKeySequence.StandardKey.Save)
        )
        self.act_save_as = QAction(
            "Speichern unter…", self, shortcut=QKeySequence(QKeySequence.StandardKey.SaveAs)
        )
        self.act_armed = QAction("Hotkeys aktiv", self, checkable=True, checked=True)
        self.act_stop = QAction("■ Alle stoppen", self)
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_armed)
        tb.addAction(self.act_stop)
        self.act_new.triggered.connect(self._new_profile)
        self.act_open.triggered.connect(self._open_profile)
        self.act_save.triggered.connect(self._save)
        self.act_save_as.triggered.connect(self._save_as)
        self.act_armed.toggled.connect(self.engine.set_armed)
        self.act_stop.triggered.connect(self.engine.stop_all)

        menu = self.menuBar().addMenu("&Datei")
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            menu.addAction(a)
        self.recent_menu = menu.addMenu("Zuletzt geöffnet")
        menu.addSeparator()
        quit_act = menu.addAction("Beenden")
        quit_act.triggered.connect(self._quit)
        help_menu = self.menuBar().addMenu("&Hilfe")
        help_menu.addAction("Über", self._about)

        # Links: Makroliste
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("<b>Makros</b>"))
        self.macro_list = QListWidget()
        self.macro_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        ll.addWidget(self.macro_list, 1)
        btns = QHBoxLayout()
        self.btn_add = QPushButton("+ Neu")
        self.btn_dup = QPushButton("Duplizieren")
        self.btn_del = QPushButton("Löschen")
        for b in (self.btn_add, self.btn_dup, self.btn_del):
            btns.addWidget(b)
        ll.addLayout(btns)
        self.btn_add.clicked.connect(self._add_macro)
        self.btn_dup.clicked.connect(self._dup_macro)
        self.btn_del.clicked.connect(self._del_macro)
        self.macro_list.currentRowChanged.connect(self._select_macro)
        self.macro_list.itemChanged.connect(self._macro_check_changed)
        self.macro_list.model().rowsMoved.connect(self._macros_reordered)

        # Rechts: Tabs Makro / Profil
        self.editor = MacroEditor(self._editor_context)
        self.editor.changed.connect(self._on_editor_changed)
        self.editor.test_requested.connect(self._test_macro)
        self.settings_panel = SettingsPanel(self.platform, self._pause_hotkeys)
        self.settings_panel.changed.connect(self._mark_dirty)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.editor, "Makro")
        self.tabs.addTab(self.settings_panel, "Profil-Einstellungen")

        self.log_panel = LogPanel()
        debug_box = QCheckBox("Debug-Ausgaben")
        debug_box.toggled.connect(lambda v: setattr(self.log_panel, "show_debug", v))

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.tabs)
        log_w = QWidget()
        lw = QVBoxLayout(log_w)
        lw.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.addWidget(QLabel("<b>Protokoll</b>"))
        head.addStretch()
        head.addWidget(debug_box)
        lw.addLayout(head)
        lw.addWidget(self.log_panel)
        right.addWidget(log_w)
        right.setSizes([560, 180])

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([280, 820])
        self.setCentralWidget(split)

        self.status_platform = QLabel()
        self.status_armed = QLabel()
        self.statusBar().addWidget(self.status_platform)
        self.statusBar().addPermanentWidget(self.status_armed)

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        menu.addAction("Anzeigen", self._show_from_tray)
        menu.addAction(self.act_armed)
        menu.addAction(self.act_stop)
        menu.addSeparator()
        menu.addAction("Beenden", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: (
                self._show_from_tray()
                if reason == QSystemTrayIcon.ActivationReason.DoubleClick
                else None
            )
        )
        self.tray.show()

    # ------------------------------------------------------------------ Kontext
    def _editor_context(self) -> EditorContext:
        return EditorContext(
            profile=self.profile,
            profile_path=self.profile_path,
            platform=self.platform,
            assets_fallback=self.store.profiles_dir / "assets",
            pause_hotkeys=self._pause_hotkeys,
        )

    def _pause_hotkeys(self, paused: bool) -> None:
        """Während der Hotkey-Aufnahme dürfen bestehende Hotkeys nicht feuern."""
        if paused and self.engine.armed:
            self._paused_for_recording = True
            self.engine.set_armed(False)
        elif not paused and self._paused_for_recording:
            self._paused_for_recording = False
            self.engine.set_armed(True)

    # ------------------------------------------------------------------ Profile
    def _load_initial_profile(self) -> None:
        last = self.app_settings.last_profile
        if last and Path(last).is_file():
            try:
                self._set_profile(load_profile(Path(last)), Path(last))
                return
            except ProfileError as exc:
                self._log(f"Letztes Profil nicht ladbar: {exc}", logging.ERROR)
        default = self.store.default_profile_path()
        if default.is_file():
            try:
                self._set_profile(load_profile(default), default)
                return
            except ProfileError as exc:
                self._log(str(exc), logging.ERROR)
        self._set_profile(Profile(name="Standard"), None)

    def _set_profile(self, profile: Profile, path: Path | None) -> None:
        self.profile = profile
        self.profile_path = path
        self.dirty = False
        self.settings_panel.set_profile(profile)
        self._refresh_macro_list(select=0)
        self._apply_to_engine()
        if path:
            self.app_settings.remember(path)
            self.store.save_settings(self.app_settings)
        self._refresh_recent()
        self._update_title()

    def _maybe_save_changes(self) -> bool:
        if not self.dirty:
            return True
        res = QMessageBox.question(
            self,
            "Ungespeicherte Änderungen",
            "Änderungen am Profil speichern?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if res == QMessageBox.StandardButton.Cancel:
            return False
        if res == QMessageBox.StandardButton.Save:
            return self._save()
        return True

    def _new_profile(self) -> None:
        if self._maybe_save_changes():
            self._set_profile(Profile(), None)

    def _open_profile(self, path: str | None = None) -> None:
        if not self._maybe_save_changes():
            return
        if not path:
            self.store.ensure()
            path, _ = QFileDialog.getOpenFileName(
                self, "Profil öffnen", str(self.store.profiles_dir), "InputForge-Profil (*.json)"
            )
        if not path:
            return
        try:
            self._set_profile(load_profile(Path(path)), Path(path))
        except ProfileError as exc:
            QMessageBox.critical(self, "Profil laden", str(exc))

    def _save(self) -> bool:
        if self.profile_path is None:
            return self._save_as()
        try:
            save_profile(self.profile, self.profile_path)
        except ProfileError as exc:
            QMessageBox.critical(self, "Speichern", str(exc))
            return False
        self.dirty = False
        self._update_title()
        self._log(f"Gespeichert: {self.profile_path}")
        return True

    def _save_as(self) -> bool:
        self.store.ensure()
        suggestion = self.store.profiles_dir / f"{self.profile.name}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Profil speichern", str(suggestion), "InputForge-Profil (*.json)"
        )
        if not path:
            return False
        self.profile_path = Path(path)
        ok = self._save()
        if ok:
            self.app_settings.remember(self.profile_path)
            self.store.save_settings(self.app_settings)
            self._refresh_recent()
            self._apply_to_engine()  # Basisverzeichnis für relative Bildpfade
        return ok

    def _refresh_recent(self) -> None:
        self.recent_menu.clear()
        for p in self.app_settings.recent_profiles:
            act = self.recent_menu.addAction(p)
            act.triggered.connect(lambda _=False, path=p: self._open_profile(path))
        self.recent_menu.setEnabled(bool(self.app_settings.recent_profiles))

    # ------------------------------------------------------------------ Makros
    def _refresh_macro_list(self, select: int | None = None) -> None:
        self.macro_list.blockSignals(True)
        self.macro_list.clear()
        running = self.engine.running_ids()
        for m in self.profile.macros:
            item = QListWidgetItem(self._macro_label(m, m.id in running))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if m.enabled else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            if m.id in running:
                item.setForeground(QColor("#4cd964"))
            self.macro_list.addItem(item)
        self.macro_list.blockSignals(False)
        if select is not None and self.profile.macros:
            self.macro_list.setCurrentRow(min(select, len(self.profile.macros) - 1))
        else:
            self._select_macro(self.macro_list.currentRow())

    @staticmethod
    def _macro_label(m: Macro, running: bool) -> str:
        trig = ", ".join(t.upper() for t in m.triggers) or "—"
        mode = MODE_LABELS[m.mode].split(" (")[0]
        dot = "● " if running else ""
        return f"{dot}{m.name}   [{trig}]\n   {mode} · {len(m.steps)} Schritte"

    def _current_macro(self) -> Macro | None:
        row = self.macro_list.currentRow()
        return self.profile.macros[row] if 0 <= row < len(self.profile.macros) else None

    def _select_macro(self, row: int) -> None:
        macro = self.profile.macros[row] if 0 <= row < len(self.profile.macros) else None
        self.editor.set_macro(macro)
        if macro is not None:
            self.tabs.setCurrentWidget(self.editor)

    def _add_macro(self) -> None:
        self.profile.macros.append(Macro(name=f"Makro {len(self.profile.macros) + 1}"))
        self._refresh_macro_list(select=len(self.profile.macros) - 1)
        self._mark_dirty()

    def _dup_macro(self) -> None:
        m = self._current_macro()
        if m is None:
            return
        copy = m.model_copy(
            deep=True, update={"id": _new_id(), "name": f"{m.name} (Kopie)", "triggers": []}
        )
        idx = self.profile.macros.index(m) + 1
        self.profile.macros.insert(idx, copy)
        self._refresh_macro_list(select=idx)
        self._mark_dirty()

    def _del_macro(self) -> None:
        m = self._current_macro()
        if m is None:
            return
        users = [
            o.name
            for o in self.profile.macros
            if any(isinstance(s, RunMacroAction) and s.macro_id == m.id for s in o.steps)
        ]
        msg = f"Makro „{m.name}“ löschen?"
        if users:
            msg += (
                "\n\nAchtung: Wird verwendet von: "
                + ", ".join(users)
                + "\nDiese Schritte werden ebenfalls entfernt."
            )
        if QMessageBox.question(self, "Löschen", msg) != QMessageBox.StandardButton.Yes:
            return
        row = self.profile.macros.index(m)
        del self.profile.macros[row]
        for o in self.profile.macros:
            o.steps[:] = [
                s for s in o.steps if not (isinstance(s, RunMacroAction) and s.macro_id == m.id)
            ]
        self._refresh_macro_list(select=max(row - 1, 0))
        self._mark_dirty()

    def _macro_check_changed(self, item: QListWidgetItem) -> None:
        mid = item.data(Qt.ItemDataRole.UserRole)
        m = self.profile.macro_by_id(mid)
        if m is not None:
            m.enabled = item.checkState() == Qt.CheckState.Checked
            if self.editor.macro is m:
                self.editor.set_macro(m)
            self._mark_dirty()

    def _macros_reordered(self, *_args: object) -> None:
        by_id = {m.id: m for m in self.profile.macros}
        order = [
            self.macro_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.macro_list.count())
        ]
        self.profile.macros[:] = [by_id[i] for i in order if i in by_id]
        self._mark_dirty()

    def _on_editor_changed(self) -> None:
        row = self.macro_list.currentRow()
        m = self._current_macro()
        if m is not None and (item := self.macro_list.item(row)) is not None:
            self.macro_list.blockSignals(True)
            item.setText(self._macro_label(m, m.id in self.engine.running_ids()))
            item.setCheckState(Qt.CheckState.Checked if m.enabled else Qt.CheckState.Unchecked)
            self.macro_list.blockSignals(False)
        self._mark_dirty()

    def _test_macro(self, macro_id: str) -> None:
        self._log("Test startet in 3 s – jetzt ins Spiel wechseln …")
        self.toast.show_message("Test in 3 s …", 2500)
        self._apply_to_engine()
        QTimer.singleShot(3000, lambda: self.engine.trigger(macro_id))

    # ------------------------------------------------------------------ Engine
    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_title()
        self._apply_timer.start()

    def _apply_to_engine(self) -> None:
        base = self.profile_path.parent if self.profile_path else self.store.profiles_dir
        try:
            validated = Profile.model_validate(self.profile.model_dump())
        except ValueError as exc:
            self._log(f"Profil ungültig, nicht übernommen: {exc}", logging.ERROR)
            return
        self.engine.load(validated, base)

    def _on_event(self, ev: EngineEvent) -> None:
        self.log_panel.add(ev)
        if ev.notify:
            self.toast.show_message(ev.message)
        if ev.kind in (EventKind.MACRO_STARTED, EventKind.MACRO_STOPPED):
            # Kurz verzögert, damit _runs bereits aktualisiert ist.
            QTimer.singleShot(30, self._refresh_running)
        if ev.kind is EventKind.ARMED:
            self.act_armed.blockSignals(True)
            self.act_armed.setChecked(self.engine.armed)
            self.act_armed.blockSignals(False)
            if not self._paused_for_recording:
                self.toast.show_message(f"Hotkeys: {ev.message}", 1000)
            self._update_status()

    def _refresh_running(self) -> None:
        running = self.engine.running_ids()
        self.macro_list.blockSignals(True)
        for i in range(self.macro_list.count()):
            item = self.macro_list.item(i)
            m = self.profile.macro_by_id(item.data(Qt.ItemDataRole.UserRole))
            if m is None:
                continue
            is_running = m.id in running
            item.setText(self._macro_label(m, is_running))
            item.setForeground(QColor("#4cd964") if is_running else self.palette().text().color())
        self.macro_list.blockSignals(False)

    def _log(self, message: str, level: int = logging.INFO) -> None:
        log.log(level, message)
        self.log_panel.add(EngineEvent(EventKind.LOG, message, level=level))

    # ------------------------------------------------------------------ Status
    def _update_title(self) -> None:
        name = self.profile_path.name if self.profile_path else "nicht gespeichert"
        star = " *" if self.dirty else ""
        self.setWindowTitle(f"{APP_NAME} {__version__} – {self.profile.name} ({name}){star}")

    def _update_status(self) -> None:
        p = self.platform
        parts = [f"Plattform: {p.name}"]
        parts += [f"⚠ {note}" for note in p.limitations]
        if p.name == "Windows":
            parts.append("Admin" if p.is_admin else "kein Admin")
        self.status_platform.setText("  ·  ".join(parts))
        armed = self.engine.armed
        self.status_armed.setText("● Hotkeys AKTIV" if armed else "○ Hotkeys pausiert")
        self.status_armed.setStyleSheet(f"color: {'#4cd964' if armed else '#ffb347'}")
        if self.tray is not None:
            self.tray.setIcon(app_icon(active=armed))

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"Über {APP_NAME}",
            f"<b>{APP_NAME} {__version__}</b><br>Makros, Hotkeys und Bildsuche für Spiele.<br><br>"
            f"Profile: {self.store.profiles_dir}",
        )

    # ------------------------------------------------------------------ Fenster
    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, ev: QCloseEvent) -> None:
        if not self._quitting and self.tray is not None:
            ev.ignore()
            self.hide()
            self.tray.showMessage(
                APP_NAME,
                "Läuft im Hintergrund weiter. Beenden über das Tray-Menü.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return
        if not self._maybe_save_changes():
            ev.ignore()
            self._quitting = False
            return
        self.app_settings.window_geometry = bytes(self.saveGeometry().toBase64().data()).decode()
        self.store.save_settings(self.app_settings)
        self.engine.shutdown()
        if self.tray is not None:
            self.tray.hide()
        ev.accept()
        from PySide6.QtWidgets import QApplication

        QApplication.quit()

    def _quit(self) -> None:
        self._quitting = True
        self.close()
