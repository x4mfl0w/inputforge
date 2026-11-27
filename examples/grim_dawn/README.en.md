# Example: Grim Dawn

**English** · [Deutsch](README.md)

A translation of the original AHK script. (Macro names and step comments inside the profile
are in German.)

| Macro | Trigger | Enabled | Contents |
|---|---|---|---|
| Buffs | F1 | ✔ | Activate window → park mouse → `12` → `y` (inventory) → right-click scroll/potion/gheed via image search → `y` |
| Respawn + Buffs | F2 | ✔ | Esc → 3 clicks with pauses → Buffs |
| Taste 3 spammen (Toggle) | F3 | ✘ | Demo: toggle loop, key 3 every 500 ms |
| Alle Skills 1–4 (Mehrfachbelegung) | Mouse 4 | ✘ | Demo: one key → several keys |

## Required images

The icons are not included (resolution and UI scaling differ for everyone). Put them in
`assets/`:

- `assets/scroll.png`
- `assets/potion.png`
- `assets/gheed.png`

The easiest way is inside InputForge itself: edit the step → **"Capture from screen…"**.
Your existing AHK PNGs work too and can simply be copied here.

The click coordinates of F2 (950/590 etc.) come from the original and are absolute screen
coordinates. For a different resolution, adjust them with "Pick from screen…", or switch to
"Target window (relative)".
