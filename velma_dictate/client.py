import requests
from typing import Optional

class WhisperClient:
    def __init__(
        self,
        endpoint_url: str,
        token: str,
        model: str = "parakeet",
        language: str = "",
        timeout_seconds: Optional[float] = None
    ):
        self.endpoint_url = endpoint_url
        self.token = token
        self.model = model
        self.language = language
        self.timeout = timeout_seconds

    def transcribe(self, wav_bytes: bytes) -> str:
        """
        Sends WAV audio to the OpenAI-compatible endpoint.
        Returns the transcribed text string.
        """
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        files = {
            "file": ("phrase.wav", wav_bytes, "audio/wav")
        }
        data = {
            "model": self.model,
            "response_format": "json"
        }
        if self.language:
            data["language"] = self.language

        resp = requests.post(
            self.endpoint_url,
            headers=headers,
            files=files,
            data=data,
            timeout=(10.0, self.timeout)
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Transcription failed with status {resp.status_code}: {resp.text[:200]}")

        # Check for JSON response vs raw text
        try:
            res_json = resp.json()
            if isinstance(res_json, dict) and "text" in res_json:
                return str(res_json["text"]).strip()
        except Exception:
            pass

        return resp.text.strip()

    def test_connection(self) -> bool:
        """
        Tests connection to the service without uploading real speech.
        Tries /v1/test/ on the same base host/port, or falls back to an options/get request.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        base_url = self.endpoint_url.split("/v1/")[0]
        test_url = f"{base_url}/v1/test/"
        try:
            r = requests.post(test_url, headers=headers, timeout=3.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        # Fallback probe
        try:
            r = requests.get(f"{base_url}/docs", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False
