import collections
import math
import struct
from typing import Generator, List, Optional

def calculate_rms(chunk: bytes) -> float:
    """Computes the root-mean-square amplitude of 16-bit mono PCM audio."""
    count = len(chunk) // 2
    if count == 0:
        return 0.0
    # Unpack 16-bit signed integers
    shorts = struct.unpack(f"<{count}h", chunk)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

class VoiceActivityDetector:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_ms: int = 30,
        silence_seconds: float = 0.6,
        threshold_multiplier: float = 2.2,
        min_speech_seconds: float = 0.35,
        max_speech_seconds: float = 30.0,
        pre_speech_ms: int = 300
    ):
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.threshold_multiplier = threshold_multiplier
        self.min_speech_chunks = max(1, int((min_speech_seconds * 1000) / chunk_ms))
        self.max_silence_chunks = max(1, int((silence_seconds * 1000) / chunk_ms))
        self.max_speech_chunks = int((max_speech_seconds * 1000) / chunk_ms)
        self.pre_speech_chunks_count = max(1, int(pre_speech_ms / chunk_ms))

        self.pre_buffer: collections.deque = collections.deque(maxlen=self.pre_speech_chunks_count)
        self.current_utterance: List[bytes] = []

        self.in_speech: bool = False
        self.silence_count: int = 0
        self.speech_chunk_count: int = 0

        # Adaptive noise floor baseline
        self.noise_floor: float = 150.0  # Safe initial baseline for typical mic in quiet room
        self.min_absolute_threshold: float = 300.0  # Ignore micro-noise below this level

    def process_chunk(self, chunk: bytes) -> Optional[bytes]:
        """
        Processes a single audio chunk.
        Returns complete phrase PCM bytes if a phrase boundary was detected, else None.
        """
        rms = calculate_rms(chunk)
        threshold = max(self.noise_floor * self.threshold_multiplier, self.min_absolute_threshold)

        if not self.in_speech:
            if rms > threshold:
                # Speech started
                self.in_speech = True
                self.silence_count = 0
                self.speech_chunk_count = 0
                self.current_utterance = list(self.pre_buffer)
                self.current_utterance.append(chunk)
                self.pre_buffer.clear()
            else:
                # Still silence: adapt noise floor slowly (alpha = 0.05)
                self.noise_floor = 0.95 * self.noise_floor + 0.05 * max(rms, 50.0)
                self.pre_buffer.append(chunk)
            return None
        else:
            # Currently accumulating speech
            self.current_utterance.append(chunk)
            self.speech_chunk_count += 1

            if rms > threshold * 0.8:  # Hysteresis for keeping speech active
                self.silence_count = 0
            else:
                self.silence_count += 1

            # Check for phrase completion on pause or max duration
            pause_reached = self.silence_count >= self.max_silence_chunks
            max_duration_reached = self.speech_chunk_count >= self.max_speech_chunks

            if pause_reached or max_duration_reached:
                phrase_pcm = b"".join(self.current_utterance)
                is_valid_length = self.speech_chunk_count >= self.min_speech_chunks

                # Reset state
                self.in_speech = False
                self.silence_count = 0
                self.speech_chunk_count = 0
                self.current_utterance = []
                self.pre_buffer.clear()

                if is_valid_length:
                    return phrase_pcm
            return None

    def flush(self) -> Optional[bytes]:
        """Flushes any remaining speech upon manual stop."""
        if self.in_speech and self.speech_chunk_count >= self.min_speech_chunks:
            phrase_pcm = b"".join(self.current_utterance)
            self.in_speech = False
            self.current_utterance = []
            return phrase_pcm
        self.in_speech = False
        self.current_utterance = []
        return None
