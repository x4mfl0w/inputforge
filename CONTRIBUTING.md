# Contributing to InputForge

Thanks for your interest! Bug reports, feature ideas and pull requests are welcome.

## Language

The project's source language is **German**: UI strings, docstrings, comments, log messages,
`docs/SPEC.md` and `CHANGELOG.md` are written in German. Issues and pull requests may be in
English or German.

User-visible strings are translated to English via `src/inputforge/locales/en.py` (see
[Translations](#translations)).

## Setup

```bash
git clone https://github.com/x4mfl0w/inputforge.git && cd inputforge
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"          # Windows: .venv\Scripts\pip
```

On Linux, Qt needs `libxcb-cursor0` (`sudo apt install libxcb-cursor0`).

## Before opening a pull request

All of these must pass – CI runs them on Windows and Ubuntu with Python 3.11 and 3.12:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/mypy src --platform linux        # CI also checks --platform win32
.venv/bin/inputforge-cli validate examples/grim_dawn/grim_dawn.json
.venv/bin/inputforge-cli validate examples/cli_quickstart/cli_quickstart.json
```

> **Warning:** the X11 integration tests send **real keyboard and mouse input**. Only run them
> on a throwaway X server, never on your desktop:
> `INPUTFORGE_X11_TESTS=1 xvfb-run -a .venv/bin/pytest tests/test_x11.py`

## Guidelines

- **Spec first.** [`docs/SPEC.md`](docs/SPEC.md) is the authoritative specification. Read the
  relevant section before changing behaviour, and update it in the same pull request.
- **Changelog.** Add an entry under `[Unreleased]` in `CHANGELOG.md`
  ([Keep a Changelog](https://keepachangelog.com/), German).
- **Hook thread.** `Engine.handle_input` runs on the OS hook thread and must return in well
  under 1 ms – no I/O, no screenshots. Windows silently removes slow hooks.
- **Platforms.** A new platform capability needs an implementation for `win32`, `x11` and
  `fallback`, plus the fake in `tests/conftest.py`.
- **Linux limitations are intentional** (SPEC §5.3): X11 without root. Please open an issue
  before proposing uinput/evdev/root-based approaches.
- **Profile schema.** Any change to the profile format must bump `SCHEMA_VERSION` in
  `config/models.py` and add a migration in `config/storage.py::_migrate`.
- **New action types** touch the model, the `Action` union and `ACTION_TYPES`, the runner,
  the step dialog, `ui/describe.py`, tests, SPEC §3.3 and the changelog. See `CLAUDE.md` for
  the full checklist.
- **Style:** ruff, line length 100. Keep pull requests focused on one change.

## Translations

Wrap every user-visible string in `tr("…")` from `inputforge/i18n.py`, using named
placeholders (`tr("Gespeichert: {path}", path=p)`), never f-strings inside `tr`. Module-level
label tables use `N_("…")`. Add the English text to `src/inputforge/locales/en.py`;
`tests/test_i18n.py` fails on missing or stale entries.

New locale modules must also be added to `hiddenimports` in `packaging/inputforge.spec`.

## Reporting bugs

Please include:

- OS and version, and on Linux the desktop environment and session type (`echo $XDG_SESSION_TYPE`)
- InputForge version (`inputforge-cli --version`) and whether you use a prebuilt or source build
- The game, and whether it runs as administrator / under Wine or Proton
- Steps to reproduce, and the log output (`inputforge-cli -v run profile.json`)
- The profile JSON, if relevant (remove anything private)

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
