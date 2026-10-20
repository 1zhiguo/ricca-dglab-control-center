# Source publication and Firebase Hosting

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
