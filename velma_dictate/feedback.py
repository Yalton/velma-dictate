import os
import subprocess
from typing import Optional

START_SOUND = "/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga"
STOP_SOUND = "/usr/share/sounds/freedesktop/stereo/bell.oga"

def play_sound(sound_path: str, volume: float = 0.4) -> None:
    if os.path.isfile(sound_path):
        try:
            subprocess.Popen(
                ["pw-play", "--volume", str(volume), sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

def send_notification(title: str, message: str, timeout_ms: int = 1500) -> None:
    try:
        subprocess.Popen(
            ["notify-send", "-t", str(timeout_ms), "-a", "Velma Dictate", title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def notify_started(sound: bool = True, visual: bool = True) -> None:
    if visual:
        send_notification("Velma Dictate", "🎤 Listening...")
    if sound:
        play_sound(START_SOUND, volume=0.3)

def notify_stopped(sound: bool = True, visual: bool = True) -> None:
    if visual:
        send_notification("Velma Dictate", "⏹ Stopped")
    if sound:
        play_sound(STOP_SOUND, volume=0.3)
