# Velma Dictate

System-wide voice dictation for Fedora / GNOME on Wayland using the self-hosted speech service on MLBox (`http://192.168.50.210:8001`, model `parakeet`).

## Features

- **Wayland Native**: Works with GNOME Wayland via `/dev/uinput` virtual keyboard typing and `wl-copy` clipboard fallback.
- **Phrase by Phrase**: Continuous Voice Activity Detection (VAD) detects speech pauses (~0.6s) and uploads individual phrases.
- **Privacy & Security**: Token is read from a mode `0600` file (`~/.config/velma-dictate/token`). Never logged or printed.
- **Audio Feedback**: Subtle chimes when toggling on/off (`pw-play`) and desktop notifications (`notify-send`).
- **Global Hotkey Integration**: Binds cleanly to GNOME media-keys / custom shortcuts.

## Usage

```bash
velma-dictate toggle   # Start or stop dictation
velma-dictate start    # Start listening
velma-dictate stop     # Stop listening
velma-dictate status   # Print RECORDING or STOPPED
velma-dictate test     # Test connection to MLBox endpoint
```

## Configuration

Config file: `~/.config/velma-dictate/config.json`
Token file: `~/.config/velma-dictate/token` (mode `0600`)
Control socket: `/run/user/<uid>/velma-dictate.sock`
