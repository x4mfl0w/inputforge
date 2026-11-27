import pytest

from inputforge.core.keys import (
    VK,
    VK_TO_NAME,
    Hotkey,
    KeyParseError,
    char_to_chord,
    parse_chord,
    parse_hotkey,
)


def test_parse_simple_and_modifiers():
    assert parse_hotkey("F1") == Hotkey("f1")
    hk = parse_hotkey("Ctrl + Shift + A")
    assert hk.key == "a"
    assert hk.modifiers == frozenset({"ctrl", "shift"})
    assert str(hk) == "ctrl+shift+a"


def test_aliases_and_side_specific_modifiers():
    assert parse_hotkey("strg+entf") == Hotkey("delete", frozenset({"ctrl"}))
    assert parse_hotkey("lctrl+mouse4") == Hotkey("xbutton1", frozenset({"ctrl"}))


@pytest.mark.parametrize("bad", ["", "+", "foo", "a+b", "ctrl+nope"])
def test_parse_errors(bad):
    with pytest.raises(KeyParseError):
        parse_hotkey(bad)


def test_chord_allows_multiple_keys_but_not_mouse():
    assert parse_chord("1+2+3") == ["1", "2", "3"]
    with pytest.raises(KeyParseError):
        parse_chord("ctrl+xbutton1")


def test_matching_exact_and_wildcard():
    hk = parse_hotkey("ctrl+f1")
    assert hk.matches("f1", frozenset({"ctrl"}), wildcard=False)
    assert not hk.matches("f1", frozenset(), wildcard=False)
    assert not hk.matches("f1", frozenset({"ctrl", "shift"}), wildcard=False)
    assert hk.matches("f1", frozenset({"ctrl", "shift"}), wildcard=True)
    assert not hk.matches("f2", frozenset({"ctrl"}), wildcard=True)


def test_modifier_as_trigger_key():
    hk = parse_hotkey("ctrl")
    # Hook meldet die seitenspezifische Taste; die Taste selbst zählt nicht als Modifier.
    assert hk.matches("lctrl", frozenset({"ctrl"}), wildcard=False)


def test_vk_table_consistency():
    assert VK["a"] == 0x41 and VK["f1"] == 0x70 and VK["numpad0"] == 0x60
    assert VK_TO_NAME[0xA2] == "lctrl"
    assert 0x11 not in VK_TO_NAME  # generisches VK_CONTROL nicht rückabbilden


def test_char_to_chord_fallback():
    assert char_to_chord("a") == ["a"]
    assert char_to_chord("A") == ["shift", "a"]
    assert char_to_chord(" ") == ["space"]
    assert char_to_chord("€") is None
