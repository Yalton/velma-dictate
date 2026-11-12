import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "velma-dictate"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "token"


@dataclass
class DictateConfig:
    endpoint_url: str = "http://192.168.50.210:8001/v1/audio/transcriptions"
    model: str = "parakeet"
    language: str = ""
    token_path: Path = DEFAULT_TOKEN_PATH
    sample_rate: int = 16000
    # Hold this key to record; release to transcribe and type once.
    trigger_key: str = "KEY_RIGHTCTRL"
    # Clips shorter than this are treated as an accidental tap and dropped.
    min_hold_seconds: float = 0.35
    silence_seconds: float = 15.0
    # RMS level in signed 16-bit PCM units.
    silence_threshold: float = 300.0
    transcription_timeout_seconds: Optional[float] = None
    # Upper bound on characters typed from one clip.
    max_output_chars: Optional[int] = None
    feedback_sound: bool = True

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "DictateConfig":
        path = config_path or DEFAULT_CONFIG_PATH
        cfg = cls()
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(cfg, k):
                    if k == "token_path":
                        v = Path(os.path.expanduser(v))
                    setattr(cfg, k, v)
        return cfg

    def save(self, config_path: Optional[Path] = None) -> None:
        path = config_path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = {
            "endpoint_url": self.endpoint_url,
            "model": self.model,
            "language": self.language,
            "token_path": str(self.token_path),
            "sample_rate": self.sample_rate,
            "trigger_key": self.trigger_key,
            "min_hold_seconds": self.min_hold_seconds,
            "silence_seconds": self.silence_seconds,
            "silence_threshold": self.silence_threshold,
            "transcription_timeout_seconds": self.transcription_timeout_seconds,
            "max_output_chars": self.max_output_chars,
            "feedback_sound": self.feedback_sound,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(path, 0o600)


def save_auth_token(token: str, token_path: Optional[Path] = None) -> None:
    path = token_path or DEFAULT_TOKEN_PATH
    path = Path(os.path.expanduser(str(path)))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "w", encoding="utf-8") as f:
        f.write(token.strip())
    os.chmod(path, 0o600)


def load_auth_token(token_path: Path) -> str:
    path = Path(os.path.expanduser(str(token_path)))
    if not path.is_file():
        raise FileNotFoundError(f"Auth token file not found at {path}")

    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(
            f"Insecure permissions on token file {path}: must be mode 0600 (chmod 600 {path})"
        )

    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()

    if not token:
        raise ValueError(f"Auth token file {path} is empty")

    return token
