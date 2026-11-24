import pytest

from aegis.hotkeys import parse_hotkey


def test_replay_shortcut_uses_win32_codes():
    assert parse_hotkey("Ctrl+Alt+F10") == (3, 0x79)
    assert parse_hotkey("Alt+Shift+Z") == (5, ord("Z"))


@pytest.mark.parametrize("value", ["A", "Shift+1", "Win+P", "Alt+F12", "Ctrl+Ctrl+A"])
def test_replay_shortcut_rejects_unsupported_keys(value):
    with pytest.raises(ValueError):
        parse_hotkey(value)
