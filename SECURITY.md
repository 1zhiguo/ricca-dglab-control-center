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

Only English game build 1.4.1 has been adapted. Do not disable its fingerprint
verification to run unverified offsets against a different game build.
