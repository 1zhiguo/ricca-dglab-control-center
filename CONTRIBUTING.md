# Contributing

Ricca × DG-LAB is a standalone, read-only Windows companion. Contributions to the
project's code are accepted under GPL-3.0-only. Third-party artwork and trademarks
are not relicensed by this project; see `THIRD_PARTY_NOTICES.md`.

## Local development

1. Install Python 3.11 on Windows, then run `setup_native.ps1`.
2. Run `run_native.ps1 --demo` for a simulated UI without game access/device output.
3. Set `PYTHONPATH=src` and run `.venv/Scripts/python.exe -m unittest discover -s tests`.
4. Run `.venv/Scripts/python.exe website/check_site.py` for static-site checks.

UI verification scripts use simulated telemetry and must not connect to real
devices. Create an empty `artifacts/` directory before running `tests/verify_*.py`;
the generated screenshots are not committed. Local game recordings are optional,
excluded from publication, and associated replay tests skip when absent.

Do not commit games, generated game assemblies, saves, user settings, recordings,
API tokens, service-account keys, private source folders or local environment paths.
Do not bypass build fingerprints, hard caps, telemetry freshness, or the emergency
stop latch. Changes to output arbitration need tests for both channels, death
priority, manual pause, disconnect, invalid reads and emergency zero.

For reports, include the app version, exact game build, steps and a redacted error.
Never post device pairing identifiers or unredacted telemetry/configuration.
