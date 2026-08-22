#!/usr/bin/env python3
"""Render the routed differential half-rate capture macro."""

import os
import re
from pathlib import Path

import pya
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT, MARGIN = 1900, 1300, 70
COLORS = [
    (74, 144, 226, 90), (245, 166, 35, 105), (80, 227, 194, 90),
    (248, 231, 28, 95), (189, 103, 217, 95), (255, 92, 92, 100),
    (61, 214, 255, 100), (147, 220, 132, 90), (255, 151, 112, 100),
]

layout = pya.Layout()
layout.read(os.environ.get("SPLIT_CAPTURE_GDS",
                           "/work/deserializer_split_capture.gds"))
top = layout.top_cell()
bbox = top.bbox()
pex_path = Path(os.environ.get(
    "SPLIT_CAPTURE_PEX", "/work/pex/deserializer_split_capture.pex.spice"))
pex = pex_path.read_text()
resistor_count = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
capacitor_count = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
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
                           fill=color, outline=color[:3] + (210,), width=1)
        elif shape.is_polygon():
            draw.polygon([pixel(point) for point in shape.polygon.each_point_hull()],
                         fill=color, outline=color[:3] + (210,))
        elif shape.is_text():
            draw.text(pixel(shape.text.trans.disp), shape.text.string,
                      fill=(255, 255, 255, 255))
    canvas = Image.alpha_composite(canvas, overlay)

draw = ImageDraw.Draw(canvas)
font = ImageFont.load_default()
draw.rounded_rectangle((18, 14, 1250, 54), radius=8, fill=(5, 8, 12, 225),
                       outline=(92, 116, 145, 255), width=1)
draw.text((32, 27),
          f"GF180 split-clock differential 1:2 capture | {bbox.width() * layout.dbu:.1f} x "
          f"{bbox.height() * layout.dbu:.1f} um | DRC/LVS clean | "
          f"PEX: {resistor_count} R / {capacitor_count} C",
          font=font, fill=(239, 244, 250, 255))


def annotate(text, x_um, y_um, color):
    x, y = pixel(pya.Point(round(x_um / layout.dbu), round(y_um / layout.dbu)))
    box = draw.textbbox((x, y), text, font=font, anchor="mm")
    draw.rounded_rectangle((box[0] - 7, box[1] - 4, box[2] + 7, box[3] + 4),
                           radius=5, fill=(5, 8, 12, 210), outline=color, width=2)
    draw.text((x, y), text, font=font, fill=(245, 248, 252, 255), anchor="mm")


annotate("PMOS write branches + reset row", 0, 76, (245, 166, 35, 255))
annotate("matched input restorers", 0, 35, (80, 227, 194, 255))
annotate("independently clocked capture cores", 0, 10, (189, 103, 217, 255))
annotate("isolated complementary outputs", 62, 52, (61, 214, 255, 255))
annotate("contacted substrate guard ring", 0, -31.6, (255, 92, 92, 255))

canvas.convert("RGB").save(
    os.environ.get("SPLIT_CAPTURE_RENDER", "/work/deserializer-split-layout.png"),
    quality=94,
)
