"""Laden/Speichern von Profilen und App-Einstellungen."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from platformdirs import user_config_path
from pydantic import BaseModel, Field

from inputforge import APP_NAME
from inputforge.config.models import SCHEMA_VERSION, Profile


class ProfileError(Exception):
    """Profil konnte nicht geladen oder gespeichert werden."""


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION:
        raise ProfileError(
            f"Profil hat Schema-Version {version}, unterstützt wird bis {SCHEMA_VERSION}. "
            "Bitte InputForge aktualisieren."
        )
    # Zukünftige Migrationen: if version < 2: ...; data["schema_version"] = 2
    return data


def load_profile(path: Path) -> Profile:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"{path}: {exc}") from exc
    try:
        return Profile.model_validate(_migrate(data))
    except ValueError as exc:
        raise ProfileError(f"{path}: ungültiges Profil:\n{exc}") from exc


def save_profile(profile: Profile, path: Path) -> None:
    """Atomar speichern (temp + replace) – ein Absturz hinterlässt nie ein halbes Profil."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = profile.model_dump_json(indent=2, exclude_defaults=False)
    fd, tmp = tempfile.mkstemp(prefix=".profile-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise ProfileError(f"{path}: {exc}") from exc


class AppSettings(BaseModel):
    last_profile: str | None = None
    start_minimized: bool = False
    window_geometry: str | None = None
    recent_profiles: list[str] = Field(default_factory=list)

    def remember(self, path: Path) -> None:
        p = str(path)
        self.last_profile = p
        if p in self.recent_profiles:
            self.recent_profiles.remove(p)
        self.recent_profiles.insert(0, p)
        del self.recent_profiles[10:]


class ProfileStore:
    """Verwaltet das Konfigurationsverzeichnis (``%APPDATA%/InputForge`` unter Windows)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or user_config_path(APP_NAME, appauthor=False, roaming=True)
        self.profiles_dir = self.root / "profiles"
        self.settings_file = self.root / "settings.json"

    def ensure(self) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> AppSettings:
        try:
            return AppSettings.model_validate_json(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return AppSettings()

    def save_settings(self, settings: AppSettings) -> None:
        self.ensure()
        self.settings_file.write_text(settings.model_dump_json(indent=2), encoding="utf-8")

    def default_profile_path(self) -> Path:
        return self.profiles_dir / "default.json"
