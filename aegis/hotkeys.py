"""Windows global replay shortcut. Receives only the registered combination."""
from __future__ import annotations

import re
import sys
import threading

_MODIFIERS = {"ALT": 1, "CTRL": 2, "SHIFT": 4}
_NO_REPEAT = 0x4000
_WM_HOTKEY = 0x0312
_REPLAY_ID = 1


def parse_hotkey(value: str) -> tuple[int, int]:
    parts = [part.strip().upper() for part in value.split("+")]
    modifiers, key = parts[:-1], parts[-1]
    if (not modifiers or len(set(modifiers)) != len(modifiers)
            or any(modifier not in _MODIFIERS for modifier in modifiers)
            or not any(modifier in {"CTRL", "ALT"} for modifier in modifiers)):
        raise ValueError("Use Ctrl or Alt with a letter, number, or F1–F11.")
    if not re.fullmatch(r"[A-Z0-9]|F(?:[1-9]|1[01])", key):
        raise ValueError("Use a letter, number, or F1–F11.")
    code = ord(key) if len(key) == 1 else 0x6F + int(key[1:])
    return sum(_MODIFIERS[modifier] for modifier in modifiers), code


class ReplayHotkey:
    def __init__(self, cfg, engine):
        self.cfg = cfg
        self.engine = engine
        self._stop = threading.Event()
        self._listener = None
        self._saving = None

    def start(self):
        if sys.platform == "win32":
            self._listener = threading.Thread(target=self._listen, daemon=True)
            self._listener.start()

    def close(self):
        self._stop.set()
        if self._listener is not None:
            self._listener.join(timeout=1)

    def _listen(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        message = wintypes.MSG()
        registered = False
        current = None
        try:
            while not self._stop.is_set():
                shortcut = self.cfg.get("hotkeys.replay", "") if not self.cfg.get("first_run") else ""
                if shortcut != current:
                    if registered:
                        user32.UnregisterHotKey(None, _REPLAY_ID)
                        registered = False
                    while user32.PeekMessageW(ctypes.byref(message), None, _WM_HOTKEY, _WM_HOTKEY, 1):
                        pass
                    current = shortcut
                    self.engine.replay_hotkey_state = "off"
                    if shortcut:
                        try:
                            modifiers, key = parse_hotkey(shortcut)
                            registered = bool(user32.RegisterHotKey(None, _REPLAY_ID, modifiers | _NO_REPEAT, key))
                        except (AttributeError, ValueError):
                            registered = False
                        self.engine.replay_hotkey_state = "active" if registered else "unavailable"
                while user32.PeekMessageW(ctypes.byref(message), None, _WM_HOTKEY, _WM_HOTKEY, 1):
                    if (registered and message.wParam == _REPLAY_ID
                            and (self._saving is None or not self._saving.is_alive())):
                        self._saving = threading.Thread(target=self.engine.save_shortcut_replay, daemon=True)
                        self._saving.start()
                self._stop.wait(0.05 if registered else 0.25)
        finally:
            if registered:
                user32.UnregisterHotKey(None, _REPLAY_ID)
