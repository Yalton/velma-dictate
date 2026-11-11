import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .audio import PipeWireAudioStream, pcm_to_wav_bytes
from .client import WhisperClient
from .config import DictateConfig, load_auth_token
from .feedback import notify_started, notify_stopped
from .typer import WaylandTyper
from .vad import VoiceActivityDetector

SOCKET_PATH = Path(f"/run/user/{os.getuid()}/velma-dictate.sock")

def is_running() -> bool:
    if not SOCKET_PATH.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(str(SOCKET_PATH))
            s.sendall(b"PING\n")
            data = s.recv(1024)
            return b"PONG" in data
    except Exception:
        # Stale socket
        try:
            SOCKET_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        return False

def stop_running_session() -> bool:
    if not SOCKET_PATH.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(str(SOCKET_PATH))
            s.sendall(b"STOP\n")
            data = s.recv(1024)
            return b"OK" in data
    except Exception:
        try:
            SOCKET_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        return False

class DictationDaemon:
    def __init__(self, config: DictateConfig):
        self.config = config
        self.stop_event = threading.Event()
        self.typer: Optional[WaylandTyper] = None
        self.stream: Optional[PipeWireAudioStream] = None
        self.server_socket: Optional[socket.socket] = None

    def _socket_listener(self) -> None:
        while not self.stop_event.is_set():
            try:
                conn, _ = self.server_socket.accept()
                with conn:
                    conn.settimeout(1.0)
                    line = conn.recv(1024).strip()
                    if line == b"PING":
                        conn.sendall(b"PONG\n")
                    elif line == b"STOP":
                        conn.sendall(b"OK\n")
                        self.stop_event.set()
                        if self.stream:
                            self.stream.stop()
                        break
                    elif line == b"STATUS":
                        conn.sendall(b"RECORDING\n")
            except Exception:
                break

    def run(self) -> None:
        # Ensure only one instance runs
        if is_running():
            print("Another dictation session is already running.")
            return

        # Prepare control socket
        SOCKET_PATH.unlink(missing_ok=True)
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(SOCKET_PATH))
        self.server_socket.listen(1)
        self.server_socket.settimeout(0.5)

        sock_thread = threading.Thread(target=self._socket_listener, daemon=True)
        sock_thread.start()

        # Load auth token
        try:
            token = load_auth_token(self.config.token_path)
        except Exception as e:
            notify_stopped(sound=False, visual=True)
            print(f"Error loading auth token: {e}", file=sys.stderr)
            SOCKET_PATH.unlink(missing_ok=True)
            return

        client = WhisperClient(
            endpoint_url=self.config.endpoint_url,
            token=token,
            model=self.config.model,
            language=self.config.language
        )
        self.typer = WaylandTyper()
        vad = VoiceActivityDetector(
            sample_rate=self.config.sample_rate,
            chunk_ms=self.config.chunk_ms,
            silence_seconds=self.config.vad_silence_seconds,
            threshold_multiplier=self.config.vad_threshold_multiplier,
            min_speech_seconds=self.config.min_speech_seconds,
            max_speech_seconds=self.config.max_speech_seconds
        )
        self.stream = PipeWireAudioStream(
            sample_rate=self.config.sample_rate,
            chunk_ms=self.config.chunk_ms
        )

        notify_started(self.config.feedback_sound, self.config.feedback_notify)
        print("Dictation started. Listening...")

        try:
            for chunk in self.stream.start():
                if self.stop_event.is_set():
                    break

                phrase_pcm = vad.process_chunk(chunk)
                if phrase_pcm:
                    # Phrase boundary detected on pause!
                    wav_bytes = pcm_to_wav_bytes(phrase_pcm, self.config.sample_rate)
                    try:
                        text = client.transcribe(wav_bytes)
                        if text:
                            self.typer.type_text(text)
                    except Exception as e:
                        print(f"Transcription error: {e}", file=sys.stderr)

            # Flush any pending audio when stopped
            final_pcm = vad.flush()
            if final_pcm and not self.stop_event.is_set():
                wav_bytes = pcm_to_wav_bytes(final_pcm, self.config.sample_rate)
                try:
                    text = client.transcribe(wav_bytes)
                    if text:
                        self.typer.type_text(text)
                except Exception:
                    pass

        finally:
            notify_stopped(self.config.feedback_sound, self.config.feedback_notify)
            print("Dictation stopped.")
            if self.typer:
                self.typer.close()
            if self.stream:
                self.stream.stop()
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass
            SOCKET_PATH.unlink(missing_ok=True)
