import os
import subprocess
import sys
import threading

from evdev import ecodes

from velma_dictate import ptt as ptt_mod
from velma_dictate.ptt import PushToTalk
from velma_dictate.typer import WaylandTyper

RATE = 16000
TRIGGER = ecodes.KEY_RIGHTCTRL
PRESS, RELEASE = 1, 0


class FakeRecorder:
    def __init__(self):
        self.recording = False
        self.starts = 0
        self.seconds = 1.0
        self.silent_seconds = 0.0

    def start(self):
        self.recording = True
        self.starts += 1

    def stop(self):
        was = self.recording
        self.recording = False
        return b"\0" * int(RATE * 2 * self.seconds) if was else b""


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def make(seconds=1.0):
    rec = FakeRecorder()
    rec.seconds = seconds
    clips = []
    busy, cancel, clock = threading.Event(), threading.Event(), Clock()
    p = PushToTalk(TRIGGER, rec, clips.append, 0.35, 15.0, RATE, cancel, busy, clock=clock)
    return p, rec, clips, busy, cancel, clock


def test_hold_and_release_submits_exactly_one_clip():
    p, rec, clips, busy, *_ = make()
    p.on_key(TRIGGER, PRESS)
    for _ in range(20):
        p.on_key(TRIGGER, 2)  # autorepeat must not restart anything
    p.on_key(TRIGGER, RELEASE)
    assert rec.starts == 1 and not rec.recording
    assert len(clips) == 1
    assert busy.is_set()


def test_short_tap_is_dropped():
    p, rec, clips, busy, *_ = make(seconds=0.1)
    p.on_key(TRIGGER, PRESS)
    p.on_key(TRIGGER, RELEASE)
    assert clips == [] and not busy.is_set() and not rec.recording


def test_press_while_busy_does_not_record():
    p, rec, clips, busy, *_ = make()
    busy.set()
    p.on_key(TRIGGER, PRESS)
    p.on_key(TRIGGER, RELEASE)
    assert rec.starts == 0 and clips == []


def test_shortcut_chord_cancels_clip():
    p, rec, clips, *_ = make()
    p.on_key(TRIGGER, PRESS)
    p.on_key(ecodes.KEY_C, PRESS)
    p.on_key(ecodes.KEY_C, RELEASE)
    p.on_key(TRIGGER, RELEASE)
    assert clips == [] and not rec.recording


def test_silence_stops_recording_but_types_only_after_release():
    p, rec, clips, busy, cancel, clock = make()
    p.on_key(TRIGGER, PRESS)
    clock.t = 120.0
    p.tick()
    assert rec.recording
    rec.silent_seconds = 15.0
    p.tick()
    assert not rec.recording
    assert clips == []  # trigger still held: must not type yet
    p.tick()
    p.on_key(TRIGGER, RELEASE)
    assert len(clips) == 1


def test_escape_cancels_typing_only_while_busy():
    p, rec, clips, busy, cancel, _ = make()
    p.on_key(ecodes.KEY_ESC, PRESS)
    assert not cancel.is_set()
    busy.set()
    p.on_key(ecodes.KEY_ESC, PRESS)
    assert cancel.is_set()


def test_typer_stops_when_cancelled():
    t = WaylandTyper.__new__(WaylandTyper)
    t.key_delay = 0
    t.ui = object()
    taps = []
    cancel = threading.Event()

    def tap(code, shift):
        taps.append(code)
        if len(taps) == 3:
            cancel.set()

    t._tap = tap
    t.type_text("hello world", cancel=cancel)
    assert len(taps) == 3


def test_prepare_maps_typographic_punctuation():
    assert WaylandTyper.prepare("it’s “ok” — yes") == "it's \"ok\" - yes "


def test_second_listener_refuses_to_start(tmp_path, monkeypatch):
    lock = tmp_path / "lock"
    monkeypatch.setattr(ptt_mod, "LOCK_PATH", str(lock))
    held = ptt_mod.acquire_single_instance_lock()
    assert held is not None
    code = (
        "import fcntl,sys\n"
        f"f=open({str(lock)!r},'a')\n"
        "try:\n fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); sys.exit(1)\n"
        "except BlockingIOError: sys.exit(0)\n"
    )
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
    held.close()
