#!/usr/bin/env bash
# PixelForge launcher.
#   bash start.sh              → web UI (also on first install)
#   bash start.sh photo.jpg …  → CLI upscaling
set -e
cd "$(dirname "$0")"

# AppImage-hosted terminals can leak LD_LIBRARY_PATH into the environment,
# which breaks Python's library lookup — start from a clean slate
unset LD_LIBRARY_PATH

# find uv (installed to ~/.local/bin on first setup; PATH may differ per setup)
find_uv() {
  for c in "${PIXELFORGE_UV:-}" "$HOME/.local/bin/uv" "$(command -v uv 2>/dev/null)"; do
    if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return; fi
  done
}
UV="$(find_uv)"
if [ -z "$UV" ]; then
  echo "Setting up Python tooling (one time, no sudo needed)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV="$(find_uv)"
fi

# create the environment + install dependencies on first run
if [ ! -x .venv/bin/python ]; then
  echo "Creating Python environment and installing PyTorch (one time, ~3 GB download)..."
  "$UV" venv --python 3.13 .venv
  "$UV" pip install -p .venv/bin/python torch spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
fi

exec .venv/bin/python pixelforge.py "$@"
