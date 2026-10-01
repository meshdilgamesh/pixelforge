"""Train your OWN PixelForge model — the genuine ingredient.

Trains a compact super-resolution network (SRVGGNetCompact, the same
architecture family as the fast General x4v3 model) from scratch on a folder
of high-resolution photos, with on-the-fly degradation (blur + downscale +
JPEG noise), and exports a .pth that PixelForge picks up automatically.

  env -u LD_LIBRARY_PATH .venv/bin/python scripts/train.py \
      --data datasets/DIV2K_valid_HR --iters 3000 --name 4x-PixelForge-Signature

For the real overnight run: --iters 30000 (or stop it whenever with Ctrl+C —
the latest checkpoint is always saved and loadable).
"""
from __future__ import annotations

import argparse
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageFilter

# -------------------------------------------------------------------------- #
# The architecture: kept bit-for-bit identical to spandrel's SRVGGNetCompact
# so the exported .pth loads in PixelForge (and chaiNNer/ComfyUI) as "Compact".
# -------------------------------------------------------------------------- #


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4):
        super().__init__()
        self.num_in_ch = num_in_ch
        self.num_out_ch = num_out_ch
        self.num_feat = num_feat
        self.num_conv = num_conv
        self.upscale = upscale

        self.body = nn.ModuleList()
        self.body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))
        self.body.append(nn.PReLU(num_parameters=num_feat))
        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=num_feat))
        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for i in range(len(self.body)):
            out = self.body[i](out)
        out = self.upsampler(out)
        base = F.interpolate(x, scale_factor=self.upscale, mode="nearest")
        out += base
        return out


# -------------------------------------------------------------------------- #
# On-the-fly degradation: a light version of the Real-ESRGAN pipeline.
# HR crop -> random blur -> downscale -> (optional) JPEG noise -> LR input.
# -------------------------------------------------------------------------- #


def degrade(hr: Image.Image, scale: int, rng: random.Random) -> Image.Image:
    w, h = hr.size
    # random blur, mostly gentle
    sigma = rng.choice([0.0, 0.3, 0.6, 0.9, 1.2])
    if sigma > 0:
        hr = hr.filter(ImageFilter.GaussianBlur(sigma))
    lr = hr.resize((w // scale, h // scale), Image.BICUBIC)
    # JPEG artefacts, sometimes strong (so it survives bad sources)
    q = rng.choice([95, 90, 80, 70, 60, 50])
    if q < 95:
        import io

        buf = io.BytesIO()
        lr.save(buf, format="JPEG", quality=q)
        buf.seek(0)
        lr = Image.open(buf).convert("RGB")
    return lr


class TrainData:
    """Keeps every dataset image decoded in RAM (~0.4 GB for 100 photos),
    so batch sampling is pure numpy slicing and the GPU never starves."""

    def __init__(self, folder: Path, patch: int, scale: int, seed: int = 7):
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        self.files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in exts)
        if not self.files:
            raise SystemExit(f"no images found in {folder}")
        self.patch = patch  # HR patch size
        self.scale = scale
        self.rng = random.Random(seed)
        self.images: list[np.ndarray] = []
        print(f"dataset: {len(self.files)} images from {folder} — loading into RAM…")
        t0 = time.time()
        for p in self.files:
            img = Image.open(p).convert("RGB")
            if max(img.size) > 1400:
                img.thumbnail((1400, 1400), Image.LANCZOS)
            self.images.append(np.asarray(img, dtype=np.uint8))
        print(f"  loaded in {time.time()-t0:.0f}s "
              f"({sum(a.nbytes for a in self.images)/1e9:.2f} GB RAM)")

    def batch(self, n: int, device) -> tuple[torch.Tensor, torch.Tensor]:
        hrs, lrs = [], []
        p, s = self.patch, self.scale
        for _ in range(n):
            arr = self.images[self.rng.randrange(len(self.images))]
            h, w = arr.shape[:2]
            x = self.rng.randrange(0, w - p + 1)
            y = self.rng.randrange(0, h - p + 1)
            hr = Image.fromarray(arr[y : y + p, x : x + p])
            lr = degrade(hr, s, self.rng)
            if self.rng.random() < 0.5:
                hr = hr.transpose(Image.FLIP_LEFT_RIGHT)
                lr = lr.transpose(Image.FLIP_LEFT_RIGHT)
            hrs.append(np.asarray(hr, dtype=np.float32) / 255)
            lrs.append(np.asarray(lr, dtype=np.float32) / 255)
        hr_t = torch.from_numpy(np.stack(hrs)).permute(0, 3, 1, 2).contiguous()
        lr_t = torch.from_numpy(np.stack(lrs)).permute(0, 3, 1, 2).contiguous()
        hr_t = hr_t[..., : lr_t.shape[2] * s, : lr_t.shape[3] * s]
        return lr_t.to(device), hr_t.to(device, non_blocking=True)


def psnr(a: torch.Tensor, b: torch.Tensor) -> float:
    mse = ((a - b) ** 2).mean().item()
    return 99.0 if mse < 1e-9 else 10 * math.log10(1.0 / mse)


# -------------------------------------------------------------------------- #


def main() -> None:
    ap = argparse.ArgumentParser(description="Train your own PixelForge model")
    ap.add_argument("--data", type=Path, required=True, help="folder of high-res photos")
    ap.add_argument("--iters", type=int, default=3000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--patch", type=int, default=64, help="HR patch size")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--feat", type=int, default=64, help="channels (64 = ~1.6 MB model)")
    ap.add_argument("--conv", type=int, default=16, help="conv blocks (more = stronger/slower)")
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--name", default="4x-PixelForge-Signature", help="exported model name")
    ap.add_argument("--out", type=Path, default=None, help="export dir (default: ../models)")
    ap.add_argument("--val-every", type=int, default=1000)
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    out_dir = args.out or (root / "models")
    out_dir.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(7)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device} ({torch.cuda.get_device_name(0) if device.type=='cuda' else 'CPU'})")

    model = SRVGGNetCompact(num_feat=args.feat, num_conv=args.conv, upscale=args.scale).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model: SRVGG compact feat={args.feat} conv={args.conv} scale={args.scale} "
          f"({n_params/1e6:.2f}M params)")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.iters)
    loss_fn = nn.L1Loss()

    data = TrainData(args.data, args.patch, args.scale)

    # fp32 only — this architecture overflows fp16 in forward (verified), and
    # the GPU idles on data prep anyway, so precision buys nothing here.
    # Background prefetch so the GPU never waits on PIL.
    import queue
    import threading

    batch_q: queue.Queue = queue.Queue(maxsize=6)

    def producer():
        while True:
            batch_q.put(data.batch(args.batch, device))

    threading.Thread(target=producer, daemon=True).start()

    def next_batch():
        return batch_q.get()

    # small held-out validation pair (fixed)
    val_rng = random.Random(123)
    val_file = data.files[-1]
    val_img = Image.open(val_file).convert("RGB")
    if max(val_img.size) > 900:
        val_img.thumbnail((900, 900), Image.LANCZOS)
    w, h = val_img.size
    vw, vh = (w // 2) // args.scale * args.scale, (h // 2) // args.scale * args.scale
    val_hr = val_img.crop(((w - vw) // 2, (h - vh) // 2,
                           (w - vw) // 2 + vw, (h - vh) // 2 + vh))
    val_lr = degrade(val_hr, args.scale, val_rng)
    val_lr_t = torch.from_numpy(np.asarray(val_lr, dtype=np.float32) / 255)[None].permute(0, 3, 1, 2).to(device)
    val_hr_t = torch.from_numpy(np.asarray(val_hr, dtype=np.float32) / 255)[None].permute(0, 3, 1, 2).to(device)

    model.train()
    t0 = time.time()
    best = 0.0
    running = 0.0
    for it in range(1, args.iters + 1):
        lr_t, hr_t = next_batch()
        pred = model(lr_t)
        # hr patch may be slightly larger than 4x due to flooring — align
        pred = pred[..., : hr_t.shape[2], : hr_t.shape[3]]
        loss = loss_fn(pred, hr_t)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        running += loss.item()

        if it % 100 == 0:
            el = time.time() - t0
            eta = el / it * (args.iters - it)
            print(f"  iter {it:>6}/{args.iters}  loss {running/100:.4f}  "
                  f"lr {sched.get_last_lr()[0]:.2e}  {el:5.0f}s elapsed, ~{eta:4.0f}s left",
                  flush=True)
            running = 0.0

        if it % args.val_every == 0 or it == args.iters:
            model.eval()
            with torch.no_grad():
                out = model(val_lr_t).clamp(0, 1)
            v = psnr(out, val_hr_t)
            best = max(best, v)
            model.train()
            print(f"  [val] iter {it}: PSNR {v:.2f} dB (best {best:.2f})", flush=True)
            torch.save(model.state_dict(), out_dir / f"{args.name}.pth")

    final = out_dir / f"{args.name}.pth"
    print(f"\nDONE — model saved to {final}")
    print("It is now a normal PixelForge model: restart the app and pick "
          f"'{args.name.replace('.pth','')}' from the model list.")


if __name__ == "__main__":
    main()
