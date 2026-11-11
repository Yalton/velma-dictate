import io
import subprocess
import wave
from typing import Generator, Optional

def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Encodes raw 16-bit PCM bytes into a standard WAV audio container in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

class PipeWireAudioStream:
    def __init__(self, sample_rate: int = 16000, chunk_ms: int = 30):
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        # 16kHz * 2 bytes/sample * (chunk_ms / 1000)
        self.samples_per_chunk = int(sample_rate * (chunk_ms / 1000.0))
        self.bytes_per_chunk = self.samples_per_chunk * 2
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> Generator[bytes, None, None]:
        cmd = [
            "pw-record",
            "--rate", str(self.sample_rate),
            "--channels", "1",
            "--format", "s16",
            "-"
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.bytes_per_chunk * 4
        )
        assert self.process.stdout is not None
        try:
            while True:
                chunk = self.process.stdout.read(self.bytes_per_chunk)
                if not chunk:
                    break
                if len(chunk) == self.bytes_per_chunk:
                    yield chunk
        finally:
            self.stop()

    def stop(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
