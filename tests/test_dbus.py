import json
import pytest
from velma_dictate.dbus_service import (
    DummyDBusService,
    DictateDBusService,
    HAS_DASBUS,
)
from velma_dictate.ptt import PushToTalk
import threading


def test_dummy_dbus_service():
    srv = DummyDBusService("http://test", "model-x", "KEY_RIGHTCTRL")
    assert srv.GetState() == "idle"
    assert srv.IsEnabled() is True
    srv.SetEnabled(False)
    assert srv.IsEnabled() is False
    assert srv.GetLastTranscription() == ""
    assert srv.GetHistory() == "[]"
    status = json.loads(srv.GetStatus())
    assert status["enabled"] is False


@pytest.mark.skipif(not HAS_DASBUS, reason="dasbus not available")
def test_dictate_dbus_service():
    srv = DictateDBusService("http://test", "parakeet", "KEY_RIGHTCTRL")
    assert srv.GetState() == "idle"
    assert srv.IsEnabled() is True

    srv.notify_state("recording")
    assert srv.GetState() == "recording"

    srv.notify_transcription_completed("test dictation text", 2.0, 150.5)
    assert srv.GetLastTranscription() == "test dictation text"

    history = json.loads(srv.GetHistory())
    assert len(history) == 1
    assert history[0]["text"] == "test dictation text"
    assert history[0]["audio_duration"] == 2.0
    assert history[0]["latency_ms"] == 150.5
    assert history[0]["status"] == "success"

    stats = json.loads(srv.GetLastStats())
    assert stats["text"] == "test dictation text"

    srv.notify_error("connection error", 1.0, 50.0)
    history = json.loads(srv.GetHistory())
    assert len(history) == 2
    assert history[0]["status"] == "error"
    assert history[0]["error"] == "connection error"


class FakeRecorder:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.silent_seconds = 0.0

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        return b"\x00\x00" * 16000  # 1 sec


def test_ptt_dbus_interaction():
    rec = FakeRecorder()
    clips = []
    dummy_dbus = DummyDBusService()
    busy = threading.Event()
    cancel = threading.Event()

    ptt = PushToTalk(
        trigger_code=97,  # Right Ctrl
        recorder=rec,
        handle_clip=lambda p: clips.append(p),
        min_hold_seconds=0.1,
        silence_seconds=15.0,
        sample_rate=16000,
        cancel_typing=cancel,
        busy=busy,
        dbus_service=dummy_dbus,
    )

    # Press trigger -> state recording
    ptt.on_key(97, 1)
    assert rec.started is True
    assert dummy_dbus.GetState() == "recording"

    # Release trigger -> submitted -> state transcribing
    ptt.on_key(97, 0)
    assert rec.stopped is True
    assert len(clips) == 1
    assert dummy_dbus.GetState() == "transcribing"


def test_ptt_dbus_disabled():
    rec = FakeRecorder()
    clips = []
    dummy_dbus = DummyDBusService()
    dummy_dbus.SetEnabled(False)
    busy = threading.Event()
    cancel = threading.Event()

    ptt = PushToTalk(
        trigger_code=97,
        recorder=rec,
        handle_clip=lambda p: clips.append(p),
        min_hold_seconds=0.1,
        silence_seconds=15.0,
        sample_rate=16000,
        cancel_typing=cancel,
        busy=busy,
        dbus_service=dummy_dbus,
    )

    # When disabled, pressing trigger should NOT start recording
    ptt.on_key(97, 1)
    assert rec.started is False
    assert dummy_dbus.GetState() == "idle"
