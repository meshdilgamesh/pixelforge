# PixelForge

**Free, open-source AI image upscaling that runs 100% on your own computer —
built for modest GPUs like the GTX 1660 Super (6 GB).**

Take a low-quality image, a compressed JPEG, or an AI-generated picture, and
get a crisp, high-detail 2×/4×/8× version — or an exact target size like
1080p, 1440p, 4K UHD, 8K, or any custom WxH. No accounts, no uploads, no
cloud: everything happens on your machine.

```
low-res / AI image ──▶ PixelForge (your GPU) ──▶ sharp high-resolution image
```

## Why PixelForge

- **Made for 6 GB cards.** Smart tiled inference means image size never
  touches your VRAM limit — the picture is processed in overlapping tiles
  with automatic GPU-memory sizing, so seams stay invisible.
- **fp16 fast path** on GTX 16-series cards (2× throughput), with automatic
  fallback to fp32 if a model misbehaves.
- **No blur, no mush.** Ships with community models known for *sharp*
  results (UltraSharp, Real-ESRGAN), plus a fast denoising model for old or
  noisy sources.
- **Lots of resolution options:** 2× 3× 4× 6× 8×, exact presets
  (1080p / 1440p / 4K UHD / 8K), or any custom WxH — bigger factors run
  multiple clean passes instead of one lossy stretch.
- **Local web UI** with a drag-to-compare before/after slider and batch
  queue, plus a full **CLI** for scripting.
- **Bring your own model:** any `.pth` super-resolution model from
  [OpenModelDB](https://openmodeldb.info) works — drop it in `models/`.

## Platforms

| OS | Status | How |
|---|---|---|
| Linux + NVIDIA | ⭐ fully supported, tested | `install.sh` / `bash start.sh` |
| Windows + NVIDIA | supported (native) | `install.bat` / double-click `start.bat` — not yet tested on real Windows hardware, report issues |
| Windows without NVIDIA | works (CPU, slow) | same, or WSL2 |
| macOS (Apple Silicon) | works (fp32 MPS) | `bash install.sh` then `~/.local/bin/pixelforge` |
| macOS (Intel) | works (CPU, slow) | same |

Platform differences live in exactly three places: the launcher scripts
(`start.sh`/`start.bat`), the device picker in `pixelforge/engine.py`
(CUDA → MPS → CPU), and the desktop-entry step of `install.sh` (Linux only).
Nothing platform-specific lives in the engine or UI.

## Install (Linux)

**Option A — one command** (needs `curl` and `tar`, both preinstalled almost everywhere):

```bash
curl -L https://github.com/meshdilgamesh/pixelforge/releases/latest/download/pixelforge.tar.gz | tar xz && bash PixelForge/install.sh
```

**Option B — the setup file:** download `install.sh` (it ships with every
release, or is included in the zip/tar.gz), then:

```bash
bash install.sh          # from the extracted release folder
```

That's it. PixelForge installs to `~/.pixelforge` (no sudo, nothing
system-wide), sets up Python + PyTorch, and gives you:

- a **PixelForge icon in your app menu** — click it like any normal program
- a **`pixelforge` command** in the terminal — no arguments opens the app;
  with arguments it's the CLI: `pixelforge photo.jpg -t 4k`

**Option B — portable:** extract the zip anywhere and run `bash start.sh`
(what `install.sh` does for you, but nothing is "installed").

Requirements: Linux, NVIDIA GPU (any GTX 10-series+; CPU fallback works
everywhere but slowly), ~5 GB disk, internet for the first-time setup.
Windows: WSL2.

## Updating

When the publisher releases a new version, installed copies show a banner at
the top of the app. To update, close the app and run:

```bash
pixelforge update
```

Your models, trained or downloaded, and your results are always kept —
updates only replace the code. (Updates need a release location: the
publisher sets `PIXELFORGE_RELEASE_URL` once, e.g. their GitHub Releases
"latest/download" URL. Until then the banner simply never appears.)

## Publishing a new version (for the maintainer)

```bash
.venv/bin/python scripts/release.py   # builds dist/ artifacts + version.json
```

Bump `__version__` in `pixelforge/__init__.py` first. Upload `dist/*`
(`pixelforge.tar.gz`, `pixelforge-<v>.zip`, `version.json`) to the release
location — e.g. attach to a GitHub release tagged `v<v>`.

## Install for development

You don't need sudo and nothing is installed system-wide. The only
requirements are an NVIDIA GPU with recent drivers and ~4 GB of disk.

```bash
bash start.sh
```

First run downloads Python + PyTorch (~3 GB, one time), then opens the UI at
http://127.0.0.1:8477. On fish shell just run `bash start.sh` the same way
(or `source $HOME/.local/share/../bin/env.fish` to get `uv` on your PATH).

> **fish users:** never paste `source venv/bin/activate` — use
> `source .venv/bin/activate.fish`, or skip activation entirely and always
> call `.venv/bin/python pixelforge.py …`.

## Models

Models download automatically when you first use them (5–155 MB each).
**Which one for which job:**

| Key | Model | Best for | Speed (1080p→4K) |
|---|---|---|---|
| `webphoto` | Nomos WebPhoto PLKSR | **Default** — crispest fine detail in our tests, fast, tolerant of compressed/noisy sources | ~16 s |
| `dat2` | Nomos2 DAT-2 | Maximum detail on **clean** sources (AI images, high-quality photos). Do **not** feed it compressed/noisy JPEGs — it breaks into blocks | ~2.6 min |
| `ultrasharpv2` | 4x-UltraSharpV2 | AI-generated images; very crisp and faithful | ~1.5 min* |
| `nomos8k` | Nomos8k DAT | Real camera photos; smooth, most faithful to the original | ~3.3 min |
| `ultrasharp` | 4x-UltraSharp | The classic — kept as a known-good fallback | ~35 s |
| `realesrgan` | RealESRGAN x4plus | Balanced, smooth, fast fp16 | ~35 s |
| `general` | realesr-general-x4v3 | Fastest; tolerant of noise/low quality | ~11 s |
| `anime` | RealESRGAN x4 anime 6B | Anime, illustrations, game art | ~fast |

*UltraSharpV2 runs fp32 on this GPU like the DAT models.

A real-photo comparison (downscale → upscale → compare against ground truth,
`scripts/compare_models.py`) found WebPhoto and DAT-2 recover visibly more
fine detail (fur, whiskers, texture) than the older classics, and WebPhoto is
also 2× faster than UltraSharp. See `outputs/compare/` for example strips.

Add your own: grab any image `.pth`/`.safetensors` from OpenModelDB, drop it
in `models/`, and it appears in the UI and CLI automatically.

## CLI examples

```bash
.venv/bin/python pixelforge.py photo.jpg                 # 4x, default model
.venv/bin/python pixelforge.py photo.jpg -s 2            # 2x
.venv/bin/python pixelforge.py photo.jpg -t 4k           # exact 4K UHD
.venv/bin/python pixelforge.py ai_art.png -m anime -s 4  # anime model
.venv/bin/python pixelforge.py ~/Pictures/batch/ -t 8k   # whole folder -> 8K
.venv/bin/python pixelforge.py --list-models
.venv/bin/python pixelforge.py --download general
```

Options: `--tile N` (lower if you run out of VRAM), `--no-fp16`,
`--device cpu`, `--format png|jpeg|webp`, `--quality N`, `-o outdir`.

## Performance (GTX 1660 Super 6 GB, auto tile 384)

Measured on real hardware with photo-style content — reproduce with
`scripts/benchmark.py`:

| Task | WebPhoto | DAT-2 | Nomos8k | UltraSharp | General |
|---|---|---|---|---|---|
| 1080p → 4K UHD | ~16 s | ~2.6 min | ~3.3 min | ~35 s | ~11 s |
| 540p → 4K UHD | ~4 s | ~40 s | ~49 s | ~7 s | ~3 s |
| 512px AI image → 4096px | ~35 s | ~5.8 min | ~7.2 min | ~65 s | ~24 s |
| 1080p → 8K | ~15 s | ~2.6 min | ~3.3 min | ~30 s | ~10 s |

The 5-minute/4K budget holds for every model. For the 8× two-pass path,
WebPhoto and the classic models stay well under it; the DAT models are
slow because they run fp32 (fp16 numerically breaks them, and PixelForge
auto-detects that and keeps them safe).

## Train your own model (the genuine ingredient)

PixelForge ships with a trainer — `scripts/train.py` — that trains a small
"compact" SR model **from scratch, on this very GPU**, and exports a normal
`.pth` that shows up in the model list automatically. This is the one
ingredient that is genuinely yours.

```bash
# demo run (~10 min): watch the loss fall and PSNR climb
env -u LD_LIBRARY_PATH .venv/bin/python scripts/train.py \
    --data datasets/DIV2K_valid_HR --iters 3000

# the real thing (a few hours, or Ctrl+C anytime — checkpoints save every 500)
env -u LD_LIBRARY_PATH .venv/bin/python scripts/train.py \
    --data datasets/DIV2K_valid_HR --iters 30000 --name 4x-MySignature
```

- Dataset: any folder of high-res photos. The classic choice is DIV2K
  (research-use); grab the 100-image starter set with:
  `curl -L -o div2k.zip https://data.vision.ee.ethz.ch/cvl/DIV2K/DIV2K_valid_HR.zip && unzip div2k.zip`
  then point `--data` at the extracted `DIV2K_valid_HR` folder. For something
  truly personal, point it at your own `~/Pictures` library.
- Degradation is applied on the fly (blur → downscale → JPEG noise), so the
  model learns to undo exactly the kind of damage real low-quality images have.
- Architecture: SRVGGNetCompact (same family as the fast General model) —
  ~1.6 MB, loads everywhere spandrel/chaiNNer/ComfyUI load it.
- Honest expectations: a compact model won't beat the big DAT models. It's a
  craft project and a learning machine: short run = soft but working; overnight
  run on more data = genuinely decent. 

## Troubleshooting

- **"GPU ran out of memory"** → lower the tile size (384 → 256), close other
  GPU apps (games, other LLM tools).
- **Weird colors / NaN artifacts** → switch precision to fp32 in Advanced.
- **No GPU detected** → check `nvidia-smi` works; PixelForge then falls back
  to CPU (works, but 10–50× slower).
- **Where do results go?** `outputs/` in the project folder (UI shows a
  Download button too).

## Honest limitations

AI upscaling *reconstructs* detail from learned patterns. It works wonders on
AI images, game renders, and slightly-soft photos, but it cannot truly recover
information that was never in the source (a heavily blurred 64px thumbnail
will never become a real 8K photograph). Face reconstruction (GFPGAN/CodeFormer
style) is a possible future addition.

## Credits & licenses

- Code: MIT — see [LICENSE](LICENSE).
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (BSD-3-Clause) — x4plus, anime, general models.
- [4x-UltraSharp](https://openmodeldb.info/models/4x-UltraSharp) by Kim2091 — non-commercial license, check before commercial use.
- Model loading by [spandrel](https://github.com/chaiNNer-org/spandrel).
