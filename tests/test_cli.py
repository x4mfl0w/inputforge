"""Tests für ``inputforge-cli`` (validate, keys, run, Argumente, Sprache)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import FakeBackend, FakeHook, FakeWindows
from inputforge import __version__, cli, i18n
from inputforge.config import storage
from inputforge.config.storage import AppSettings
from inputforge.core.keys import all_key_names
from inputforge.platform.base import Platform

EXAMPLES = Path(__file__).parent.parent / "examples"
QUICKSTART = EXAMPLES / "cli_quickstart" / "cli_quickstart.json"
GRIM_DAWN = EXAMPLES / "grim_dawn" / "grim_dawn.json"


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Eigenes Konfigurationsverzeichnis (Sprache Deutsch) statt der echten Einstellungen."""
    store = storage.ProfileStore(tmp_path / "cfg")
    store.save_settings(AppSettings(language="de"))
    monkeypatch.setattr(storage, "ProfileStore", lambda: store)
    yield store
    i18n.set_language("de")


def _write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------------------
def test_validate_quickstart_ok(capsys: pytest.CaptureFixture[str]):
    assert cli.main(["validate", str(QUICKSTART)]) == 0
    out = capsys.readouterr().out
    assert "OK: 'CLI Quickstart' – 5 Makros, 0 fehlende Bilder" in out
    assert "WARNUNG" not in out


def test_validate_reports_missing_images(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    profile = {
        "name": "Bilder",
        "macros": [
            {
                "name": "Suche",
                "triggers": ["f1"],
                "steps": [
                    {"type": "image_click", "image": "assets/da.png"},
                    {"type": "image_click", "image": "assets/fehlt.png"},
                ],
            }
        ],
    }
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "da.png").write_bytes(b"")
    path = _write(tmp_path / "p.json", profile)

    assert cli.main(["validate", str(path)]) == 0  # fehlende Bilder sind nur Warnungen
    out = capsys.readouterr().out
    assert "WARNUNG: Suche: Bild fehlt: assets/fehlt.png" in out
    assert "da.png" not in out
    assert "1 fehlende Bilder" in out


def test_validate_resolves_images_relative_to_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    sub = tmp_path / "profile"
    (sub / "assets").mkdir(parents=True)
    (sub / "assets" / "icon.png").write_bytes(b"")
    profile = {
        "macros": [{"steps": [{"type": "image_click", "image": "assets/icon.png"}]}],
    }
    path = _write(sub / "p.json", profile)
    monkeypatch.chdir(tmp_path)  # Arbeitsverzeichnis ≠ Profilordner

    assert cli.main(["validate", "profile/p.json"]) == 0
    assert "0 fehlende Bilder" in capsys.readouterr().out
    assert path.exists()


def test_validate_ignores_absolute_image_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    absolute = str((tmp_path / "gibt_es_nicht.png").resolve())
    profile = {"macros": [{"steps": [{"type": "image_click", "image": absolute}]}]}
    path = _write(tmp_path / "p.json", profile)

    assert cli.main(["validate", str(path)]) == 0
    assert "0 fehlende Bilder" in capsys.readouterr().out


def test_validate_grim_dawn_example_lists_missing_assets(capsys: pytest.CaptureFixture[str]):
    assert cli.main(["validate", str(GRIM_DAWN)]) == 0
    out = capsys.readouterr().out
    for name in ("scroll", "potion", "gheed"):
        if not (GRIM_DAWN.parent / "assets" / f"{name}.png").exists():
            assert f"assets/{name}.png" in out


def test_validate_invalid_profile(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    path = _write(tmp_path / "p.json", {"macros": [{"unbekannt": 1}]})

    assert cli.main(["validate", str(path)]) == 1
    captured = capsys.readouterr()
    assert "ungültiges Profil" in captured.err
    assert captured.out == ""


def test_validate_broken_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "p.json"
    path.write_text("{ kaputt", encoding="utf-8")

    assert cli.main(["validate", str(path)]) == 1
    assert str(path) in capsys.readouterr().err


def test_validate_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "gibt_es_nicht.json"

    assert cli.main(["validate", str(path)]) == 1
    assert str(path) in capsys.readouterr().err


# --------------------------------------------------------------------------------------
# keys, Argumente, Sprache
# --------------------------------------------------------------------------------------
def test_keys_lists_all_key_names(capsys: pytest.CaptureFixture[str]):
    assert cli.main(["keys"]) == 0
    names = capsys.readouterr().out.split()
    assert names == list(all_key_names())
    assert {"f1", "space", "xbutton1", "ctrl"} <= set(names)


def test_version(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


@pytest.mark.parametrize("argv", [[], ["unbekannt"], ["validate"], ["run"]])
def test_invalid_arguments_exit_with_usage_error(argv: list[str]):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2


def test_uses_language_from_settings(
    isolated_settings: storage.ProfileStore, capsys: pytest.CaptureFixture[str]
):
    isolated_settings.save_settings(AppSettings(language="en"))

    assert cli.main(["validate", str(QUICKSTART)]) == 0
    assert "OK: 'CLI Quickstart' – 5 macros, 0 missing images" in capsys.readouterr().out
    assert i18n.current_language() == "en"


def test_help_is_translated(
    isolated_settings: storage.ProfileStore, capsys: pytest.CaptureFixture[str]
):
    isolated_settings.save_settings(AppSettings(language="en"))

    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "Profil prüfen" not in out
    assert "inputforge-cli validate" in out


# --------------------------------------------------------------------------------------
# run (mit Fake-Plattform – sendet keine echten Eingaben)
# --------------------------------------------------------------------------------------
class _FakeGrabber:
    def grab(self, rect=None):  # pragma: no cover - im Quickstart-Profil ohne Bildsuche
        raise AssertionError("keine Bildsuche erwartet")


def _fake_platform(monkeypatch: pytest.MonkeyPatch) -> Platform:
    import inputforge.core.engine as engine_mod
    import inputforge.platform as platform_mod

    platform = Platform("fake", FakeBackend(), FakeHook(), FakeWindows(), game_ready=True)
    monkeypatch.setattr(platform_mod, "create_platform", lambda: platform)
    # Kein mss im Test: Engine bekommt einen Grabber, der nie benutzt werden darf.
    real_engine = engine_mod.Engine
    monkeypatch.setattr(
        engine_mod,
        "Engine",
        lambda plat, **kw: real_engine(plat, grabber=kw.pop("grabber", _FakeGrabber()), **kw),
    )
    return platform


def _wait_until(cond, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > deadline:
            raise AssertionError("Bedingung nicht erfüllt")
        time.sleep(0.005)


def test_run_executes_hotkeys_until_ctrl_c(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    platform = _fake_platform(monkeypatch)
    hook = platform.hook
    backend = platform.backend
    assert isinstance(hook, FakeHook)
    assert isinstance(backend, FakeBackend)
    seen: dict[str, object] = {}

    class _Event:
        """Ersetzt ``threading.Event().wait()`` im CLI: drückt F6, dann „Strg+C“."""

        def wait(self) -> None:
            seen["hook_started"] = hook.callback is not None
            hook.tap("f6")  # Makro „Type greeting“
            # Letztes Zeichen „!“ = shift+1 → sobald „1“ losgelassen wurde, ist der Text getippt.
            _wait_until(lambda: backend.count("up", "1") == 1)
            raise KeyboardInterrupt

    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=_Event))

    assert cli.main(["run", str(QUICKSTART)]) == 0
    out = capsys.readouterr().out
    assert f"InputForge {__version__}" in out
    assert "'CLI Quickstart' läuft auf fake" in out
    assert seen["hook_started"] is True
    assert hook.callback is None  # shutdown() hat den Hook gestoppt
    pressed = [c[1] for c in backend.snapshot() if c[0] == "down" and c[1] != "shift"]
    assert "".join(k if len(k) == 1 else " " for k in pressed) == "hello from inputforge1"


def test_run_invalid_profile_does_not_start_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    import inputforge.platform as platform_mod

    def _fail() -> Platform:
        raise AssertionError("Plattform darf bei ungültigem Profil nicht erzeugt werden")

    monkeypatch.setattr(platform_mod, "create_platform", _fail)
    path = _write(tmp_path / "p.json", {"schema_version": 1, "macros": "keine Liste"})

    assert cli.main(["run", str(path)]) == 1
    assert "ungültiges Profil" in capsys.readouterr().err
