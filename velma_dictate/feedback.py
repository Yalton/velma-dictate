import os
import subprocess

START_SOUND = "/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga"
STOP_SOUND = "/usr/share/sounds/freedesktop/stereo/bell.oga"
BUSY_SOUND = "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga"


def play_sound(sound_path: str, volume: float = 0.3) -> None:
    if os.path.isfile(sound_path):
        try:
            subprocess.Popen(["pw-play", "--volume", str(volume), sound_path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def cue_start() -> None:
    play_sound(START_SOUND)


def cue_stop() -> None:
    play_sound(STOP_SOUND)


def cue_busy() -> None:
    play_sound(BUSY_SOUND)
