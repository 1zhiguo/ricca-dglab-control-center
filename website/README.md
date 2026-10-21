# Ricca × DG-LAB website

Buildless static website in `dist/`, inspired by the Manaka product-site structure.
The desktop companion remains independent; the website does not connect to a device.

- `dist/index.html`: Manaka-family landing-page layout, Chinese/English/Japanese copy, download-source menu,
  compact two-column features, three download channels and full-width screenshot gallery.
- `dist/manaka-layout.css`: layout measurements based on the local Manaka reference
  (1120px shell, 72px header, large product title, section spacing and mobile breakpoints).
- `dist/guide.html`: connection guide, compatibility, first-test checklist, troubleshooting.
- `dist/i18n-ja.js`: complete shared Japanese translations; selector preference persists across pages.
- `dist/release-config.js`: set actual HTTPS package URLs only after publishing real Ricca files.
- `dist/assets/`: existing Ricca branding, simulated desktop screenshots and mobile connection guide.
- `.openai/hosting.json`: retains this independent Site's identity. Do not reuse the Manaka ID.
- `../firebase.json`: public Firebase Hosting deploy, restricted to `website/dist` and site `ricca-dglab`.
- `../.firebaserc`: the independent `ricca-dglab` Firebase project, never the Manaka project.

GitHub and COS downloads point to the published 1.0.1 ZIP; Baidu opens the supplied share link with its extraction code displayed and copyable. No game files, telemetry recordings,
user configuration, device commands or private game assets are distributed.
Game icon artwork and DG-LAB marks belong to their respective rights holders.

Local preview: run `python -m http.server 4317 --bind 127.0.0.1 --directory dist` in this folder.
Verify desktop/mobile layout, download disclosure and Escape behavior, image viewer, language persistence,
guide navigation, clipboard fallback and disabled download channels before publishing.

Public source: https://github.com/1zhiguo/ricca-dglab-control-center (GPL-3.0-only code;
third-party artwork retains its original rights). Product site: https://ricca-dglab.web.app.
From the repository root, deploy only with `firebase deploy --only hosting --project ricca-dglab`.
The existing private Sites preview is not made public or redeployed by this Firebase workflow.

## Website analytics

GA4 web stream: `G-3JZLXPP17E` (Ricca website). `analytics.js` loads Google only
after explicit consent, only on `ricca-dglab.web.app`. Footer preferences allow
withdrawal; browser GPC / Do Not Track disables analytics. Consent expires after
180 days. Local previews never send analytics. Advertising and Google signals
are disabled; enhanced measurement was disabled when creating the stream.
Only page views, download-channel clicks, quick-start/guide opens and known
project/profile navigation are measured. Query strings, fragments, referrer paths,
form content, device data, game telemetry and audio are not included by our code.
Google still processes standard technical data for consented website analytics.
Verify collection in GA4 Realtime; standard reports can take 24–48 hours.
