# Ricca woodland theme

The existing Firebase site retains its product copy, download sources, language
menu, analytics consent and application screenshots. `forest-theme.css` is a
presentation-only layer loaded last on the homepage and guide; the legacy
layout file remains as a structural base. No desktop software changes.

## Artwork

`dist/assets/ricca-enchanted-forest.webp` is original AI-generated environment
art, made with the built-in imagegen tool (not a game screenshot or official
game artwork). The original PNG is retained in the generator's output library;
the site uses a WebP encoding with unchanged composition for faster delivery.

Generation brief: an original enchanted ancient woodland at blue-green
twilight, painted Japanese RPG environment style; old mossy oaks, fern leaves,
ivy, a distant path, warm golden fireflies and jade motes, an engraved weathered
stone arch on the right, soft mist and filtered light. Deep forest greens,
warm dark wood, antique gold and ivory. Wide landscape with a dark quiet left
half for typography, detailed right third, dark bottom. Environment only:
no people, characters, text, logos, watermarks or UI panels.

## Presentation and checks

- Local system serif fonts for fantasy headings; existing sans-serif body copy.
- Antique-gold/leaf-green focus states and controls; no remote font requests.
- Full artwork in the hero, subdued fixed forest behind opaque content panels.
- CSS-only motes; disabled for `prefers-reduced-motion`.
- Single-column mobile layout and two-column desktop screenshots/features.
- Verify all three locales, download menu, quick-start dialog, screenshot
  lightbox, guide navigation and absence of horizontal overflow.
