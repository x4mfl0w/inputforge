# InputForge – Spezifikation

| | |
|---|---|
| **Version** | 0.1.0 (Schema-Version 1) |
| **Status** | Entwurf / Alpha |
| **Zielplattformen** | Windows 10/11 (64 Bit) · Linux mit X11-Sitzung (getestet: Linux Mint 22 / Cinnamon) |
| **Sprache** | Python ≥ 3.11, Qt 6 (PySide6) |

---

## 1. Zweck

InputForge ist ein Makro- und Hotkey-Werkzeug für PC-Spiele mit grafischer Oberfläche. Es
ersetzt handgeschriebene AutoHotkey-Skripte wie dieses:

```ahk
F1::RunBuffs()          ; Fenster aktivieren, Tasten senden, Icons per ImageSearch finden und anklicken
F2:: ...                ; Klicksequenz mit Pausen, danach RunBuffs()
```

Alles, was das Skript tut, muss sich ohne Programmieren in der UI einstellen lassen. Dazu
kommen Schleifen (Toggle, Halten, Anzahl/Dauer), Mehrfachbelegung, Notaus und Profile.

### 1.1 Ziele

- **G1 – Spieletauglichkeit:** Eingaben müssen in Spielen ankommen. Unter Windows auch in
  DirectInput-/Raw-Input-Spielen (wie AHK `SendInput`), unter Linux in nativen X11-Spielen
  und Wine/Proton.
- **G1b – Plattformen:** Windows und Linux (X11) aus derselben Codebasis. Funktionen, die
  unter Linux nur mit unverhältnismäßigem Aufwand gehen, entfallen dort vorerst und stehen
  in §5.3.
- **G2 – Vollständig per UI konfigurierbar:** Trigger, Schritte, Klickart, Timing, Schleifen
  und Bildsuche.
- **G3 – Bildsuche:** Icons auf dem Bildschirm finden und anklicken, mit Toleranz,
  Suchbereich und Warten auf Sichtbarkeit.
- **G4 – Auslieferbar:** portable Windows-EXE, versionierte Profile, CI, automatisierte
  Releases.

### 1.2 Nicht-Ziele

- Umgehen von Anti-Cheat-Systemen oder Erkennungsmechanismen. Kein Treiber-Level-Input,
  keine Speicherzugriffe auf Spielprozesse.
- Eine allgemeine Skriptsprache. Logik wie Bedingungen und Variablen ist bewusst nicht
  enthalten (siehe §12 Roadmap).
- Wayland und macOS. Dort startet die UI, es werden aber keine Eingaben gesendet oder
  erkannt.
- Lösungen unter Linux, die Root-Rechte oder Systemänderungen brauchen (evdev/uinput),
  vorerst nicht (siehe §5.3).

---

## 2. Begriffe

| Begriff | Bedeutung |
|---|---|
| **Profil** | JSON-Datei mit Einstellungen und Makros, typischerweise eine pro Spiel. |
| **Makro** | Benannte Folge von **Schritten** mit **Triggern** und einem **Laufmodus**. |
| **Trigger** | Hotkey, der ein Makro auslöst, z. B. `f1`, `ctrl+shift+a`, `xbutton1`. |
| **Schritt / Aktion** | Eine einzelne Operation: Taste, Klick, Bildsuche, Warten, … |
| **Durchlauf** | Einmaliges Abarbeiten aller Schritte eines Makros. |
| **Lauf (Run)** | Ein Thread, der ein Makro gemäß Laufmodus einen oder mehrere Durchläufe ausführt. |
| **Zielfenster** | Fenster, dessen Titel den Profilwert `target_window` enthält. |
| **Scharf / pausiert** | Globaler Zustand: Werden Hotkeys ausgewertet oder nicht? |

---

## 3. Funktionale Anforderungen

### 3.1 Trigger & Hotkeys

| ID | Anforderung |
|---|---|
| FR-T1 | Ein Makro hat 0…n Trigger. Ohne Trigger lässt es sich nur über „Anderes Makro ausführen“ oder „Testen“ starten. |
| FR-T2 | Trigger-Syntax: `[modifier+]…taste` mit den Modifiern `ctrl`, `shift`, `alt`, `win` (gilt jeweils für links und rechts). Siehe §6. |
| FR-T3 | Gültige Trigger sind alle Tastaturtasten sowie `mbutton`, `xbutton1`, `xbutton2`, `wheelup`, `wheeldown` (`lbutton`/`rbutton` sind möglich, aber nicht empfohlen). |
| FR-T4 | **Mehrfachbelegung:** Mehrere Makros dürfen denselben Trigger haben. Alle passenden Makros starten parallel. |
| FR-T5 | **Exakter Modifier-Abgleich** ist Standard (`f1` löst bei gehaltenem Shift nicht aus). Mit `wildcard = true` reicht es, dass die geforderten Modifier gehalten werden; zusätzliche sind erlaubt (entspricht AHK `*`). |
| FR-T6 | **Unterdrückung** *(nur Windows, siehe §5.3)*: Standardmäßig erreicht der Trigger das Spiel nicht. Mit `passthrough = true` wird er durchgereicht. Ist mindestens ein passendes Makro nicht-passthrough, wird unterdrückt. Das Loslassen und Autorepeat einer unterdrückten Taste werden ebenfalls unterdrückt. |
| FR-T7 | **Autorepeat** (gehaltene Taste) löst nicht erneut aus. |
| FR-T8 | **Eigene Eingaben** lösen niemals Trigger aus. Windows: Erkennung über `dwExtraInfo = 0x1F0F1F0F`. Linux: Jede selbst gesendete Taste wird vorgemerkt und ihr Echo im Hook verworfen (Verfall nach 1 s). Synthetische Eingaben anderer Programme werden wie echte behandelt. |
| FR-T9 | **Fokusbindung:** Ist `require_window_focus` gesetzt, lösen Trigger nur aus, wenn der Titel des Vordergrundfensters `target_window` enthält (Groß-/Kleinschreibung egal). Andernfalls wird die Taste unverändert durchgereicht. |
| FR-T10 | **Notaus** (`stop_all_hotkey`, Standard `ctrl+f12`) stoppt alle Läufe. Es wirkt auch im pausierten Zustand und wird immer unterdrückt. |
| FR-T11 | **Scharf/Pause** (`arm_toggle_hotkey`, Standard `ctrl+pause`) schaltet die Hotkey-Auswertung um. Beim Pausieren werden alle Läufe gestoppt. |
| FR-T12 | Während der Hotkey-Aufnahme in der UI ist die Engine pausiert, damit bestehende Hotkeys nicht feuern. |

### 3.2 Laufmodi

| Modus | Trigger gedrückt | Trigger erneut gedrückt | Trigger losgelassen | Ende |
|---|---|---|---|---|
| `once` | startet 1 Durchlauf | ignoriert, solange der Lauf aktiv ist | – | nach dem Durchlauf |
| `toggle` | startet die Schleife | stoppt die Schleife | – | Stopp, `repeat_count` oder `duration_s` |
| `hold` | startet die Schleife | – (Autorepeat) | stoppt die Schleife | Loslassen, `repeat_count` oder `duration_s` |
| `repeat` | startet die Schleife | bricht ab | – | `repeat_count` oder `duration_s` (mindestens eines > 0 ist Pflicht) |

Gemeinsame Parameter:

- `interval_ms`: Pause **zwischen** zwei Durchläufen. Nach dem letzten Durchlauf wird nicht
  gewartet.
- `repeat_count`: maximale Anzahl Durchläufe, 0 = unbegrenzt.
- `duration_s`: maximale Laufzeit der Schleife, 0 = unbegrenzt. Wird während der Pause
  zwischen zwei Durchläufen geprüft. Ein laufender Durchlauf wird nicht abgebrochen.

**Zeitbasiertes Loopen**, etwa „alle 500 ms Taste 3“, ist `toggle` mit `interval_ms = 500`.
**Zeitbegrenztes Loopen**, etwa „10 s lang“, ist `repeat` mit `duration_s = 10`.

Stopp-Semantik: Ein Stopp-Wunsch wird spätestens beim nächsten Warten oder vor dem nächsten
Schritt wirksam. Alle Wartezeiten sind unterbrechbar. Wird ein Lauf **gestoppt oder
abgebrochen**, lässt InputForge alle von diesem Lauf gedrückten Tasten und Maustasten los.
Bei **regulärem Ende** bleiben Tasten aus `key`-Schritten mit Art „nur drücken“ absichtlich
gedrückt.

### 3.3 Aktionen

Alle Aktionen haben `id`, `enabled`, `comment` und `post_delay_ms` (Wartezeit nach dem
Schritt).

| `type` | Felder | Verhalten |
|---|---|---|
| `key` | `keys` (Chord, z. B. `1`, `ctrl+c`, `1+2+3`), `mode` (`tap`/`down`/`up`), `hold_ms` (Std. 30) | `tap`: alle Tasten der Reihe nach drücken, `hold_ms` halten, in umgekehrter Reihenfolge loslassen. **Ein Trigger → mehrere Tasten gleichzeitig.** |
| `type_text` | `text`, `key_delay_ms`, `hold_ms` | Tippt jedes Zeichen als eigenen Tastendruck. Die Zuordnung Zeichen → Taste folgt dem aktiven Tastaturlayout (`VkKeyScanW`). Nicht tippbare Zeichen werden mit Warnung übersprungen. |
| `mouse_click` | `button` (`left/right/middle/x1/x2`), `x`,`y` (optional), `space` (`screen`/`window`), `clicks`, `hold_ms`, `interval_ms` | Bewegt optional die Maus, dann folgen `clicks` Klicks. Ohne x/y wird an der aktuellen Position geklickt. |
| `mouse_move` | `x`,`y`, `space`, `relative` | Absolut: Cursor an die Position setzen. Relativ: Raw-Bewegung um dx/dy (Kamera). |
| `delay` | `ms`, `random_ms` | Wartet `ms` plus eine Zufallszeit von 0…`random_ms`. |
| `image_click` | siehe §3.4 | Bild suchen und anklicken (Pendant zu AHK `ImageSearch`). |
| `activate_window` | `title` (leer = Zielfenster), `wait_ms` | Fenster wiederherstellen und in den Vordergrund holen. Ein Fehlschlag erzeugt eine Warnung, der Lauf geht weiter. |
| `run_macro` | `macro_id` | Führt die Schritte eines anderen Makros einmal inline aus, ohne dessen Schleife. Verschachtelung ist auf 8 Ebenen begrenzt; darüber wird abgebrochen (Schutz vor Endlosrekursion). |

### 3.4 Bildsuche (`image_click`)

| Feld | Standard | Bedeutung |
|---|---|---|
| `image` | – | PNG, BMP oder JPG. Relative Pfade gelten relativ zur Profildatei (üblich: `assets/…`). |
| `confidence` | 0.90 | Mindestähnlichkeit 0.5–1.0 (`TM_CCOEFF_NORMED`). |
| `grayscale` | false | Vergleich in Graustufen. |
| `area` | `window` | `window` = Client-Bereich des Zielfensters, `screen` = gesamter virtueller Desktop, `region` = (x, y, w, h) relativ zum Zielfenster bzw. zum Bildschirm, wenn kein Zielfenster gesetzt ist. |
| `button` | `right` | Klicktaste. `null` bewegt nur die Maus. |
| `anchor` | `center` | Klickpunkt: Bildmitte oder obere linke Ecke. |
| `offset_x/y` | 0 | Versatz zum Anker. |
| `timeout_ms` | 0 | 0 = ein Suchversuch. Sonst wird alle `retry_interval_ms` erneut gesucht, bis der Timeout erreicht ist. |
| `on_not_found` | `continue` | `continue` = nächster Schritt, `stop` = Lauf abbrechen. |
| `notify_not_found` | true | Zeigt eine Einblendung „NICHT GEFUNDEN: …“ (Pendant zum AHK-ToolTip). |

**Transparenz:** Hat die Vorlage einen Alphakanal mit transparenten Pixeln, werden diese
per Maske ignoriert (`TM_CCORR_NORMED` mit Maske, entspricht AHK `*Trans`).

**Umrechnung der AHK-Toleranz:** AHK `*n` ist die Farbabweichung pro Kanal, InputForge
verwendet eine Korrelation. Richtwerte: `*0` ≈ 0.99, `*50` ≈ 0.92, `*90` ≈ 0.87,
`*100` ≈ 0.85. Der „Testen“-Button im Dialog zeigt den tatsächlichen Score, damit sich der
Wert passend einstellen lässt.

Fehlerfälle führen alle zu „nicht gefunden“ mit Policy-Anwendung: Bilddatei fehlt,
Zielfenster fehlt, Suchbereich liegt außerhalb des Bildschirms.

### 3.5 Koordinaten

- Alle Koordinaten sind **physische Pixel**. Der Prozess ist Per-Monitor-DPI-aware (V2).
- `screen`: absolut auf dem virtuellen Desktop. Negative Werte sind bei Monitoren links bzw.
  oberhalb des Hauptmonitors möglich.
- `window`: relativ zur linken oberen Ecke des **Client-Bereichs** des Zielfensters, also
  ohne Titelleiste und Rahmen. Das ist robuster als AHK `WinGetPos`, weil es unabhängig von
  Fensterposition und Rahmen ist.
- Ist das Zielfenster nicht auffindbar, bricht ein Schritt mit `space = window` den Lauf ab.

### 3.6 Profile & Persistenz

| ID | Anforderung |
|---|---|
| FR-P1 | Profile sind UTF-8-JSON-Dateien mit `schema_version`. Unbekannte Felder werden abgelehnt (`extra = forbid`). |
| FR-P2 | Gespeichert wird atomar: erst in eine temporäre Datei, dann per `os.replace`. |
| FR-P3 | Eine höhere Schema-Version als unterstützt führt zu einer verständlichen Fehlermeldung. Migrationen laufen in `config/storage.py::_migrate`. |
| FR-P4 | Standardablage: Windows `%APPDATA%\InputForge\profiles\`, Linux `~/.config/InputForge/profiles/`. Bilder liegen in `assets/` neben dem Profil. Profile sind zwischen den Plattformen austauschbar. |
| FR-P5 | App-Einstellungen (zuletzt geöffnet, Fenstergeometrie) liegen in `settings.json` im selben Konfigurationsverzeichnis. |
| FR-P6 | Validierung: Tastennamen, Koordinatenpaare (x und y gemeinsam), Regionen, Pflichtfelder für `repeat`, eindeutige Makro-IDs und gültige `run_macro`-Verweise. |

### 3.7 Benutzeroberfläche

| ID | Anforderung |
|---|---|
| FR-U1 | Hauptfenster: Makroliste (aktivieren/deaktivieren per Checkbox, Drag & Drop-Sortierung, laufende Makros grün markiert), Editor-Tabs „Makro“ und „Profil-Einstellungen“, Protokoll. |
| FR-U2 | Makro-Editor: Name, Trigger (Aufnahme per Tastendruck oder Maustaste, oder manuelle Eingabe), Passthrough, Wildcard, Modus mit kontextabhängigen Feldern und Erklärtext, Schrittliste (hinzufügen, bearbeiten, duplizieren, verschieben, Drag & Drop, deaktivieren, löschen), „Testen (3 s)“. |
| FR-U3 | Schritt-Dialog je Aktionstyp, mit Validierung und klaren Fehlermeldungen. |
| FR-U4 | **Bildschirm-Picker:** Countdown → eingefrorener Screenshot in physischen Pixeln → Punkt oder Rahmen wählen (Zoom per Mausrad). Das Zielfenster wird markiert, Bildschirm- und Fensterkoordinaten werden live angezeigt. Damit lassen sich Klickpositionen, Suchregionen und **Icon-Vorlagen** (Ausschneiden + Speichern als PNG in `assets/`) erfassen. |
| FR-U5 | Bildsuche „Jetzt testen“: zeigt den besten Score und die Position, auch wenn der Score unter der Schwelle liegt. |
| FR-U6 | Änderungen werden 400 ms nach der letzten Eingabe automatisch in die Engine übernommen (Debounce). Ungespeicherte Änderungen werden im Titel mit `*` angezeigt; beim Schließen und Wechseln wird nachgefragt. |
| FR-U7 | Tray-Icon (grau = pausiert) mit Anzeigen, Hotkeys an/aus, Alle stoppen, Beenden. Schließen des Fensters minimiert in den Tray. |
| FR-U8 | Einblendungen (Toasts) stehlen **nie** den Fokus (`WA_ShowWithoutActivating`, `WindowDoesNotAcceptFocus`, `WindowTransparentForInput`). |
| FR-U9 | Einzelinstanz: Ein zweiter Start holt die laufende Instanz nach vorne. |
| FR-U10 | Die Statusleiste zeigt Plattform, Adminrechte und den Zustand Scharf/Pausiert. |

### 3.8 Kommandozeile

```
inputforge [profil.json] [--minimized] [-v]      GUI
inputforge-cli validate profil.json               Profil + Bildpfade prüfen
inputforge-cli run profil.json                    Headless ausführen (Strg+C beendet)
inputforge-cli keys                               Alle gültigen Tastennamen
```

---

## 4. Architektur

```
┌────────────────────────── UI (PySide6, GUI-Thread) ───────────────────────────┐
│ MainWindow ─ MacroEditor ─ StepDialog ─ Picker ─ Toast ─ LogPanel ─ Tray        │
│        │ Profile (pydantic, editierbar)                ▲ EngineEvent (Signal)   │
└────────┼───────────────────────────────────────────────┼───────────────────────┘
         │ engine.load(deep copy)                         │ EventBridge (queued)
┌────────▼────────────────────── core ───────────────────┴───────────────────────┐
│ Engine: Bindings, Modifier-Status, Unterdrückung, Scharf/Notaus, Läufe          │
│   handle_input(InputEvent) → bool   ◄── Hook-Thread                             │
│   MacroRun (Thread je Lauf) ── führt Aktionen aus, unterbrechbare Waits         │
└────────┬───────────────────────────────┬───────────────────────────────────────┘
         │ InputBackend / WindowManager  │ Grabber + TemplateCache + find_template
┌────────▼─────────── platform ──────────┐ ┌──────────── vision ─────────────────┐
│ win32: SendInput(Scancode), LL-Hooks,  │ │ mss (Screenshot), OpenCV            │
│        Fenster, DPI, timeBeginPeriod   │ │ matchTemplate (+Maske)              │
│ x11:   XTest, XRecord, EWMH            │ └─────────────────────────────────────┘
│ fallback: Null (Wayland/macOS/CI)      │
└────────────────────────────────────────┘
```

### 4.1 Paketstruktur

```
src/inputforge/
  app.py              GUI-Einstieg, Logging, Einzelinstanz
  cli.py              Kommandozeile
  config/models.py    Datenmodell (pydantic v2), Validierung
  config/storage.py   Laden/Speichern, Migration, App-Einstellungen
  core/keys.py        Tastennamen, VK-Codes, Hotkey-/Chord-Parser (abhängigkeitsfrei)
  core/engine.py      Hotkey-Auswertung, Lauf-Verwaltung
  core/runner.py      Ausführung eines Makros (Thread)
  core/events.py      Engine → UI Ereignisse
  platform/base.py    Protokolle (InputBackend, InputHook, WindowManager), Rect
  platform/win32.py   Windows-Implementierung (ctypes)
  platform/x11.py     Linux/X11-Implementierung (python-xlib)
  platform/fallback.py  Null-Backend (Wayland, macOS, Headless)
  vision/matcher.py   Template-Matching, Cache
  vision/screen.py    Bildschirmaufnahme
  ui/                 Qt-Oberfläche
```

### 4.2 Threading-Modell

| Thread | Aufgabe | Regeln |
|---|---|---|
| GUI | Qt-Eventloop, Bearbeitung | Hält das *editierbare* Profil. Die Engine erhält bei jeder Übernahme eine **tiefe Kopie**. |
| Hook | Windows: `WH_KEYBOARD_LL`/`WH_MOUSE_LL` + Message-Loop. Linux: XRecord-Thread | `handle_input` muss in deutlich unter 1 ms zurückkehren. Windows entfernt Hooks, die länger als `LowLevelHooksTimeout` (~1 s) brauchen. Keine Bildschirmaufnahme und kein I/O im Hook. |
| MacroRun (n) | ein Thread je laufendem Makro | Mehrere Makros laufen parallel. Wartezeiten über `Event.wait` (unterbrechbar). |
| Events | Engine → UI | über `EventBridge.received` (Qt queued connection). |

Die Engine schützt Läufe und Halte-Zuordnungen mit einem `RLock`. `mss` wird je Thread
instanziiert (GDI-Kontexte sind threadgebunden).

### 4.3 Engine-Algorithmus (Taste gedrückt)

1. Ist die Taste schon gedrückt (Autorepeat)? Dann nicht auslösen und *suppressed*
   zurückgeben, wenn sie beim ersten Druck unterdrückt wurde.
2. Gehaltene Modifier aus der Menge der gedrückten Tasten ableiten (`lctrl` → `ctrl`).
3. Notaus- und Scharf-Hotkey prüfen. Beide wirken immer.
4. Ist die Engine pausiert: durchreichen.
5. Passende Bindungen suchen (FR-T5). Keine gefunden: durchreichen.
6. Fokusbedingung prüfen (FR-T9).
7. Für jedes Makro `_fire(macro)` gemäß Modus-Tabelle §3.2. Bei `hold` wird die Taste dem
   Lauf zugeordnet.
8. Unterdrücken, wenn ein Makro nicht-passthrough ist.

Beim Loslassen stoppt die Engine alle `hold`-Läufe, die dieser Taste zugeordnet sind.
Wurde der Tastendruck unterdrückt, wird auch das Loslassen unterdrückt.

---

## 5. Plattform-Details

### 5.1 Windows

| Thema | Umsetzung | Grund |
|---|---|---|
| Tastatureingabe | `SendInput` mit `KEYEVENTF_SCANCODE` (+`EXTENDEDKEY` für Pfeile, Navigation, rechte Modifier …). Scancode via `MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)`. | DirectInput- und Raw-Input-Spiele lesen Scancodes. Reine VK-Events werden oft ignoriert. |
| Haltedauer | Standard 30 ms pro Taste | Spiele pollen pro Frame. 0-ms-Taps gehen bei 30–60 FPS verloren. |
| Maus absolut | `SendInput` `MOVE|ABSOLUTE|VIRTUALDESK` (normiert 0–65535), danach `SetCursorPos` für pixelgenaue Korrektur | erzeugt echte Bewegungsereignisse (Hover in Spiel-UIs) und landet exakt auf dem Ziel |
| Maus relativ | `SendInput` `MOVE` | Raw-Input-Kamera |
| Hooks | `WH_KEYBOARD_LL`, `WH_MOUSE_LL` (nur installiert, wenn ein Maus-Trigger existiert). `WM_MOUSEMOVE` wird ohne Python-Overhead durchgereicht. | Unterdrückung möglich. Mausbewegung bleibt latenzfrei. |
| Eigene Eingaben | `dwExtraInfo = 0x1F0F1F0F` | keine Selbstauslösung (FR-T8) |
| Timer | `timeBeginPeriod(1)` | Delays ±1 ms statt ±15,6 ms |
| DPI | Per-Monitor-V2 (setzt Qt; das CLI setzt es selbst) | Screenshot-, Hook- und Klick-Koordinaten passen zusammen. |
| Fokus | `AttachThreadInput` + `SetForegroundWindow`, Fallback ALT-Tap | Windows-Fokus-Sperre |
| Rechte | UIPI: Läuft das Spiel als Administrator, muss InputForge ebenfalls als Administrator laufen. Sonst ignoriert Windows Hooks und `SendInput` stillschweigend. Ein Fehlschlag von `SendInput` wird protokolliert. | Windows-Sicherheitsmodell |

### 5.2 Linux (X11)

| Thema | Umsetzung | Anmerkung |
|---|---|---|
| Plattformwahl | `XDG_SESSION_TYPE=x11` und `DISPLAY` gesetzt → X11-Backend. Bei Wayland oder ohne Display: Null-Backend mit Hinweis in der Statusleiste. | – |
| Tastatureingabe | XTest `fake_input` mit Keycodes. Tastenname → Keysym → Keycode im **aktuellen Layout** (`y` ist auf QWERTZ die Y-Taste). | Wine/Proton übersetzen X11-Events für Windows-Spiele. |
| Tippen | Zeichen → Keysym → Keycode, Ebene 1 bzw. Ebene 2 mit Shift. | Zeichen auf der AltGr-Ebene (z. B. `@`, `€` auf QWERTZ) entfallen (§5.3). |
| Maus | XTest-Motion absolut und relativ, Tasten 1/2/3/8/9 | – |
| Hotkeys | XRecord (Geräteereignisse KeyPress…ButtonRelease) auf eigener Verbindung. Ohne Maus-Trigger nur Tastatur. | Mithören, **kein Unterdrücken**. |
| Autorepeat | X11 erzeugt beim Halten Loslassen/Drücken-Paare mit gleichem Zeitstempel. Das Loslassen wird 30 ms zurückgehalten und verworfen, wenn ein solches Paar folgt. | Das Loslassen kommt daher bis zu 30 ms später an (relevant nur für `hold`). |
| Fenster | EWMH: `_NET_CLIENT_LIST`, `_NET_WM_NAME`, `_NET_ACTIVE_WINDOW` (Aktivieren per ClientMessage, Quelle „Pager“). Client-Rechteck über `translate_coords`. | – |
| Screenshots | mss (XGetImage/XShm) | – |
| Rechte | keine Root-Rechte, keine Gruppen, keine udev-Regeln | – |
| Systempaket | Qt ≥ 6.5 braucht `libxcb-cursor0`. Fehlt es, gibt die App beim Start einen klaren Hinweis aus. Der Release-Build bringt die Bibliothek mit. | `sudo apt install libxcb-cursor0` |
| Threads | python-xlib ist nicht thread-sicher: Backend, Hook und Fensterverwaltung haben je eine eigene Verbindung mit Lock. | – |

### 5.3 Unter Linux vorerst ausgelassen

Bewusst nicht umgesetzt, weil es unter Linux nur mit Root-Setup oder unverhältnismäßigem
Aufwand geht. Entscheidung: zuerst X11 ohne Root, die Backend-Schnittstelle bleibt für ein
späteres uinput-Backend offen.

| # | Funktion | Grund | Mögliche spätere Lösung |
|---|---|---|---|
| L1 | **Trigger abfangen** (`passthrough = false`) | XRecord kann nur mithören. Das Spiel erhält den Trigger immer; die Option ist in der UI deaktiviert. | XGrabKey (nur feste Kombinationen, Konflikte mit anderen Programmen) oder evdev-Grab + uinput (Root-Setup; Risiko, dass die Tastatur bei einem Hänger systemweit blockiert; Gruppe `input` = Keylogger-Rechte für alle Programme) |
| L2 | **Wayland** | keine Fenster-API, Screenshots nur per Portal mit Bestätigung, globale Hotkeys nur über evdev | evdev/uinput + xdg-desktop-portal |
| L3 | **Spiele, die XTest-Eingaben ignorieren** | XTest-Events sind als synthetisch erkennbar | uinput-Backend (virtuelles Kernel-Gerät) |
| L4 | **Zeichen auf der AltGr-Ebene tippen** (`@`, `€`, `{` … auf QWERTZ) | Ebenen ≥ 3 erfordern XKB-Zustandsmanipulation | XKB-Level-Auswertung oder temporäres Keycode-Remapping |
| L5 | **Adminstatus / UIPI** | gibt es unter Linux nicht, entfällt ersatzlos | – |

Nicht garantiert, aber enthalten:

- **Raw-Mausbewegung** (relativ, für die Kamera) kommt in vielen, aber nicht allen Spielen an.
- **Fenster aktivieren** kann am Fokus-Schutz des Fenstermanagers scheitern. Dann erscheint
  eine Warnung und der Lauf geht weiter.

### 5.4 Beide Plattformen

**Vollbild:** Bildsuche funktioniert im *randlosen Fenstermodus* zuverlässig. Im exklusiven
Vollbild (DirectX) liefern Screenshots je nach Spiel schwarze Bilder. Das ist eine
Einschränkung der Bildschirmaufnahme und keine von InputForge.

---

## 6. Tasten-Referenz

- Buchstaben `a`–`z`, Ziffern `0`–`9`, `f1`–`f24`, `numpad0`–`numpad9`
- `space enter tab esc backspace insert delete home end pageup pagedown up down left right`
- `shift ctrl alt win lshift rshift lctrl rctrl lalt ralt lwin rwin apps`
- `capslock numlock scrolllock printscreen pause`
- `multiply add subtract decimal divide`
- OEM: `semicolon plus comma minus period slash backtick lbracket backslash rbracket quote oem102`
  (die physische Taste hängt vom Layout ab; `oem102` ist die `<>`-Taste auf deutschen Tastaturen)
- Medien: `volumeup volumedown volumemute medianext mediaprev mediaplay mediastop`
- Maus (nur Trigger): `lbutton rbutton mbutton xbutton1 xbutton2 wheelup wheeldown`
- Aliase: `strg`→ctrl, `entf`/`del`→delete, `einfg`/`ins`→insert, `escape`→esc,
  `return`→enter, `pgup`/`pgdn`, `mouse4`/`mouse5`, `altgr`→ralt, `num0`… u. a.

Buchstabentasten werden als Virtual Keys des **aktiven Layouts** interpretiert. `y` ist
deshalb auch auf QWERTZ die Taste mit der Aufschrift Y, wie bei AHK.

---

## 7. AHK → InputForge

| AHK | InputForge |
|---|---|
| `F1::RunBuffs()` | Makro „Buffs“, Trigger `f1`, Modus `once` |
| `#SingleInstance Force` | Einzelinstanz (FR-U9) |
| `WinActivate, Grim Dawn` | Schritt `activate_window` (leer = Zielfenster) |
| `MouseMove, 0, 0, 0` | `mouse_move` x=0 y=0 |
| `SendInput, 12` | `type_text` „12“ |
| `SendInput, y` | `key` „y“ |
| `Sleep, 100` | `post_delay_ms` am Schritt oder Schritt `delay` |
| `ImageSearch … *100 scroll.png` + `Click, Right, x+5, y+5` | `image_click` image=`assets/scroll.png`, confidence≈0.85, anchor=`top_left`, offset 5/5, button=`right` |
| `ToolTip NICHT GEFUNDEN` | `notify_not_found = true` |
| `Click, 950, 590` | `mouse_click` x=950 y=590 |
| `RunBuffs()` aus F2 | `run_macro` → Buffs |
| `#IfWinActive` | `require_window_focus` |
| `*F1::` | `wildcard = true` |
| `~F1::` | `passthrough = true` |
| `SetTimer`/Loop-Hotkeys | Modus `toggle`/`repeat` + `interval_ms` |

Das vollständig übersetzte Skript liegt in `examples/grim_dawn/grim_dawn.json`.

---

## 8. Nicht-funktionale Anforderungen

| ID | Anforderung | Messung |
|---|---|---|
| NFR-1 | Hook-Latenz: `handle_input` braucht im Median unter 0,2 ms. | Profiling |
| NFR-2 | Leerlauf-CPU unter 0,5 % (keine Polling-Schleifen). | Task-Manager |
| NFR-3 | Bildsuche im Fenster 1920×1080 mit Vorlage 40×40 unter 30 ms. | Benchmark |
| NFR-4 | Kein Fokusdiebstahl durch eigene Fenster während Makros (FR-U8). | manuell |
| NFR-5 | Ein Absturz eines Makros beeinträchtigt weder Engine noch UI. Fehler werden protokolliert. | Tests |
| NFR-6 | Logdatei rotierend (3 × 1 MB) in `%LOCALAPPDATA%\InputForge\Logs`. | – |
| NFR-7 | Startzeit der portablen Version unter 3 s. | manuell |

---

## 9. Sicherheit & Fairness

- InputForge erzeugt ausschließlich Standard-Windows-Eingaben. Es greift nicht in
  Spielprozesse ein und versteckt sich nicht.
- **Online-Spiele:** Makros können gegen Nutzungsbedingungen verstoßen. Anti-Cheat-Systeme
  erkennen synthetische Eingaben (`LLKHF_INJECTED`). Die Verantwortung liegt beim Nutzer.
  Das Tool enthält bewusst **keine** Mechanismen zur Verschleierung.
- Unter Linux kommt InputForge ohne erhöhte Rechte aus. Es werden keine Gerätedateien
  geöffnet und keine Systemkonfiguration geändert.
- Profile enthalten keinen ausführbaren Code. Es gibt kein `eval`, und die Dateien werden
  strikt validiert.
- Kein Netzwerkzugriff, keine Telemetrie. Die Einzelinstanz nutzt einen lokalen,
  benutzerspezifischen Named Pipe (`QLocalServer`).

---

## 10. Qualitätssicherung

| Ebene | Inhalt |
|---|---|
| Unit | `keys` (Parser, Matching), `models` (Validierung, Roundtrip, Migration), `matcher` (exakt, Rauschen, Graustufen, Alpha-Maske, Unicode-Pfade) |
| Engine | Fake-Backend, -Hook, -Fenster und -Grabber: alle Modi, Unterdrückung, Autorepeat, Modifier, Mehrfachbelegung, Chords, Notaus, Scharf, Fokus, Verschachtelung/Rekursion, Loslassen gehaltener Tasten, Fensterkoordinaten, Bildsuche inkl. Policies |
| UI | Offscreen-Smoke-Tests: jeder Dialogtyp, Editieren und Speichern, Beispielprofil |
| Windows | ABI-Größen der ctypes-Strukturen, Scancodes, Hook-Lebenszyklus, Fenster-API (nur Windows-CI) |
| Linux/X11 | Unit: Echo-Filter, Autorepeat-Entprellung, Keymap, Maustasten. Integration auf Xvfb (`INPUTFORGE_X11_TESTS=1`): Senden → kein Selbstauslösen, `xdotool` → erkannt, Mausposition. **Niemals auf dem eigenen Desktop ausführen.** |
| Statisch | ruff (Lint + Format), mypy |
| Manuell (vor Release) | Texteditor: Tasten, Text, Klicks. Spiel im randlosen Fenster: F1/F2 aus dem Beispiel, unter Windows und unter Linux (nativ + Proton). Windows: Admin-Spiel mit Admin-Build, Multi-Monitor mit 150 % Skalierung. |

CI: GitHub Actions, Matrix Windows/Ubuntu × Python 3.11/3.12. Unter Linux mit Xvfb und den X11-Integrationstests.

---

## 11. Build & Release

- Versionsquelle: `src/inputforge/__init__.py::__version__`. Der Git-Tag `vX.Y.Z` muss
  übereinstimmen (prüft der Release-Workflow).
- `packaging/inputforge.spec` (PyInstaller) erzeugt:
  - `InputForge-X.Y.Z-win64.zip`: portabler Ordner (empfohlen, schneller Start, weniger
    AV-Fehlalarme)
  - `InputForge-X.Y.Z-win64-admin.exe`: Einzeldatei, die immer Adminrechte anfordert (für
    Spiele, die als Administrator laufen)
  - `InputForge-X.Y.Z-linux-x86_64.tar.gz`: portabler Ordner, gebaut auf Ubuntu 22.04 für
    glibc-Kompatibilität, inklusive `libxcb-cursor`
- Ohne UPX. Ungenutzte Qt-Module werden ausgeschlossen.
- Lokal: `packaging\build.ps1 [-OneFile] [-Admin]` (Windows) bzw. `bash packaging/build.sh`
  (Linux)
- Paketgröße: entpackt ca. 400 MB, davon ca. 170 MB OpenCV (siehe Roadmap).
- Empfehlung für die öffentliche Verteilung: die EXE signieren (Authenticode), weil
  Hook-Tools sonst häufig von SmartScreen oder Antivirenprogrammen markiert werden.
- Changelog nach *Keep a Changelog*, Versionierung nach SemVer. Eine Änderung am
  Profilschema erhöht `SCHEMA_VERSION` und bringt eine Migration mit.

---

## 12. Roadmap / bewusst offen

- Linux: Punkte L1–L4 aus §5.3 (uinput/evdev-Backend als optionale Alternative)
- Paketgröße: OpenCV durch eine schlanke Template-Matching-Implementierung ersetzen (nur
  `matchTemplate` und Farbkonvertierung werden genutzt)
- Bedingungen: „wenn Bild sichtbar, dann …“ (Verzweigung), Pixel-Farbe prüfen
- Makro-Rekorder (Eingaben aufzeichnen → Schritte)
- Pro-Makro-Fensterbindung statt nur pro Profil
- Mehrsprachige UI (Qt Linguist), aktuell nur Deutsch
- Optional: Interception-Treiber-Backend für Spiele, die injizierte Eingaben ignorieren
  (nur Single-Player, mit deutlichem Hinweis)
- Autostart mit Windows, automatisches Laden eines Profils pro Prozess
