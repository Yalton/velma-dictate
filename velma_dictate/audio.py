import io
import wave

def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Encodes raw 16-bit PCM bytes into a standard WAV audio container in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()
