"""Push-to-talk listener.

Hold the trigger key to record; release it to transcribe that one clip and
type the result once. Nothing listens or types unless the key is held.

Safety rules this module enforces:
- One listener per user session (flock); a second copy exits at once.
- Only one clip is ever being transcribed or typed; presses during that time
  are ignored.
- Pressing any other key while the trigger is held (a shortcut such as
  Right Ctrl+C) cancels the clip.
- Esc while text is being typed stops the typing.
- Only physical keyboards are read; the tool's own virtual keyboard is ignored.
"""
import fcntl
import os
import selectors
import sys
import threading
import time
from typing import Callable, Dict, Optional

import evdev
from evdev import ecodes

from .audio import pcm_to_wav_bytes
from .client import WhisperClient
from .config import DictateConfig, load_auth_token
from .feedback import cue_busy, cue_start, cue_stop
from .recorder import HoldRecorder
from .typer import VIRTUAL_KEYBOARD_NAME, WaylandTyper

LOCK_PATH = f"/run/user/{os.getuid()}/velma-dictate.lock"
RESCAN_SECONDS = 3.0


def acquire_single_instance_lock():
    """Returns an open lock file, or None if another listener holds it."""
    fh = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


class PushToTalk:
    """Key-event state machine. Separated from device I/O so it can be tested."""

    def __init__(
        self,
        trigger_code: int,
        recorder,
        handle_clip: Callable[[bytes], None],
        min_hold_seconds: float,
        silence_seconds: float,
        sample_rate: int,
        cancel_typing: threading.Event,
        busy: threading.Event,
        clock: Callable[[], float] = time.monotonic,
        cues: Optional[Dict[str, Callable[[], None]]] = None,
    ):
        self.trigger_code = trigger_code
        self.recorder = recorder
        self.handle_clip = handle_clip
        self.min_bytes = int(sample_rate * 2 * min_hold_seconds)
        self.silence_seconds = silence_seconds
        self.cancel_typing = cancel_typing
        self.busy = busy
        self.clock = clock
        self.cues = cues or {}
        self.pressed_at: Optional[float] = None
        self.aborted = False
        self.capped: Optional[bytes] = None

    def _cue(self, name: str) -> None:
        fn = self.cues.get(name)
        if fn:
            fn()

    def on_key(self, code: int, value: int) -> None:
        # value: 1 = press, 0 = release, 2 = autorepeat
        if code == self.trigger_code:
            if value == 1:
                self._press()
            elif value == 0:
                self._release()
            return
        if value == 1:
            if code == ecodes.KEY_ESC and self.busy.is_set():
                self.cancel_typing.set()
            if self.pressed_at is not None and not self.aborted:
                # Trigger used as a modifier in a shortcut: not dictation.
                self._abort()

    def tick(self) -> None:
        """Stop after sustained silence; defer typing until key release."""
        if (self.pressed_at is not None and not self.aborted and self.capped is None
                and self.recorder.silent_seconds >= self.silence_seconds):
            # Stop recording now, but type only after release: typing while
            # the trigger (a modifier) is held would fire shortcuts.
            self.capped = self.recorder.stop()
            self._cue("stop")

    def _press(self) -> None:
        if self.pressed_at is not None:
            return
        if self.busy.is_set():
            self._cue("busy")
            return
        self.pressed_at = self.clock()
        self.aborted = False
        self.recorder.start()
        self._cue("start")

    def _release(self) -> None:
        if self.pressed_at is None:
            return
        if self.capped is not None:
            if not self.aborted:
                self._submit(self.capped)
        elif not self.aborted:
            self._submit(self.recorder.stop())
            self._cue("stop")
        self.pressed_at = None
        self.aborted = False
        self.capped = None

    def _abort(self) -> None:
        self.recorder.stop()
        self.aborted = True

    def _submit(self, pcm: bytes) -> None:
        if len(pcm) < self.min_bytes:
            return
        self.busy.set()
        self.cancel_typing.clear()
        self.handle_clip(pcm)


def find_keyboards(trigger_code: int) -> Dict[str, evdev.InputDevice]:
    found = {}
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        keys = dev.capabilities().get(ecodes.EV_KEY, [])
        if dev.name == VIRTUAL_KEYBOARD_NAME or trigger_code not in keys:
            dev.close()
            continue
        found[path] = dev
    return found


def run_listener(cfg: DictateConfig) -> int:
    lock = acquire_single_instance_lock()
    if lock is None:
        print("velma-dictate is already running; not starting a second copy.", file=sys.stderr)
        return 0

    trigger_code = ecodes.ecodes.get(cfg.trigger_key)
    if trigger_code is None:
        print(f"Unknown trigger_key {cfg.trigger_key!r}", file=sys.stderr)
        return 2

    token = load_auth_token(cfg.token_path)
    client = WhisperClient(cfg.endpoint_url, token, model=cfg.model, language=cfg.language,
                           timeout_seconds=cfg.transcription_timeout_seconds)
    typer = WaylandTyper()
    recorder = HoldRecorder(cfg.sample_rate, cfg.silence_threshold)
    busy = threading.Event()
    cancel_typing = threading.Event()

    def worker(pcm: bytes) -> None:
        try:
            text = client.transcribe(pcm_to_wav_bytes(pcm, cfg.sample_rate))
            text = " ".join(text.split())[: cfg.max_output_chars]
            if text and not cancel_typing.is_set():
                typer.type_text(text, cancel=cancel_typing)
        except Exception as e:  # network, server or typing failure: report, never retry
            print(f"Transcription failed: {e}", file=sys.stderr)
            if cfg.feedback_sound:
                cue_busy()
        finally:
            busy.clear()

    def handle_clip(pcm: bytes) -> None:
        threading.Thread(target=worker, args=(pcm,), daemon=True).start()

    cues = {"start": cue_start, "stop": cue_stop, "busy": cue_busy} if cfg.feedback_sound else {}
    ptt = PushToTalk(trigger_code, recorder, handle_clip, cfg.min_hold_seconds,
                     cfg.silence_seconds, cfg.sample_rate, cancel_typing, busy, cues=cues)

    sel = selectors.DefaultSelector()
    devices: Dict[str, evdev.InputDevice] = {}
    last_scan = 0.0
    print(f"velma-dictate listening: hold {cfg.trigger_key} to dictate.", flush=True)
    try:
        while True:
            now = time.monotonic()
            if not devices or now - last_scan > RESCAN_SECONDS:
                last_scan = now
                for path, dev in find_keyboards(trigger_code).items():
                    if path in devices:
                        dev.close()
                        continue
                    devices[path] = dev
                    sel.register(dev, selectors.EVENT_READ)
                    print(f"Reading keys from {path} ({dev.name})", flush=True)
            for key, _ in sel.select(timeout=0.25):
                dev = key.fileobj
                try:
                    for ev in dev.read():
                        if ev.type == ecodes.EV_KEY:
                            ptt.on_key(ev.code, ev.value)
                except OSError:  # unplugged
                    sel.unregister(dev)
                    devices.pop(dev.path, None)
                    dev.close()
                    if ptt.pressed_at is not None:
                        ptt.on_key(trigger_code, 0)
            ptt.tick()
    except KeyboardInterrupt:
        return 0
    finally:
        recorder.stop()
        typer.close()
