# InputForge

[English](README.md) · **Deutsch**

Makros, Hotkeys und Bildsuche für PC-Spiele, komplett per Oberfläche konfigurierbar. Gedacht
als Ersatz für handgeschriebene AutoHotkey-Skripte. Läuft unter **Windows** und **Linux (X11)**.

- **Spieletauglich:** Unter Windows `SendInput` mit Scancodes und Low-Level-Hooks, wie AHK.
  Unter Linux XTest/XRecord ohne Root-Rechte, für native Spiele und Wine/Proton.
- **Bildsuche:** Icons auf dem Bildschirm finden und anklicken. Vorlagen lassen sich direkt
  in der App ausschneiden; die Übereinstimmung kann man live testen. Transparenz wird
  unterstützt.
- **Schleifen:** Toggle (an/aus), solange gehalten, N-mal oder für eine feste Dauer, jeweils
  mit Intervall.
- **Mehrfachbelegung:** eine Taste löst mehrere Makros oder Tasten gleichzeitig aus
  (`1+2+3`).
- **Trigger:** Tasten, Kombinationen (`ctrl+shift+f1`) und Maustasten 3/4/5 sowie das
  Mausrad. Unter Windows wahlweise abgefangen oder an das Spiel durchgereicht.
- **Sicherheitsnetz:** Notaus (`Strg+F12`), Hotkeys global an/aus (`Strg+Pause`), optional
  nur aktiv, wenn das Spiel im Vordergrund ist.
- Profile pro Spiel (JSON), Tray-Icon, Einzelinstanz, CLI für den Betrieb ohne UI.

> **Hinweis:** Gedacht für Single-Player- und Koop-Spiele. In Online-Spielen können Makros
> gegen die Nutzungsbedingungen verstoßen. Die Verantwortung liegt bei dir.

## Plattformen

| | Windows | Linux (X11) |
|---|---|---|
| Tasten, Klicks, Tippen, Mausbewegung | ✔ | ✔ (Tippen ohne AltGr-Zeichen wie `@`, `€`) |
| Hotkeys inkl. Maus 3/4/5 und Rad | ✔ | ✔ |
| Trigger abfangen (Spiel bekommt F1 nicht) | ✔ | ✘ – das Spiel erhält die Taste mit |
| Bildsuche, Fenster aktivieren, Fensterkoordinaten | ✔ | ✔ |
| Root/Admin nötig | nur wenn das Spiel als Admin läuft | nein |
| Wayland | – | ✘ (X11-Sitzung wählen) |

Details und Gründe: [`docs/SPEC.md` §5.3](docs/SPEC.md#53-unter-linux-vorerst-ausgelassen).

## Installation

### Linux

**Fertiger Build:** `InputForge-x.y.z-linux-x86_64.tar.gz` entpacken und
`InputForge-x.y.z/InputForge` starten.

**Aus dem Quellcode:**

```bash
sudo apt install libxcb-cursor0          # von Qt ≥ 6.5 benötigt
git clone https://github.com/x4mfl0w/inputforge.git inputforge && cd inputforge
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/inputforge                     # GUI
```

Die Sitzung muss X11 sein (bei Linux Mint/Cinnamon Standard). Root-Rechte, Gruppen oder
udev-Regeln sind nicht nötig.

### Windows

**Fertiger Build:** `InputForge-x.y.z-win64.zip` von der Release-Seite herunterladen,
entpacken und `InputForge.exe` starten.

> Läuft das Spiel **als Administrator**, muss InputForge ebenfalls als Administrator laufen
> (oder du nimmst `InputForge-…-admin.exe`). Sonst blockiert Windows die Eingaben
> stillschweigend.

**Aus dem Quellcode** (Python ≥ 3.11):

```powershell
git clone https://github.com/x4mfl0w/inputforge.git inputforge; cd inputforge
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\inputforge                # GUI
```

## Schnellstart

### Kommandozeile ohne Einrichtung: `examples/cli_quickstart`

Ein spielunabhängiges Profil ohne Bild-Assets – Texteditor öffnen und `F6` drücken:

```bash
.venv/bin/inputforge-cli run examples/cli_quickstart/cli_quickstart.json
```

Siehe [`examples/cli_quickstart/README.md`](examples/cli_quickstart/README.md) (Englisch).

### Oberfläche: das Grim-Dawn-Beispiel

1. `Datei → Öffnen…` → `examples/grim_dawn/grim_dawn.json`
2. Spiel im **randlosen Fenstermodus** starten, Inventar öffnen.
3. Makro „Buffs“ → Schritt „Suche assets/scroll.png“ doppelklicken →
   **„Vom Bildschirm ausschneiden…“**. Ins Spiel wechseln, nach dem Countdown einen engen
   Rahmen um das Icon ziehen, speichern.
4. **„Jetzt testen“** zeigt den Score. Liegt er über der Schwelle, passt alles.
5. Dasselbe für `potion.png` und `gheed.png`, danach speichern (`Strg+S`).
6. Im Spiel **F1** drücken.

Wie das Original-AHK-Skript übersetzt wird, steht in
[`docs/SPEC.md` §7](docs/SPEC.md#7-ahk--inputforge).

## Typische Rezepte

| Ziel | Einstellung |
|---|---|
| Taste 3 alle 500 ms drücken, F3 an/aus | Modus *Toggle*, Pause 500 ms, Schritt *Taste* `3` |
| Linksklick-Spam, solange Maus 4 gehalten wird | Trigger `xbutton1`, Modus *solange gehalten*, Pause 50 ms, Schritt *Mausklick* |
| 10 s lang alle 2 s ein Trank | Modus *N-mal / Dauer*, Dauer 10 s, Pause 2000 ms |
| F1 drückt 1, 2, 3, 4 nacheinander | vier *Taste*-Schritte oder *Tastenfolge tippen* „1234“ |
| F1 drückt 1 und 2 gleichzeitig | Schritt *Taste* `1+2` |
| Warten, bis ein Button sichtbar ist, dann klicken | *Bild suchen*, „Warten bis sichtbar“ 5000 ms, „Wenn nicht gefunden“ = Abbrechen |
| F1 soll im Spiel trotzdem ankommen | Makro → „Trigger an das Spiel durchlassen“ |

## Kommandozeile

```
inputforge-cli validate profil.json    # Profil und Bildpfade prüfen
inputforge-cli run profil.json         # ohne UI ausführen
inputforge-cli keys                    # alle Tastennamen
```

## Entwicklung

```bash
pip install -e ".[dev]"
pytest                       # Linux: QT_QPA_PLATFORM=offscreen pytest
ruff check src tests && ruff format --check src tests
mypy src
```

X11-Integrationstests senden echte Eingaben und laufen deshalb nur auf einem Wegwerf-X-Server:
`INPUTFORGE_X11_TESTS=1 xvfb-run -a pytest tests/test_x11.py`. Niemals auf dem eigenen
Desktop ausführen.

**Release:** Version in `src/inputforge/__init__.py` erhöhen, `CHANGELOG.md` pflegen und
den Tag `vX.Y.Z` pushen. GitHub Actions baut und veröffentlicht die Windows- und
Linux-Pakete. Lokal: `packaging\build.ps1` (Windows) bzw. `bash packaging/build.sh` (Linux).

## Projektstruktur

```
src/inputforge/   Anwendung (config, core, platform, vision, ui)
tests/            pytest (Engine mit Fake-Backends, UI-Smoke, Windows- und X11-Tests)
docs/SPEC.md      Spezifikation
examples/         Beispielprofile (grim_dawn, cli_quickstart – CLI-Beispiel auf Englisch)
packaging/        PyInstaller-Spec, Build-Skript
.github/          CI und Release-Pipeline
```

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md) (Englisch). Sicherheitslücken bitte gemäß
[SECURITY.md](SECURITY.md) melden.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
