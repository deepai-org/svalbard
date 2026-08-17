#!/usr/bin/env python3
"""Render the generated GDS for visual design review inside the tool image."""

import pya
from PIL import Image, ImageDraw

WIDTH = 1400
HEIGHT = 1800
MARGIN = 55
PALETTE = [
    (86, 180, 233, 105),
    (230, 159, 0, 115),
    (0, 158, 115, 105),
    (240, 228, 66, 105),
    (204, 121, 167, 105),
    (213, 94, 0, 115),
    (0, 114, 178, 115),
    (141, 211, 199, 105),
    (251, 128, 114, 105),
    (190, 186, 218, 105),
]

layout = pya.Layout()
layout.read("/work/serdes_tx.gds")
top = layout.top_cell()
bbox = top.bbox()
scale = min(
    (WIDTH - 2 * MARGIN) / bbox.width(),
    (HEIGHT - 2 * MARGIN) / bbox.height(),
)
xoff = MARGIN - bbox.left * scale
yoff = MARGIN + bbox.top * scale


def pixel(point):
    return (round(xoff + point.x * scale), round(yoff - point.y * scale))


canvas = Image.new("RGBA", (WIDTH, HEIGHT), (16, 18, 24, 255))
for order, layer_index in enumerate(layout.layer_indices()):
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = PALETTE[order % len(PALETTE)]
    outline = color[:3] + (225,)
    for shape in top.shapes(layer_index).each():
        if shape.is_box():
            box = shape.box
            left, bottom = pixel(pya.Point(box.left, box.bottom))
            right, top_y = pixel(pya.Point(box.right, box.top))
            draw.rectangle(
                [(min(left, right), min(bottom, top_y)), (max(left, right), max(bottom, top_y))],
                fill=color,
                outline=outline,
                width=1,
            )
        elif shape.is_polygon():
            points = [pixel(point) for point in shape.polygon.each_point_hull()]
            draw.polygon(points, fill=color, outline=outline)
        elif shape.is_path():
            points = [pixel(point) for point in shape.path.polygon().each_point_hull()]
            draw.polygon(points, fill=color, outline=outline)
        elif shape.is_text():
            draw.text(pixel(shape.text.trans.disp), shape.text.string, fill=(255, 255, 255, 255))
    canvas = Image.alpha_composite(canvas, overlay)

ImageDraw.Draw(canvas).text(
    (MARGIN, 18),
    f"GF180 serdes_tx | {bbox.width() * layout.dbu:.1f} x "
    f"{bbox.height() * layout.dbu:.1f} um",
    fill=(235, 239, 245, 255),
)
canvas.convert("RGB").save("/work/serdes_tx-layout.png")
