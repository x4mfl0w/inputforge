"""UI-Smoke-Tests (offscreen). Prüfen, dass alle Dialoge aufgebaut und bestätigt werden können."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from inputforge.config.models import ACTION_TYPES, Macro, Profile  # noqa: E402
from inputforge.config.storage import ProfileStore, load_profile  # noqa: E402
from inputforge.ui.describe import ACTION_LABELS, describe  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def window(qapp, harness, tmp_path):
    from inputforge.ui.main_window import MainWindow

    store = ProfileStore(tmp_path / "cfg")
    w = MainWindow(harness.platform, harness.engine, store)
    yield w
    w._quitting = True
    w.dirty = False
    w.close()


def test_every_action_type_has_label_and_dialog(window):
    from inputforge.ui.step_dialog import StepDialog

    assert set(ACTION_LABELS) == set(ACTION_TYPES)
    window._add_macro()
    ctx = window._editor_context()
    for kind in ACTION_TYPES:
        dlg = StepDialog(kind, None, ctx, window)
        dlg._accept()
        assert dlg.result_action is not None, kind
        assert dlg.result_action.type == kind
        assert describe(dlg.result_action, window.profile)


def test_edit_macro_and_save(window, tmp_path):
    window._add_macro()
    m: Macro = window.profile.macros[-1]
    editor = window.editor
    editor.name.setText("Buffs")
    editor.name.textEdited.emit("Buffs")
    editor.mode.setCurrentIndex(editor.mode.findData("repeat"))
    assert m.mode == "repeat" and m.repeat_count == 10
    m.triggers = ["f1"]
    m.steps.append(ACTION_TYPES["key"](keys="1"))
    editor.set_macro(m)
    assert editor.steps.count() == 1

    window.profile_path = tmp_path / "p.json"
    assert window._save()
    loaded = load_profile(tmp_path / "p.json")
    assert loaded.macros[-1].name == "Buffs"
    window._apply_to_engine()  # sonst erst nach 400 ms Debounce
    assert window.engine.profile.macros[-1].triggers == ["f1"]


def test_load_example_profile(window):
    from pathlib import Path

    path = Path(__file__).parent.parent / "examples" / "grim_dawn" / "grim_dawn.json"
    window._set_profile(load_profile(path), path)
    assert window.dirty is False  # Laden darf nichts als geändert markieren
    assert window.macro_list.count() == 4
    assert window.engine.profile.settings.target_window == "Grim Dawn"
    window.macro_list.setCurrentRow(1)
    assert window.editor.macro is not None
    assert window.editor.steps.count() == 5


def test_hotkey_edit_validation(qapp):
    from inputforge.ui.widgets import HotkeyEdit

    e = HotkeyEdit("ctrl+f1")
    assert e.is_valid()
    e.setText("ctrl+")
    assert not e.is_valid()
    c = HotkeyEdit("1+2", chord=True)
    assert c.is_valid()


def test_profile_default_empty(window):
    window._set_profile(Profile(), None)
    assert window.macro_list.count() == 0
    assert not window.editor.isEnabled()
