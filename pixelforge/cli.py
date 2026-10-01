"""PixelForge CLI.

Examples:
  python pixelforge.py photo.jpg                       # 4x with the default model
  python pixelforge.py photo.jpg -s 2                  # 2x
  python pixelforge.py photo.jpg -t 4k                 # exactly 3840x2160-class target
  python pixelforge.py photo.jpg -t 7680x4320          # custom exact target (8K)
  python pixelforge.py anime.png -m anime -s 4
  python pixelforge.py ~/Pictures/lowres/ -t 4k        # batch a whole folder
  python pixelforge.py --list-models
  python pixelforge.py ui                              # launch the local web UI
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .engine import Upscaler
from .models import MODELS, IMAGE_EXTS, find_model_file, models_dir

TARGETS = {
    "hd": (1280, 720),
    "720p": (1280, 720),
    "fhd": (1920, 1080),
    "1080p": (1920, 1080),
    "2k": (2560, 1440),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
    "2160p": (3840, 2160),
    "5k": (5120, 2880),
    "8k": (7680, 4320),
    "4320p": (7680, 4320),
}

DEFAULT_MODEL = "webphoto"


def resolve_target(text: str):
    t = text.strip().lower()
    if t in TARGETS:
        return TARGETS[t]
    if "x" in t:
        w, _, h = t.partition("x")
        try:
            return (int(w), int(h))
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        f"unknown target '{text}' — use 720p/1080p/2k/4k/8k or WxH like 3840x2160"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pixelforge",
        description="High-detail AI image upscaling on modest GPUs. Runs 100% locally.",
        epilog="Models: " + ", ".join(f"{k} = {v.name}" for k, v in MODELS.items()),
    )
    p.add_argument("input", nargs="?", help="image file or folder of images")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help=f"model key or .pth path (default: {DEFAULT_MODEL})")
    p.add_argument("-s", "--scale", type=float, default=None,
                   help="scale factor, e.g. 2, 4, 8 (ignored if --target is given)")
    p.add_argument("-t", "--target", type=resolve_target, default=None,
                   help="exact output resolution: 1080p, 2k, 4k, 8k or WxH")
    p.add_argument("-o", "--outdir", default="outputs", help="output folder (default: ./outputs)")
    p.add_argument("--tile", type=int, default=0,
                   help="tile size in px (0 = auto from VRAM; lower if you hit OOM)")
    p.add_argument("--no-fp16", action="store_true", help="disable fp16 (slower, most compatible)")
    p.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    p.add_argument("--format", choices=["auto", "png", "jpeg", "webp"], default="auto",
                   help="output format (auto keeps PNG for images with transparency, else JPEG)")
    p.add_argument("--quality", type=int, default=95, help="JPEG/WebP quality (default 95)")
    p.add_argument("--list-models", action="store_true", help="list available models and exit")
    p.add_argument("--download", metavar="KEY", help="download a model now and exit")
    p.add_argument("--quiet", action="store_true")
    return p


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit != "B" else f"{n:.0f} B"
        n /= 1024
    return f"{n:.1f} TB"


def cmd_list_models(mdir: Path) -> None:
    print(f"Models directory: {mdir}\n")
    for key, m in MODELS.items():
        have = find_model_file(key, mdir) is not None
        state = "downloaded" if have else f"not downloaded ({m.size_mb:.0f} MB)"
        print(f"  {key:<12} {m.name:<28} {state}")
        print(f"  {'':<12} {m.desc}")
    customs = sorted(p for p in mdir.glob("*.pth") if p.name not in {m.file for m in MODELS.values()})
    if customs:
        print("\nCustom models found in models/:")
        for c in customs:
            print(f"  {c.name}  (use with -m {c.stem} or -m {c})")
    if not any(find_model_file(k, mdir) for k in MODELS):
        print("\nTip: download one with:  python pixelforge.py --download ultrasharp")


def gather_images(inp: Path) -> list[Path]:
    if inp.is_dir():
        files = sorted(p for p in inp.iterdir() if p.suffix.lower() in IMAGE_EXTS and not p.name.startswith("."))
        if not files:
            sys.exit(f"No images found in {inp}")
        return files
    if not inp.exists():
        sys.exit(f"Input not found: {inp}")
    return [inp]


def save_image(img, path: Path, fmt: str, quality: int) -> Path:
    has_alpha = img.mode == "RGBA"
    if fmt == "auto":
        fmt = "png" if has_alpha else "jpeg"
    if fmt == "jpeg":
        path = path.with_suffix(".jpg")
        img = img.convert("RGB")
    elif fmt == "png":
        path = path.with_suffix(".png")
    elif fmt == "webp":
        path = path.with_suffix(".webp")
    img.save(path, quality=quality) if fmt != "png" else img.save(path)
    return path


def process_one(up: Upscaler, src: Path, args, outdir: Path) -> Path:
    from PIL import Image

    img = Image.open(src)
    img.load()

    target = args.target
    if target is None and args.scale:
        # express the requested factor as an exact pixel target so the engine
        # can multi-pass (e.g. 8x with a 4x model = two clean passes)
        target = (round(img.width * args.scale), round(img.height * args.scale))

    cb = None
    if not args.quiet:
        def cb(frac, msg):
            bar = int(frac * 24)
            sys.stdout.write(f"\r   [{'#' * bar}{'.' * (24 - bar)}] {msg:<44}")
            sys.stdout.flush()

    result = up.upscale(img, target=target, cb=cb)
    if not args.quiet:
        print()

    tag = f"{target[0]}x{target[1]}" if target else f"x{int(up.scale)}"
    out = outdir / f"{src.stem}_{tag}{src.suffix}"
    return save_image(result, out, args.format, args.quality)


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    mdir = models_dir(root)

    if args.list_models:
        cmd_list_models(mdir)
        return
    if args.download:
        from .models import download_model

        def dl_cb(frac, msg):
            print(f"\r{msg:<60}", end="" if frac < 1 else "\n", flush=True)

        path = download_model(args.download, mdir, cb=dl_cb)
        print(f"Saved to {path}")
        return
    if not args.input:
        build_parser().print_help()
        return

    files = gather_images(Path(args.input).expanduser())
    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    model_path = find_model_file(args.model, mdir)
    if not model_path:
        m = MODELS.get(args.model)
        hint = f" — run: python pixelforge.py --download {args.model}" if m else ""
        sys.exit(f"Model '{args.model}' not found{hint}. Or run --list-models.")

    up = Upscaler(model_path, device=args.device, fp16=not args.no_fp16, tile=args.tile)
    dev = "GPU (fp16)" if up.half else ("GPU" if up.device.type == "cuda" else "CPU")
    if not args.quiet:
        print(f"PixelForge — {model_path.name} | tile {up.tile}px | {dev}")

    t_all = time.time()
    for i, src in enumerate(files, 1):
        if not args.quiet:
            print(f"[{i}/{len(files)}] {src.name} ({_fmt_bytes(src.stat().st_size)})")
        t0 = time.time()
        try:
            out = process_one(up, src, args, outdir)
            if not args.quiet:
                from PIL import Image
                w, h = Image.open(out).size
                print(f"   -> {out}  {w}x{h} in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"   ERROR on {src.name}: {e}")
    if len(files) > 1 and not args.quiet:
        print(f"Done: {len(files)} images in {time.time() - t_all:.1f}s -> {outdir}")


if __name__ == "__main__":
    main()
