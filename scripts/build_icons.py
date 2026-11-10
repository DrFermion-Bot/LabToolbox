#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_icons.py - generate the replaceable LabToolbox application icons.

Creates:
    assets/labtoolbox.ico    multi-resolution Windows icon (16-256 px)
    assets/labtoolbox.png    1024x1024 master image (useful for docs / other tools)
    assets/labtoolbox.icns   macOS icon (PNG-based ICNS, 16-1024 px)

The icons are plain placeholders: replace them with your own artwork and re-run
this script only if you also want the PNG/ICO/ICNS derived from it. Any valid
.ico / .icns dropped at these paths is picked up automatically by
labtoolbox.spec and installer.iss.

Usage:
    python scripts/build_icons.py            # (requires Pillow)
"""
from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 1024


def rounded_rect_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=255)
    return mask


def draw_master() -> Image.Image:
    """Deep-blue rounded square + white Erlenmeyer flask with liquid and bubbles."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # vertical gradient background (dark navy -> lab blue)
    grad = Image.new("RGBA", (1, SIZE), (0, 0, 0, 255))
    top, bottom = (11, 31, 75), (30, 90, 168)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    grad = grad.resize((SIZE, SIZE))
    img.paste(grad, (0, 0), rounded_rect_mask(SIZE, int(SIZE * 0.22)))

    d = ImageDraw.Draw(img)
    cx = SIZE // 2
    white = (246, 250, 255, 255)
    liquid = (64, 211, 255, 255)

    # flask neck + body (outline by drawing thick polylines / polygons)
    neck_w = int(SIZE * 0.105)
    neck_top = int(SIZE * 0.20)
    neck_bottom = int(SIZE * 0.40)
    body_top = int(SIZE * 0.40)
    body_bottom = int(SIZE * 0.80)
    body_left = int(SIZE * 0.22)
    body_right = int(SIZE * 0.78)

    # body: trapezoid then rounded bottom
    d.polygon(
        [
            (cx - neck_w, neck_bottom),
            (cx + neck_w, neck_bottom),
            (body_right, body_bottom - int(SIZE * 0.05)),
            (body_right, body_bottom),
            (body_left, body_bottom),
            (body_left, body_bottom - int(SIZE * 0.05)),
        ],
        fill=white,
    )
    d.rounded_rectangle(
        [body_left, body_bottom - int(SIZE * 0.09), body_right, body_bottom],
        radius=int(SIZE * 0.045),
        fill=white,
    )
    # neck + rim
    d.rectangle([cx - neck_w, neck_top, cx + neck_w, neck_bottom], fill=white)
    rim_w = neck_w + int(SIZE * 0.03)
    d.rounded_rectangle(
        [cx - rim_w, neck_top - int(SIZE * 0.035), cx + rim_w, neck_top],
        radius=int(SIZE * 0.012),
        fill=white,
    )

    # liquid: fill lower part of the body, clipped by the flask shape
    flask_mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(flask_mask)
    md.polygon(
        [
            (cx - neck_w, neck_bottom),
            (cx + neck_w, neck_bottom),
            (body_right, body_bottom - int(SIZE * 0.05)),
            (body_right, body_bottom),
            (body_left, body_bottom),
            (body_left, body_bottom - int(SIZE * 0.05)),
        ],
        fill=255,
    )
    md.rounded_rectangle(
        [body_left, body_bottom - int(SIZE * 0.09), body_right, body_bottom],
        radius=int(SIZE * 0.045),
        fill=255,
    )
    liquid_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ld = ImageDraw.Draw(liquid_layer)
    liquid_top = int(SIZE * 0.60)
    ld.polygon(
        [
            (int(SIZE * 0.14), liquid_top),
            (int(SIZE * 0.86), liquid_top),
            (int(SIZE * 0.80), body_bottom - int(SIZE * 0.02)),
            (int(SIZE * 0.20), body_bottom - int(SIZE * 0.02)),
        ],
        fill=liquid,
    )
    img.paste(liquid_layer, (0, 0), Image.composite(flask_mask, Image.new("L", (SIZE, SIZE), 0), flask_mask))
    # Actually clip liquid by flask mask directly (also under the white outline):
    clipped = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clipped.paste(liquid_layer, (0, 0), flask_mask)
    img = Image.alpha_composite(img, clipped)
    d = ImageDraw.Draw(img)

    # bubbles in the liquid
    for bx, by, br in [
        (int(SIZE * 0.42), int(SIZE * 0.68), int(SIZE * 0.020)),
        (int(SIZE * 0.56), int(SIZE * 0.74), int(SIZE * 0.014)),
        (int(SIZE * 0.63), int(SIZE * 0.64), int(SIZE * 0.011)),
        (int(SIZE * 0.34), int(SIZE * 0.75), int(SIZE * 0.010)),
    ]:
        d.ellipse([bx - br, by - br, bx + br, by + br], fill=(246, 250, 255, 230))

    # rising bubbles above the liquid
    for bx, by, br in [
        (int(SIZE * 0.48), int(SIZE * 0.52), int(SIZE * 0.010)),
        (int(SIZE * 0.58), int(SIZE * 0.45), int(SIZE * 0.008)),
    ]:
        d.ellipse([bx - br, by - br, bx + br, by + br], fill=(180, 235, 255, 200))

    return img


# ---------------------------------------------------------------- ICNS writer
def write_icns(master: Image.Image, dest: Path) -> None:
    """Minimal PNG-based ICNS writer (valid for macOS 10.7+)."""
    # (icns type, pixel size) - 'icp4'..'icp6' legacy 32-bit entries also accept PNG in practice;
    # ic07..ic14 are the modern PNG entries.
    entries = [
        (b"icp4", 16),
        (b"icp5", 32),
        (b"icp6", 64),
        (b"ic07", 128),
        (b"ic08", 256),
        (b"ic09", 512),
        (b"ic10", 1024),
        (b"ic11", 32),    # 16x16@2x
        (b"ic12", 64),    # 32x32@2x
        (b"ic13", 256),   # 128x128@2x
        (b"ic14", 512),   # 256x256@2x
    ]
    chunks = []
    for kind, size in entries:
        resized = master.resize((size, size), Image.LANCZOS)
        from io import BytesIO

        buf = BytesIO()
        resized.save(buf, format="PNG")
        payload = buf.getvalue()
        chunks.append(kind + struct.pack(">I", len(payload) + 8) + payload)
    body = b"".join(chunks)
    dest.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = draw_master()
    png_path = ASSETS / "labtoolbox.png"
    master.save(png_path)

    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    # Save from the 1024 px master so Pillow emits every requested resolution.
    master.save(ASSETS / "labtoolbox.ico", format="ICO", sizes=ico_sizes)

    write_icns(master, ASSETS / "labtoolbox.icns")
    for p in (png_path, ASSETS / "labtoolbox.ico", ASSETS / "labtoolbox.icns"):
        print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())