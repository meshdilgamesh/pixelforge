"""Model registry + downloader. Curated models auto-download on first use;
any .pth dropped into models/ is picked up too (spandrel auto-detects the
architecture), so users can add models from https://openmodeldb.info."""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".jfif", ".avif"}


@dataclass
class ModelInfo:
    key: str
    name: str
    file: str
    url: str
    size_mb: float
    scale: int
    desc: str
    license: str
    built_in: bool = True


MODELS: dict[str, ModelInfo] = {
    m.key: m
    for m in [
        ModelInfo(
            key="webphoto",
            name="Nomos WebPhoto PLKSR",
            file="4xNomosWebPhoto_RealPLKSR.pth",
            url="https://github.com/Phhofm/models/releases/download/4xNomosWebPhoto_RealPLKSR/4xNomosWebPhoto_RealPLKSR.pth",
            size_mb=30,
            scale=4,
            desc="Default — crispest fine detail in tests, fast, and tolerant of compressed/noisy sources.",
            license="CC-BY-NC-SA (see Phhofm/models)",
        ),
        ModelInfo(
            key="dat2",
            name="Nomos2 DAT-2 (max detail)",
            file="4xNomos2_hq_dat2.pth",
            url="https://github.com/Phhofm/models/releases/download/4xNomos2_hq_dat2/4xNomos2_hq_dat2.pth",
            size_mb=140,
            scale=4,
            desc="Most detailed for CLEAN sources (AI images, high-quality photos). Slow (fp32) — do not use on compressed/noisy images.",
            license="CC-BY-NC-SA (see Phhofm/models)",
        ),
        ModelInfo(
            key="ultrasharpv2",
            name="4x-UltraSharpV2 (AI art)",
            file="4x-UltraSharpV2.safetensors",
            url="https://huggingface.co/Kim2091/UltraSharpV2/resolve/main/4x-UltraSharpV2.safetensors",
            size_mb=133,
            scale=4,
            desc="Successor to UltraSharp, trained for AI-generated images — very crisp, faithful.",
            license="CC-BY-NC-SA-4.0",
        ),
        ModelInfo(
            key="nomos8k",
            name="Nomos8k DAT (real photos)",
            file="4xNomos8kDAT.pth",
            url="https://github.com/Phhofm/models/releases/download/4xNomos8kDAT/4xNomos8kDAT.pth",
            size_mb=155,
            scale=4,
            desc="Smooth, most faithful to the original photo; handles grain/compression. Slow (fp32).",
            license="CC-BY-NC-SA (see Phhofm/models)",
        ),
        ModelInfo(
            key="ultrasharp",
            name="4x-UltraSharp (classic)",
            file="4x-UltraSharp.pth",
            url="https://huggingface.co/kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth",
            size_mb=67,
            scale=4,
            desc="The classic sharp model — superseded by WebPhoto/DAT-2, kept as a known-good fallback.",
            license="Non-commercial (see OpenModelDB)",
        ),
        ModelInfo(
            key="realesrgan",
            name="RealESRGAN x4plus",
            file="RealESRGAN_x4plus.pth",
            url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            size_mb=64,
            scale=4,
            desc="Balanced all-rounder; smooth results, fast fp16.",
            license="BSD-3-Clause",
        ),
        ModelInfo(
            key="general",
            name="General x4v3 (fast + denoise)",
            file="realesr-general-x4v3.pth",
            url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
            size_mb=5,
            scale=4,
            desc="Small and fast; handles noisy / low-quality sources well.",
            license="BSD-3-Clause",
        ),
        ModelInfo(
            key="anime",
            name="RealESRGAN x4 anime",
            file="RealESRGAN_x4plus_anime_6B.pth",
            url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
            size_mb=18,
            scale=4,
            desc="Anime, illustrations, game art, pixel-art style images.",
            license="BSD-3-Clause",
        ),
    ]
}


def models_dir(project_root: Path) -> Path:
    d = project_root / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_model_file(key: str, mdir: Path) -> Optional[Path]:
    info = MODELS.get(key)
    if info:
        p = mdir / info.file
        if p.exists() and p.stat().st_size > 1_000_000:
            return p
    # allow direct file paths and custom .pth/.safetensors files
    as_path = Path(key)
    if as_path.is_file():
        return as_path
    for suffix in (".pth", ".safetensors"):
        candidate = mdir / f"{key}{suffix}"
        if candidate.exists():
            return candidate
    return None


def download_model(
    key: str,
    mdir: Path,
    cb: Optional[Callable[[float, str], None]] = None,
) -> Path:
    info = MODELS[key]
    dest = mdir / info.file
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(info.url, headers={"User-Agent": "PixelForge/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if cb and total:
                cb(done / total, f"downloading {info.name}: {done / 1e6:.0f}/{total / 1e6:.0f} MB")
    if cb:
        cb(1.0, f"downloaded {info.name} ({info.size_mb:.0f} MB)")
    tmp.rename(dest)
    return dest
