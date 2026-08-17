#!/usr/bin/env python3
"""Render the generated Alexander phase-detector GDS for physical review."""

import pya
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT, MARGIN = 1800, 1200, 70
COLORS = [
    (74, 144, 226, 95), (245, 166, 35, 110), (80, 227, 194, 90),
    (248, 231, 28, 100), (189, 103, 217, 100), (255, 92, 92, 105),
    (61, 214, 255, 105), (147, 220, 132, 95), (255, 151, 112, 105),
]

layout = pya.Layout()
layout.read("/work/cml_alexander_boundary.gds")
top = layout.top_cell()
bbox = top.bbox()
scale = min((WIDTH - 2 * MARGIN) / bbox.width(), (HEIGHT - 2 * MARGIN) / bbox.height())
xoff = MARGIN - bbox.left * scale
yoff = MARGIN + bbox.top * scale


def pixel(point):
    return round(xoff + point.x * scale), round(yoff - point.y * scale)


canvas = Image.new("RGBA", (WIDTH, HEIGHT), (13, 17, 23, 255))
for order, layer_index in enumerate(layout.layer_indices()):
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = COLORS[order % len(COLORS)]
    for shape in top.shapes(layer_index).each():
        if shape.is_box():
            box = shape.box
            a = pixel(pya.Point(box.left, box.bottom))
            b = pixel(pya.Point(box.right, box.top))
            draw.rectangle([(min(a[0], b[0]), min(a[1], b[1])),
                            (max(a[0], b[0]), max(a[1], b[1]))],
                           fill=color, outline=color[:3] + (220,), width=1)
        elif shape.is_polygon():
            draw.polygon([pixel(point) for point in shape.polygon.each_point_hull()],
                         fill=color, outline=color[:3] + (220,))
        elif shape.is_text():
            draw.text(pixel(shape.text.trans.disp), shape.text.string,
                      fill=(255, 255, 255, 255))
    canvas = Image.alpha_composite(canvas, overlay)

draw = ImageDraw.Draw(canvas)
font = ImageFont.load_default()
draw.rounded_rectangle((18, 14, 1120, 52), radius=8, fill=(5, 8, 12, 225),
                       outline=(92, 116, 145, 255), width=1)
draw.text((32, 25),
          f"GF180 half-rate Alexander boundary | {bbox.width() * layout.dbu:.1f} x "
          f"{bbox.height() * layout.dbu:.1f} um | DRC 0 | unique LVS | 463R/178C PEX",
          font=font, fill=(239, 244, 250, 255))
draw.rounded_rectangle((1150, 14, 1782, 52), radius=8, fill=(5, 8, 12, 225),
                       outline=(92, 116, 145, 255), width=1)
draw.text((1164, 25), "EARLY = PREV xor EDGE | LATE = EDGE xor CUR",
          font=font, fill=(239, 244, 250, 255))


def annotate(text, x_um, y_um, color):
    x, y = pixel(pya.Point(round(x_um / layout.dbu), round(y_um / layout.dbu)))
    box = draw.textbbox((x, y), text, font=font, anchor="mm")
    draw.rounded_rectangle((box[0] - 7, box[1] - 4, box[2] + 7, box[3] + 4),
                           radius=5, fill=(5, 8, 12, 210), outline=color, width=2)
    draw.text((x, y), text, font=font, fill=(245, 248, 252, 255), anchor="mm")


annotate("EARLY XOR", -24, 28, (80, 227, 194, 255))
annotate("LATE XOR", 24, 28, (80, 227, 194, 255))
annotate("stacked switching pairs", -24, 13, (245, 166, 35, 255))
annotate("stacked switching pairs", 24, 13, (245, 166, 35, 255))
annotate("programmable tails", 0, -13, (189, 103, 217, 255))
annotate("contacted guard ring", 0, 39.6, (255, 92, 92, 255))

canvas.convert("RGB").save("/work/cml_alexander_boundary-layout.png", quality=94)
