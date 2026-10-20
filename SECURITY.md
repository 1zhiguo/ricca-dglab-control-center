# Security and output-safety reporting

This software controls a physical electrical-stimulation device. A software hard
cap is a numerical limit, not a guarantee of safe sensation or physical safety.
Follow the device manufacturer's instructions and start with low settings.

Death feedback deliberately outranks ordinary game/app pauses. Use **Emergency
Zero** to stop all output. Disconnect, unsupported builds, invalid/stale telemetry,
zero hard cap and incomplete onboarding must still block device commands.

Please report safety/output defects promptly with reproduction steps and a
redacted diagnostic. If a defect exposes credentials or permits remote control,
use GitHub private vulnerability reporting if available; otherwise contact the
maintainer through the profile linked in the README without publishing exploit
details or secrets in a public issue. Do not test an exploit on a person/device.

English and Chinese 1.4.1 with the verified identical core fingerprint are supported. Do not disable fingerprint
verification to run unverified offsets against a different game build.

Ctrl+F12 is the default global Emergency Zero chord from 1.0.1. Single keys and
press-to-record customization are supported. Saved shortcuts are preserved on upgrade.
F12 uses a pass-through keyboard observer because Windows reserves F12 for debuggers;
it does not suppress game input or store typed text. It can be changed in
Intensity Range. RegisterHotKey conflicts are reported; the F12 observer cannot
claim exclusive ownership and other apps may also react to that chord.
An independent Win32 message thread asks the Socket thread to zero before
notifying Qt; it is not a guarantee against OS/device failure or disconnected
transport. Shutdown requests zero before waiting for audio/telemetry cleanup.
