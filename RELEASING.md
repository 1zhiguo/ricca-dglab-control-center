# Source publication and Firebase Hosting

## 1.0.1 hotkey update

Keep the frozen 1.0.0 ZIP/tag unchanged. 1.0.1 adds direct key-event recording,
single-key stop shortcuts, default Ctrl+F12 via a pass-through F12 observer, and
the penultimate onboarding step. Preserve saved user shortcuts on update.
Verify native observer installation/removal and registration conflicts, isolated
Qt key recording, onboarding save/failure, all unit tests and portable launch.

## 1.0.0 freeze

Run `tools/build_release.py` using the build Python with PyInstaller installed.
It emits a Windows x64 onedir ZIP, SHA-256, dependency versions, bundled source
and license notices. No game, user configuration or telemetry is included.
The frozen app is smoke-tested with isolated LOCALAPPDATA and --demo --no-socket.
Upload the exact ZIP to COS/Baidu; fill only their real HTTPS links in
website/dist/release-config.js. Never regenerate a published version in place.
The matching public-source commit/tag and release JSON must be retained.

The default global emergency hotkey is Ctrl+Alt+F10. Check native registration,
conflict fallback, unregister and direct mock zero without pumping the Qt loop.
Do not test QA hotkey messages against a physical-device callback.

The public source snapshot is separate from a developer checkout that may hold
the game, telemetry and unrelated projects. `tools/prepare_public_source.py`
copies a strict allowlist, creates a SHA-256 manifest and rejects secret/private
file patterns. It never deletes or uploads the developer's original files.

1. Run unit tests and `python website/check_site.py`.
2. Run `python tools/prepare_public_source.py` and inspect the exported manifest.
3. Initialize/commit only the resulting `public_repo/ricca-dglab-control-center`
   directory. Publish to `1zhiguo/ricca-dglab-control-center` without force-push.
4. For a manual website deploy, install Firebase CLI, sign in, then run
   `firebase deploy --only hosting --project ricca-dglab` from the public root.
   The explicit hosting site is `ricca-dglab`; never use Manaka's site ID.

`firebase.json` deploys only `website/dist/`, not Python code, test records,
credentials or downloadable desktop binaries. Keep package URLs disabled until
the actual audited package and checksum exist; a source archive is not an app
installer. Open-source publication does not mark physical-device testing complete.

The manual GitHub Actions workflow needs a least-privilege repository secret
`FIREBASE_SERVICE_ACCOUNT_RICCA_DGLAB`. This file contains only the secret's name,
never its value. Do not copy Manaka credentials or commit service-account keys.
Initial deployment can use the maintainer's existing local Firebase CLI login;
setting up CI deployment credentials is a separate step.
