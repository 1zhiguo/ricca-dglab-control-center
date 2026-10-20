# Ricca × DG-LAB Control Center

[简体中文](README.zh-CN.md) · English · [Website](https://ricca-dglab.web.app) · [Game Dashboard](https://dglab-x-game.web.app)

A standalone Windows companion that synchronizes **Holy Knight Ricca** with DG-LAB.
Reads game state externally: **no BepInEx, DLL injection, game-file changes or memory writes**.

## Features

- HP damage, hit reactions, armor break, sustained capture/struggle and death feedback.
- Independent A/B combat and story/gallery strategies: fixed wave, playlist, audio, or combined modes.
- Official waveform presets, a custom waveform editor, live monitors and an in-game HUD.
- DG-LAB Socket QR pairing, network-adapter selection and connection diagnostics.
- Chinese, English and Japanese UI. Global emergency stop: **Ctrl+F12** by default, with press-to-record and single-key support.

## Quick start

1. Get the Windows ZIP from the [website](https://ricca-dglab.web.app/#downloads) when a download link is available. Extract the **entire folder**, then run `Ricca-x-DGlab.exe`. No Python installation needed.
2. Complete the tutorial and manually set a conservative safety cap.
3. Start a supported game build. Connect the phone and PC to the same LAN, then scan the QR code using DG-LAB 3.0 App's Socket mode.

Once paired, valid game state drives output automatically. Pause first if you do not want immediate output.

**Emergency stop zeros and locks both channels; pressing again does not resume.**
Death feedback can override ordinary pauses. Resume manually only when ready.
Software limits do **not** guarantee physical safety. The Windows package is unsigned.

## Compatibility and documentation

Windows x64; verified Ricca **1.4.1 Chinese/English builds** only.
Game updates, mods or different binaries may invalidate detection.

- [Setup, output rules, scene/audio modes and configuration](docs/USAGE.md)
- [Supported build fingerprint and troubleshooting](docs/USAGE.md#supported-build-and-troubleshooting)
- [Run from source and contribute](CONTRIBUTING.md)
- [Build and publish](RELEASING.md) · [Safety reporting](SECURITY.md)

Current source version: **1.0.1**. Download mirrors are added separately; GitHub's automatic “Source code” ZIP is not the Windows app.

## License

[GPL-3.0-only](LICENSE). No game files, saves, personal settings or telemetry are distributed.
Third-party artwork and trademarks retain their original rights; see [third-party notices](THIRD_PARTY_NOTICES.md).
