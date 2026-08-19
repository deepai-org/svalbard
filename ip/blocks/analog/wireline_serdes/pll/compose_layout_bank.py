#!/usr/bin/env python3
"""Compose the emitted VCO-tile GDS renders into a reviewable visual index."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


TILES = (
    ("SLOW  C=2.40  R=5.25", "slow"),
    ("CENTER  C=0.80  R=5.25", "center"),
    ("FAST  C=0.60  R=5.25", "fast"),
    ("ULTRA FAST  C=0.50  R=4.25", "ultra_fast"),
    ("HIGH GAIN  C=0.50  R=6.50", "high_gain"),
    ("SS/FF  C=0.37 W=4.0 R=6.25 tails=15/5", "ss_ff"),
    ("SS/SS  C=0.38 W=4.0 R=4.00 tails=15/6", "ss_ss"),
    ("MARGIN LOW  C=0.50 W=4.0 R=4.00 tails=15/6", "margin_slow"),
    ("MARGIN HIGH  C=0.37 W=3.2 R=4.00 tails=15/6", "margin_fast"),
    ("TYP MARGIN LOW  C=0.85 W=4.0 R=5.25", "typ_margin_slow"),
    ("SS/FF MARGIN LOW  C=0.40 W=4.0 R=6.25 tails=15/5", "ss_ff_margin_slow"),
    ("SS/FF MARGIN HIGH  C=0.37 W=3.2 R=6.25 tails=15/5", "ss_ff_margin_fast"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    columns = 4
    rows = (len(TILES) + columns - 1) // columns
    tile_width, tile_height = 720, 720
    canvas = Image.new("RGB", (columns * tile_width, rows * tile_height + 36), "#202329")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
        footer_font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = footer_font = ImageFont.load_default()

    for index, (label, variant) in enumerate(TILES):
        row, column = divmod(index, columns)
        image_path = (args.source / "layout.png" if variant == "center" else
                      args.work / f"cml_vco_delay_{variant}-layout.png")
        image = Image.open(image_path).convert("RGB")
        image = ImageOps.contain(image, (tile_width - 32, tile_height - 62))
        x = column * tile_width + (tile_width - image.width) // 2
        y = row * tile_height + 42 + (tile_height - 52 - image.height) // 2
        canvas.paste(image, (x, y))
        draw.text((column * tile_width + 16, row * tile_height + 14), label,
                  fill="#d8dde6", font=font)

    draw.text((16, rows * tile_height + 10),
              "GF180MCU CML VCO delay-tile family — KLayout renders of emitted GDS; dimensions in um",
              fill="#aeb5c0", font=footer_font)
    canvas.save(args.output, optimize=True)


if __name__ == "__main__":
    main()
