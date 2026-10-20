# Ricca × DG-LAB website

Buildless static website in `dist/`, inspired by the Manaka product-site structure.
The desktop companion remains independent; the website does not connect to a device.

- `dist/index.html`: Manaka-family landing-page layout, Chinese/English copy, download-source menu,
  compact two-column features, three download channels and full-width screenshot gallery.
- `dist/manaka-layout.css`: layout measurements based on the local Manaka reference
  (1120px shell, 72px header, large product title, section spacing and mobile breakpoints).
- `dist/guide.html`: connection guide, compatibility, first-test checklist, troubleshooting.
- `dist/release-config.js`: set actual HTTPS package URLs only after publishing real Ricca files.
- `dist/assets/`: existing Ricca branding, simulated desktop screenshots and mobile connection guide.
- `.openai/hosting.json`: retains this independent Site's identity. Do not reuse the Manaka ID.
- `../firebase.json`: public Firebase Hosting deploy, restricted to `website/dist` and site `ricca-dglab`.
- `../.firebaserc`: the independent `ricca-dglab` Firebase project, never the Manaka project.

Public packages are deliberately unavailable until configured. No game files, telemetry recordings,
user configuration, device commands, tracking scripts or private game assets are distributed.
Game icon artwork and DG-LAB marks belong to their respective rights holders.

Local preview: run `python -m http.server 4317 --bind 127.0.0.1 --directory dist` in this folder.
Verify desktop/mobile layout, download disclosure and Escape behavior, image viewer, language persistence,
guide navigation, clipboard fallback and disabled download channels before publishing.

Public source: https://github.com/1zhiguo/ricca-dglab-control-center (GPL-3.0-only code;
third-party artwork retains its original rights). Product site: https://ricca-dglab.web.app.
From the repository root, deploy only with `firebase deploy --only hosting --project ricca-dglab`.
The existing private Sites preview is not made public or redeployed by this Firebase workflow.
