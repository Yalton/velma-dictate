import io
import struct

from velma_dictate.recorder import HoldRecorder


class AudioPipe(io.BytesIO):
    def read1(self, size):
        return self.read(min(size, 997))  # include partial samples/windows


class Process:
    def __init__(self, data):
        self.stdout = AudioPipe(data)


def test_long_audio_is_preserved_and_silence_resets():
    rec = HoldRecorder()
    speech = struct.pack('<h', 1200) * (16000 * 40)
    silence = b'\0' * (16000 * 2 * 15)
    data = speech + silence + speech + silence
    rec._read(Process(data))
    assert bytes(rec._buffer) == data
    assert rec.silent_seconds == 15
    rec._read(Process(speech))
    assert rec.silent_seconds == 0
