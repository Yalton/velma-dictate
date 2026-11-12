# velma-dictate

Push-to-talk dictation for GNOME on Wayland, using the Parakeet/Whisper
endpoint on mlbox (`http://192.168.50.210:8001/v1/audio/transcriptions`).

**Hold Right Ctrl, speak, release.** The clip is transcribed once and typed
once into the focused window. Nothing listens unless the key is held.

- Right Ctrl used as a shortcut (Right Ctrl+C, etc.) cancels the clip.
- Esc while text is being typed stops the typing.
- Recording has no duration cap and stops after 15 seconds of silence; the text is typed when you release the key.
- A press while the previous clip is still being typed plays a warning sound and is ignored.
- Only one listener can run (lock at `/run/user/$UID/velma-dictate.lock`).

## Running

Runs as a systemd user service:

    systemctl --user status velma-dictate
    systemctl --user stop velma-dictate      # turn off
    systemctl --user disable --now velma-dictate   # turn off for good
    journalctl --user -u velma-dictate -f    # logs

Unit file: `systemd/velma-dictate.service`, symlinked into `~/.config/systemd/user/`.
Launcher: `~/.local/bin/velma-dictate` (`listen`, `stop`, `test`).

Reading the physical keyboard relies on the logind `uaccess` ACL on its
`/dev/input/event*` node; typing goes through a `/dev/uinput` virtual keyboard
named `velma-dictate-keyboard`, which the listener ignores.

## Config

`~/.config/velma-dictate/config.json` (mode 0600): `trigger_key` (evdev name,
default `KEY_RIGHTCTRL`), `min_hold_seconds`, `silence_seconds` (default 15), `silence_threshold` (16-bit RMS, default 300),
`transcription_timeout_seconds` (default null: wait for model loading and transcription),
`max_output_chars` (default null: unlimited), `feedback_sound`, `endpoint_url`, `model`, `language`.
Bearer token: `~/.config/velma-dictate/token` (mode 0600).

## Tests

    python3 -m pytest -q tests

Legacy `max_hold_seconds` settings are ignored. The HTTP connection timeout is
10 seconds; the response wait is unlimited by default so cold model loads can finish.
