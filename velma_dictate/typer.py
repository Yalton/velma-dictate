import subprocess
import threading
import time
from typing import Dict, Optional, Tuple

from evdev import ecodes, UInput

# Mapping standard ASCII characters to (evdev_keycode, shift_needed)
ASCII_TO_KEY: Dict[str, Tuple[int, bool]] = {
    'a': (ecodes.KEY_A, False), 'b': (ecodes.KEY_B, False), 'c': (ecodes.KEY_C, False),
    'd': (ecodes.KEY_D, False), 'e': (ecodes.KEY_E, False), 'f': (ecodes.KEY_F, False),
    'g': (ecodes.KEY_G, False), 'h': (ecodes.KEY_H, False), 'i': (ecodes.KEY_I, False),
    'j': (ecodes.KEY_J, False), 'k': (ecodes.KEY_K, False), 'l': (ecodes.KEY_L, False),
    'm': (ecodes.KEY_M, False), 'n': (ecodes.KEY_N, False), 'o': (ecodes.KEY_O, False),
    'p': (ecodes.KEY_P, False), 'q': (ecodes.KEY_Q, False), 'r': (ecodes.KEY_R, False),
    's': (ecodes.KEY_S, False), 't': (ecodes.KEY_T, False), 'u': (ecodes.KEY_U, False),
    'v': (ecodes.KEY_V, False), 'w': (ecodes.KEY_W, False), 'x': (ecodes.KEY_X, False),
    'y': (ecodes.KEY_Y, False), 'z': (ecodes.KEY_Z, False),
    'A': (ecodes.KEY_A, True), 'B': (ecodes.KEY_B, True), 'C': (ecodes.KEY_C, True),
    'D': (ecodes.KEY_D, True), 'E': (ecodes.KEY_E, True), 'F': (ecodes.KEY_F, True),
    'G': (ecodes.KEY_G, True), 'H': (ecodes.KEY_H, True), 'I': (ecodes.KEY_I, True),
    'J': (ecodes.KEY_J, True), 'K': (ecodes.KEY_K, True), 'L': (ecodes.KEY_L, True),
    'M': (ecodes.KEY_M, True), 'N': (ecodes.KEY_N, True), 'O': (ecodes.KEY_O, True),
    'P': (ecodes.KEY_P, True), 'Q': (ecodes.KEY_Q, True), 'R': (ecodes.KEY_R, True),
    'S': (ecodes.KEY_S, True), 'T': (ecodes.KEY_T, True), 'U': (ecodes.KEY_U, True),
    'V': (ecodes.KEY_V, True), 'W': (ecodes.KEY_W, True), 'X': (ecodes.KEY_X, True),
    'Y': (ecodes.KEY_Y, True), 'Z': (ecodes.KEY_Z, True),
    '1': (ecodes.KEY_1, False), '2': (ecodes.KEY_2, False), '3': (ecodes.KEY_3, False),
    '4': (ecodes.KEY_4, False), '5': (ecodes.KEY_5, False), '6': (ecodes.KEY_6, False),
    '7': (ecodes.KEY_7, False), '8': (ecodes.KEY_8, False), '9': (ecodes.KEY_9, False),
    '0': (ecodes.KEY_0, False),
    '!': (ecodes.KEY_1, True), '@': (ecodes.KEY_2, True), '#': (ecodes.KEY_3, True),
    '$': (ecodes.KEY_4, True), '%': (ecodes.KEY_5, True), '^': (ecodes.KEY_6, True),
    '&': (ecodes.KEY_7, True), '*': (ecodes.KEY_8, True), '(': (ecodes.KEY_9, True),
    ')': (ecodes.KEY_0, True),
    ' ': (ecodes.KEY_SPACE, False), '\n': (ecodes.KEY_ENTER, False), '\t': (ecodes.KEY_TAB, False),
    '.': (ecodes.KEY_DOT, False), ',': (ecodes.KEY_COMMA, False),
    '?': (ecodes.KEY_SLASH, True), '/': (ecodes.KEY_SLASH, False),
    ':': (ecodes.KEY_SEMICOLON, True), ';': (ecodes.KEY_SEMICOLON, False),
    '\'': (ecodes.KEY_APOSTROPHE, False), '"': (ecodes.KEY_APOSTROPHE, True),
    '-': (ecodes.KEY_MINUS, False), '_': (ecodes.KEY_MINUS, True),
    '=': (ecodes.KEY_EQUAL, False), '+': (ecodes.KEY_EQUAL, True),
    '[': (ecodes.KEY_LEFTBRACE, False), '{': (ecodes.KEY_LEFTBRACE, True),
    ']': (ecodes.KEY_RIGHTBRACE, False), '}': (ecodes.KEY_RIGHTBRACE, True),
    '\\': (ecodes.KEY_BACKSLASH, False), '|': (ecodes.KEY_BACKSLASH, True),
    '`': (ecodes.KEY_GRAVE, False), '~': (ecodes.KEY_GRAVE, True),
}

VIRTUAL_KEYBOARD_NAME = "velma-dictate-keyboard"

# Typographic characters the model may emit, mapped to typeable ASCII.
ASCII_SUBSTITUTES = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
}

ALL_CAP_KEYS = set(k for k, _ in ASCII_TO_KEY.values()) | {
    ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFTCTRL, ecodes.KEY_V, ecodes.KEY_INSERT
}

class WaylandTyper:
    """Types text into the focused window through one virtual keyboard.

    The uinput device is created once and kept, so the compositor has
    already seen it by the time the first clip is typed.
    """

    def __init__(self, key_delay: float = 0.004):
        self.key_delay = key_delay
        self.ui: Optional[UInput] = None
        try:
            self.ui = UInput({ecodes.EV_KEY: list(ALL_CAP_KEYS)}, name=VIRTUAL_KEYBOARD_NAME)
        except Exception:
            self.ui = None

    def _tap(self, keycode: int, shift: bool) -> None:
        ui = self.ui
        if shift:
            ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
            ui.syn()
        ui.write(ecodes.EV_KEY, keycode, 1)
        ui.syn()
        time.sleep(self.key_delay)
        ui.write(ecodes.EV_KEY, keycode, 0)
        ui.syn()
        if shift:
            ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
            ui.syn()
        time.sleep(self.key_delay)

    def _paste(self, text: str) -> None:
        """Clipboard + Ctrl+V, used only for text that has non-ASCII characters."""
        subprocess.run(["wl-copy", "--", text], check=True, timeout=2.0)
        if not self.ui:
            return
        time.sleep(0.05)
        for code, val in ((ecodes.KEY_LEFTCTRL, 1), (ecodes.KEY_V, 1),
                          (ecodes.KEY_V, 0), (ecodes.KEY_LEFTCTRL, 0)):
            self.ui.write(ecodes.EV_KEY, code, val)
            self.ui.syn()
            time.sleep(self.key_delay)

    @staticmethod
    def prepare(text: str, append_space: bool = True) -> str:
        out = "".join(ASCII_SUBSTITUTES.get(ch, ch) for ch in text)
        if append_space and out and not out.endswith(" "):
            out += " "
        return out

    def type_text(self, text: str, cancel: Optional[threading.Event] = None,
                  append_space: bool = True) -> None:
        out = self.prepare(text, append_space)
        if not out:
            return
        if self.ui and all(ch in ASCII_TO_KEY for ch in out):
            for ch in out:
                if cancel is not None and cancel.is_set():
                    return
                self._tap(*ASCII_TO_KEY[ch])
        else:
            self._paste(out)

    def close(self) -> None:
        if self.ui:
            try:
                self.ui.close()
            except Exception:
                pass
            self.ui = None
