# Beispiel: Grim Dawn

Übersetzung des ursprünglichen AHK-Skripts.

| Makro | Trigger | Aktiv | Inhalt |
|---|---|---|---|
| Buffs | F1 | ✔ | Fenster aktivieren → Maus parken → `12` → `y` (Inventar) → scroll/potion/gheed per Bildsuche rechtsklicken → `y` |
| Respawn + Buffs | F2 | ✔ | Esc → 3 Klicks mit Pausen → Buffs |
| Taste 3 spammen | F3 | ✘ | Demo: Toggle-Schleife, alle 500 ms Taste 3 |
| Alle Skills 1–4 | Maus 4 | ✘ | Demo: eine Taste → mehrere Tasten |

## Benötigte Bilder

Die Icons sind nicht enthalten (Auflösung und UI-Skalierung sind bei jedem anders). Lege sie
in `assets/` ab:

- `assets/scroll.png`
- `assets/potion.png`
- `assets/gheed.png`

Am einfachsten geht das in InputForge selbst: Schritt bearbeiten →
**„Vom Bildschirm ausschneiden…“**. Deine bisherigen AHK-PNGs funktionieren ebenfalls und
können einfach hierher kopiert werden.

Die Klickkoordinaten von F2 (950/590 usw.) stammen aus dem Original und sind absolute
Bildschirmkoordinaten. Bei anderer Auflösung passt du sie über „Vom Bildschirm wählen…“ an,
oder du stellst auf „Zielfenster (relativ)“ um.
