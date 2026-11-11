import os
import stat
import tempfile
import pytest
from pathlib import Path

from velma_dictate.config import DictateConfig, load_auth_token

def test_dictate_config_defaults():
    cfg = DictateConfig()
    assert cfg.model == "parakeet"
    assert "8001" in cfg.endpoint_url
    assert cfg.sample_rate == 16000
    assert cfg.vad_silence_seconds == 0.6

def test_load_auth_token_success():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("my-secret-test-token\n")
        tf.flush()
        token_path = Path(tf.name)

    try:
        os.chmod(token_path, 0o600)
        token = load_auth_token(token_path)
        assert token == "my-secret-test-token"
    finally:
        os.unlink(token_path)

def test_load_auth_token_insecure_permissions():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("my-secret-test-token\n")
        tf.flush()
        token_path = Path(tf.name)

    try:
        # Give group and other read permissions (0644)
        os.chmod(token_path, 0o644)
        with pytest.raises(PermissionError) as exc_info:
            load_auth_token(token_path)
        assert "Insecure permissions" in str(exc_info.value)
    finally:
        os.unlink(token_path)

def test_load_auth_token_missing():
    fake_path = Path("/tmp/nonexistent-token-file-xyz")
    with pytest.raises(FileNotFoundError):
        load_auth_token(fake_path)
