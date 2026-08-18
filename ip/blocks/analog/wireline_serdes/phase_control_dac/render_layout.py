#!/usr/bin/env python3
"""Render the generated dual phase-control DAC GDS."""
import pya
from PIL import Image,ImageDraw,ImageFont
W,H,M=1800,1200,60; colors=[(74,144,226,90),(245,166,35,105),(80,227,194,90),(248,231,28,95),(189,103,217,100),(255,92,92,100),(61,214,255,100)]
l=pya.Layout(); l.read('/work/phase_control_dac.gds'); top=l.top_cell(); box=top.bbox(); scale=min((W-2*M)/box.width(),(H-2*M)/box.height()); xo=M-box.left*scale; yo=M+box.top*scale
def px(p): return round(xo+p.x*scale),round(yo-p.y*scale)
c=Image.new('RGBA',(W,H),(13,17,23,255))
for order,li in enumerate(l.layer_indices()):
 o=Image.new('RGBA',c.size,(0,0,0,0)); d=ImageDraw.Draw(o); col=colors[order%len(colors)]
 for s in top.shapes(li).each():
  if s.is_box():
   a=px(pya.Point(s.box.left,s.box.bottom)); b=px(pya.Point(s.box.right,s.box.top)); d.rectangle([(min(a[0],b[0]),min(a[1],b[1])),(max(a[0],b[0]),max(a[1],b[1]))],fill=col,outline=col[:3]+(220,),width=1)
  elif s.is_polygon(): d.polygon([px(p) for p in s.polygon.each_point_hull()],fill=col,outline=col[:3]+(220,))
  elif s.is_text(): d.text(px(s.text.trans.disp),s.text.string,fill='white')
 c=Image.alpha_composite(c,o)
d=ImageDraw.Draw(c); f=ImageFont.load_default(); d.rounded_rectangle((18,14,1120,52),8,fill=(5,8,12,225),outline=(92,116,145,255)); d.text((32,25),f"GF180 dual 5-bit phase-control R-2R DAC | {box.width()*l.dbu:.1f} x {box.height()*l.dbu:.1f} um",font=f,fill=(239,244,250,255))
def note(t,x,y,col):
 q=px(pya.Point(round(x/l.dbu),round(y/l.dbu))); bb=d.textbbox(q,t,font=f,anchor='mm'); d.rounded_rectangle((bb[0]-6,bb[1]-4,bb[2]+6,bb[3]+4),5,fill=(5,8,12,210),outline=col,width=2); d.text(q,t,font=f,fill='white',anchor='mm')
note('mirrored A / B R-2R ladders',0,66,(80,227,194,255)); note('matched shunts',0,38,(245,166,35,255)); note('high / low switch banks',0,-8,(189,103,217,255)); note('contacted substrate guard',0,97.6,(255,92,92,255))
c.convert('RGB').save('/work/phase_control_dac-layout.png',quality=94)
