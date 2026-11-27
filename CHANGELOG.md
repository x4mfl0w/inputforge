# Changelog

Alle relevanten Änderungen an diesem Projekt. Format nach
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung nach
[SemVer](https://semver.org/lang/de/).

## [Unreleased]

### Hinzugefügt
- Englische Oberfläche. Die Sprache folgt der Systemsprache und lässt sich über das Menü
  „Sprache / Language“ festlegen (wirksam nach Neustart). Auch CLI-, Protokoll- und
  Validierungsmeldungen sowie die Qt-Standardknöpfe sind übersetzt.
- Englischsprachiges Beispiel `examples/cli_quickstart/` für die Nutzung ohne GUI
  (`validate`, `keys`, `run`), ohne Bild-Assets; wird in der CI mitvalidiert.
- Englische Projektdokumentation: `README.md` ist jetzt Englisch (deutsche Fassung in
  `README.de.md`), dazu `CONTRIBUTING.md`, `SECURITY.md`, Issue- und PR-Vorlagen sowie
  eine englische Anleitung zum Grim-Dawn-Beispiel.

### Geändert
- Eindeutige Beschriftungen: „Neu“ in der Werkzeugleiste heißt jetzt „Neues Profil“
  (dazu „Profil öffnen…“), der Knopf unter der Makroliste „+ Neues Makro“. Die Knöpfe zum
  Duplizieren und Löschen von Makros und Schritten haben Tooltips.

## [0.1.0] – 2026-11-24

### Hinzugefügt
- Engine mit den Laufmodi Einmal, Toggle, Halten und Wiederholen (Anzahl/Dauer), Intervall
  und Mehrfachbelegung.
- Aktionen: Taste/Chord, Tastenfolge, Mausklick, Maus bewegen (absolut/relativ), Warten
  (mit Zufallsanteil), Bild suchen und klicken, Fenster aktivieren, Makro ausführen.
- Windows-Backend: SendInput mit Scancodes, Low-Level-Tastatur-/Maus-Hooks mit
  Unterdrückung, DPI-Awareness, 1-ms-Timer.
- Linux/X11-Backend ohne Root: XTest (Senden), XRecord (Hotkeys, mit Echo-Filter und
  Autorepeat-Entprellung), EWMH (Fenster). Einschränkungen in `docs/SPEC.md` §5.3.
- Startprüfung unter Linux auf `libxcb-cursor0` mit klarer Fehlermeldung.
- Bildsuche mit OpenCV (Graustufen, Alpha-Maske, Suchregion, Warten bis sichtbar).
- Qt-Oberfläche: Makro-Editor, Schritt-Dialoge, Hotkey-Aufnahme, Bildschirm-Picker zum
  Ausschneiden von Vorlagen, Live-Test, Tray, Toasts, Protokoll.
- Profile als versioniertes JSON mit Validierung und atomarem Speichern.
- CLI (`validate`, `run`, `keys`), PyInstaller-Builds für Windows und Linux, CI (inkl. Xvfb) und Release-Workflow.
- Beispielprofil: Grim Dawn (Übersetzung des ursprünglichen AHK-Skripts).
