"""PixelForge smoke test + benchmark.

Run with the project venv after models are downloaded:
  .venv/bin/python scripts/test_engine.py

Checks: tiling seam-free-ness, alpha preservation, exact-target math,
and prints real GPU timing for a 4K upscale.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageDraw

from pixelforge.engine import Upscaler
from pixelforge.models import find_model_file, models_dir

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "test_images"
TMP.mkdir(exist_ok=True)


def make_test_image(w=480, h=320) -> Image.Image:
    """Synthetic low-res image with fine structure (text, edges, checker, noise)."""
    img = Image.new("RGB", (w, h), (24, 26, 34))
    d = ImageDraw.Draw(img)
    for x in range(0, w // 2, 8):
        d.line([(x, 0), (x, h // 2)], fill=(240, 240, 240), width=1)
    for y in range(0, h, 10):
        d.line([(w // 2, y), (w, y)], fill=(255, 120, 40), width=2)
    d.ellipse([w // 2 - 40, h // 2 - 20, w // 2 + 40, h // 2 + 20], outline=(80, 220, 255), width=2)
    d.text((12, h - 30), "PixelForge 4K detail test 0123", fill=(255, 255, 255))
    rng = np.random.default_rng(7)
    noise = (rng.random((h // 4, w // 4, 3)) * 255).astype(np.uint8)
    img.paste(Image.fromarray(noise).resize((w // 2, h // 2), Image.NEAREST), (w // 2, h // 2))
    return img


def max_diff(a: Image.Image, b: Image.Image) -> float:
    x = np.asarray(a.convert("RGB"), dtype=np.float32)
    y = np.asarray(b.convert("RGB"), dtype=np.float32)
    return float(np.abs(x - y).max())


def main() -> None:
    mdir = models_dir(ROOT)
    key = sys.argv[1] if len(sys.argv) > 1 else "ultrasharp"
    path = find_model_file(key, mdir)
    if not path:
        sys.exit(f"model '{key}' not downloaded — run: .venv/bin/python pixelforge.py --download {key}")

    src = make_test_image()
    src_path = TMP / "test_src.png"
    src.save(src_path)

    print(f"model: {path.name}")
    up = Upscaler(path)
    print(f"device={up.device.type} fp16={up.half} tile={up.tile} scale={up.scale}")

    # 1) plain 4x
    t0 = time.time()
    out = up.upscale(src, cb=lambda f, m: None)
    t4 = time.time() - t0
    assert out.size == (src.width * 4, src.height * 4), out.size
    print(f"PASS plain 4x: {out.size} in {t4:.1f}s")

    # 2) exact 4K target from a 1080p-ish input (2x effective) — 3:2 source
    #    must stay 3:2, fitted to the long side
    photo = src.resize((960, 640), Image.BICUBIC)
    t0 = time.time()
    out4k = up.upscale(photo, target=(3840, 2160), cb=lambda f, m: None)
    t4k = time.time() - t0
    assert out4k.size == (3840, 2560), out4k.size
    print(f"PASS exact 4K fit: 960x640 -> {out4k.size} (aspect kept) in {t4k:.1f}s")

    # 3) seam check: two tile sizes must agree inside the image, and any
    # differences must be scattered (GAN/fp16 sensitivity), never clustered
    # into lines at tile boundaries
    small = src.resize((640, 448), Image.BICUBIC)
    up.tile = 512
    a = np.asarray(up.upscale(small, cb=lambda f, m: None).convert("RGB"), dtype=np.int16)
    up.tile = 144
    b = np.asarray(up.upscale(small, cb=lambda f, m: None).convert("RGB"), dtype=np.int16)
    d = np.abs(a - b).max(axis=2)
    H, W = d.shape
    mean_diff = float(d.mean())
    assert mean_diff < 0.5, f"seam check failed: mean diff {mean_diff:.3f}"
    # a seam would be a 1px line with hundreds of consecutive diffs; scattered
    # GAN/fp16 sensitivity is a few isolated pixels anywhere in the image
    stride_out = (144 - 2 * 16) * 4  # tile 144, overlap 16, scale 4
    worst = 0
    for bnd in range(stride_out, W, stride_out):
        for off in (-2, 0, 2):
            worst = max(worst, int((d[:, bnd + off] > 6).sum()))
    for bnd in range(stride_out, H, stride_out):
        for off in (-2, 0, 2):
            worst = max(worst, int((d[bnd + off, :] > 6).sum()))
    assert worst <= 10, f"seam check failed: boundary line carries {worst} diff pixels"
    print(f"PASS seams: mean diff {mean_diff:.3f}/255, worst boundary line {worst} diff px")

    # 4) alpha preserved
    rgba = src.convert("RGBA")
    arr = np.array(rgba)
    arr[..., 3] = 128
    rgba = Image.fromarray(arr)
    outa = up.upscale(rgba, target=(1920, 1280), cb=lambda f, m: None)
    assert outa.mode == "RGBA" and outa.size == (1920, 1280), (outa.mode, outa.size)
    assert abs(np.asarray(outa)[..., 3].mean() - 128) < 3
    print("PASS alpha: RGBA preserved through upscale")

    # 5) big-factor target = multi-pass
    tiny = src.resize((240, 160), Image.BICUBIC)
    out8 = up.upscale(tiny, target=(3840, 2560), cb=lambda f, m: None)
    assert out8.size == (3840, 2560), out8.size
    print("PASS multi-pass: 240x160 -> 16x pixels exactly")

    print("\nALL TESTS PASSED")
    print(f"Benchmark summary ({path.name}, tile {up.tile}, fp16={up.half}):")
    print(f"  plain 4x 480x320->{src.width*4}x{src.height*4}: {t4:.1f}s")
    print(f"  exact 4K from 960x640: {t4k:.1f}s")


if __name__ == "__main__":
    main()
