"""Static completeness checks without browser or external-network access."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import json

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path, self.ids, self.refs, self.h1 = path, set(), [], 0
        self.english, self.languages = set(), set()
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if attrs.get("data-en"):
            self.english.add(attrs["data-en"])
        if tag == "option":
            self.languages.add(attrs.get("value"))
        if "id" in attrs:
            assert attrs["id"] not in self.ids, (self.path, "duplicate id", attrs["id"])
            self.ids.add(attrs["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "img":
            assert "alt" in attrs, (self.path, "missing image alt")
        for key in ("href", "src"):
            if attrs.get(key):
                self.refs.append(attrs[key])
        if attrs.get("target") == "_blank":
            assert "noopener" in attrs.get("rel", ""), (self.path, "unsafe external target")


pages = {p.name: Page(p) for p in DIST.glob("*.html")}
assert set(pages) == {"index.html", "guide.html"}
for name, page in pages.items():
    assert page.h1 == 1, (name, "expected one h1")
    assert page.languages == {"zh", "en", "ja"}, (name, "language selector")
    for reference in page.refs:
        url = urlsplit(reference)
        if url.scheme:
            assert url.scheme == "https", reference
            continue
        target = DIST / (url.path or name)
        assert target.is_file(), (name, "missing file", reference)
        if url.fragment and target.suffix == ".html":
            assert url.fragment in pages[target.name].ids, (name, "broken fragment", reference)
for screen in ("overview", "strategy", "editor", "audio"):
    assert (DIST / "assets" / "screens" / f"{screen}.png").stat().st_size > 1000
manifest_path = ROOT / ".openai/hosting.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["static"]["directory"] == "dist" and manifest["project_id"]
firebase_path = ROOT.parent / "firebase.json"
if firebase_path.exists():
    hosting = json.loads(firebase_path.read_text(encoding="utf-8"))["hosting"]
    assert hosting["public"] == "website/dist" and hosting["site"] == "ricca-dglab"
assert manifest_path.exists() or firebase_path.exists(), "Missing deployment configuration"
for excluded in ("settings.json", "GameAssembly.dll", "HolyKnightRicca.exe", "Ricca-x-DGlab.exe"):
    assert not list(DIST.rglob(excluded)), ("non-website file", excluded)
assert not list(DIST.rglob("*.jsonl")), "Telemetry must not be included in website assets"
home = (DIST / "index.html").read_text(encoding="utf-8")
order = [home.index(f'id="{name}"') for name in ("top", "features", "downloads", "screens", "support", "credits")]
assert order == sorted(order), "Keep the Manaka reference's product/features/downloads/screens/support order"
assert home.count("data-screenshot") == 6
assert 'aria-controls="download-sources"' in home and 'id="download-sources" hidden' in home
ja_text = (DIST / "i18n-ja.js").read_text(encoding="utf-8")
ja = json.loads(ja_text[ja_text.index("{"):ja_text.rindex("}")+1])
required = set().union(*(page.english for page in pages.values()))
assert not required - ja.keys(), ("missing Japanese translations", sorted(required-ja.keys()))
assert all(isinstance(ja[key], str) and ja[key].strip() for key in required)
assert "Ctrl+Alt+F10" not in home and "1.0.0" not in home
release = (DIST / "release-config.js").read_text(encoding="utf-8")
assert 'version: "1.0.1"' in release and "releases/download/v1.0.1/" in release
assert "cbc582be67d89f576e2e4dbe28ad874226a0f2a7bd8cb49e2778d94249ad7d37" in release
print(f"Website checks passed: links, images, package isolation, 3 languages, {len(required)} Japanese translations and 1.0.1 downloads.")
