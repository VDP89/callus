"""Render the callus launch GIF.

Concept: a Futurama-Bender-style robot mouth (a cold metal grille that opens
and closes) speaks, morphs into a warm human mouth (real lips with a cupid's
bow), and the human voice settles into the callus wordmark. Cold -> warm.
Everything is centered on the canvas.

Palette (project family fscars / lucy-syndrome):
    cream      #F5F1E8   surface
    navy       #0F1A2E   ink / wordmark / robot outline (cold)
    muted      #94A3B8   robot teeth + cold sound waves (cold)
    terracota  #CC785C   human lips + warm sound waves + underline (warm)

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
THROAT = (74, 40, 32)        # dark mouth interior (warm)

CX = W // 2
CY = H // 2                  # true center
MW = 90                      # mouth half-width
TEETH = 7                    # Bender grille teeth


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


def _lerp(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), CREAM)


def _speak(phase: float) -> float:
    """Open factor 0..1 from a continuous phase (reads as syllables)."""
    return 0.5 - 0.5 * math.cos(phase)


def _square_waves(draw: ImageDraw.ImageDraw, color, pulse: float) -> None:
    if color == CREAM:
        return
    for ring in (1, 2):
        d = 18 + ring * 22 + 6 * math.sin(pulse - ring)
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
        d = 18 + ring * 22 + 6 * math.sin(pulse - ring)
        rr = 18
        for sign in (-1, 1):
            x = CX + sign * (MW + d)
            box = [x - rr, CY - rr * 1.5, x + rr, CY + rr * 1.5]
            if sign < 0:
                draw.arc(box, start=300, end=420, fill=color, width=3)
            else:
                draw.arc(box, start=120, end=240, fill=color, width=3)


def _bender_mouth(draw: ImageDraw.ImageDraw, half_h: float, outline, teeth) -> None:
    """Futurama-Bender mouth: a metal grille capsule that opens and closes."""
    if outline == CREAM and teeth == CREAM:
        return
    half_h = max(8.0, half_h)
    draw.rounded_rectangle(
        [CX - MW, CY - half_h, CX + MW, CY + half_h],
        radius=min(14.0, half_h),
        outline=outline,
        width=5,
    )
    span = 2 * (MW - 18)
    step = span / (TEETH - 1)
    top, bot = CY - half_h + 8, CY + half_h - 8
    if bot > top:
        for k in range(TEETH):
            tx = CX - (MW - 18) + k * step
            draw.line([tx, top, tx, bot], fill=teeth, width=3)


def _human_lips(draw: ImageDraw.ImageDraw, open_gap: float, lip) -> None:
    """Organic lips with a cupid's bow; opening reveals throat + a tooth line."""
    if lip == CREAM:
        return
    xL, xR = CX - MW + 6, CX + MW - 6
    sh = open_gap / 2.0
    if open_gap > 3:
        draw.ellipse(
            [xL + 20, CY - open_gap + 2, xR - 20, CY + open_gap - 2], fill=THROAT
        )
        draw.rectangle(
            [xL + 28, CY - open_gap + 2, xR - 28, CY - open_gap + 8], fill=CREAM
        )
    # upper lip = two lobes meeting at a central cupid's bow
    draw.chord([xL, CY - 26 - sh, CX + 9, CY + 6 - sh], 180, 360, fill=lip)
    draw.chord([CX - 9, CY - 26 - sh, xR, CY + 6 - sh], 180, 360, fill=lip)
    # lower lip = one fuller curve
    draw.chord([xL, CY - 6 + sh, xR, CY + 34 + sh], 0, 180, fill=lip)


def _draw_wordmark(draw: ImageDraw.ImageDraw, ink, accent) -> None:
    text = "callus"
    b = draw.textbbox((0, 0), text, font=FONT_WORDMARK)
    tw = b[2] - b[0]
    left = (W - tw) // 2
    x = left - b[0]
    y = (CY - 14) - (b[1] + b[3]) // 2          # wordmark ink centered just above CY
    draw.text((x, y), text, font=FONT_WORDMARK, fill=ink)
    draw.line([left + 4, CY + 16, left + tw - 4, CY + 16], fill=accent, width=3)


def _draw_tagline(draw: ImageDraw.ImageDraw, color) -> None:
    text = "your voice, calibrated by use"
    b = draw.textbbox((0, 0), text, font=FONT_TAGLINE)
    tw = b[2] - b[0]
    x = (W - tw) // 2 - b[0]
    y = (CY + 44) - (b[1] + b[3]) // 2
    draw.text((x, y), text, font=FONT_TAGLINE, fill=color)


# --- phases -----------------------------------------------------------------

def _phase_robot(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    phase = i * 1.4
    half_h = 16 + _speak(phase) * 16
    _square_waves(draw, MUTED, pulse=i * 0.9)
    _bender_mouth(draw, half_h, outline=NAVY, teeth=MUTED)
    return img


def _phase_morph(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    phase = (n + i) * 1.4
    half_h = 16 + _speak(phase) * 16
    open_gap = 6 + _speak(phase) * 16
    _square_waves(draw, _lerp(MUTED, CREAM, t), pulse=i * 0.9)
    _curved_waves(draw, _lerp(CREAM, TERRACOTA, t), pulse=i * 0.9)
    _bender_mouth(draw, half_h, outline=_lerp(NAVY, CREAM, t), teeth=_lerp(MUTED, CREAM, t))
    _human_lips(draw, open_gap, lip=_lerp(CREAM, TERRACOTA, t))
    return img


def _phase_human(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    phase = i * 1.3
    open_gap = 4 + _speak(phase) * 20
    _curved_waves(draw, TERRACOTA, pulse=i * 0.9)
    _human_lips(draw, open_gap, lip=TERRACOTA)
    return img


def _phase_resolve(i: int, n: int) -> Image.Image:
    img = _new_frame()
    draw = ImageDraw.Draw(img)
    t = i / max(n - 1, 1)
    if t < 0.7:
        _human_lips(draw, 4, lip=_lerp(TERRACOTA, CREAM, t / 0.7))
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
    b = draw.textbbox((0, 0), badge, font=FONT_BADGE)
    draw.text((W - (b[2] - b[0]) - 24, H - 30), badge, font=FONT_BADGE, fill=MUTED)
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
