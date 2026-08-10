#!/usr/bin/env python3
"""
Generate the launcher's wallpaper pack: purely procedural, combustion/
chemistry-flavored abstract backdrops. No photographs, no external
downloads -- every pixel is computed here, so there is no licensing
question at all (unlike scraping "openly available" stock photos, which
still carries per-image attribution/license terms that would need tracking
and could break if a source disappears).

Each wallpaper is saved to assets/wallpapers/<id>.png with a sidecar
assets/wallpapers/<id>.json (name, author, source, license,
dominant_luminance, recommended_scrim_alpha) as documented in the visual
system plan (Session A3). Run with the GUI venv (needs Pillow, already a
.venv-gui dependency):

    ./.venv-gui/bin/python scripts/generate_wallpapers.py
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "assets" / "wallpapers"
SIZE = (1920, 1080)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mean_luminance(img: Image.Image) -> float:
    small = img.convert("L").resize((64, 36))
    pixels = list(small.getdata())
    return (sum(pixels) / len(pixels)) / 255.0


def _vertical_gradient(size, top_hex: str, bottom_hex: str) -> Image.Image:
    w, h = size
    top = _hex_to_rgb(top_hex)
    bottom = _hex_to_rgb(bottom_hex)
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        row = tuple(int(_lerp(top[i], bottom[i], t)) for i in range(3))
        for x in range(w):
            px[x, y] = row
    return img


def gen_flame_field(seed: int = 7) -> Image.Image:
    """Soft overlapping radial 'flame front' blobs -- reads as a diffuse
    combustion field rather than a literal photo of fire."""
    rng = random.Random(seed)
    base = _vertical_gradient(SIZE, "#0b0e17", "#1e2433")
    overlay = Image.new("RGB", SIZE, (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    palette = ["#ef4444", "#f59e0b", "#4f8ef7", "#38bdf8"]
    for _ in range(18):
        cx = rng.uniform(0, SIZE[0])
        cy = rng.uniform(0, SIZE[1])
        r = rng.uniform(120, 420)
        color = _hex_to_rgb(rng.choice(palette))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(140))
    return Image.blend(base, overlay, alpha=0.35)


def gen_reaction_network(seed: int = 11) -> Image.Image:
    """A faint node/edge graph, evoking a reaction network -- thin lines,
    low contrast, meant to sit behind text at low opacity."""
    rng = random.Random(seed)
    img = _vertical_gradient(SIZE, "#171c29", "#252b3b")
    draw = ImageDraw.Draw(img, "RGBA")
    nodes = [(rng.uniform(0, SIZE[0]), rng.uniform(0, SIZE[1])) for _ in range(40)]
    for i, (x0, y0) in enumerate(nodes):
        for (x1, y1) in nodes[i + 1:]:
            d = math.hypot(x1 - x0, y1 - y0)
            if d < 260:
                alpha = int(60 * (1 - d / 260))
                draw.line([(x0, y0), (x1, y1)], fill=(79, 142, 247, alpha), width=1)
    for x, y in nodes:
        r = rng.uniform(2, 5)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(148, 163, 184, 120))
    return img.convert("RGB").filter(ImageFilter.GaussianBlur(0.6))


def gen_arrhenius_mesh(seed: int = 13) -> Image.Image:
    """A dim wireframe surface reminiscent of an Arrhenius/PRS response
    surface, rendered as a faint diagonal mesh over a dark gradient."""
    img = _vertical_gradient(SIZE, "#1e2433", "#0b0e17")
    draw = ImageDraw.Draw(img, "RGBA")
    step = 64
    rng = random.Random(seed)
    phase = rng.uniform(0, math.pi)
    for x in range(-SIZE[1], SIZE[0], step):
        pts = []
        for t in range(0, SIZE[0] + SIZE[1], 24):
            y = t
            xv = x + t + 40 * math.sin(t / 220.0 + phase)
            if 0 <= xv <= SIZE[0] and 0 <= y <= SIZE[1]:
                pts.append((xv, y))
        if len(pts) > 1:
            draw.line(pts, fill=(56, 189, 248, 28), width=1)
    return img.filter(ImageFilter.GaussianBlur(0.4))


def gen_twilight_gradient(seed: int = 3) -> Image.Image:
    return _vertical_gradient(SIZE, "#1e2433", "#0b0e17")


def gen_daybreak_gradient(seed: int = 5) -> Image.Image:
    return _vertical_gradient(SIZE, "#eef2ff", "#f4f5f7")


GENERATORS = {
    "flame-field": (gen_flame_field, "Procedural flame-front field", 0.55),
    "reaction-network": (gen_reaction_network, "Procedural reaction-network graph", 0.5),
    "arrhenius-mesh": (gen_arrhenius_mesh, "Procedural Arrhenius surface mesh", 0.5),
    "twilight-gradient": (gen_twilight_gradient, "Plain dark twilight gradient", 0.35),
    "daybreak-gradient": (gen_daybreak_gradient, "Plain light daybreak gradient", 0.2),
}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for wallpaper_id, (fn, name, recommended_scrim) in GENERATORS.items():
        img = fn()
        png_path = OUT_DIR / f"{wallpaper_id}.png"
        img.save(png_path)
        luminance = _mean_luminance(img)
        meta = {
            "id": wallpaper_id,
            "name": name,
            "author": "generated",
            "source": "scripts/generate_wallpapers.py (procedural, no external asset)",
            "license": "CC0-1.0 (originated by this repo; no third-party rights involved)",
            "dominant_luminance": round(luminance, 3),
            "recommended_scrim_alpha": recommended_scrim,
        }
        (OUT_DIR / f"{wallpaper_id}.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(f"  wrote {png_path.relative_to(REPO_ROOT)} (luminance={luminance:.3f})")

    credits = OUT_DIR / "CREDITS.md"
    lines = [
        "# Wallpaper pack -- provenance",
        "",
        "Every wallpaper here is procedurally generated by "
        "`scripts/generate_wallpapers.py` -- no photographs, no downloaded "
        "stock imagery, no third-party licensing to track.",
        "",
    ]
    for wallpaper_id, (_, name, _) in GENERATORS.items():
        lines.append(f"- **{wallpaper_id}** -- {name}. License: CC0-1.0 (originated here).")
    credits.write_text("\n".join(lines) + "\n")
    print(f"  wrote {credits.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
