"""Build PixelForge release artifacts.

  .venv/bin/python scripts/release.py

Creates in dist/:
  pixelforge.tar.gz     what install.sh / `pixelforge update` download
  pixelforge-<v>.zip    human-friendly copy for manual sharing
  version.json          the update manifest

Publishing a new version: bump __version__, run this, upload dist/* to your
release location (e.g. attach to a GitHub release tagged v<v>).
"""
import json
import sys
import tarfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pixelforge import __version__  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
EXCLUDE_DIRS = {".venv", "outputs", "uploads", "test_images", "__pycache__",
                ".git", "datasets", "dist"}
# user data that must survive updates — only ship the creator's own model
ALLOWED_MODELS = {"4x-PixelForge-Signature.pth"}


def collect():
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_dir() or p.suffix == ".pyc":
            continue
        parts = set(p.parts)
        if parts & EXCLUDE_DIRS:
            continue
        if "models" in p.parts and p.name not in ALLOWED_MODELS:
            continue
        files.append(p)
    return files


def main() -> None:
    DIST.mkdir(exist_ok=True)
    files = collect()

    tar_path = DIST / "pixelforge.tar.gz"
    with tarfile.open(tar_path, "w:gz") as t:
        for p in files:
            t.add(p, arcname="PixelForge/" + str(p.relative_to(ROOT)))
    print(f"{tar_path.name}: {tar_path.stat().st_size/1e6:.1f} MB ({len(files)} files)")

    zip_path = DIST / f"pixelforge-{__version__}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, "PixelForge/" + str(p.relative_to(ROOT)))
    print(f"{zip_path.name}: {zip_path.stat().st_size/1e6:.1f} MB")

    manifest = DIST / "version.json"
    manifest.write_text(json.dumps({"version": __version__, "notes": ""}, indent=2))
    print(f"{manifest.name}: version {__version__}")
    print("\nNext: upload these 3 files to your release location "
          "(GitHub Releases → attach to a tag like v" + __version__ + ").")


if __name__ == "__main__":
    main()
