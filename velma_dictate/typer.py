import os
import subprocess
import time
from typing import Dict, Tuple, Optional
import evdev
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

ALL_CAP_KEYS = set(k for k, _ in ASCII_TO_KEY.values()) | {
    ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFTCTRL, ecodes.KEY_V, ecodes.KEY_INSERT
}

class WaylandTyper:
    def __init__(self):
        self.ui: Optional[UInput] = None
        self._init_uinput()

    def _init_uinput(self) -> None:
        try:
            cap = {ecodes.EV_KEY: list(ALL_CAP_KEYS)}
            self.ui = UInput(cap, name="velma-dictate-keyboard")
        except Exception as e:
            # If UInput cannot be opened, we fall back to clipboard-only methods
            self.ui = None

    def type_char(self, keycode: int, shift: bool) -> None:
        if not self.ui:
            return
        if shift:
            self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
            self.ui.syn()
        self.ui.write(ecodes.EV_KEY, keycode, 1)
        self.ui.syn()
        time.sleep(0.003)
        self.ui.write(ecodes.EV_KEY, keycode, 0)
        self.ui.syn()
        if shift:
            self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
            self.ui.syn()
        time.sleep(0.003)

    def paste_via_clipboard(self, text: str) -> bool:
        """Copies text to Wayland clipboard using wl-copy and sends Ctrl+V."""
        try:
            subprocess.run(["wl-copy", text], check=True, timeout=2.0)
            if self.ui:
                # Send Ctrl+V
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
                self.ui.syn()
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
                self.ui.syn()
                time.sleep(0.01)
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
                self.ui.syn()
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
                self.ui.syn()
                return True
        except Exception:
            pass
        return False

    def type_text(self, text: str, append_space: bool = True) -> None:
        """
        Types the text directly into the focused window.
        Uses character typing for standard ASCII, or clipboard paste fallback if needed.
        """
        if not text:
            return

        out_text = text + (" " if append_space and not text.endswith(" ") else "")

        # Check if all characters can be typed directly
        can_type_all = self.ui is not None and all(ch in ASCII_TO_KEY for ch in out_text)

        if can_type_all and self.ui:
            for ch in out_text:
                keycode, shift = ASCII_TO_KEY[ch]
                self.type_char(keycode, shift)
        else:
            # Use clipboard paste for unicode/special characters or if typing is unavailable
            self.paste_via_clipboard(out_text)

    def close(self) -> None:
        if self.ui:
            try:
                self.ui.close()
            except Exception:
                pass
            self.ui = None
