#!/usr/bin/env python3
"""Render minimum, fast-under-default-area, and default NAND2 layouts."""
from pathlib import Path

import pya
from PIL import Image, ImageDraw

WIDTH, HEIGHT, MARGIN = 1800, 900, 55
COLORS = [(86, 180, 233, 110), (230, 159, 0, 120), (0, 158, 115, 110),
          (240, 228, 66, 105), (204, 121, 167, 110), (213, 94, 0, 120),
          (0, 114, 178, 120), (141, 211, 199, 110)]
CELLS = (
    ("nand2_min_3v3", "minimum FO1", "1.96 x 2.75 um"),
    ("nand2_fast_3v3", "fast, area < default", "1.96 x 5.06 um"),
    ("nand2_std_5v", "default 7-track", "2.80 x 3.92 um"),
)


def render(name: str, width: int, height: int) -> Image.Image:
    layout = pya.Layout()
    layout.read(f"/work/{name}.gds")
    top = layout.top_cell()
    bbox = top.bbox()
    scale = min((width - 40) / bbox.width(), (height - 60) / bbox.height())
    xoff = 20 - bbox.left * scale
    yoff = 25 + bbox.top * scale
    canvas = Image.new("RGBA", (width, height), (16, 18, 24, 255))
    for order, layer_index in enumerate(layout.layer_indices()):
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        color = COLORS[order % len(COLORS)]
        for shape in top.shapes(layer_index).each():
            if shape.is_box():
                box = shape.box
                points = ((round(xoff + box.left * scale), round(yoff - box.bottom * scale)),
                          (round(xoff + box.right * scale), round(yoff - box.top * scale)))
                draw.rectangle([(min(points[0][0], points[1][0]), min(points[0][1], points[1][1])),
                                (max(points[0][0], points[1][0]), max(points[0][1], points[1][1]))],
                               fill=color, outline=color[:3] + (230,), width=1)
            elif shape.is_polygon():
                draw.polygon([(round(xoff + p.x * scale), round(yoff - p.y * scale))
                              for p in shape.polygon.each_point_hull()], fill=color,
                             outline=color[:3] + (230,))
        canvas = Image.alpha_composite(canvas, overlay)
    return canvas.convert("RGB")


canvas = Image.new("RGB", (WIDTH, HEIGHT), (10, 12, 18))
panel_width = WIDTH // len(CELLS)
draw = ImageDraw.Draw(canvas)
for index, (cell, title, dimensions) in enumerate(CELLS):
    panel = render(cell, panel_width - 2 * MARGIN, HEIGHT - 150)
    x = index * panel_width + MARGIN
    canvas.paste(panel, (x, 90))
    draw.text((x, 24), title, fill=(242, 245, 250))
    draw.text((x, 48), dimensions, fill=(180, 190, 205))
canvas.save("/work/nand2-layout-comparison.png")
assert Path("/work/nand2-layout-comparison.png").stat().st_size > 10000
