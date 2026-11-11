import subprocess
import threading
from typing import Optional


class HoldRecorder:
    """Records from the default PipeWire source between start() and stop().

    One pw-record process per clip. stop() always terminates it, so no
    recorder outlives the key press that started it.
    """

    def __init__(self, sample_rate: int = 16000, max_seconds: float = 30.0):
        self.sample_rate = sample_rate
        self.max_bytes = int(sample_rate * 2 * max_seconds)
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._buffer = bytearray()
        self._lock = threading.Lock()

    @property
    def recording(self) -> bool:
        return self._process is not None

    def start(self) -> None:
        if self._process is not None:
            return
        self._buffer = bytearray()
        self._process = subprocess.Popen(
            ["pw-record", "--rate", str(self.sample_rate), "--channels", "1",
             "--format", "s16", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._reader = threading.Thread(target=self._read, args=(self._process,), daemon=True)
        self._reader.start()

    def _read(self, p: subprocess.Popen) -> None:
        assert p.stdout is not None
        while True:
            chunk = p.stdout.read1(4096)
            if not chunk:
                return
            with self._lock:
                room = self.max_bytes - len(self._buffer)
                self._buffer.extend(chunk[:max(room, 0)])

    def stop(self) -> bytes:
        p = self._process
        self._process = None
        if p is None:
            return b""
        p.terminate()
        try:
            p.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        if self._reader:
            self._reader.join(timeout=1.0)
            self._reader = None
        with self._lock:
            data = bytes(self._buffer)
            self._buffer = bytearray()
        # Keep whole 16-bit samples only.
        return data[: len(data) - (len(data) % 2)]
