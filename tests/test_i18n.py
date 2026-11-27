"""Übersetzungen: Vollständigkeit des englischen Katalogs und Sprachumschaltung."""

from __future__ import annotations

import ast
import string
from collections.abc import Iterator
from pathlib import Path

import pytest

from inputforge import i18n
from inputforge.locales.en import CATALOG

SRC = Path(__file__).resolve().parents[1] / "src" / "inputforge"


def _source_keys() -> set[str]:
    keys: set[str] = set()
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("tr", "N_")
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.fixture
def english() -> Iterator[None]:
    i18n.set_language("en")
    yield
    i18n.set_language("de")


def test_every_source_text_has_english_translation() -> None:
    missing = sorted(_source_keys() - CATALOG.keys())
    assert not missing, "Fehlende Übersetzungen in locales/en.py:\n" + "\n".join(missing)


def test_no_stale_catalog_entries() -> None:
    stale = sorted(CATALOG.keys() - _source_keys())
    assert not stale, "Nicht mehr verwendete Einträge in locales/en.py:\n" + "\n".join(stale)


@pytest.mark.parametrize("de", sorted(CATALOG))
def test_placeholders_match(de: str) -> None:
    assert _fields(de) == _fields(CATALOG[de])


def test_tr_german_is_identity_and_formats() -> None:
    assert i18n.current_language() == "de"
    assert i18n.tr("Speichern") == "Speichern"
    assert i18n.tr("Gespeichert: {path}", path="x.json") == "Gespeichert: x.json"


def test_tr_english(english: None) -> None:
    assert i18n.tr("Speichern") == "Save"
    assert i18n.tr("Gespeichert: {path}", path="x.json") == "Saved: x.json"
    assert i18n.tr("nicht im Katalog") == "nicht im Katalog"


def test_describe_in_english(english: None) -> None:
    from inputforge.config.models import DelayAction, KeyAction
    from inputforge.ui.describe import describe

    assert describe(KeyAction(keys="f1")).startswith("Press F1")
    assert describe(DelayAction(ms=100, random_ms=50)) == "Wait 100 ms (+0–50 ms random)"


def test_unknown_language_falls_back_to_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(i18n, "detect_language", lambda: "en")
    try:
        assert i18n.set_language("xx") == "en"
        assert i18n.set_language(None) == "en"
    finally:
        i18n.set_language("de")


@pytest.mark.parametrize(
    ("env", "expected"), [("de_DE.UTF-8", "de"), ("en_US.UTF-8", "en"), ("fr_FR.UTF-8", "en")]
)
def test_detect_language(monkeypatch: pytest.MonkeyPatch, env: str, expected: str) -> None:
    monkeypatch.setattr(i18n, "_windows_ui_language", lambda: "")
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", env)
    assert i18n.detect_language() == expected


@pytest.mark.parametrize(("ui", "expected"), [("de_DE", "de"), ("en_US", "en")])
def test_windows_ui_language_wins_over_lang(
    monkeypatch: pytest.MonkeyPatch, ui: str, expected: str
) -> None:
    monkeypatch.setattr(i18n, "_windows_ui_language", lambda: ui)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert i18n.detect_language() == expected
