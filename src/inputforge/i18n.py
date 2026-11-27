"""Minimale Übersetzung der Oberfläche (Qt-frei, auch für CLI und Engine nutzbar).

Deutsch ist die Quellsprache: Texte stehen im Code auf Deutsch und werden über
:func:`tr` nachgeschlagen. Andere Sprachen liegen als Katalog ``{deutsch: übersetzt}``
in ``inputforge/locales/<code>.py`` (Variable ``CATALOG``).

* ``tr("Gespeichert: {path}", path=p)`` übersetzt und formatiert (nur mit Keyword-Argumenten).
* ``N_("…")`` markiert Texte, die erst später übersetzt werden (z. B. Werte in
  Label-Tabellen auf Modulebene). Sie werden an der Verwendungsstelle mit ``tr`` übersetzt.

Die Sprache wird einmal beim Start gesetzt (:func:`set_language`). Ein Wechsel wirkt
nach einem Neustart, da bereits aufgebaute Widgets ihre Texte behalten.
"""

from __future__ import annotations

import contextlib
import importlib
import locale
import os
import sys

LANGUAGES: dict[str, str] = {"de": "Deutsch", "en": "English"}
DEFAULT_LANGUAGE = "de"

_lang = DEFAULT_LANGUAGE
_catalog: dict[str, str] = {}


def detect_language() -> str:
    """Sprache aus der Systemumgebung: Deutsch bei deutscher Locale, sonst Englisch."""
    candidates = [os.environ.get(v, "") for v in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")]
    with contextlib.suppress(ValueError):
        candidates.append(locale.getlocale()[0] or "")
    if sys.platform == "win32":
        try:
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            candidates.insert(0, locale.windows_locale.get(lcid, ""))
        except (AttributeError, OSError):
            pass
    for c in candidates:
        c = c.strip().lower()
        if not c or c in ("c", "posix"):
            continue
        return "de" if c.startswith(("de", "german")) else "en"
    return "en"


def set_language(lang: str | None) -> str:
    """Setzt die Sprache (``None`` → automatisch). Gibt die tatsächlich gesetzte zurück."""
    global _lang, _catalog
    code = lang if lang in LANGUAGES else detect_language()
    if code == DEFAULT_LANGUAGE:
        _catalog = {}
    else:
        _catalog = importlib.import_module(f"inputforge.locales.{code}").CATALOG
    _lang = code
    return code


def current_language() -> str:
    return _lang


def tr(text: str, /, **kwargs: object) -> str:
    out = _catalog.get(text, text)
    return out.format(**kwargs) if kwargs else out


def N_(text: str, /) -> str:  # gettext-Konvention
    return text


__all__ = ["LANGUAGES", "N_", "current_language", "detect_language", "set_language", "tr"]
