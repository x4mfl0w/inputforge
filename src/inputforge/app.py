"""GUI-Einstiegspunkt."""

from __future__ import annotations

import argparse
import getpass
import logging
import logging.handlers
import sys
from pathlib import Path

from platformdirs import user_log_path

from inputforge import APP_NAME, __version__

log = logging.getLogger("inputforge")


def _setup_logging(verbose: bool) -> Path:
    log_dir = user_log_path(APP_NAME, appauthor=False)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "inputforge.log"
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        ),
    ]
    if sys.stderr is not None:  # PyInstaller --windowed hat kein stderr
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
    )
    return log_file


def _missing_linux_libs() -> list[str]:
    """Qt ≥ 6.5 benötigt unter X11 libxcb-cursor – fehlt sie, stürzt Qt ohne Hinweis ab."""
    import ctypes.util
    import os

    if not sys.platform.startswith("linux") or os.environ.get("QT_QPA_PLATFORM"):
        return []
    if getattr(sys, "frozen", False):
        return []  # Release-Build bringt die Bibliothek selbst mit
    return [] if ctypes.util.find_library("xcb-cursor") else ["libxcb-cursor0"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("profile", nargs="?", help="Profil, das geöffnet werden soll")
    parser.add_argument("--minimized", action="store_true", help="Im Tray starten")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    log_file = _setup_logging(args.verbose)
    log.info("%s %s startet (Log: %s)", APP_NAME, __version__, log_file)

    missing = _missing_linux_libs()
    if missing:
        log.error(
            "Fehlende Systembibliothek(en) für die Qt-Oberfläche: %s\n"
            "Installieren mit:  sudo apt install %s",
            ", ".join(missing),
            " ".join(missing),
        )
        return 1

    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv if argv is None else [APP_NAME, *argv])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    # --- Einzelinstanz (wie #SingleInstance): vorhandene Instanz nach vorne holen ----
    server_name = f"{APP_NAME}-{getpass.getuser()}"
    probe = QLocalSocket()
    probe.connectToServer(server_name)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        log.info("Instanz läuft bereits – aktiviert")
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)

    from inputforge.config.storage import ProfileStore
    from inputforge.core.engine import Engine
    from inputforge.platform import create_platform
    from inputforge.ui.main_window import MainWindow

    platform = create_platform()
    if not platform.game_ready:
        log.warning("Plattform %s: Eingaben in Spielen werden nicht unterstützt", platform.name)
    engine = Engine(platform)
    store = ProfileStore()
    store.ensure()

    try:
        window = MainWindow(platform, engine, store)
    except RuntimeError as exc:  # z. B. Hook konnte nicht installiert werden
        QMessageBox.critical(None, APP_NAME, str(exc))
        return 1

    def on_connection() -> None:
        sock = server.nextPendingConnection()
        if sock is None:
            return

        def on_ready() -> None:
            sock.readAll()
            window._show_from_tray()

        sock.readyRead.connect(on_ready)

    server.newConnection.connect(on_connection)

    if args.profile:
        window._open_profile(str(Path(args.profile).resolve()))
    if args.minimized or window.app_settings.start_minimized:
        if window.tray is None:
            window.showMinimized()
    else:
        window.show()

    code = app.exec()
    engine.shutdown()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
