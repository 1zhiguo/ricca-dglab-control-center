"""Export and audit an explicit public source allowlist, never the whole checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


ROOT_FILES = (
    ".gitignore", ".firebaserc", "firebase.json", "LICENSE", "README.md", "README.zh-CN.md", "RELEASE_1.0.0.json", "RELEASE_1.0.1.json",
    "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", "SECURITY.md", "RELEASING.md", "DIAGNOSTICS.md",
    "requirements-native.txt", "setup_native.ps1", "run_native.ps1", "run_native.cmd",
    "run_native_debug.cmd", "build_launcher.ps1", "ricca_hp_smoke_test.py",
    "ricca_dashboard.py", "start_dashboard.cmd", "start_dashboard.ps1",
    "website/README.md", "website/FOREST_THEME.md", "website/check_site.py", "tools/prepare_public_source.py",
    "tools/extract_localization.py", "RELEASE_1.1.0.json",
)
SOURCE_DIRS = ("src", "tests", "tools", "docs", "launcher", "dashboard", ".github", "website/dist")
SKIP_PARTS = {"__pycache__", ".git", ".openai", "node_modules", ".venv"}
ALLOWED_SUFFIXES = {".py", ".qml", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico",
                    ".cs", ".html", ".css", ".js", ".json", ".md", ".txt",
                    ".ps1", ".cmd", ".yml", ".yaml"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".ico"}
SENSITIVE = (
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r'"private_key"\s*:\s*"',
    r"\bgh[pousr]_[A-Za-z0-9_]{25,}",
    r"\bgithub_pat_[A-Za-z0-9_]{25,}",
    r"\bya29\.[A-Za-z0-9_-]{25,}",
    r"\b1//[A-Za-z0-9_-]{30,}",
    r"\bAKIA[A-Z0-9]{16}\b",
    r"(?i)[A-Z]:[\\/]+Users[\\/]",
)


def source_files(root: Path):
    files = {root / name for name in ROOT_FILES}
    for folder in SOURCE_DIRS:
        for file in (root / folder).rglob("*"):
            relative = file.relative_to(root)
            if not file.is_file() or any(part in SKIP_PARTS for part in relative.parts):
                continue
            if file.suffix.lower() in ALLOWED_SUFFIXES:
                files.add(file)
    return sorted(files)


def public_bytes(path: Path, relative: str) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in BINARY_SUFFIXES:
        return data
    text = data.decode("utf-8-sig")
    # Publish relocatable developer/test references, never workstation paths.
    if relative.startswith(("docs/", "tests/")):
        workspace = Path(__file__).resolve().parents[1]
        text = text.replace(workspace.as_posix(), "<RICCA_WORKSPACE>")
        text = text.replace(str(workspace), "<RICCA_WORKSPACE>")
    # Keep local developer convenience in the original checkout, but make the
    # published launcher relocatable and free of personal workstation paths.
    if relative == "run_native.ps1":
        text, count = re.subn(r'^\$ReferencePython = .+$',
                             '$ReferencePython = $env:RICCA_DEV_PYTHON', text, flags=re.M)
        if count != 1:
            raise ValueError("run_native.ps1 developer-path marker changed; review manually")
        text = text.replace("elseif (Test-Path -LiteralPath $ReferencePython)",
                            "elseif ($ReferencePython -and (Test-Path -LiteralPath $ReferencePython))")
    if relative == "launcher/RiccaLauncher.cs":
        text, count = re.subn(r'^    private const string ReferencePython = .+$',
                             '    private static readonly string ReferencePython = '
                             'Environment.GetEnvironmentVariable("RICCA_DEV_PYTHON") ?? "";',
                             text, flags=re.M)
        if count != 1:
            raise ValueError("Launcher developer-path marker changed; review manually")
    for pattern in SENSITIVE:
        if re.search(pattern, text):
            raise ValueError(f"Publication blocked: sensitive/private content in {relative}")
    return text.replace("\r\n", "\n").encode("utf-8")


def export(root: Path, destination: Path):
    root, destination = root.resolve(), destination.resolve()
    expected = root / "public_repo" / "ricca-dglab-control-center"
    if destination != expected:
        raise ValueError("Export target must be the dedicated public_repo subfolder")
    files = source_files(root)
    prepared = {}
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Symlinks or files outside the source root are not allowed")
        relative = path.relative_to(root).as_posix()
        prepared[relative] = public_bytes(path, relative)
    manifest = {
        "format": "RiccaPublicSource/1", "license": "GPL-3.0-only",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in prepared.items()},
        "excluded": ["game files", "private settings", "telemetry recordings", "caches",
                     "credentials", "unrelated Ricca-Look-Library", "private Sites metadata"],
    }
    if destination.exists() and any(destination.iterdir()) and not (destination / "PUBLIC_SOURCE_MANIFEST.json").is_file():
        raise ValueError("Refusing to overwrite an existing, unmanaged public folder")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in prepared.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (destination / "artifacts").mkdir(exist_ok=True)
    (destination / "PUBLIC_SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    total = sum(len(data) for data in prepared.values())
    print(json.dumps({"destination": str(destination), "files": len(prepared),
                      "bytes": total, "license": manifest["license"],
                      "original_files_deleted": 0}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    export(args.root, args.root / "public_repo" / "ricca-dglab-control-center")
