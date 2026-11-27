"""Englischer Katalog: deutscher Quelltext → Englisch.

Platzhalter in ``{…}`` müssen in beiden Spalten identisch sein (prüft ``tests/test_i18n.py``).
"""

CATALOG: dict[str, str] = {
    # --- CLI / App ---------------------------------------------------------------------
    "Profil, das geöffnet werden soll": "Profile to open",
    "Im Tray starten": "Start minimized to tray",
    "OK: '{name}' – {macros} Makros, {missing} fehlende Bilder": (
        "OK: '{name}' – {macros} macros, {missing} missing images"
    ),
    "'{name}' läuft auf {platform}. Strg+C beendet.": (
        "'{name}' running on {platform}. Press Ctrl+C to quit."
    ),
    "Profil prüfen": "Validate a profile",
    "Profil ohne UI ausführen": "Run a profile without UI",
    "Alle gültigen Tastennamen auflisten": "List all valid key names",
    "WARNUNG: {macro}: Bild fehlt: {image}": "WARNING: {macro}: image missing: {image}",
    # --- Validierung -------------------------------------------------------------------
    "x und y müssen beide gesetzt oder beide leer sein": "x and y must both be set or both empty",
    "area=region benötigt eine region (x, y, w, h)": "area=region requires a region (x, y, w, h)",
    "region muss positive Breite und Höhe haben": "region must have positive width and height",
    "Modus 'repeat' benötigt repeat_count > 0 oder duration_s > 0": (
        "Mode 'repeat' requires repeat_count > 0 or duration_s > 0"
    ),
    "Makro-IDs müssen eindeutig sein": "Macro IDs must be unique",
    "Makro '{name}' verweist auf unbekanntes Makro '{id}'": (
        "Macro '{name}' refers to unknown macro '{id}'"
    ),
    "Profil hat Schema-Version {version}, unterstützt wird bis {supported}. "
    "Bitte InputForge aktualisieren.": (
        "Profile has schema version {version}, supported up to {supported}. "
        "Please update InputForge."
    ),
    "{path}: ungültiges Profil:\n{error}": "{path}: invalid profile:\n{error}",
    "Unbekannte Taste: '{name}'": "Unknown key: '{name}'",
    "Leere Tastenangabe": "Empty key specification",
    "Ungültige Angabe '{text}' (für die Plus-Taste 'plus' schreiben)": (
        "Invalid input '{text}' (write 'plus' for the plus key)"
    ),
    "'{key}' ist kein Modifier – nur ctrl/shift/alt/win dürfen vor der Taste stehen": (
        "'{key}' is not a modifier – only ctrl/shift/alt/win may precede the key"
    ),
    "Maustaste '{key}' ist in einer Tastenaktion nicht erlaubt": (
        "Mouse button '{key}' is not allowed in a key action"
    ),
    # --- Engine / Lauf -----------------------------------------------------------------
    "Hotkeys aktiv ({n} Bindungen)": "Hotkeys active ({n} bindings)",
    "Scharf": "Armed",
    "Pausiert": "Paused",
    "Notaus – alle Makros gestoppt": "Emergency stop – all macros stopped",
    "fertig": "done",
    "gestoppt": "stopped",
    "abgebrochen: {error}": "aborted: {error}",
    "Fehler: {error}": "Error: {error}",
    "Zielfenster '{title}' nicht gefunden": "Target window '{title}' not found",
    "Zielfenster '{title}' fehlt": "Target window '{title}' missing",
    "NICHT GEFUNDEN: {name}": "NOT FOUND: {name}",
    "{name} gefunden bei ({x}, {y}), Score {score}": "{name} found at ({x}, {y}), score {score}",
    "Fenster aktivieren: kein Titel und kein Zielfenster gesetzt": (
        "Activate window: no title and no target window set"
    ),
    "Maximale Verschachtelung ({n}) erreicht – Endlosschleife?": (
        "Maximum nesting ({n}) reached – infinite loop?"
    ),
    "Makro {id} existiert nicht": "Macro {id} does not exist",
    "Kein Zielfenster im Profil konfiguriert": "No target window configured in the profile",
    "Unbekannter Schritt: {step}": "Unknown step: {step}",
    "Bilddatei fehlt: {name} ({error})": "Image file missing: {name} ({error})",
    "Fenster '{title}' nicht aktivierbar": "Window '{title}' could not be activated",
    "Zeichen '{ch}' nicht tippbar – übersprungen": "Character '{ch}' cannot be typed – skipped",
    # --- Plattform ---------------------------------------------------------------------
    "Plattform {name} wird nicht unterstützt": "Platform {name} is not supported",
    "{name} (ohne Eingabe)": "{name} (no input)",
    "Wayland wird nicht unterstützt – bitte X11-Sitzung": (
        "Wayland is not supported – please use an X11 session"
    ),
    "Kein X11-Display (DISPLAY nicht gesetzt)": "No X11 display (DISPLAY not set)",
    "X11 nicht nutzbar: {error}": "X11 unavailable: {error}",
    "Trigger werden nicht abgefangen – das Spiel erhält die Taste ebenfalls": (
        "Triggers are not intercepted – the game receives the key as well"
    ),
    # --- Label-Tabellen (describe.py) --------------------------------------------------
    "Taste / Kombination": "Key / combination",
    "Tastenfolge tippen": "Type text",
    "Mausklick": "Mouse click",
    "Maus bewegen": "Move mouse",
    "Warten": "Wait",
    "Bild suchen & klicken": "Find image & click",
    "Fenster aktivieren": "Activate window",
    "Anderes Makro ausführen": "Run another macro",
    "Einmal ausführen": "Run once",
    "Schleife – Toggle (an/aus)": "Loop – toggle (on/off)",
    "Schleife – solange gehalten": "Loop – while held",
    "Schleife – N-mal / Dauer": "Loop – N times / duration",
    "Links": "Left",
    "Rechts": "Right",
    "Mitte": "Middle",
    "Maus 4 (Zurück)": "Mouse 4 (Back)",
    "Maus 5 (Vor)": "Mouse 5 (Forward)",
    "Linksklick": "Left click",
    "Rechtsklick": "Right click",
    "Mittelklick": "Middle click",
    "Maus-4-Klick": "Mouse 4 click",
    "Maus-5-Klick": "Mouse 5 click",
    "Bildschirm (absolut)": "Screen (absolute)",
    "Zielfenster (relativ)": "Target window (relative)",
    "Zielfenster": "Target window",
    "Ganzer Bildschirm": "Entire screen",
    "Bereich im Fenster": "Region in window",
    "Bildmitte": "Image center",
    "Obere linke Ecke": "Top-left corner",
    "Weiter mit nächstem Schritt": "Continue with next step",
    "Makro abbrechen": "Abort macro",
    # --- Schrittbeschreibungen ---------------------------------------------------------
    "Fenster": "window",
    "Bildschirm": "screen",
    'Tippe "{text}"': 'Type "{text}"',
    "Maus um ({x}, {y}) bewegen": "Move mouse by ({x}, {y})",
    "Maus nach ({x}, {y}) [{space}]": "Move mouse to ({x}, {y}) [{space}]",
    "Warte {ms} ms": "Wait {ms} ms",
    " (+0–{ms} ms zufällig)": " (+0–{ms} ms random)",
    "Suche {image} (≥{conf}) → {action}": "Find {image} (≥{conf}) → {action}",
    ", warte bis {ms} ms": ", wait up to {ms} ms",
    "Maus hin": "move mouse",
    'Aktiviere Fenster "{title}"': 'Activate window "{title}"',
    "<Zielfenster>": "<target window>",
    "Führe Makro aus: {name}": "Run macro: {name}",
    "Drücke {keys} ({ms} ms)": "Press {keys} ({ms} ms)",
    "Halte {keys}": "Hold {keys}",
    "Lasse {keys} los": "Release {keys}",
    " bei ({x}, {y}) [{space}]": " at ({x}, {y}) [{space}]",
    " an Mausposition": " at mouse position",
    # --- Makro-Editor ------------------------------------------------------------------
    "Trigger hinzufügen": "Add trigger",
    "Taste, Kombination oder Maustaste (Mitte/4/5/Rad) drücken:": (
        "Press a key, combination or mouse button (middle/4/5/wheel):"
    ),
    "Ungültig": "Invalid",
    "Unbekannte Taste oder Kombination.": "Unknown key or combination.",
    "Makro": "Macro",
    "Name": "Name",
    "Aktiv": "Enabled",
    "+ Trigger": "+ Trigger",
    "Neuen Trigger (Hotkey) für dieses Makro hinzufügen": (
        "Add a new trigger (hotkey) to this macro"
    ),
    "Entfernen": "Remove",
    "Trigger": "Triggers",
    "Trigger an das Spiel durchlassen": "Pass trigger through to the game",
    "Auch mit zusätzlich gehaltenen Modifiern auslösen (Shift/Strg/…)": (
        "Also fire while extra modifiers are held (Shift/Ctrl/…)"
    ),
    "Ausführung": "Execution",
    "Modus": "Mode",
    "Pause zwischen Durchläufen": "Pause between iterations",
    "unbegrenzt": "unlimited",
    "Max. Durchläufe": "Max. iterations",
    "Max. Dauer": "Max. duration",
    "Schritte": "Steps",
    "+ Schritt": "+ Step",
    "Neuen Schritt zu diesem Makro hinzufügen": "Add a new step to this macro",
    "Bearbeiten": "Edit",
    "Ausgewählten Schritt bearbeiten": "Edit selected step",
    "Duplizieren": "Duplicate",
    "Ausgewählten Schritt duplizieren": "Duplicate selected step",
    "Löschen": "Delete",
    "Ausgewählten Schritt löschen": "Delete selected step",
    "Schritt nach oben": "Move step up",
    "Schritt nach unten": "Move step down",
    "▶ Testen (3 s)": "▶ Test (3 s)",
    "Trigger drücken → Schritte laufen einmal. Während des Laufs wird "
    "ein erneuter Druck ignoriert.": (
        "Press trigger → steps run once. Pressing again while running is ignored."
    ),
    "1. Druck startet die Schleife, 2. Druck stoppt sie. Ideal für "
    "„alle X ms Taste drücken“ (Pause zwischen Durchläufen = Intervall).": (
        "1st press starts the loop, 2nd press stops it. Ideal for "
        "“press a key every X ms” (pause between iterations = interval)."
    ),
    "Schleife läuft, solange der Trigger gehalten wird.": (
        "The loop runs while the trigger is held."
    ),
    "Ein Druck → bis zu „Max. Durchläufe“ bzw. „Max. Dauer“. Erneuter Druck bricht ab.": (
        "One press → up to “Max. iterations” or “Max. duration”. Pressing again aborts."
    ),
    "(kein Trigger – nur über „Anderes Makro ausführen“)": (
        "(no trigger – only via “Run another macro”)"
    ),
    "Auf dieser Plattform nicht möglich – der Trigger erreicht das Spiel immer.": (
        "Not possible on this platform – the trigger always reaches the game."
    ),
    "Unbenannt": "Untitled",
    # --- Hauptfenster ------------------------------------------------------------------
    "{n} Schritte": "{n} steps",
    "Makro „{name}“ löschen?": "Delete macro “{name}”?",
    "Achtung: Wird verwendet von: {users}\nDiese Schritte werden ebenfalls entfernt.": (
        "Warning: used by: {users}\nThose steps will be removed as well."
    ),
    "Makro löschen": "Delete macro",
    "Profilname": "Profile name",
    "optional – Teil des Fenstertitels des Spiels": "optional – part of the game's window title",
    "Offene Fenster neu einlesen": "Refresh open windows",
    "Hotkeys nur auslösen, wenn das Zielfenster aktiv ist": (
        "Only fire hotkeys while the target window is active"
    ),
    "Notaus (alle stoppen)": "Emergency stop (stop all)",
    "Hotkeys an/aus": "Hotkeys on/off",
    "Einblendungen anzeigen (z. B. „NICHT GEFUNDEN“)": "Show notifications (e.g. “NOT FOUND”)",
    "Profil": "Profile",
    "Werkzeuge": "Tools",
    "Neues Profil": "New profile",
    "Neues, leeres Profil anlegen (Strg+N)": "Create a new, empty profile (Ctrl+N)",
    "Profil öffnen…": "Open profile…",
    "Speichern": "Save",
    "Speichern unter…": "Save as…",
    "Hotkeys aktiv": "Hotkeys active",
    "■ Alle stoppen": "■ Stop all",
    "&Datei": "&File",
    "Zuletzt geöffnet": "Recent",
    "Beenden": "Quit",
    "&Sprache": "&Language",
    "Automatisch (Systemsprache)": "Automatic (system language)",
    "&Hilfe": "&Help",
    "Über": "About",
    "<b>Makros</b>": "<b>Macros</b>",
    "+ Neues Makro": "+ New macro",
    "Neues Makro zu diesem Profil hinzufügen": "Add a new macro to this profile",
    "Ausgewähltes Makro duplizieren": "Duplicate selected macro",
    "Ausgewähltes Makro löschen": "Delete selected macro",
    "Profil-Einstellungen": "Profile settings",
    "Debug-Ausgaben": "Debug output",
    "<b>Protokoll</b>": "<b>Log</b>",
    "Anzeigen": "Show",
    "Ungespeicherte Änderungen": "Unsaved changes",
    "Änderungen am Profil speichern?": "Save changes to the profile?",
    "Profil öffnen": "Open profile",
    "Profil laden": "Load profile",
    "Profil speichern": "Save profile",
    "InputForge-Profil (*.json)": "InputForge profile (*.json)",
    "Gespeichert: {path}": "Saved: {path}",
    "Letztes Profil nicht ladbar: {error}": "Could not load last profile: {error}",
    "Standard": "Default",
    "Makro {n}": "Macro {n}",
    "{name} (Kopie)": "{name} (copy)",
    "Test startet in 3 s – jetzt ins Spiel wechseln …": (
        "Test starts in 3 s – switch to the game now …"
    ),
    "Test in 3 s …": "Test in 3 s …",
    "Profil ungültig, nicht übernommen: {error}": "Profile invalid, not applied: {error}",
    "Hotkeys: {state}": "Hotkeys: {state}",
    "nicht gespeichert": "not saved",
    "Plattform: {name}": "Platform: {name}",
    "Admin": "Admin",
    "kein Admin": "not admin",
    "● Hotkeys AKTIV": "● Hotkeys ACTIVE",
    "○ Hotkeys pausiert": "○ Hotkeys paused",
    "Über {app}": "About {app}",
    "Makros, Hotkeys und Bildsuche für Spiele.": "Macros, hotkeys and image search for games.",
    "Profile: {path}": "Profiles: {path}",
    "Die Sprache wird nach einem Neustart von InputForge übernommen.": (
        "The language will change after restarting InputForge."
    ),
    "Läuft im Hintergrund weiter. Beenden über das Tray-Menü.": (
        "Still running in the background. Quit via the tray menu."
    ),
    # --- Picker ------------------------------------------------------------------------
    "Klicke auf den gewünschten Punkt": "Click the desired point",
    "Ziehe einen Rahmen um das Icon (möglichst eng, ohne wechselnden Hintergrund)": (
        "Drag a frame around the icon (as tight as possible, without changing background)"
    ),
    "  ·  Mausrad = Zoom  ·  Esc/Rechtsklick = Abbrechen": (
        "  ·  Mouse wheel = zoom  ·  Esc/right-click = cancel"
    ),
    "  ·  Fenster: ({x}, {y})": "  ·  Window: ({x}, {y})",
    "Bildschirm: ({x}, {y})": "Screen: ({x}, {y})",
    "Screenshot in {s} s – jetzt ins Spiel wechseln …": (
        "Screenshot in {s} s – switch to the game now …"
    ),
    # --- Schritt-Dialog ----------------------------------------------------------------
    "Schritt: {name}": "Step: {name}",
    "Allgemein": "General",
    "Warten danach": "Wait afterwards",
    "Kommentar": "Comment",
    "Taste(n)": "Key(s)",
    "Mehrere Tasten gleichzeitig mit + verbinden, z. B. 1+2+3": (
        "Join multiple simultaneous keys with +, e.g. 1+2+3"
    ),
    "Art": "Type",
    "Drücken & loslassen": "Press & release",
    "Nur drücken (halten)": "Press only (hold)",
    "Nur loslassen": "Release only",
    "Haltedauer": "Hold time",
    "Text": "Text",
    "Pause zwischen Tasten": "Pause between keys",
    "Haltedauer je Taste": "Hold time per key",
    "An aktueller Mausposition": "At current mouse position",
    "Vom Bildschirm wählen…": "Pick from screen…",
    "Position": "Position",
    "Koordinaten": "Coordinates",
    "Zielfenster nicht gefunden – nutze Bildschirmkoordinaten.": (
        "Target window not found – using screen coordinates."
    ),
    "Taste": "Button",
    "Anzahl Klicks": "Number of clicks",
    "Pause zwischen Klicks": "Pause between clicks",
    "Relativ zur aktuellen Position (Raw-Bewegung, z. B. Kamera drehen)": (
        "Relative to current position (raw movement, e.g. turning the camera)"
    ),
    "Dauer": "Duration",
    "+ zufällig bis": "+ random up to",
    "leer = Zielfenster des Profils": "empty = profile's target window",
    "Fenstertitel enthält": "Window title contains",
    "Die Schritte des Makros laufen einmal inline (ohne Schleife).": (
        "The macro's steps run once inline (without looping)."
    ),
    "Bild": "Image",
    "Vom Bildschirm ausschneiden…": "Capture from screen…",
    "Vorschau": "Preview",
    "Mindest-Übereinstimmung": "Minimum match",
    "Graustufen (robuster bei Farbeffekten, etwas ungenauer)": (
        "Grayscale (more robust against color effects, slightly less precise)"
    ),
    "Suchbereich": "Search area",
    "Wählen…": "Pick…",
    "B": "W",
    "H": "H",
    "Bereich": "Region",
    "Nicht klicken (nur Maus hinbewegen)": "Don't click (only move mouse)",
    "Klick": "Click",
    "Klickpunkt": "Click point",
    "Versatz": "Offset",
    "Klick-Haltedauer": "Click hold time",
    "einmal suchen": "search once",
    "Warten bis sichtbar": "Wait until visible",
    "Suchintervall": "Search interval",
    "Wenn nicht gefunden": "If not found",
    "Einblendung „NICHT GEFUNDEN“ anzeigen": "Show “NOT FOUND” notification",
    "Jetzt testen (3 s Verzögerung)": "Test now (3 s delay)",
    "<i>Bild nicht gefunden</i>": "<i>Image not found</i>",
    "Bild wählen": "Choose image",
    "Bilder (*.png *.bmp *.jpg)": "Images (*.png *.bmp *.jpg)",
    "Vorlage speichern": "Save template",
    "Fehler": "Error",
    "PNG konnte nicht kodiert werden": "Could not encode PNG",
    "❌ Vorlage größer als Suchbereich": "❌ Template larger than search area",
    "✅ Gefunden": "✅ Found",
    "❌ Zu unsicher": "❌ Too uncertain",
    "{mark}: Score {score} bei ({x}, {y})": "{mark}: score {score} at ({x}, {y})",
    "Ungültige Eingabe": "Invalid input",
    # --- Widgets -----------------------------------------------------------------------
    "Aufnehmen": "Record",
    "Taste drücken… (Esc)": "Press a key… (Esc)",
    "z. B. ctrl+shift+1": "e.g. ctrl+shift+1",
    "z. B. f1, ctrl+f2, xbutton1": "e.g. f1, ctrl+f2, xbutton1",
}
