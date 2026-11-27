# InputForge

**English** · [Deutsch](README.de.md)

[![CI](https://github.com/x4mfl0w/inputforge/actions/workflows/ci.yml/badge.svg)](https://github.com/x4mfl0w/inputforge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Macros, hotkeys and image search for PC games, configured entirely through a GUI. Meant as a
replacement for hand-written AutoHotkey scripts. Runs on **Windows** and **Linux (X11)**.

- **Game-ready:** on Windows, `SendInput` with scancodes and low-level hooks, like AHK.
  On Linux, XTest/XRecord without root, for native games and Wine/Proton.
- **Image search:** find icons on screen and click them. Templates can be captured directly
  in the app, and the match score can be tested live. Transparency is supported.
- **Loops:** toggle (on/off), while held, N times or for a fixed duration, each with an
  interval.
- **Multi-binding:** one key triggers several macros or keys at once (`1+2+3`).
- **Triggers:** keys, combinations (`ctrl+shift+f1`), mouse buttons 3/4/5 and the mouse
  wheel. On Windows, triggers can either be suppressed or passed through to the game.
- **Safety net:** emergency stop (`Ctrl+F12`), global hotkey on/off (`Ctrl+Pause`), optionally
  only active while the game is in the foreground.
- Per-game profiles (JSON), tray icon, single instance, CLI for running without the UI.
- UI in English and German (follows the system language, switchable via *Language*).

> **Note:** Intended for single-player and co-op games. In online games, macros may violate the
> terms of service. You are responsible for how you use it.

## Platforms

| | Windows | Linux (X11) |
|---|---|---|
| Keys, clicks, typing, mouse movement | ✔ | ✔ (no AltGr characters such as `@`, `€` when typing) |
| Hotkeys incl. mouse 3/4/5 and wheel | ✔ | ✔ |
| Suppress trigger (game doesn't receive F1) | ✔ | ✘ – the game receives the key too |
| Image search, window activation, window coordinates | ✔ | ✔ |
| Root/admin required | only if the game runs as admin | no |
| Wayland | – | ✘ (choose an X11 session) |

Details and rationale: [`docs/SPEC.md` §5.3](docs/SPEC.md#53-unter-linux-vorerst-ausgelassen)
(German).

## Installation

### Linux

**Prebuilt:** extract `InputForge-x.y.z-linux-x86_64.tar.gz` from the
[releases page](https://github.com/x4mfl0w/inputforge/releases) and run
`InputForge-x.y.z/InputForge`.

**From source:**

```bash
sudo apt install libxcb-cursor0          # required by Qt ≥ 6.5
git clone https://github.com/x4mfl0w/inputforge.git inputforge && cd inputforge
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/inputforge                     # GUI
```

The session must be X11 (the default on Linux Mint/Cinnamon). No root, groups or udev rules
are needed.

### Windows

**Prebuilt:** download `InputForge-x.y.z-win64.zip` from the
[releases page](https://github.com/x4mfl0w/inputforge/releases), extract it and run
`InputForge.exe`.

> If the game runs **as administrator**, InputForge must run as administrator too (or use
> `InputForge-…-win64-admin.exe`). Otherwise Windows silently blocks the input.

**From source** (Python ≥ 3.11):

```powershell
git clone https://github.com/x4mfl0w/inputforge.git inputforge; cd inputforge
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\inputforge                # GUI
```

## Quick start

### Command line, no setup: `examples/cli_quickstart`

A game-agnostic profile without image assets – open a text editor and press `F6`:

```bash
.venv/bin/inputforge-cli run examples/cli_quickstart/cli_quickstart.json
```

See [`examples/cli_quickstart/README.md`](examples/cli_quickstart/README.md).

### GUI: the Grim Dawn example

1. *File → Open profile…* → `examples/grim_dawn/grim_dawn.json`
2. Start the game in **borderless windowed mode** and open the inventory.
3. Macro "Buffs" → double-click the step "Find assets/scroll.png" →
   **"Capture from screen…"**. Switch to the game, after the countdown drag a tight
   rectangle around the icon, save.
4. **"Test now"** shows the score. If it is above the threshold, you're set.
5. Repeat for `potion.png` and `gheed.png`, then save (`Ctrl+S`).
6. Press **F1** in the game.

See [`examples/grim_dawn/README.en.md`](examples/grim_dawn/README.en.md). How the original AHK
script maps to InputForge is described in [`docs/SPEC.md` §7](docs/SPEC.md#7-ahk--inputforge)
(German).

## Common recipes

| Goal | Setting |
|---|---|
| Press 3 every 500 ms, F3 toggles | Mode *Loop – toggle*, pause 500 ms, step *Key* `3` |
| Spam left click while mouse 4 is held | Trigger `xbutton1`, mode *Loop – while held*, pause 50 ms, step *Mouse click* |
| A potion every 2 s for 10 s | Mode *Loop – N times / duration*, duration 10 s, pause 2000 ms |
| F1 presses 1, 2, 3, 4 in sequence | four *Key* steps or *Type text* "1234" |
| F1 presses 1 and 2 simultaneously | step *Key* `1+2` |
| Wait until a button is visible, then click | *Find image & click*, "Wait until visible" 5000 ms, "If not found" = Abort macro |
| F1 should still reach the game | Macro → "Pass trigger through to the game" |

## Command line

```
inputforge-cli validate profile.json    # check profile and image paths (exit code 1 on error)
inputforge-cli run profile.json         # run without UI (Ctrl+C stops)
inputforge-cli keys                     # list all key names
```

## Development

```bash
pip install -e ".[dev]"
pytest                       # Linux: QT_QPA_PLATFORM=offscreen pytest
ruff check src tests && ruff format --check src tests
mypy src
```

X11 integration tests send real input and therefore only run on a throwaway X server:
`INPUTFORGE_X11_TESTS=1 xvfb-run -a pytest tests/test_x11.py`. Never run them on your own
desktop.

**Release:** bump the version in `src/inputforge/__init__.py`, update `CHANGELOG.md` and push
the tag `vX.Y.Z`. GitHub Actions builds and publishes the Windows and Linux packages. Locally:
`packaging\build.ps1` (Windows) or `bash packaging/build.sh` (Linux).

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions (the codebase, spec and changelog are
written in German).

## Project layout

```
src/inputforge/   application (config, core, platform, vision, ui)
tests/            pytest (engine with fake backends, UI smoke, Windows and X11 tests)
docs/SPEC.md      specification (German)
examples/         example profiles (grim_dawn, cli_quickstart)
packaging/        PyInstaller spec, build scripts
.github/          CI and release pipeline
```

## Security

Please report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## License

MIT, see [LICENSE](LICENSE).
