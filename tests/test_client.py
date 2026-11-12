import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytest

from velma_dictate.client import WhisperClient

class FakeWhisperHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging in test output
        pass

    def do_POST(self):
        auth = self.headers.get("Authorization", "")
        if auth != "Bearer test-secret-token":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        if self.path == "/v1/test/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"message": "ok"}')
            return

        if "/v1/audio/transcriptions" in self.path:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Check for multipart boundary and form field 'parakeet'
            if b'name="model"' in body and b"parakeet" in body:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"text": "Hello world from test server."}')
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing model=parakeet")
            return

        self.send_response(404)
        self.end_headers()

@pytest.fixture(scope="module")
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), FakeWhisperHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()

def test_transcribe_with_fake_server(fake_server):
    endpoint = f"{fake_server}/v1/audio/transcriptions"
    client = WhisperClient(endpoint_url=endpoint, token="test-secret-token", model="parakeet")
    fake_wav = b"RIFF....WAVEfmt ...."
    text = client.transcribe(fake_wav)
    assert text == "Hello world from test server."

def test_transcribe_unauthorized(fake_server):
    endpoint = f"{fake_server}/v1/audio/transcriptions"
    client = WhisperClient(endpoint_url=endpoint, token="wrong-token", model="parakeet")
    with pytest.raises(RuntimeError) as exc_info:
        client.transcribe(b"fake-wav")
    assert "401" in str(exc_info.value)

def test_connection_test(fake_server):
    endpoint = f"{fake_server}/v1/audio/transcriptions"
    client = WhisperClient(endpoint_url=endpoint, token="test-secret-token")
    assert client.test_connection() is True


def test_waits_past_old_timeout_for_cold_load():
    import time

    class ColdHandler(FakeWhisperHandler):
        def do_POST(self):
            time.sleep(8.2)
            super().do_POST()

    server = HTTPServer(('127.0.0.1', 0), ColdHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WhisperClient(
            f'http://127.0.0.1:{server.server_port}/v1/audio/transcriptions',
            'test-secret-token')
        assert client.transcribe(b'RIFF test') == 'Hello world from test server.'
    finally:
        server.shutdown()
        server.server_close()
