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
# user data that must survive updates -- only ship the creator's own model
ALLOWED_MODELS = {"4x-PixelForge-Signature.pth"}




def verify_windows_scripts():
    """Refuse to build if the Windows scripts can silently die on a user's PC.
    Checks (lessons from real-world failures):
      1. pure ASCII - PS 5.1 reads no-BOM files as ANSI; non-ASCII corrupts them
      2. no backslash-doublequote in .ps1 - PS does not escape with backslash;
         it truncates the string at the wrong place (silent Add-Type failure)
      3. string-aware paren/brace/bracket balance for .ps1
    """
    import re as _re
    problems = []
    for p in sorted(ROOT.rglob("*")):
        if p.suffix not in (".ps1", ".bat") or not p.is_file():
            continue
        data = p.read_bytes()
        high = [i for i, b in enumerate(data) if b > 0x7F]
        if high:
            problems.append(f"{p.name}: non-ASCII bytes at {high[:3]} (PS 5.1 ANSI corruption)")
        text = data.decode("ascii")
        if p.suffix == ".ps1":
            # backslash-quote inside double-quoted regions truncates strings
            in_dq = False
            for i, ch in enumerate(text):
                if ch == '"' and (i == 0 or text[i-1] != "`"):
                    in_dq = not in_dq
                elif ch == "\\" and in_dq and i + 1 < len(text) and text[i+1] == '"':
                    problems.append(f"{p.name}: backslash-quote at offset {i} truncates a PS string")
                    break
            stack, line, i, state = [], 1, 0, None
            while i < len(text):
                ch = text[i]
                if ch == "\n":
                    line += 1
                    if state == "#":
                        state = None
                if state == "#":
                    i += 1; continue
                if state:
                    if ch == "`": i += 2; continue
                    if ch == state: state = None
                    i += 1; continue
                if ch == "#": state = "#"; i += 1; continue
                if ch == "`": i += 2; continue
                if ch in "({[": stack.append((ch, line)); i += 1; continue
                if ch in ")}]":
                    pairs = {")": "(", "}": "{", "]": "["}
                    if not stack or stack[-1][0] != pairs[ch]:
                        problems.append(f"{p.name}: mismatched {ch} at line {line}")
                        if stack: stack.pop()
                    else:
                        stack.pop()
                    i += 1; continue
                i += 1
            if stack:
                problems.append(f"{p.name}: unclosed {stack[-1]}")
    if problems:
        for pr in problems:
            print("SCRIPT CHECK FAILED:", pr)
        raise SystemExit("Windows script checks failed - fix before releasing.")
    print("Windows script checks: OK (ASCII, quoting, structure)")


def collect(include_shell_scripts=True):
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_dir() or p.suffix == ".pyc":
            continue
        parts = set(p.parts)
        if parts & EXCLUDE_DIRS:
            continue
        if "models" in p.parts and p.name not in ALLOWED_MODELS:
            continue
        if not include_shell_scripts:
            # the Windows package: only Windows launchers, no console installer
            if p.suffix in (".sh",) or p.name in ("install.bat",):
                continue
        files.append(p)
    return files


def main() -> None:
    DIST.mkdir(exist_ok=True)
    verify_windows_scripts()
    files_all = collect()
    files_win = collect(include_shell_scripts=False)

    tar_path = DIST / "pixelforge.tar.gz"
    with tarfile.open(tar_path, "w:gz") as t:
        for p in files_all:
            t.add(p, arcname="PixelForge/" + str(p.relative_to(ROOT)))
    print(f"{tar_path.name}: {tar_path.stat().st_size/1e6:.1f} MB ({len(files_all)} files)")

    zip_path = DIST / f"pixelforge-{__version__}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files_win:
            z.write(p, "PixelForge/" + str(p.relative_to(ROOT)))
    print(f"{zip_path.name}: {zip_path.stat().st_size/1e6:.1f} MB")

    manifest = DIST / "version.json"
    manifest.write_text(json.dumps({"version": __version__, "notes": ""}, indent=2))
    print(f"{manifest.name}: version {__version__}")
    print("\nNext: upload these 3 files to your release location "
          "(GitHub Releases -> attach to a tag like v" + __version__ + ").")


if __name__ == "__main__":
    main()
