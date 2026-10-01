"""PixelForge upscaling engine.

Tiled GPU inference for image super-resolution models loaded via spandrel,
so even a 6 GB card can upscale to 4K/8K. Handles:
  - automatic tile sizing from VRAM
  - fp16 with probe + NaN fallback (Turing cards get 2x fp16 throughput)
  - OOM recovery by shrinking tiles
  - seam-free tiling via overlap margins
  - exact target resolutions (multi-pass + Lanczos finish)
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np
import torch
from PIL import Image

ProgressCb = Optional[Callable[[float, str], None]]


def get_device(pref: str = "auto") -> torch.device:
    if pref == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if pref == "cuda":
        raise RuntimeError(
            "CUDA was requested but is not available. "
            "Make sure the NVIDIA driver is installed and PyTorch is the CUDA build."
        )
    # Apple Silicon (macOS): MPS backend, runs fp32 here — fp16 stays CUDA-only
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available() and pref in ("auto", "mps"):
        return torch.device("mps")
    if pref == "mps":
        raise RuntimeError("MPS was requested but is not available on this Mac.")
    return torch.device("cpu")


def auto_tile_size(device: torch.device) -> int:
    """Conservative default tile for the available memory."""
    if device.type == "cuda":
        vram_gb = torch.cuda.get_device_properties(device).total_memory / 1e9
        if vram_gb >= 22:
            return 768
        if vram_gb >= 11:
            return 512
        if vram_gb >= 5.5:
            return 384  # fits a 6 GB card comfortably with fp16
        return 256
    if device.type == "mps":
        return 384  # unified memory on Apple Silicon is roomy, but stay safe
    return 128


def _size_requirements(model) -> Tuple[int, int]:
    """(minimum, multiple_of) for the model's input size, with safe fallbacks."""
    sr = getattr(model, "size_requirements", None)
    if sr is None:
        return 1, 1
    minimum = int(getattr(sr, "minimum", 1) or 1)
    multiple = int(getattr(sr, "multiple_of", 1) or 1)
    return max(1, minimum), max(1, multiple)


class Upscaler:
    """Loads one model and upscales PIL images with it."""

    def __init__(
        self,
        model_path: Path,
        device: str = "auto",
        fp16: bool = True,
        tile: int = 0,  # 0 = auto
    ):
        from spandrel import ImageModelDescriptor, ModelLoader

        self.device = get_device(device)
        model = ModelLoader().load_from_file(str(model_path))
        if not isinstance(model, ImageModelDescriptor):
            raise ValueError(
                f"{model_path.name} is not an image upscaling model "
                "(only image-to-image SR models are supported)."
            )
        self.model = model.to(self.device).eval()
        self.scale = float(model.scale)
        self.in_ch = int(model.input_channels)
        self.out_ch = int(model.output_channels)
        self.req_min, self.req_mult = _size_requirements(model)

        self.tile = tile if tile and tile > 0 else auto_tile_size(self.device)
        self.half = False
        if fp16 and self.device.type == "cuda":
            self.half = self._probe_fp16()

    # ------------------------------------------------------------------ #

    def _probe_fp16(self) -> bool:
        """Check the model actually works in fp16 (some archs NaN out)."""
        import copy

        probe = None
        try:
            probe = copy.deepcopy(self.model).half()
            x = torch.randn(1, self.in_ch, 64, 64, device=self.device, dtype=torch.float16)
            with torch.inference_mode():
                y = probe(x)
            if not torch.isfinite(y).all():
                return False
            del probe, x, y
            torch.cuda.empty_cache()
            self.model = self.model.half()
            return True
        except Exception:
            if probe is not None:
                del probe
            torch.cuda.empty_cache()
            return False

    def _prep_tile(self, tile: torch.Tensor) -> torch.Tensor:
        """Pad a tile so its size satisfies the model's requirements."""
        _, _, h, w = tile.shape
        pad_h = (-h) % self.req_mult if self.req_mult > 1 else 0
        pad_w = (-w) % self.req_mult if self.req_mult > 1 else 0
        if self.req_min > 1:
            pad_h = max(pad_h, max(0, self.req_min - h))
            pad_w = max(pad_w, max(0, self.req_min - w))
        if pad_h or pad_w:
            tile = torch.nn.functional.pad(tile, (0, pad_w, 0, pad_h), mode="replicate")
        return tile

    def _forward(self, tile: torch.Tensor) -> torch.Tensor:
        dtype = torch.float16 if self.half else torch.float32
        t = tile.to(dtype)
        with torch.inference_mode():
            out = self.model(t)
        out = out.float()
        if not torch.isfinite(out).all():
            raise FloatingPointError("fp16 NaN")
        return out

    # ------------------------------------------------------------------ #

    def _tiled_forward(self, img: torch.Tensor, cb: ProgressCb, stage: str) -> torch.Tensor:
        """img: 1,C,H,W float32 on device. Returns 1,out_ch,H*s,W*s float32."""
        _, _, H, W = img.shape
        s = self.scale
        out_w, out_h = round(W * s), round(H * s)

        tile = self.tile
        while True:  # retries with a smaller tile on OOM, or fp32 on fp16 NaN
            try:
                return self._tiled_pass(img, tile, out_w, out_h, cb, stage)
            except torch.OutOfMemoryError:
                if self.device.type == "cuda":
                    torch.cuda.empty_cache()
                if tile <= 128:
                    raise RuntimeError(
                        "GPU ran out of memory even with the smallest tile size. "
                        "Close other GPU apps or use --device cpu."
                    )
                tile = max(128, tile // 2)
                if cb:
                    cb(0.0, f"GPU memory tight — retrying with tile size {tile}")
            except FloatingPointError:
                if self.half:
                    self.model = self.model.float()
                    self.half = False
                    if cb:
                        cb(0.0, "fp16 unstable for this model — switching to fp32")
                else:
                    raise

    def _tiled_pass(
        self,
        img: torch.Tensor,
        tile: int,
        out_w: int,
        out_h: int,
        cb: ProgressCb,
        stage: str,
    ) -> torch.Tensor:
        _, _, H, W = img.shape
        s = self.scale
        overlap = 32 if tile >= 256 else 16
        rm = self.req_mult
        if rm > 1:
            overlap = max(rm, (overlap // rm) * rm)
        # adjacent tiles overlap by 2*overlap: each tile keeps its centre
        # [x0+ov, x0+tile-ov), which is exactly `stride` wide → no gaps, no seams
        stride = max(1, tile - 2 * overlap)

        def n_tiles(total: int) -> int:
            return 1 if total <= tile else math.ceil((total - tile) / stride) + 1

        nx, ny = n_tiles(W), n_tiles(H)
        Wp = (nx - 1) * stride + tile
        Hp = (ny - 1) * stride + tile
        pad_w, pad_h = Wp - W, Hp - H
        if pad_w or pad_h:
            img = torch.nn.functional.pad(img, (0, pad_w, 0, pad_h), mode="replicate")

        out_dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        out = torch.empty(
            (1, self.out_ch, round(Hp * s), round(Wp * s)),
            dtype=out_dtype,
            device=self.device,
        )

        total = nx * ny
        done = 0
        t0 = time.time()
        for iy in range(ny):
            for ix in range(nx):
                x0, y0 = ix * stride, iy * stride
                t = img[:, :, y0 : y0 + tile, x0 : x0 + tile]
                t = self._prep_tile(t)
                r = self._forward(t)  # 1,out_ch,tile*s,tile*s (approx)

                # keep the region that no neighbour tile also produces
                left = round(x0 * s) + (round(overlap * s) if ix > 0 else 0)
                top = round(y0 * s) + (round(overlap * s) if iy > 0 else 0)
                right = round((x0 + tile) * s) - (round(overlap * s) if ix < nx - 1 else 0)
                bottom = round((y0 + tile) * s) - (round(overlap * s) if iy < ny - 1 else 0)
                src = r[
                    :,
                    :,
                    top - round(y0 * s) : bottom - round(y0 * s),
                    left - round(x0 * s) : right - round(x0 * s),
                ]
                out[:, :, top:bottom, left:right] = src.to(out_dtype)

                del t, r
                done += 1
                if cb and (done % 2 == 0 or done == total):
                    frac = done / total
                    elapsed = time.time() - t0
                    eta = elapsed / frac - elapsed if frac > 0.02 else 0
                    cb(
                        frac,
                        f"{stage} tile {done}/{total}"
                        + (f" — ~{eta:.0f}s left" if eta > 2 else ""),
                    )

        return out[:, :, :out_h, :out_w].float()

    # ------------------------------------------------------------------ #

    def upscale(
        self,
        image: Image.Image,
        target: Optional[Tuple[int, int]] = None,
        max_passes: int = 3,
        cb: ProgressCb = None,
    ) -> Image.Image:
        """Upscale a PIL image. If target (w, h) is given, multi-pass until the
        model overshoots the target, then finish with a Lanczos resize so the
        output is exactly the requested resolution."""
        had_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        alpha = image.convert("RGBA").split()[3] if had_alpha else None
        rgb_mode = "L" if self.in_ch == 1 else "RGB"
        W, H = image.size

        arr = np.asarray(image if image.mode == rgb_mode else image.convert(rgb_mode), dtype=np.float32)
        if arr.ndim == 2:
            arr = arr[None]          # 1,H,W grayscale
        else:
            arr = arr.transpose(2, 0, 1)  # C,H,W
        x = torch.from_numpy(arr[None] / 255.0)
        if x.shape[1] < self.in_ch:
            x = x.repeat(1, self.in_ch, 1, 1)
        elif x.shape[1] > self.in_ch:
            x = x[:, : self.in_ch]
        x = x.to(self.device)

        if target:
            needed = max(target[0] / W, target[1] / H)
            passes = max(1, min(max_passes, math.ceil(needed / self.scale)))
        else:
            passes = 1

        for p in range(passes):
            stage = f"pass {p + 1}/{passes}" if passes > 1 else "upscaling"
            share = 1.0 / passes
            base = p * share
            wrapped = (
                (lambda f, msg: cb(base + f * share, msg)) if cb else None
            )
            x = self._tiled_forward(x, wrapped, stage)
            if target and max(x.shape[3], x.shape[2]) >= max(target):
                break  # overshoot reached; Lanczos finish below lands exactly on target

        arr = x[0].clamp(0, 1).mul(255).round().byte().permute(1, 2, 0).cpu().numpy()
        out = Image.fromarray(arr.squeeze() if arr.shape[2] == 1 else arr)
        if out.mode == "L":
            out = out.convert("RGB")

        if target:
            # fit the long side to the target and keep aspect ratio — never
            # stretch a 3:2 photo into 16:9. "4k" on a 3:2 source -> 3840x2560.
            f = max(target) / max(W, H)
            fitted = (round(W * f), round(H * f))
            if out.size != fitted:
                out = out.resize(fitted, Image.LANCZOS)
        if alpha is not None:
            alpha = alpha.resize(out.size, Image.LANCZOS)
            out = out.convert("RGBA")
            out.putalpha(alpha)

        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        return out
