"""PixelForge benchmark — measures real upscale times on your hardware.

  .venv/bin/python scripts/benchmark.py [model-key]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pixelforge.engine import Upscaler
from pixelforge.models import find_model_file, models_dir


def natural_image(w: int, h: int) -> Image.Image:
    """Smooth, photo-like content: gradients, soft blobs, text."""
    rng = np.random.default_rng(3)
    small = (rng.random((h // 32, w // 32, 3)) * 255).astype(np.uint8)
    img = Image.fromarray(small).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(img)
    d.ellipse([w * 0.1, h * 0.15, w * 0.45, h * 0.75], fill=(90, 140, 230))
    d.ellipse([w * 0.4, h * 0.3, w * 0.9, h * 0.95], outline=(250, 210, 90), width=3)
    d.text((w * 0.06, h * 0.06), "PixelForge benchmark 12345", fill=(255, 255, 255))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def run(up: Upscaler, src: Image.Image, target, label: str) -> None:
    t0 = time.time()
    out = up.upscale(src, target=target)
    dt = time.time() - t0
    mp = (out.width * out.height) / 1e6
    rate = f"{mp / dt:.1f} MP/s" if dt > 0.2 else ""
    print(f"  {label:<34} {out.width}x{out.height}  {dt:6.1f}s  {rate}")


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "ultrasharp"
    up = Upscaler(find_model_file(key, models_dir(Path("."))))
    dev = "fp16 GPU" if up.half else ("GPU" if up.device.type == "cuda" else "CPU")
    print(f"{key} | tile {up.tile}px | {dev}\n")

    hd = natural_image(1920, 1080)      # typical AI render / screenshot size
    hd_small = natural_image(960, 540)  # low-quality source

    print("Photo-style content:")
    run(up, hd, (3840, 2160), "1080p -> 4K UHD")
    run(up, hd_small, (3840, 2160), "540p -> 4K UHD (4x effective)")
    run(up, natural_image(512, 512), (4096, 4096), "512px AI image -> 4096px")
    if up.device.type == "cuda":
        run(up, hd, (7680, 4320), "1080p -> 8K")


if __name__ == "__main__":
    main()
