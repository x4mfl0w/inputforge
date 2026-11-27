import json

import pytest
from pydantic import ValidationError

from inputforge.config.models import (
    DelayAction,
    ImageClickAction,
    KeyAction,
    Macro,
    MouseClickAction,
    Profile,
    RunMacroAction,
    RunMode,
    SearchArea,
)
from inputforge.config.storage import ProfileError, ProfileStore, load_profile, save_profile


def _profile() -> Profile:
    buffs = Macro(name="Buffs", triggers=["F1"], steps=[KeyAction(keys="1"), DelayAction(ms=30)])
    respawn = Macro(
        name="Respawn",
        triggers=["f2"],
        steps=[MouseClickAction(x=950, y=590), RunMacroAction(macro_id=buffs.id)],
    )
    return Profile(name="Test", macros=[buffs, respawn])


def test_roundtrip(tmp_path):
    p = _profile()
    path = tmp_path / "sub" / "p.json"
    save_profile(p, path)
    loaded = load_profile(path)
    assert loaded == p
    assert isinstance(loaded.macros[1].steps[1], RunMacroAction)
    assert loaded.macros[0].triggers == ["f1"]  # normalisiert


def test_discriminator_from_json():
    data = {"macros": [{"steps": [{"type": "delay", "ms": 5}, {"type": "key", "keys": "A"}]}]}
    p = Profile.model_validate(data)
    assert isinstance(p.macros[0].steps[0], DelayAction)
    assert p.macros[0].steps[1].keys == "a"


def test_validation_errors():
    with pytest.raises(ValidationError):
        KeyAction(keys="notakey")
    with pytest.raises(ValidationError):
        MouseClickAction(x=1)
    with pytest.raises(ValidationError):
        Macro(mode=RunMode.REPEAT)
    with pytest.raises(ValidationError):
        Macro(triggers=["ctrl+"])
    with pytest.raises(ValidationError):
        ImageClickAction(image="x.png", area=SearchArea.REGION)
    with pytest.raises(ValidationError):
        Profile(macros=[Macro(steps=[RunMacroAction(macro_id="missing")])])


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        Profile.model_validate({"macros": [{"bogus": 1}]})


def test_future_schema_version_refused(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(ProfileError, match="Schema-Version"):
        load_profile(path)


def test_broken_json(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(path)


def test_store_settings(tmp_path):
    store = ProfileStore(tmp_path)
    s = store.load_settings()
    assert s.last_profile is None
    for i in range(12):
        s.remember(tmp_path / f"{i}.json")
    store.save_settings(s)
    again = store.load_settings()
    assert again.last_profile == str(tmp_path / "11.json")
    assert len(again.recent_profiles) == 10


def test_example_profile_is_valid():
    from pathlib import Path

    path = Path(__file__).parent.parent / "examples" / "grim_dawn" / "grim_dawn.json"
    p = load_profile(path)
    assert {t for m in p.macros for t in m.triggers} >= {"f1", "f2"}


def test_cli_quickstart_example_is_valid():
    from pathlib import Path

    path = Path(__file__).parent.parent / "examples" / "cli_quickstart" / "cli_quickstart.json"
    p = load_profile(path)
    ids = {m.id for m in p.macros}
    # run_macro-Verweise müssen auf existierende Makros zeigen
    for m in p.macros:
        for s in m.steps:
            if s.type == "run_macro":
                assert s.macro_id in ids
    assert {m.mode for m in p.macros} == {"once", "toggle", "hold", "repeat"}
