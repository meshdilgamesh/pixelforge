"""Generate the branded side-banner art for the Windows setup wizard.

  .venv/bin/python scripts/make_setup_art.py

Creates setup-art.png (480x960, displayed at 240x480) - dark gradient,
rising pixel sparks, the PixelForge logo and wordmark. Committed to the repo
so the installer never needs to generate anything.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
W, H = 480, 1140

img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)

# vertical gradient: deep navy -> indigo -> violet glow at bottom
top = (10, 13, 24)
mid = (24, 27, 58)
bot = (76, 45, 180)
for y in range(H):
    t = y / H
    if t < 0.55:
        k = t / 0.55
        c = tuple(int(top[i] + (mid[i] - top[i]) * k) for i in range(3))
    else:
        k = (t - 0.55) / 0.45
        c = tuple(int(mid[i] + (bot[i] - mid[i]) * (k ** 1.6)) for i in range(3))
    d.line([(0, y), (W, y)], fill=c)

# subtle grid
for x in range(0, W, 40):
    d.line([(x, 0), (x, H)], fill=(255, 255, 255, 6) if False else (30, 36, 66))
for y in range(0, H, 40):
    d.line([(0, y), (W, y)], fill=(30, 36, 66))

# rising pixel sparks (deterministic)
import random

rng = random.Random(7)
hues = [(251, 191, 36), (244, 114, 182), (34, 211, 238), (139, 92, 246)]
for _ in range(90):
    x, y = rng.randrange(0, W), rng.randrange(0, H)
    s = rng.choice([2, 2, 3, 3, 4, 5])
    c = rng.choice(hues)
    fade = 0.25 + 0.6 * (1 - y / H)
    col = tuple(int(ci * fade + 16 * (1 - fade)) for ci in c)
    d.rectangle([x, y, x + s, y + s], fill=col)

# logo: two rounded squares + pink pixel, like the app icon
def rrect(x0, y0, x1, y1, r, fill):
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill)

cx = W // 2
rrect(cx - 92, 300, cx - 8, 384, 22, (139, 92, 246))
rrect(cx + 8, 384, cx + 92, 468, 22, (34, 211, 238))
rrect(cx - 6, 376, cx + 6, 388, 4, (244, 114, 182))
# dashed flow line
for x in range(cx + 8, cx + 76, 16):
    d.line([(x, 330), (x + 8, 330)], fill=(238, 242, 255), width=6)

# wordmark
from PIL import ImageFont

try:
    f_big = ImageFont.load_default(size=56)
    f_small = ImageFont.load_default(size=24)
except TypeError:  # older Pillow
    f_big = ImageFont.load_default()
    f_small = ImageFont.load_default()

def center_text(y, text, font, fill):
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)

center_text(520, "PixelForge", f_big, (238, 242, 255))
center_text(590, "A I   I M A G E   F O R G E", f_small, (34, 211, 238))
center_text(640, "free  .  open source  .  100 percent local", f_small, (154, 166, 195))

img.save(ROOT / "setup-art.png")
print(f"saved {ROOT / 'setup-art.png'} ({(ROOT / 'setup-art.png').stat().st_size/1024:.0f} KB)")
