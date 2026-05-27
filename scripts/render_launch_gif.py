"""Render the callus launch GIF.

Concept: a clean surface receives repeated strokes; the strokes consolidate
into a callus-shaped mark; the mark resolves into the callus wordmark with
the tagline "your voice, calibrated by use".

Palette matches the project family (fscars / lucy-syndrome):
    cream      #F5F1E8   surface
    navy       #0F1A2E   ink / wordmark
    terracota  #CC785C   accent / mark / underline
    muted      #94A3B8   tagline

Output: assets/callus-launch.gif at 600x400, ~3.5s loop, 9fps.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow required. pip install Pillow") from exc

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
OUT = ASSETS_DIR / "callus-launch.gif"

W, H = 600, 400
DURATION_MS = 110

CREAM = (245, 241, 232)
NAVY = (15, 26, 46)
TERRACOTA = (204, 120, 92)
MUTED = (148, 163, 184)

CX = W // 2
CY = H // 2 - 20


def _try_load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "JetBrainsMono-Bold.ttf" if bold else "JetBrainsMono-Regular.ttf",
        "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_WORDMARK = _try_load_font(54, bold=True)
FONT_TAGLINE = _try_load_font(15)
FONT_BADGE = _try_load_font(11, bold=True)


def _new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), CREAM)


def _draw_wordmark(draw: ImageDraw.ImageDraw) -> None:
    text = "callus"
    bbox = draw.textbbox((0, 0), text, font=FONT_WORDMARK)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = (H - th) // 2 - 30
    draw.text((x, y), text, font=FONT_WORDMARK, fill=NAVY)
    underline_y = y + th + 6
    draw.line([x + 4, underline_y, x + tw - 4, underline_y], fill=TERRACOTA, width=3)


def _draw_tagline(draw: ImageDraw.ImageDraw) -> None:
    text = "your voice, calibrated by use"
    bbox = draw.textbbox((0, 0), text, font=FONT_TAGLINE)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = (H - th) // 2 + 50
    draw.text((x, y), text, font=FONT_TAGLINE, fill=MUTED)


def _draw_stroke(draw: ImageDraw.ImageDraw, t: float, seed: int) -> None:
    rng = random.Random(seed)
    rx, ry = 70, 35
    angle = rng.uniform(-math.pi / 4, math.pi / 4)
    sx = CX + int(rng.uniform(-rx + 10, rx - 10))
    sy = CY + int(rng.uniform(-ry + 8, ry - 8))
    length = int(20 + 20 * t)
    dx = int(length * math.cos(angle))
    dy = int(length * math.sin(angle))
    draw.line([sx - dx, sy - dy, sx + dx, sy + dy], fill=NAVY, width=2)


def _phase_intro(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    alpha = int(40 * t)
    if alpha > 0:
        draw.ellipse(
            [CX - 80, CY - 40, CX + 80, CY + 40],
            outline=MUTED,
            width=1,
        )
    return img


def _phase_strokes(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    draw.ellipse([CX - 80, CY - 40, CX + 80, CY + 40], outline=MUTED, width=1)
    strokes_so_far = int(2 + 12 * (i / max(n - 1, 1)))
    for k in range(strokes_so_far):
        _draw_stroke(draw, t=k / max(strokes_so_far - 1, 1), seed=k)
    return img


def _phase_consolidate(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    for k in range(14):
        _draw_stroke(draw, t=1.0, seed=k)
    draw.ellipse([CX - 80, CY - 40, CX + 80, CY + 40], outline=TERRACOTA, width=3)
    if t > 0.3:
        draw.ellipse([CX - 64, CY - 30, CX + 64, CY + 30], outline=NAVY, width=2)
    if t > 0.6:
        draw.ellipse([CX - 46, CY - 21, CX + 46, CY + 21], outline=NAVY, width=1)
    return img


def _phase_resolve(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    _draw_wordmark(draw)
    if t > 0.5:
        _draw_tagline(draw)
    return img


def _phase_hold(_i: int, _n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    _draw_wordmark(draw)
    _draw_tagline(draw)
    badge = "v0.1.0"
    bbox = draw.textbbox((0, 0), badge, font=FONT_BADGE)
    bw = bbox[2] - bbox[0]
    draw.text((W - bw - 24, H - 30), badge, font=FONT_BADGE, fill=MUTED)
    return img


def render() -> None:
    frames: list[Image.Image] = []
    for i in range(6):
        frames.append(_phase_intro(i, 6))
    for i in range(10):
        frames.append(_phase_strokes(i, 10))
    for i in range(6):
        frames.append(_phase_consolidate(i, 6))
    for i in range(6):
        frames.append(_phase_resolve(i, 6))
    for i in range(6):
        frames.append(_phase_hold(i, 6))

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Wrote: {OUT}  ({len(frames)} frames, {DURATION_MS}ms each)")


if __name__ == "__main__":
    render()
