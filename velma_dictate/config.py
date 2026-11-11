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
    # Recording stops by itself after this long, even if the key is still held.
    max_hold_seconds: float = 30.0
    # Upper bound on characters typed from one clip.
    max_output_chars: int = 2000
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
