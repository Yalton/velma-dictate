import argparse
import sys
from pathlib import Path

from .client import WhisperClient
from .config import DictateConfig, load_auth_token
from .daemon import DictationDaemon, is_running, stop_running_session

def main() -> None:
    parser = argparse.ArgumentParser(description="Velma System-Wide Wayland Dictation")
    parser.add_argument(
        "action",
        nargs="?",
        default="toggle",
        choices=["toggle", "start", "stop", "status", "test"],
        help="Action to perform (default: toggle)"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to custom config.json"
    )

    args = parser.parse_args()
    cfg = DictateConfig.load(args.config)

    if args.action == "status":
        if is_running():
            print("Status: RECORDING")
            sys.exit(0)
        else:
            print("Status: STOPPED")
            sys.exit(0)

    elif args.action == "stop":
        if is_running():
            stop_running_session()
            print("Stopped dictation session.")
        else:
            print("No active dictation session.")
        sys.exit(0)

    elif args.action == "start":
        if is_running():
            print("Dictation is already running.")
            sys.exit(0)
        daemon = DictationDaemon(cfg)
        daemon.run()

    elif args.action == "toggle":
        if is_running():
            stop_running_session()
            print("Dictation toggled OFF.")
        else:
            daemon = DictationDaemon(cfg)
            daemon.run()

    elif args.action == "test":
        print(f"Testing connection to endpoint: {cfg.endpoint_url}")
        try:
            token = load_auth_token(cfg.token_path)
            client = WhisperClient(cfg.endpoint_url, token, model=cfg.model)
            ok = client.test_connection()
            if ok:
                print("✓ Connection successful: Whisper API endpoint is responsive.")
                sys.exit(0)
            else:
                print("✗ Failed to verify responsiveness from Whisper API endpoint.", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"✗ Test failed: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
