"""D-Bus session service for velma-dictate.

Exposes org.velma.Dictate at /org/velma/Dictate so GNOME Shell extensions,
desktop widgets, or scripts can monitor dictation status, view latency
and history, and toggle dictation on or off.
"""
import json
import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger("velma_dictate.dbus")

try:
    from gi.repository import GLib
    from dasbus.connection import SessionMessageBus
    from dasbus.server.interface import dbus_interface, dbus_signal
    HAS_DASBUS = True
except ImportError:
    HAS_DASBUS = False


class DictateDBusInterfaceBase:
    """Base class defining D-Bus interface methods and signals."""

    def GetState(self) -> str:
        raise NotImplementedError

    def GetLastTranscription(self) -> str:
        raise NotImplementedError

    def GetLastStats(self) -> str:
        raise NotImplementedError

    def GetHistory(self) -> str:
        raise NotImplementedError

    def GetStatus(self) -> str:
        raise NotImplementedError

    def SetEnabled(self, enabled: bool) -> bool:
        raise NotImplementedError

    def IsEnabled(self) -> bool:
        raise NotImplementedError

    def GetConfiguration(self) -> str:
        raise NotImplementedError

    def UpdateConfiguration(self, endpoint_url: str, model: str, language: str, trigger_key: str, token: str) -> bool:
        raise NotImplementedError

    def TestConnection(self) -> str:
        raise NotImplementedError


if HAS_DASBUS:
    @dbus_interface("org.velma.Dictate")
    class DictateDBusService(DictateDBusInterfaceBase):
        """Live D-Bus service registered on session bus."""

        @dbus_signal
        def StateChanged(self, new_state: str):
            pass

        @dbus_signal
        def TranscriptionCompleted(self, text: str, audio_duration: float, latency_ms: float):
            pass

        @dbus_signal
        def ErrorOccurred(self, error_message: str):
            pass

        def __init__(self, endpoint_url: str = "", model: str = "", trigger_key: str = ""):
            self._lock = threading.Lock()
            self._state = "idle"
            self._enabled = True
            self._endpoint_url = endpoint_url
            self._model = model
            self._trigger_key = trigger_key
            self._last_transcription = ""
            self._last_stats: Dict[str, Any] = {
                "audio_duration": 0.0,
                "latency_ms": 0.0,
                "timestamp": int(time.time()),
            }
            self._history: deque = deque(maxlen=50)

        # Internal notification methods called by PTT daemon:

        def notify_state(self, state: str) -> None:
            with self._lock:
                self._state = state
            try:
                self.StateChanged(state)
            except Exception as e:
                logger.debug(f"Failed to emit StateChanged: {e}")

        def notify_transcription_completed(self, text: str, duration: float, latency_ms: float) -> None:
            item = {
                "text": text,
                "audio_duration": round(duration, 2),
                "latency_ms": round(latency_ms, 1),
                "timestamp": int(time.time()),
                "status": "success",
            }
            with self._lock:
                self._last_transcription = text
                self._last_stats = item
                self._history.appendleft(item)
            try:
                self.TranscriptionCompleted(text, float(duration), float(latency_ms))
            except Exception as e:
                logger.debug(f"Failed to emit TranscriptionCompleted: {e}")

        def notify_error(self, message: str, duration: float = 0.0, latency_ms: float = 0.0) -> None:
            item = {
                "text": "",
                "audio_duration": round(duration, 2),
                "latency_ms": round(latency_ms, 1),
                "timestamp": int(time.time()),
                "status": "error",
                "error": message,
            }
            with self._lock:
                self._history.appendleft(item)
            try:
                self.ErrorOccurred(message)
            except Exception as e:
                logger.debug(f"Failed to emit ErrorOccurred: {e}")

        # D-Bus Methods:

        def GetState(self) -> str:
            with self._lock:
                return self._state

        def GetLastTranscription(self) -> str:
            with self._lock:
                return self._last_transcription

        def GetLastStats(self) -> str:
            with self._lock:
                return json.dumps(self._last_stats)

        def GetHistory(self) -> str:
            with self._lock:
                return json.dumps(list(self._history))

        def GetStatus(self) -> str:
            with self._lock:
                status = {
                    "state": self._state,
                    "enabled": self._enabled,
                    "endpoint_url": self._endpoint_url,
                    "model": self._model,
                    "trigger_key": self._trigger_key,
                    "history_count": len(self._history),
                }
                return json.dumps(status)

        def SetEnabled(self, enabled: bool) -> bool:
            with self._lock:
                self._enabled = bool(enabled)
                return self._enabled

        def IsEnabled(self) -> bool:
            with self._lock:
                return self._enabled

        def GetConfiguration(self) -> str:
            with self._lock:
                return json.dumps({
                    "endpoint_url": self._endpoint_url,
                    "model": self._model,
                    "trigger_key": self._trigger_key,
                })

        def UpdateConfiguration(self, endpoint_url: str, model: str, language: str, trigger_key: str, token: str) -> bool:
            with self._lock:
                self._endpoint_url = endpoint_url
                self._model = model
                self._trigger_key = trigger_key
            try:
                from .config import DictateConfig, save_auth_token
                cfg = DictateConfig.load()
                cfg.endpoint_url = endpoint_url
                cfg.model = model
                cfg.language = language
                cfg.trigger_key = trigger_key
                cfg.save()
                if token:
                    save_auth_token(token)
                return True
            except Exception as e:
                logger.error(f"Failed to update configuration: {e}")
                return False

        def TestConnection(self) -> str:
            try:
                from .client import WhisperClient
                from .config import DictateConfig, load_auth_token
                cfg = DictateConfig.load()
                token = load_auth_token(cfg.token_path)
                client = WhisperClient(cfg.endpoint_url, token, model=cfg.model)
                ok = client.test_connection()
                return json.dumps({"ok": ok, "message": "Endpoint OK" if ok else "Endpoint did not respond"})
            except Exception as e:
                return json.dumps({"ok": False, "message": str(e)})


class DummyDBusService:
    """Fallback no-op service when D-Bus or dasbus is unavailable."""

    def __init__(self, endpoint_url: str = "", model: str = "", trigger_key: str = ""):
        self.endpoint_url = endpoint_url
        self.model = model
        self.trigger_key = trigger_key
        self._enabled = True
        self._state = "idle"

    def notify_state(self, state: str) -> None:
        self._state = state

    def notify_transcription_completed(self, text: str, duration: float, latency_ms: float) -> None:
        pass

    def notify_error(self, message: str, duration: float = 0.0, latency_ms: float = 0.0) -> None:
        pass

    def GetState(self) -> str:
        return self._state

    def GetLastTranscription(self) -> str:
        return ""

    def GetLastStats(self) -> str:
        return "{}"

    def GetHistory(self) -> str:
        return "[]"

    def GetStatus(self) -> str:
        return json.dumps({"state": self._state, "enabled": self._enabled})

    def SetEnabled(self, enabled: bool) -> bool:
        self._enabled = bool(enabled)
        return self._enabled

    def IsEnabled(self) -> bool:
        return self._enabled

    def GetConfiguration(self) -> str:
        return json.dumps({
            "endpoint_url": self.endpoint_url,
            "model": self.model,
            "trigger_key": self.trigger_key,
        })

    def UpdateConfiguration(self, endpoint_url: str, model: str, language: str, trigger_key: str, token: str) -> bool:
        try:
            from .config import DictateConfig, save_auth_token
            cfg = DictateConfig.load()
            cfg.endpoint_url = endpoint_url
            cfg.model = model
            cfg.language = language
            cfg.trigger_key = trigger_key
            cfg.save()
            if token:
                save_auth_token(token)
            return True
        except Exception:
            return False

    def TestConnection(self) -> str:
        return json.dumps({"ok": False, "message": "Daemon not running"})


class DBusPublisher:
    """Manages the lifecycle of the DBus service and GLib main loop in a background thread."""

    def __init__(self, endpoint_url: str = "", model: str = "", trigger_key: str = ""):
        self.endpoint_url = endpoint_url
        self.model = model
        self.trigger_key = trigger_key
        self.service: Any = None
        self._loop: Optional[Any] = None
        self._bus: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> Any:
        if not HAS_DASBUS:
            logger.info("dasbus or GLib not available; D-Bus service disabled.")
            self.service = DummyDBusService(self.endpoint_url, self.model, self.trigger_key)
            return self.service

        try:
            self.service = DictateDBusService(self.endpoint_url, self.model, self.trigger_key)
            self._bus = SessionMessageBus()
            self._bus.publish_object("/org/velma/Dictate", self.service)
            self._bus.register_service("org.velma.Dictate")

            self._loop = GLib.MainLoop()
            self._thread = threading.Thread(target=self._loop.run, name="velma-dbus-loop", daemon=True)
            self._thread.start()
            logger.info("D-Bus service org.velma.Dictate started successfully.")
            return self.service
        except Exception as e:
            logger.warning(f"Could not initialize D-Bus service: {e}. Continuing with dummy service.")
            self.service = DummyDBusService(self.endpoint_url, self.model, self.trigger_key)
            return self.service

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            try:
                self._loop.quit()
            except Exception:
                pass
        if self._bus:
            try:
                self._bus.disconnect()
            except Exception:
                pass
