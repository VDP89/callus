"""Render the callus launch GIF.

Concept: a robot mouth speaks in cold, mechanical segments; it morphs into a
warm human mouth that keeps speaking; the human voice settles into the callus
wordmark. Reads as "machine voice -> your voice". Cold -> warm.

Minimal line-art. The mouth is one rounded shape throughout:
    robot  -> boxy rounded rectangle + equalizer bars + square sound brackets
    human  -> soft pill + open/close + curved sound waves
The morph interpolates corner radius, color (navy/muted -> terracota), and
cross-fades the bars out and the curves in.

Palette (project family fscars / lucy-syndrome):
    cream      #F5F1E8   surface
    navy       #0F1A2E   ink / wordmark / robot outline (cold)
    muted      #94A3B8   robot bars + cold sound waves (cold)
    terracota  #CC785C   human mouth + warm sound waves + underline (warm)

Output: assets/callus-launch.gif at 600x400, ~4.5s loop, ~9fps.
"""
from __future__ import annotations

import math
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
CY = H // 2 - 24
MW = 88          # mouth half-width
BARS = 5


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


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), CREAM)


def _speak(phase: float) -> float:
    """Open factor 0..1 driven by a continuous phase (reads as syllables)."""
    return 0.5 - 0.5 * math.cos(phase)


def _mouth_outline(
    draw: ImageDraw.ImageDraw, half_h: float, radius: float, color, width: int = 4
) -> None:
    half_h = max(6.0, half_h)
    radius = max(2.0, min(radius, MW, half_h))
    draw.rounded_rectangle(
        [CX - MW, CY - half_h, CX + MW, CY + half_h],
        radius=radius,
        outline=color,
        width=width,
    )


def _equalizer_bars(draw: ImageDraw.ImageDraw, energy: float, color, phase: float) -> None:
    if color == CREAM:
        return
    span = 2 * (MW - 26)
    step = span / (BARS - 1)
    for k in range(BARS):
        bx = CX - (MW - 26) + k * step
        bh = 6 + energy * 22 * (0.45 + 0.55 * abs(math.sin(phase * 0.9 + k * 1.7)))
        draw.line([bx, CY - bh, bx, CY + bh], fill=color, width=9)


def _square_waves(draw: ImageDraw.ImageDraw, color, pulse: float) -> None:
    if color == CREAM:
        return
    for ring in (1, 2):
        d = 16 + ring * 20 + 6 * math.sin(pulse - ring)
        h = 13
        for sign in (-1, 1):
            x = CX + sign * (MW + d)
            draw.line([x, CY - h, x, CY + h], fill=color, width=3)
            draw.line([x, CY - h, x - sign * 9, CY - h], fill=color, width=3)
            draw.line([x, CY + h, x - sign * 9, CY + h], fill=color, width=3)


def _curved_waves(draw: ImageDraw.ImageDraw, color, pulse: float) -> None:
    if color == CREAM:
        return
    for ring in (1, 2):
        d = 16 + ring * 20 + 6 * math.sin(pulse - ring)
        rr = 18
        for sign in (-1, 1):
            x = CX + sign * (MW + d)
            box = [x - rr, CY - rr * 1.5, x + rr, CY + rr * 1.5]
            if sign < 0:
                draw.arc(box, start=300, end=420, fill=color, width=3)
            else:
                draw.arc(box, start=120, end=240, fill=color, width=3)


def _draw_wordmark(draw: ImageDraw.ImageDraw, ink, accent) -> None:
    text = "callus"
    bbox = draw.textbbox((0, 0), text, font=FONT_WORDMARK)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = CY - th // 2 - 6
    draw.text((x, y), text, font=FONT_WORDMARK, fill=ink)
    uy = y + th + 8
    draw.line([x + 4, uy, x + tw - 4, uy], fill=accent, width=3)


def _draw_tagline(draw: ImageDraw.ImageDraw, color) -> None:
    text = "your voice, calibrated by use"
    bbox = draw.textbbox((0, 0), text, font=FONT_TAGLINE)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, CY + 56), text, font=FONT_TAGLINE, fill=color)


# --- phases -----------------------------------------------------------------

def _phase_robot(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    phase = i * 1.4
    energy = _speak(phase)
    _square_waves(draw, MUTED, pulse=i * 0.9)
    _mouth_outline(draw, half_h=34, radius=12, color=NAVY)
    _equalizer_bars(draw, energy=energy, color=MUTED, phase=phase)
    return img


def _phase_morph(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    phase = (n + i) * 1.4
    energy = _speak(phase)
    half_h = 34 - 6 * t                       # settle a touch
    radius = 12 + (half_h - 12) * t           # box -> pill
    outline = _lerp(NAVY, TERRACOTA, t)
    # cold elements fade out, warm fade in (fade via lerp to/from cream)
    _square_waves(draw, _lerp(MUTED, CREAM, t), pulse=i * 0.9)
    _curved_waves(draw, _lerp(CREAM, TERRACOTA, t), pulse=i * 0.9)
    _mouth_outline(draw, half_h=half_h, radius=radius, color=outline)
    _equalizer_bars(draw, energy=energy, color=_lerp(MUTED, CREAM, t), phase=phase)
    return img


def _phase_human(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    phase = i * 1.3
    open01 = _speak(phase)
    half_h = 10 + open01 * 22
    _curved_waves(draw, TERRACOTA, pulse=i * 0.9)
    _mouth_outline(draw, half_h=half_h, radius=half_h, color=TERRACOTA)
    return img


def _phase_resolve(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    # human mouth fades out, wordmark fades in
    if t < 0.7:
        _mouth_outline(
            draw, half_h=16, radius=16, color=_lerp(TERRACOTA, CREAM, t / 0.7)
        )
    _draw_wordmark(draw, ink=_lerp(CREAM, NAVY, t), accent=_lerp(CREAM, TERRACOTA, t))
    if t > 0.5:
        _draw_tagline(draw, _lerp(CREAM, MUTED, (t - 0.5) / 0.5))
    return img


def _phase_hold(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    _draw_wordmark(draw, ink=NAVY, accent=TERRACOTA)
    _draw_tagline(draw, MUTED)
    badge = "v0.2.0"
    bbox = draw.textbbox((0, 0), badge, font=FONT_BADGE)
    bw = bbox[2] - bbox[0]
    draw.text((W - bw - 24, H - 30), badge, font=FONT_BADGE, fill=MUTED)
    return img


def render() -> None:
    frames: list[Image.Image] = []
    plan = [
        (_phase_robot, 10),
        (_phase_morph, 8),
        (_phase_human, 10),
        (_phase_resolve, 6),
        (_phase_hold, 7),
    ]
    for fn, count in plan:
        for i in range(count):
            frames.append(fn(i, count))

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
