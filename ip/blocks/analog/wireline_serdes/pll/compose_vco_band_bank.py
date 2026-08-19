#!/usr/bin/env python3
"""Compose complete-band GDS renders into a physical review index."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

VARIANTS = (
    "center", "fast", "ultra_fast", "slow", "high_gain", "ss_ff", "ss_ss",
    "margin_slow", "margin_fast", "typ_margin_slow", "ss_ff_margin_slow",
    "ss_ff_margin_fast",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    parser.add_argument(
        "--title",
        default="GF180MCU complete CML VCO-band parents — emitted-GDS renders",
    )
    args = parser.parse_args()
    variants = tuple(args.variants)
    columns, tile_width, tile_height = 3, 960, 520
    rows = (len(variants) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * tile_width, rows * tile_height + 40), "#202329")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
        footer = ImageFont.truetype("DejaVuSans.ttf", 15)
    except OSError:
        font = footer = ImageFont.load_default()
    for index, variant in enumerate(variants):
        row, column = divmod(index, columns)
        image = Image.open(args.work / f"cml_vco_band_{variant}-layout.png").convert("RGB")
        image = ImageOps.contain(image, (tile_width - 24, tile_height - 58))
        x = column * tile_width + (tile_width - image.width) // 2
        y = row * tile_height + 40 + (tile_height - 48 - image.height) // 2
        canvas.paste(image, (x, y))
        draw.text((column * tile_width + 14, row * tile_height + 10),
                  variant.replace("_", " ").upper(), fill="#d8dde6", font=font)
    draw.text((14, rows * tile_height + 10),
              args.title,
              fill="#aeb5c0", font=footer)
    canvas.save(args.output, optimize=True)


if __name__ == "__main__":
    main()
