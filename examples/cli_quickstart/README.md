# Example: CLI Quickstart

A small, game-agnostic profile that shows how to use InputForge **from the command line only**,
without opening the GUI. It needs no screenshots or image assets, so it works out of the box
on Windows and Linux/X11.

## Macros

| Macro | Trigger | Mode | What it does |
|---|---|---|---|
| Type greeting | `F6` | once | Types `Hello from InputForge!` into the focused window |
| Greeting + Enter | `Ctrl+Alt+G` | once | Short delay → runs *Type greeting* → presses `Enter` |
| Autoclicker (toggle) | `F7` | toggle | Left click every 100 ms until `F7` is pressed again |
| Spam 1 while held | `F8` | hold | Taps `1` every 200 ms while `F8` is held down |
| Jump burst (5x) | `F9` | repeat | Presses `Space` 5 times, 300–400 ms apart (random jitter) |

Global hotkeys (from `settings`):

- `Ctrl+F12` – stop all running macros
- `Ctrl+Pause` – arm/disarm all triggers

`target_window` is empty, so the macros fire in every window. All triggers use
`"passthrough": true`, which means the trigger key still reaches the active application. This
keeps the behaviour identical on Windows and Linux (on X11, triggers can't be suppressed anyway,
see `docs/SPEC.md` §5.3).

## Commands

Install from source first (see the main `README.md`), then run from the repository root.
On Windows use `.venv\Scripts\inputforge-cli` instead of `.venv/bin/inputforge-cli`.

### 1. Validate the profile

```bash
.venv/bin/inputforge-cli validate examples/cli_quickstart/cli_quickstart.json
```

Checks the JSON against the schema and reports missing images. Exit code `0` = valid,
`1` = invalid, so it's usable in scripts and CI:

```bash
inputforge-cli validate my_profile.json || echo "profile is broken"
```

### 2. List valid key names

```bash
.venv/bin/inputforge-cli keys
```

Prints every key name accepted in `triggers` and `keys` (e.g. `f1`, `space`, `lbutton`,
`xbutton1`, `numpad0`). Combine keys with `+`, e.g. `ctrl+shift+a`.

### 3. Run the profile headless

```bash
.venv/bin/inputforge-cli run examples/cli_quickstart/cli_quickstart.json
```

The hotkeys stay active until you press `Ctrl+C` in the terminal. To try it, open a text editor,
click into it and press `F6`. Add `-v` for debug logging:

```bash
.venv/bin/inputforge-cli -v run examples/cli_quickstart/cli_quickstart.json
```

> **Careful:** `run` sends real keyboard and mouse input. Press `Ctrl+F12` (or `Ctrl+C` in the
> terminal) if a macro does something unexpected.

### Other options

```bash
inputforge-cli --version
inputforge-cli --help
inputforge-cli run --help
```

The CLI language follows the language set in the GUI (menu *Sprache / Language*) or, if none is
set, the system language.

## Adapting the profile

The file is plain JSON – edit it with any text editor, then run `validate` again. Fields you leave
out get their default value. Useful step types:

| `type` | Key fields |
|---|---|
| `key` | `keys` (`"ctrl+s"`), `mode` (`tap` / `down` / `up`), `hold_ms` |
| `type_text` | `text`, `key_delay_ms` |
| `mouse_click` | `button`, optional `x` / `y` + `space` (`screen` / `window`), `clicks` |
| `mouse_move` | `x`, `y`, `space`, `relative` |
| `delay` | `ms`, `random_ms` |
| `image_click` | `image` (path relative to the profile), `confidence`, `button` |
| `activate_window` | `title` (empty = profile's `target_window`) |
| `run_macro` | `macro_id` |

Macro modes: `once`, `toggle`, `hold`, `repeat` (`repeat_count` and/or `duration_s`).
The full reference is in `docs/SPEC.md` §3.

To restrict the macros to one game, set `settings.target_window` to part of its window title,
and optionally `"require_window_focus": true`.
