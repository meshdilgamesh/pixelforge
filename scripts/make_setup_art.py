"""Generate the branded side-banner art for the Windows setup wizard.

  .venv/bin/python scripts/make_setup_art.py

Creates setup-art.png (480x1140, displayed at 240x570). Designed, not
decorated: crisp pixel-grid logo, a BEFORE/AFTER demonstration of what the
product does, and three clean badges. Drawn at 2x and supersampled down so
every edge stays sharp on high-DPI displays.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 480, 1140
S = 2  # supersample factor
img = Image.new("RGB", (W * S, H * S))
d = ImageDraw.Draw(img)
w, h = W * S, H * S

# ---- background: calm vertical gradient + faint grid -----------------------
top, mid, bot = (11, 14, 26), (18, 23, 46), (42, 32, 88)
for y in range(h):
    t = y / h
    if t < 0.6:
        k = t / 0.6
        c = tuple(int(top[i] + (mid[i] - top[i]) * k) for i in range(3))
    else:
        k = (t - 0.6) / 0.4
        c = tuple(int(mid[i] + (bot[i] - mid[i]) * (k ** 1.7)) for i in range(3))
    d.line([(0, y), (w, y)], fill=c)
grid = (33, 40, 70)
for x in range(0, w, 40 * S):
    d.line([(x, 0), (x, h)], fill=grid)
for y in range(0, h, 40 * S):
    d.line([(0, y), (w, y)], fill=grid)

VIOLET, CYAN, PINK = (139, 92, 246), (34, 211, 238), (244, 114, 182)
TEXT, DIM = (238, 242, 255), (139, 151, 176)

# ---- fonts -------------------------------------------------------------------
def font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()

def center_text(y, text, f, fill, bold=False):
    tw = d.textlength(text, font=f)
    x = (w - tw) / 2
    if bold:
        d.text((x + S, y), text, font=f, fill=fill)
        d.text((x, y + S), text, font=f, fill=fill)
    d.text((x, y), text, font=f, fill=fill)

def rrect(x0, y0, x1, y1, r, outline=None, fill=None, width=2):
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=outline, fill=fill, width=width)

# ---- 1. logo mark (top) -------------------------------------------------------
cx = w // 2
s1 = 40 * S
gap = 12 * S
y0 = 50 * S
rrect(cx - s1 - gap, y0, cx - gap, y0 + s1, 9 * S, fill=VIOLET)
rrect(cx + gap, y0 + s1 + gap, cx + gap + s1, y0 + 2 * s1 + gap, 9 * S, fill=CYAN)
d.rectangle([cx - 3 * S, y0 + s1 - 3 * S, cx + 3 * S, y0 + s1 - 1 * S], fill=PINK)
# dashed forge-flow from violet square to cyan square
fx0 = cx - gap - s1 + s1 // 2
fy0 = y0 + s1 + gap // 2
step = 10 * S
xx = fx0
while xx < cx + gap + s1 // 2 - step:
    d.line([(xx, fy0), (xx + step // 2, fy0)], fill=TEXT, width=2 * S)
    xx += step

f_word = font(22 * S)
center_text(y0 + 2 * s1 + gap + 12 * S, "PixelForge", f_word, TEXT, bold=True)
f_small = font(8 * S)
center_text(y0 + 2 * s1 + gap + 18 * S + 22 * S, "A I   I M A G E   F O R G E", f_small, CYAN)

# ---- 2. BEFORE / AFTER demo (the product, drawn) -------------------------------
panel_y0, panel_y1 = 200 * S, 360 * S
rrect(30 * S, panel_y0, w - 30 * S, panel_y1, 10 * S, outline=(52, 62, 96), width=S)
f_tag = font(8 * S)

def draw_scene(g, x0, y0, size, smooth=True):
    """A little mountain-and-sun scene; blocky when smooth=False."""
    if smooth:
        ss = 4
        tmp = Image.new("RGB", (size * ss, size * ss))
        td = ImageDraw.Draw(tmp)
        td.rectangle([0, 0, size * ss, size * ss], fill=(24, 30, 56))
        td.ellipse([size*ss*0.52, size*ss*0.10, size*ss*0.92, size*ss*0.50], fill=(253, 224, 120))
        td.polygon([(0, size*ss*0.78), (size*ss*0.30, size*ss*0.42), (size*ss*0.55, size*ss*0.78)], fill=(13, 16, 38))
        td.polygon([(size*ss*0.42, size*ss*0.82), (size*ss*0.72, size*ss*0.50), (size*ss, size*ss*0.82)], fill=(10, 12, 30))
        td.rectangle([0, size*ss*0.80, size*ss, size*ss], fill=(16, 20, 42))
        d._image.paste(tmp.resize((size, size), Image.LANCZOS), (x0, y0))
    else:
        n = 16  # tiny grid, nearest-upscaled = chunky pixels
        tmp = Image.new("RGB", (n, n))
        td = ImageDraw.Draw(tmp)
        td.rectangle([0, 0, n, n], fill=(24, 30, 56))
        td.ellipse([n*0.52, n*0.10, n*0.92, n*0.50], fill=(253, 224, 120))
        td.polygon([(0, n*0.78), (n*0.30, n*0.42), (n*0.55, n*0.78)], fill=(13, 16, 38))
        td.polygon([(n*0.42, n*0.82), (n*0.72, n*0.50), (n, n*0.82)], fill=(10, 12, 30))
        td.rectangle([0, n*0.80, n, n], fill=(16, 20, 42))
        d._image.paste(tmp.resize((size, size), Image.NEAREST), (x0, y0))

demo_size = 64 * S
gx0, gx1 = 55 * S, w - 55 * S - demo_size
draw_scene(d, gx0, panel_y0 + 30 * S, demo_size, smooth=False)
draw_scene(d, gx1, panel_y0 + 30 * S, demo_size, smooth=True)
# arrow between
ay = panel_y0 + 30 * S + demo_size // 2
ax0, ax1 = gx0 + demo_size + 10 * S, gx1 - 10 * S
d.line([(ax0, ay), (ax1 - 8 * S, ay)], fill=CYAN, width=3 * S)
d.polygon([(ax1, ay), (ax1 - 10 * S, ay - 6 * S), (ax1 - 10 * S, ay + 6 * S)], fill=CYAN)

def left_text(y, text, f, fill):
    d.text((55 * S, y), text, font=f, fill=fill)

left_text(panel_y1 - 20 * S, "B E F O R E", f_tag, DIM)
tw = d.textlength("A F T E R", font=f_tag)
d.text((w - 55 * S - demo_size + (demo_size - tw) / 2, panel_y1 - 20 * S), "A F T E R", font=f_tag, fill=CYAN)
left_text(panel_y0 + 10 * S, "WHAT THE APP DOES:", f_tag, DIM)

# ---- 3. badges -----------------------------------------------------------------
by = 410 * S
badges = ["FREE", "OPEN SOURCE", "RUNS LOCAL"]
f_badge = font(9 * S)
total_w = 0
widths = []
for b in badges:
    bw = d.textlength(b, font=f_badge) + 26 * S
    widths.append(bw)
    total_w += bw
bx = (w - (total_w + 2 * 12 * S)) / 2
for b, bw in zip(badges, widths):
    rrect(bx, by, bx + bw, by + 22 * S, 11 * S, outline=CYAN, width=S)
    tw = d.textlength(b, font=f_badge)
    d.text((bx + (bw - tw) / 2, by + 6 * S), b, font=f_badge, fill=TEXT)
    bx += bw + 12 * S

# ---- 4. feature list ------------------------------------------------------------
fy = 510 * S
f_feat = font(10 * S)
feats = [("9", "AI models included"), ("6 GB", "GPU is plenty"), ("0", "uploads. ever.")]
for big, small in feats:
    rrect(40 * S, fy, w - 40 * S, fy + 40 * S, 8 * S, fill=(24, 29, 54))
    d.text((58 * S, fy + 8 * S), big, font=font(15 * S), fill=CYAN)
    d.text((140 * S, fy + 12 * S), small, font=f_feat, fill=TEXT)
    fy += 50 * S

# ---- 5. resolution chips ----------------------------------------------------------
ry = fy + 34 * S
f_res = font(13 * S)
chips = ["2x", "4x", "8x"]
cw = 52 * S
total = cw * 3 + 2 * 14 * S
rx = (w - total) / 2
for c in chips:
    rrect(rx, ry, rx + cw, ry + 34 * S, 8 * S, outline=VIOLET, width=2 * S)
    tw = d.textlength(c, font=f_res)
    d.text((rx + (cw - tw) / 2, ry + 7 * S), c, font=f_res, fill=TEXT)
    rx += cw + 14 * S
f_cap = font(8 * S)
center_text(ry + 42 * S, "U P   T O   8 K", f_cap, DIM)
f_close = font(10 * S)
center_text(ry + 92 * S, "your images. your gpu. your rules.", f_close, TEXT, bold=True)

# ---- 6. footer -------------------------------------------------------------------
f_foot = font(9 * S)
center_text(h - 36 * S, "nothing leaves your computer", f_foot, DIM)

img = img.resize((W, H), Image.LANCZOS)
img.save(ROOT / "setup-art.png")
print(f"saved {ROOT / 'setup-art.png'} ({(ROOT / 'setup-art.png').stat().st_size/1024:.0f} KB)")
