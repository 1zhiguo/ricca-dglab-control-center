# User guide

[中文](USAGE.zh-CN.md) · [Back to README](../README.md)

## Setup and pairing

- Windows x64. Extract the full portable ZIP; keep `_internal` next to the EXE. Do not put the companion inside the game folder. Close the old app before upgrading.
- The tutorial covers overview, pairing, intensity profiles, channel strategies, key recording and the final manually entered safety cap (0–100). A cap of 0 disables output.
- In **Device & game**, select a LAN IPv4 reachable by your phone. Pair through DG-LAB 3.0 App's Socket mode. Use **Cannot connect?** for port, VPN, adapter and Wi-Fi isolation diagnostics.
- Auto-detection looks for `HolyKnightRicca.exe`. If it fails, select the game EXE in the app. Its directory may contain Chinese or Japanese characters; the build fingerprint must still match.

## Output rules

- Each channel has separate **Combat** and **Story/gallery** categories in Waveform studio → Channel strategy.
- Combat can use HP damage, action feedback, both or neither. Configure event strength, waveform and duration independently. HP thresholds use absolute lost HP, not percentages.
- Ordinary hits support 0.1–3 seconds, death up to 10 seconds, armor-break feedback up to 5 seconds. Sustained capture lasts until escape; it has no editable duration. Guarding alone produces no punishment.
- Overlapping ordinary events do not add: the stronger takes over, equal strength refreshes duration, and weaker events are ignored. Channels arbitrate independently.
- The first detected armor break applies a fixed ×1.2 boost for that life, not stacking stages. Respawn or re-entering gameplay resets it. The final result remains capped.
- Death feedback requires actual death evidence, not merely entering a gallery scene. It has priority over ordinary pauses but **never over Emergency Zero or output safety gates**. Pairing, valid telemetry, a supported build, tutorial completion and the hard cap still apply.

## Story, gallery and audio

- Per channel, choose fixed wave, playlist, audio, fixed + audio, playlist + audio, or off. Registered story/gallery scenes do not require a combat death to loop.
- The story tab edits per-channel playlists: wave, strength and duration for every step. Exit stops the scene output; pauses freeze playlist progress rather than catching up later.
- Enable capture separately on the Audio sync page. Choose system loopback for game sound. It measures **all sound from that output device**, not isolated character speech; BGM and other apps may affect it. No recordings are stored.
- Gain adjusts the audio intensity mapping. **Playlist + audio** can retain a user-set minimum intensity during valid quiet gaps; it does not override muted gain, explicit rest steps, disabled capture, invalid audio, pauses or the hard cap.
- A scene missing from the catalog may need recording and explicit registration. Scene names alone are not proof that device commands are being sent; check the connection and diagnostic status.

## Pause and emergency stop

**Ctrl+F12** is the default global emergency shortcut for new configurations. In Intensity range → Emergency hotkey, select **Record keys**, then press a key or chord. Single keys such as Pause and F10 work; avoid normal game/typing keys. Esc cancels recording.

Recording or saving first emergency-stops output. The penultimate tutorial page also saves the shortcut. Existing saved shortcuts survive updates. A failed registration/save preserves the old setting.

Emergency Zero clears both channels and locks output. Repeated presses, reconnects and settings saves do not resume it; use the app's Resume control deliberately. F12 uses a pass-through observer, so other apps may also react to it. No global shortcut can guarantee operation during OS or device failure.

## Saved settings and updates

Settings: `%LOCALAPPDATA%\Ricca-x-DGlab\settings.json`

Custom waves: `%LOCALAPPDATA%\Ricca-x-DGlab\waveforms\`

Updates preserve these user files. Do not distribute your personal settings as an app default. Saving uses atomic replacement and retains a last-known-good backup. See [migration and logs](../DIAGNOSTICS.md#configuration-compatibility).

UI language changes only interface text, not waveform keys, detection hashes or channel settings. Chinese/English/Japanese UI support is separate from game-build compatibility.

## Supported build and troubleshooting

Verified Ricca 1.4.1 Chinese/English builds share this `GameAssembly.dll` SHA-256:

```text
5D815721F6B45251137DC8AB78446FAA3A79CFC3BC0520FC4D8EB8C872BDB52B
```

Other versions, modified binaries or mods are not guaranteed. Do not disable fingerprint checks to make an unsupported build run. HUD requires windowed/borderless mode if exclusive fullscreen hides the overlay.

For no output, check pairing, saved cap, tutorial completion, app emergency/pause state, game detection and scene strategy. Use [diagnostics](../DIAGNOSTICS.md) and redact logs before sharing; never post pairing tokens or personal paths. Report safety issues via [SECURITY.md](../SECURITY.md).

Implementation: [safety gates](../src/ricca_dglab/safety.py), [event mapping](../src/ricca_dglab/mapping.py), [death/scene tracking](../src/ricca_dglab/defeat_scene.py), [Socket output](../src/ricca_dglab/dglab_bridge.py).
