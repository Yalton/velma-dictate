import math
import struct
import pytest

from velma_dictate.vad import VoiceActivityDetector, calculate_rms

def generate_pcm_chunk(amplitude: int = 0, sample_count: int = 480) -> bytes:
    """Generates synthetic 16-bit mono PCM samples."""
    if amplitude == 0:
        return b"\x00" * (sample_count * 2)
    # Sine wave
    samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(sample_count)]
    return struct.pack(f"<{sample_count}h", *samples)

def test_calculate_rms():
    silence = generate_pcm_chunk(0)
    assert calculate_rms(silence) == 0.0

    loud = generate_pcm_chunk(10000)
    rms = calculate_rms(loud)
    assert rms > 6000

def test_vad_phrase_segmentation():
    # 30ms chunks, 0.6s silence = 20 chunks
    vad = VoiceActivityDetector(
        sample_rate=16000,
        chunk_ms=30,
        silence_seconds=0.3,  # 10 chunks silence to trigger phrase boundary
        min_speech_seconds=0.1,  # 4 chunks speech minimum
        threshold_multiplier=2.0
    )

    silence_chunk = generate_pcm_chunk(0)
    speech_chunk = generate_pcm_chunk(12000)

    # 1. Start with 15 frames of silence
    for _ in range(15):
        phrase = vad.process_chunk(silence_chunk)
        assert phrase is None

    # 2. Feed 10 frames of speech
    for _ in range(10):
        phrase = vad.process_chunk(speech_chunk)
        assert phrase is None  # Speech is still active

    # 3. Feed pause (silence) for 10 frames
    completed_phrase = None
    for _ in range(11):
        result = vad.process_chunk(silence_chunk)
        if result:
            completed_phrase = result
            break

    assert completed_phrase is not None
    assert len(completed_phrase) > 0

def test_vad_flush_speech():
    vad = VoiceActivityDetector(
        sample_rate=16000,
        chunk_ms=30,
        silence_seconds=1.0,
        min_speech_seconds=0.1
    )
    speech_chunk = generate_pcm_chunk(12000)

    # Feed 8 frames of speech
    for _ in range(8):
        vad.process_chunk(speech_chunk)

    # Flush manually
    flushed = vad.flush()
    assert flushed is not None
    assert len(flushed) > 0
