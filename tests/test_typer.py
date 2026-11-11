import pytest
from velma_dictate.typer import ASCII_TO_KEY, WaylandTyper
from evdev import ecodes

def test_ascii_to_key_coverage():
    # Verify standard lowercase, uppercase, digits, and common punctuation are present
    for ch in "abcdefghijklmnopqrstuvwxyz":
        assert ch in ASCII_TO_KEY
        code, shift = ASCII_TO_KEY[ch]
        assert shift is False

    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert ch in ASCII_TO_KEY
        code, shift = ASCII_TO_KEY[ch]
        assert shift is True

    for ch in "0123456789":
        assert ch in ASCII_TO_KEY

    for ch in " .,!?:;'\"-()":
        assert ch in ASCII_TO_KEY

def test_wayland_typer_init():
    typer = WaylandTyper()
    # UInput might succeed if /dev/uinput is writable
    if typer.ui is not None:
        assert typer.ui.name == "velma-dictate-keyboard"
    typer.close()
