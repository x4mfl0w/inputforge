# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

InputForge: GUI-configurable macro/hotkey/image-search tool for PC games (AutoHotkey replacement), Python ≥ 3.11 + PySide6. Targets **Windows** and **Linux/X11**. `docs/SPEC.md` is the authoritative spec (requirement IDs like FR-P3, platform tables, threading model) — read the relevant section before changing behavior, and update it when behavior changes. UI strings, docs, docstrings and comments are in German. Exception: the GitHub-facing docs `README.md`, `CONTRIBUTING.md`, `SECURITY.md` and `.github/` templates are English; `README.de.md` is the German README — keep both READMEs in sync.

## Commands

```bash
.venv/bin/pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen .venv/bin/pytest                      # all tests (offscreen needed on Linux for UI tests)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_engine.py::test_name   # single test
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/mypy src --platform linux          # CI also runs --platform win32 on Windows
.venv/bin/inputforge-cli validate examples/grim_dawn/grim_dawn.json   # CI validates the example profile
bash packaging/build.sh                      # PyInstaller build (Linux); packaging\build.ps1 on Windows
```

X11 integration tests send **real input** — only run them on a throwaway X server, never on the user's desktop:
`INPUTFORGE_X11_TESTS=1 xvfb-run -a .venv/bin/pytest tests/test_x11.py`. `tests/test_win32.py` only runs on Windows.

CI (`.github/workflows/ci.yml`): Windows/Ubuntu × Python 3.11/3.12, ruff lint + format check, mypy, pytest (Linux under Xvfb with X11 integration tests), example profile validation.

## Architecture

Layers: `config` (pydantic data model) → `core` (engine + macro runner) → `platform` (OS input/hooks/windows) and `vision` (screenshot + OpenCV template matching) → `ui` (Qt). See SPEC §4 for the diagram.

**Data flow.** The UI owns the *editable* `Profile`; `Engine.load()` takes a **deep copy** (`model_copy(deep=True)`), so edits only take effect when the profile is re-applied. Engine → UI communication goes through `EngineEvent` (`core/events.py`) and `EventBridge` in `ui/main_window.py` (Qt queued signal).

**Threading (SPEC §4.2) — critical constraints:**
- `Engine.handle_input(InputEvent) -> bool` runs on the hook thread (Windows LL hooks / Linux XRecord thread). It must return in well under 1 ms: no screenshots, no I/O. Windows silently removes hooks that exceed `LowLevelHooksTimeout`. Return value `True` = suppress the event.
- Each running macro is a `MacroRun` thread (`core/runner.py`); waits use `Event.wait` so they are interruptible. Engine state is guarded by an `RLock`.
- `mss` must be instantiated per thread. python-xlib is not thread-safe: X11 backend, hook and window manager each use their own connection + lock.

**Platform abstraction.** `platform/base.py` defines the `InputBackend`, `InputHook`, `WindowManager` protocols and the `Platform` bundle; `platform/__init__.py::create_platform()` picks `win32`, `x11`, or the `fallback` null backend (Wayland, no `DISPLAY`, macOS, headless). Any new platform capability needs an implementation in all three plus the fake in `tests/conftest.py`. Self-generated input is tagged with `INJECT_MARKER` (Windows `dwExtraInfo`; X11 uses an `InjectionTracker` echo filter) so macros don't retrigger themselves.

**Linux limitations are deliberate** (SPEC §5.3): XRecord can only listen, so triggers can't be suppressed (`passthrough=false` is disabled in the UI); no Wayland; no AltGr-level characters when typing. Don't "fix" these with root/uinput/evdev without discussing — the design choice is X11 without root.

**Actions (macro steps).** Each step type is a pydantic model in `config/models.py` with a `type: Literal[...]` discriminator. Adding a new action type touches:
1. `config/models.py`: model class, the `Action` union, `ACTION_TYPES` dict (the UI builds dialogs from it)
2. `config/__init__.py`: export
3. `core/runner.py`: `_exec` match-dispatch + `_do_*` method
4. `ui/step_dialog.py`: editor form; `ui/describe.py`: list text
5. Tests (`tests/test_engine.py` uses the fake backend/hook/window/grabber from `conftest.py`), `docs/SPEC.md` §3.3, `CHANGELOG.md`

**Profiles.** UTF-8 JSON with `schema_version`; models use `extra="forbid"`. Saving is atomic (temp file + `os.replace`). Any profile schema change must bump `SCHEMA_VERSION` (`config/models.py`) and add a migration in `config/storage.py::_migrate`. `core/keys.py` (key names, VK codes, hotkey/chord parser) is dependency-free.

**Windows input details** (SPEC §5.1): `SendInput` with scancodes (DirectInput games ignore plain VK events), default 30 ms key hold (games poll per frame), `timeBeginPeriod(1)`, per-monitor-v2 DPI awareness. mypy ignores `attr-defined` in `platform/win32.py` because `ctypes.WinDLL` only exists on Windows.

## Conventions

- **i18n:** German is the source language. Wrap every user-visible string in `tr("…")` from `inputforge/i18n.py` (named placeholders: `tr("Gespeichert: {path}", path=p)`, never f-strings inside `tr`); module-level label tables use `N_("…")` and are translated with `tr(label)` where shown. Add the English text to `src/inputforge/locales/en.py`. `tests/test_i18n.py` fails on missing/stale catalog entries or mismatched placeholders. Python `log.*` messages stay German. New locale modules must be added to `hiddenimports` in `packaging/inputforge.spec`.

- ruff: line length 100, rules `E F W I B UP SIM RUF` (RUF001–003 ignored for German typography).
- `CHANGELOG.md` follows Keep a Changelog (German); add entries under `[Unreleased]`.
- Release: bump `__version__` in `src/inputforge/__init__.py` (must match tag `vX.Y.Z`, checked by the release workflow), update CHANGELOG, push the tag.
