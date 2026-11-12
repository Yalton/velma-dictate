import array
import sys
import subprocess
import threading
from typing import Optional


class HoldRecorder:
    """Records from the default PipeWire source between start() and stop().

    One pw-record process per clip. stop() always terminates it, so no
    recorder outlives the key press that started it.
    """

    def __init__(self, sample_rate: int = 16000, silence_threshold: float = 300.0):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self._silent_samples = 0
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._buffer = bytearray()
        self._lock = threading.Lock()

    @property
    def silent_seconds(self) -> float:
        with self._lock:
            return self._silent_samples / self.sample_rate

    @property
    def recording(self) -> bool:
        return self._process is not None

    def start(self) -> None:
        if self._process is not None:
            return
        self._buffer = bytearray()
        self._silent_samples = 0
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
        pending = b""
        while True:
            chunk = p.stdout.read1(4096)
            if not chunk:
                return
            pending += chunk
            # Fixed 20 ms windows make detection independent of pipe read sizes.
            window_bytes = max(2, int(self.sample_rate * 0.02) * 2)
            with self._lock:
                self._buffer.extend(chunk)
                while len(pending) >= window_bytes:
                    samples = array.array("h", pending[:window_bytes])
                    if sys.byteorder != "little":
                        samples.byteswap()
                    rms = (sum(x * x for x in samples) / len(samples)) ** 0.5
                    if rms < self.silence_threshold:
                        self._silent_samples += len(samples)
                    else:
                        self._silent_samples = 0
                    pending = pending[window_bytes:]

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
