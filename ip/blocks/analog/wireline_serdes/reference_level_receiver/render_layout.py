#!/usr/bin/env python3
import pya
from PIL import Image, ImageDraw

WIDTH, HEIGHT, MARGIN = 1500, 1100, 50
COLORS = [(86,180,233,105),(230,159,0,115),(0,158,115,105),(240,228,66,105),(204,121,167,105),(213,94,0,115)]
layout=pya.Layout(); layout.read("/work/reference_level_receiver.gds")
top=layout.top_cell(); bbox=top.bbox(); scale=min((WIDTH-2*MARGIN)/bbox.width(),(HEIGHT-2*MARGIN)/bbox.height())
xoff,yoff=MARGIN-bbox.left*scale,MARGIN+bbox.top*scale
pixel=lambda p:(round(xoff+p.x*scale),round(yoff-p.y*scale))
canvas=Image.new("RGBA",(WIDTH,HEIGHT),(16,18,24,255))
for order,layer_index in enumerate(layout.layer_indices()):
    overlay=Image.new("RGBA",canvas.size,(0,0,0,0)); draw=ImageDraw.Draw(overlay); color=COLORS[order%len(COLORS)]
    for shape in top.shapes(layer_index).each():
        if shape.is_box():
            a,b=pixel(pya.Point(shape.box.left,shape.box.bottom)),pixel(pya.Point(shape.box.right,shape.box.top))
            draw.rectangle([(min(a[0],b[0]),min(a[1],b[1])),(max(a[0],b[0]),max(a[1],b[1]))],fill=color,outline=color[:3]+(225,),width=1)
        elif shape.is_polygon(): draw.polygon([pixel(p) for p in shape.polygon.each_point_hull()],fill=color,outline=color[:3]+(225,))
        elif shape.is_text(): draw.text(pixel(shape.text.trans.disp),shape.text.string,fill=(255,255,255,255))
    canvas=Image.alpha_composite(canvas,overlay)
ImageDraw.Draw(canvas).text((MARGIN,15),f"GF180 reference level receiver | {bbox.width()*layout.dbu:.1f} x {bbox.height()*layout.dbu:.1f} um",fill=(235,239,245,255))
canvas.convert("RGB").save("/work/reference-level-receiver-layout.png")
