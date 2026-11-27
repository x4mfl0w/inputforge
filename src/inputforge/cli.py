"""Kommandozeile: Profile prüfen oder ohne UI ausführen.

inputforge-cli validate profile.json
inputforge-cli run profile.json
inputforge-cli keys
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from inputforge import __version__
from inputforge.config.storage import ProfileError, load_profile
from inputforge.core.keys import all_key_names
from inputforge.i18n import set_language, tr


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        profile = load_profile(Path(args.profile))
    except ProfileError as exc:
        print(exc, file=sys.stderr)
        return 1
    base = Path(args.profile).resolve().parent
    missing = 0
    for m in profile.macros:
        for s in m.steps:
            image = getattr(s, "image", None)
            if image and not (base / image).exists() and not Path(image).is_absolute():
                print(tr("WARNUNG: {macro}: Bild fehlt: {image}", macro=m.name, image=image))
                missing += 1
    print(
        tr(
            "OK: '{name}' – {macros} Makros, {missing} fehlende Bilder",
            name=profile.name,
            macros=len(profile.macros),
            missing=missing,
        )
    )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from inputforge.core.engine import Engine
    from inputforge.platform import create_platform

    if sys.platform == "win32":
        from inputforge.platform.win32 import enable_dpi_awareness

        enable_dpi_awareness()
    path = Path(args.profile).resolve()
    try:
        profile = load_profile(path)
    except ProfileError as exc:
        print(exc, file=sys.stderr)
        return 1
    platform = create_platform()
    engine = Engine(platform)
    engine.load(profile, path.parent)
    engine.start()
    print(
        f"InputForge {__version__} – "
        + tr(
            "'{name}' läuft auf {platform}. Strg+C beendet.",
            name=profile.name,
            platform=platform.name,
        )
    )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        engine.shutdown()
    return 0


def _cmd_keys(_args: argparse.Namespace) -> int:
    print(" ".join(all_key_names()))
    return 0


def main(argv: list[str] | None = None) -> int:
    from inputforge.config.storage import ProfileStore

    set_language(ProfileStore().load_settings().language)
    parser = argparse.ArgumentParser(
        prog="inputforge-cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate", help=tr("Profil prüfen"))
    p.add_argument("profile")
    p.set_defaults(func=_cmd_validate)
    p = sub.add_parser("run", help=tr("Profil ohne UI ausführen"))
    p.add_argument("profile")
    p.set_defaults(func=_cmd_run)
    p = sub.add_parser("keys", help=tr("Alle gültigen Tastennamen auflisten"))
    p.set_defaults(func=_cmd_keys)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
