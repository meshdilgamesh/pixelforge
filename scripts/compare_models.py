"""Quality comparison: which model recovers the most real detail?

Method: take a high-res photo (ground truth), degrade it (small + JPEG),
upscale it back with every downloaded model, then compare against the truth
with (a) PSNR on luminance and (b) side-by-side crop strips you can eyeball.

  env -u LD_LIBRARY_PATH .venv/bin/python scripts/compare_models.py [photo.jpg]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pixelforge.engine import Upscaler
from pixelforge.models import MODELS, find_model_file, models_dir

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "compare"
OUT.mkdir(parents=True, exist_ok=True)

BASELINE_ORDER = ["ultrasharp", "ultrasharpv2", "webphoto", "nomos8k", "dat2", "realesrgan"]
LABELS = {
    "ultrasharp": "UltraSharp v1",
    "ultrasharpv2": "UltraSharpV2",
    "webphoto": "WebPhoto PLKSR",
    "nomos8k": "Nomos8k DAT",
    "dat2": "DAT-2 Nomos2",
    "realesrgan": "RealESRGAN",
}


def psnr_luma(a: Image.Image, b: Image.Image) -> float:
    x = np.asarray(a.convert("L"), dtype=np.float64)
    y = np.asarray(b.convert("L"), dtype=np.float64)
    mse = ((x - y) ** 2).mean()
    return 99.0 if mse < 1e-9 else 10 * np.log10(255**2 / mse)


def sharpness(img: Image.Image) -> float:
    """Laplacian variance — a crude no-reference 'crispness' metric."""
    x = np.asarray(img.convert("L"), dtype=np.float32)
    lap = (
        -4 * x
        + np.roll(x, 1, 0) + np.roll(x, -1, 0)
        + np.roll(x, 1, 1) + np.roll(x, -1, 1)
    )[2:-2, 2:-2]
    return float(lap.var())


def label_bar(width, text):
    bar = Image.new("RGB", (width, 26), (12, 14, 26))
    d = ImageDraw.Draw(bar)
    d.text((8, 6), text, fill=(235, 240, 255))
    return bar


def main() -> None:
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not src_path:
        sys.exit("usage: compare_models.py <high-res photo>  (need a real photo as ground truth)")

    truth = Image.open(src_path); truth.load()
    truth = truth.convert("RGB")
    truth.thumbnail((1600, 1600), Image.LANCZOS)          # ground truth ~1600px
    small = truth.resize((truth.width // 4, truth.height // 4), Image.LANCZOS)
    # degrade: JPEG artefacts like a bad download / heavily compressed source
    degraded = ROOT / "outputs" / "compare_input.jpg"
    small.save(degraded, quality=70)
    small = Image.open(degraded)
    print(f"ground truth {truth.size} | degraded input {small.size} (JPEG q70)\n")

    mdir = models_dir(ROOT)
    results = {}
    for key in BASELINE_ORDER:
        path = find_model_file(key, mdir)
        if not path:
            print(f"-- {key}: not downloaded, skipping")
            continue
        up = Upscaler(path, tile=384)
        t0 = time.time()
        out = up.upscale(small, target=truth.size)
        if out.size != truth.size:
            out = out.resize(truth.size, Image.LANCZOS)
        dt = time.time() - t0
        results[key] = out
        print(f"{LABELS[key]:<18} {dt:6.1f}s  PSNR {psnr_luma(out, truth):5.2f} dB  "
              f"sharpness {sharpness(out):8.0f}")
        del up
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

    print(f"{'GROUND TRUTH':<18}    ref  PSNR    --  sharpness {sharpness(truth):8.0f}")

    # side-by-side strips for 3 interesting regions (center, thirds)
    W, H = truth.size
    regions = [
        ("center", (int(W*0.42), int(H*0.30), int(W*0.42)+300, int(H*0.30)+300)),
        ("left-detail", (int(W*0.08), int(H*0.45), int(W*0.08)+300, int(H*0.45)+300)),
        ("right-detail", (int(W*0.68), int(H*0.55), int(W*0.68)+300, int(H*0.55)+300)),
    ]
    for name, box in regions:
        strip = Image.new("RGB", (304 * (len(results) + 1), 356), (10, 12, 22))
        gt_crop = truth.crop(box)
        strip.paste(label_bar(304, "GROUND TRUTH"), (0, 0))
        strip.paste(gt_crop, (2, 30))
        for i, (key, img) in enumerate(results.items(), 1):
            strip.paste(label_bar(304, LABELS[key] + f"  {psnr_luma(img, truth):.1f}dB"), (304*i, 0))
            strip.paste(img.crop(box), (304*i + 2, 30))
        strip.save(OUT / f"strip_{name}.png")
    print(f"\ncrops saved to {OUT}/strip_*.png — open and eyeball them")


if __name__ == "__main__":
    main()
