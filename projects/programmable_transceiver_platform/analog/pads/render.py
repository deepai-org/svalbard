"""Render the generated flattened Magic geometry, not a conceptual floorplan."""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw
from layout import rectangles

parser = argparse.ArgumentParser()
parser.add_argument('layout',type=Path)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--title',default='Wired TX pad')
parser.add_argument('--primitive',action='store_true',help='Render a primitive without bond openings')
parser.add_argument('--scale',type=float,help='Pixels per micron; useful for tall core macros')
args = parser.parse_args()
layers = rectangles(args.layout)
visible = {k:v for k,v in layers.items() if k not in ('checkpaint',)}
xmax=max(r[2] for rs in visible.values() for r in rs)
ymax=max(r[3] for rs in visible.values() for r in rs)
xmin=min(0,min(r[0] for rs in visible.values() for r in rs))
ymin=min(0,min(r[1] for rs in visible.values() for r in rs))
scale=args.scale if args.scale is not None else (20 if args.primitive else 3)
if scale<=0:raise ValueError('Scale must be positive')
image=Image.new('RGB',(max(540 if args.primitive else 0,int((xmax-xmin)*scale)+80),int((ymax-ymin)*scale)+100),'#fcfcfc')
colors={'pwell':'#e8eddf','nwell':'#dfd7ef','polysilicon':'#db4949',
        'metal1':'#438ad6','metal2':'#63af7a','metal3':'#d2bd53',
        'metal4':'#cc8650','metal5':'#945d9e','padl':'#b3bac7','glass':'#f0f0f0'}
for layer,rs in visible.items():
    overlay=Image.new('RGBA',image.size)
    draw=ImageDraw.Draw(overlay)
    color=colors.get(layer,'#41624e')
    alpha=110 if layer.startswith('metal') else 160
    rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))+(alpha,)
    for x1,y1,x2,y2 in rs:
        box=(40+(x1-xmin)*scale,50+(ymax-y2)*scale,40+(x2-xmin)*scale,50+(ymax-y1)*scale)
        draw.rectangle(box,fill=rgb)
    image=Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB')
draw=ImageDraw.Draw(image)
draw.text((15,12),args.title+': actual generated geometry',fill='black')
draw.text((15,27),f'{xmax-xmin:.1f} x {ymax-ymin:.1f} um; '+('primitive only' if args.primitive else 'packaging integration pending'),fill='black')
openings=sorted(layers.get('glass',[]),key=lambda r:r[0])
if not args.primitive and len(openings)!=2:raise ValueError('Expected two physical bond openings for pair labels')
for name,opening in zip(('PAD P','PAD N'),openings):
    center=(opening[0]+opening[2])/2
    draw.text((40+(center-xmin)*scale,image.height-30),name,fill='black',anchor='mm')
args.output.parent.mkdir(parents=True,exist_ok=True)
image.save(args.output)
