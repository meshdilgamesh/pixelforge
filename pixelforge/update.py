"""Self-update for installed PixelForge copies.

How it works: the publisher (you) uploads two small files to a release
location (e.g. GitHub Releases "latest"): version.json and pixelforge.tar.gz.
Installed copies check version.json (shown as a banner in the UI), and
`pixelforge update` downloads+applies the new code in place. User data —
models/, outputs/, uploads/, datasets/, .venv — is never touched.

The release location is configured via the PIXELFORGE_RELEASE_URL environment
variable, e.g.:
    export PIXELFORGE_RELEASE_URL="https://github.com/YOU/pixelforge/releases/latest/download"
Until that is set, updates are simply disabled and everything else works.
"""
from __future__ import annotations

import json
import os
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import __version__

KEEP_USER_DATA = {"models", "outputs", "uploads", "datasets", ".venv", "__pycache__", ".git"}


def release_url(explicit: str | None = None) -> str:
    return (explicit or os.environ.get("PIXELFORGE_RELEASE_URL") or "").rstrip("/")


def check(url: str | None = None) -> dict | None:
    """Ask the release location for version.json. Returns None when no update
    server is configured or the check fails (offline etc.)."""
    base = release_url(url)
    if not base:
        return None
    try:
        req = urllib.request.Request(f"{base}/version.json", headers={"User-Agent": f"PixelForge/{__version__}"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        latest = str(data.get("version", "")).lstrip("v")
        return {
            "configured": True,
            "local": __version__,
            "latest": latest,
            "available": latest != __version__ and latest != "",
            "notes": data.get("notes", ""),
        }
    except Exception as e:  # noqa: BLE001 — offline / not hosted yet is normal
        return {"configured": True, "error": str(e), "local": __version__,
                "latest": None, "available": False, "notes": ""}


def apply(url: str | None = None, dest: Path | None = None) -> None:
    base = release_url(url)
    if not base:
        print("No update server configured.")
        print("Set it once, e.g.:  export PIXELFORGE_RELEASE_URL=\"https://github.com/YOU/pixelforge/releases/latest/download\"")
        sys.exit(1)
    dest = (dest or Path(__file__).resolve().parent.parent).resolve()

    info = check(base)
    if not info or info.get("error"):
        sys.exit(f"Update check failed: {info.get('error') if info else 'no response'}")
    if not info["available"]:
        print(f"Already up to date (v{__version__}).")
        return

    print(f"Updating PixelForge {__version__} -> {info['latest']} …")
    tmp = Path(tempfile.mkdtemp(prefix="pixelforge-update-"))
    try:
        tar_path = tmp / "release.tar.gz"
        urllib.request.urlretrieve(f"{base}/pixelforge.tar.gz", tar_path)
        with tarfile.open(tar_path) as t:
            # only replace code — never touch the user's models/outputs/datasets
            members = [m for m in t.getmembers()
                       if m.name.split("/")[0] not in KEEP_USER_DATA]
            t.extractall(dest, members=members)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Done — PixelForge is now v{info['latest']}. Your models and outputs were kept.")
    print("Restart the app to run the new version.")


if __name__ == "__main__":
    apply()
