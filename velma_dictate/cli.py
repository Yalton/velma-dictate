import argparse
import subprocess
import sys
from pathlib import Path

from .client import WhisperClient
from .config import DictateConfig, load_auth_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Velma push-to-talk dictation: hold the trigger key, speak, release.")
    parser.add_argument("action", choices=["listen", "stop", "test"],
                        help="listen: run the hotkey listener (normally via the systemd user "
                             "service); stop: stop the service; test: check the endpoint")
    parser.add_argument("--config", "-c", type=Path, default=None)
    args = parser.parse_args()
    cfg = DictateConfig.load(args.config)

    if args.action == "listen":
        from .ptt import run_listener
        sys.exit(run_listener(cfg))

    if args.action == "stop":
        subprocess.run(["systemctl", "--user", "stop", "velma-dictate.service"])
        subprocess.run(["pkill", "-f", "velma_dictate.cli listen"])
        sys.exit(0)

    if args.action == "test":
        print(f"Testing endpoint: {cfg.endpoint_url}")
        try:
            token = load_auth_token(cfg.token_path)
            ok = WhisperClient(cfg.endpoint_url, token, model=cfg.model).test_connection()
        except Exception as e:
            print(f"Test failed: {e}", file=sys.stderr)
            sys.exit(1)
        print("Endpoint OK" if ok else "Endpoint did not respond")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
