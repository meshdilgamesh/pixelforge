#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  PixelForge installer
#
#  Run from an extracted release folder:      bash install.sh
#  Or straight from a release URL:            curl -L <url>/install.sh | bash
#
#  What it does:
#    1. installs PixelForge to ~/.pixelforge (no sudo, nothing system-wide)
#    2. sets up Python + PyTorch on first install
#    3. creates the `pixelforge` command and an app-menu icon
#
#  Optional: set PIXELFORGE_RELEASE_URL to also enable in-app updates, e.g.
#    PIXELFORGE_RELEASE_URL="https://github.com/YOU/pixelforge/releases/latest/download" bash install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e
unset LD_LIBRARY_PATH

DEST="${PIXELFORGE_HOME:-$HOME/.pixelforge}"
RELEASE_URL="${PIXELFORGE_RELEASE_URL:-}"
SRC=""
TMP=""

# --- locate the source package -------------------------------------------- #
if [ -f "$(dirname "$0" 2>/dev/null)/pixelforge.py" ]; then
  SRC="$(cd "$(dirname "$0")" && pwd)"
elif [ -n "$RELEASE_URL" ]; then
  TMP="$(mktemp -d)"
  echo "Downloading PixelForge from $RELEASE_URL …"
  curl -L "$RELEASE_URL/pixelforge.tar.gz" -o "$TMP/app.tar.gz"
  tar -xzf "$TMP/app.tar.gz" -C "$TMP"
  SRC="$TMP/app"
else
  echo "Error: run this from an extracted PixelForge folder, or set"
  echo "  PIXELFORGE_RELEASE_URL=https://github.com/YOU/pixelforge/releases/latest/download"
  exit 1
fi

echo "Installing PixelForge to $DEST …"
mkdir -p "$DEST"
# copy code over any existing install (keeps user's models/outputs/datasets);
# skip runtime-only folders that never belong to a release
tar -C "$SRC" -cf - \
    --exclude='.venv' --exclude='outputs' --exclude='uploads' \
    --exclude='datasets' --exclude='__pycache__' --exclude='.git' \
    . | tar -C "$DEST" -xf -
[ -n "$TMP" ] && rm -rf "$TMP"

# --- python environment ---------------------------------------------------- #
find_uv() {
  for c in "${PIXELFORGE_UV:-}" "$HOME/.local/bin/uv" "$(command -v uv 2>/dev/null)"; do
    if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return; fi
  done
}
if [ ! -x "$DEST/.venv/bin/python" ]; then
  UV="$(find_uv)"
  if [ -z "$UV" ]; then
    echo "Setting up Python tooling (one time, no sudo needed)…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV="$(find_uv)"
  fi
  echo "Installing PyTorch + dependencies (one time, ~3 GB download)…"
  "$UV" venv --python 3.13 "$DEST/.venv"
  "$UV" pip install -p "$DEST/.venv/bin/python" \
      torch spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
fi

# --- app icon --------------------------------------------------------------- #
"$DEST/.venv/bin/python" - << PYEOF 2>/dev/null || true
from PIL import Image, ImageDraw
img = Image.new("RGBA", (128, 128), (10, 13, 24, 255))
d = ImageDraw.Draw(img)
d.rounded_rectangle([10, 10, 58, 58], radius=8, fill=(139, 92, 246, 255))
d.rounded_rectangle([70, 70, 118, 118], radius=8, fill=(34, 211, 238, 255))
d.rectangle([60, 60, 68, 68], fill=(244, 114, 182, 255))
img.save("$DEST/icon.png")
PYEOF

# --- command + desktop entry ------------------------------------------------ #
# desktop entries are a Linux thing; on macOS the `pixelforge` command is the launcher
OS="$(uname -s)"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/pixelforge" << LAUNCHER
#!/usr/bin/env bash
export PIXELFORGE_RELEASE_URL="$RELEASE_URL"
exec bash "$DEST/start.sh" "\$@"
LAUNCHER
chmod +x "$HOME/.local/bin/pixelforge"

if [ "$OS" = "Linux" ]; then
  cat > "$HOME/.local/share/applications/pixelforge.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=PixelForge
Comment=Forge blurry pixels into crystal 4K — locally
Exec=$HOME/.local/bin/pixelforge
Icon=$DEST/icon.png
Terminal=false
Categories=Graphics;
DESKTOP
  echo "  • App menu  → look for 'PixelForge'"
elif [ "$OS" = "Darwin" ]; then
  echo "  • Launch it → type: $HOME/.local/bin/pixelforge   (add ~/.local/bin to PATH to just type 'pixelforge')"
fi

echo
echo "  ✔ PixelForge is installed."
echo "    • Terminal  → type: pixelforge"
echo "    • Photos land in $DEST/outputs"
echo "    First launch downloads the AI models (one time)."
