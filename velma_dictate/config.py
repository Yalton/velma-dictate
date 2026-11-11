import os
import json
import stat
from dataclasses import dataclass, field
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
    chunk_ms: int = 30
    vad_silence_seconds: float = 0.6
    vad_threshold_multiplier: float = 2.2
    min_speech_seconds: float = 0.35
    max_speech_seconds: float = 30.0
    feedback_sound: bool = True
    feedback_notify: bool = True
    typing_method: str = "uinput"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "DictateConfig":
        path = config_path or DEFAULT_CONFIG_PATH
        cfg = cls()
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        if k == "token_path":
                            v = Path(os.path.expanduser(v))
                        setattr(cfg, k, v)
            except Exception as e:
                # Log error without exposing any sensitive details
                pass
        return cfg

def load_auth_token(token_path: Path) -> str:
    """
    Reads bearer token from a secure mode-600 / mode-400 file.
    Enforces strict permissions: refuses to read if group or others have read/write access.
    Never prints or logs the token.
    """
    path = Path(os.path.expanduser(str(token_path)))
    if not path.is_file():
        # Fallback check for ~/.config/speech-token
        alt_path = Path.home() / ".config" / "speech-token"
        if alt_path.is_file():
            path = alt_path
        else:
            raise FileNotFoundError(f"Auth token file not found at {path}")

    # Check file permissions (must be mode 0600, 0400, or strict user-only)
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
