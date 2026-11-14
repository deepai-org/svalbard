"""Labelled floorplan PNG with optional signal-flow arrows (PIL only).

    python3 fp_png.py <work> <out.png> [--flow] [--bg <klayout render png>] [--title "..."]

Draws die, core, pad families (with signal names), fixed reserves, the digital macro,
every placed block coloured by island (orientation marker for mirrored cells), decap
banks, and with --flow the signal-flow chains of floorplan_rules.CHAINS along their
planned routes (waypoints) between the real block centres and pad ports.
With --bg, the boxes are drawn as outlines over a KLayout render of the assembled GDS
(kl_render.py, same die-to-pixel mapping), in the style of docs/images/chip-assembly-*.png.
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLOR = {'rf': (200, 30, 30), 'conv': (140, 60, 180), 'pll': (220, 120, 0), 'wired': (20, 140, 70),
         'debug': (0, 130, 150), 'core': (90, 90, 90)}
CHAIN_COLOR = {'rf_rx': (220, 0, 0), 'rf_tx': (255, 140, 0), 'wired_rx': (0, 90, 220), 'wired_tx': (0, 170, 210),
               'clock': (150, 0, 190), 'host': (0, 150, 0)}
CHAIN_LABEL = {'rf_rx': 'RF RX: pad-LNA-mixers-BB filter-ADC-digital', 'rf_tx': 'RF TX: digital-DAC-filter-TX mix-sum-PA-pad',
               'wired_rx': 'Wired RX: pad-CTLE-slicer-CDR-digital', 'wired_tx': 'Wired TX: digital-serializer/driver-pad',
               'clock': 'Clocks: REF/AUX/PLLs-LO hub-mixers, rings-samplers', 'host': 'Host link: digital-gearboxes-pads'}
DIE = (3932.0, 5122.0)
SHORT = {'bbfilter_i': 'BB filter I', 'bbfilter_q': 'BB filter Q', 'rxmix_i': 'RX mix I', 'rxmix_q': 'RX mix Q',
         'txmix_i': 'TX mix I', 'txmix_q': 'TX mix Q', 'adc_i': 'ADC I', 'adc_q': 'ADC Q', 'dac_i': 'DAC I',
         'dac_q': 'DAC Q', 'lna': 'LNA', 'lo_ext': 'LO hub', 'txsum': 'TX sum',
         'rfdriver': 'RF driver (PA)', 'refbuf': 'Ref buf', 'core_bias': 'Core bias', 'wiredtx': 'Wired TX',
         'ctle': 'CTLE', 'slicer': 'Slicer', 'cdr': 'CDR', 'pll_cdr': 'PLL cdr', 'pll_tx': 'PLL tx', 'pll_host': 'PLL host (RF)',
         'termination': 'Term', 'rxselect': 'Sel', 'rxlevel': 'Lvl', 'detect': 'Detect', 'attached_tx_buffer': 'TX steering buf'}


def font(sz):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(p, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def render(work, out, flow=False, bg=None, title=None, width=1400):
    sys.path.insert(0, str(Path(__file__).parent))
    import floorplan_rules as rules
    work = Path(work)
    fp = json.loads((work/'floorplan.json').read_text())
    W = width
    H = int(round(W*DIE[1]/DIE[0]))
    s = W/DIE[0]
    if bg:
        base = Image.open(bg).convert('RGB').resize((W, H))
    else:
        base = Image.new('RGB', (W, H), 'white')
    im = Image.new('RGB', (W, H+30), 'white')
    im.paste(base, (0, 0))
    d = ImageDraw.Draw(im, 'RGBA')
    f9, f11, f13, f28 = font(10), font(12), font(14), font(30)

    def R(r):
        return (r[0]*s, H-r[3]*s, r[2]*s, H-r[1]*s)

    def tag(xy, text, col, fnt=f11):
        x, y = xy
        tw = d.textlength(text, font=fnt)
        d.rectangle((x, y, x+tw+4, y+fnt.size+3), fill=(255, 255, 255, 225), outline=col)
        d.text((x+2, y+1), text, fill=col, font=fnt)

    fill_a = 0 if bg else 90
    d.rectangle(R((0, 0)+DIE), outline='black', width=2)
    d.rectangle(R((442, 442, 3490, 4680)), outline=(150, 150, 150))
    for x in fp['fixed']:
        r = R(x['rect'])
        if x['kind'] == 'pad_family':
            d.rectangle(r, fill=(60, 60, 60, 40 if bg else 90), outline=(70, 70, 70), width=2)
            tag((r[0]+2, r[1]+2), x['name'].replace('pad_', '').upper()+' pad', (70, 70, 70))
            if x.get('port_xy'):
                px, py = x['port_xy'][0]*s, H-x['port_xy'][1]*s
                d.ellipse((px-4, py-4, px+4, py+4), fill=(0, 0, 0))
        elif x['kind'] == 'digital_abstract':
            d.rectangle(r, fill=(225, 233, 248, 255), outline=(30, 80, 200), width=3)
            t = 'DIGITAL MACRO\n(outline only)'
            d.multiline_text(((r[0]+r[2])/2-120, (r[1]+r[3])/2-35), t, fill=(30, 80, 200), font=f28, align='center')
        else:
            d.rectangle(r, fill=(240, 220, 60, 70), outline=(160, 140, 0), width=1)
            tag((r[0]+2, r[1]+2), x['name'].replace('rsv_', ''), (130, 110, 0), f9)
    for p in fp['placed']:
        r = R(p['rect'])
        c = COLOR[p['island']]
        if p['name'].startswith('atb'):
            d.rectangle(r, fill=c+(60,), outline=c+(160,))
            continue
        d.rectangle(r, fill=c+(fill_a or 25,), outline=c+(255,), width=2)
        o = p.get('orient', 'R0')
        name = SHORT.get(p['name'], p['name'].replace('_', ' '))
        tag((r[0]+2, r[1]+2), name+('' if o == 'R0' else f' [{o}]'), c, f11 if (r[2]-r[0]) > 40 else f9)
    for b in fp['decaps']:
        d.rectangle(R(b['rect']), fill=(0, 170, 200, 60), outline=(0, 120, 160), width=2)
    if fp['decaps']:
        r = R(max(fp['decaps'], key=lambda q: (q['rect'][2]-q['rect'][0])*(q['rect'][3]-q['rect'][1]))['rect'])
        tag((r[0]+2, r[3]-16), 'Decap pool', (0, 110, 150), f9)
    if flow:
        for chain, hops, _why in rules.CHAINS:
            col = CHAIN_COLOR[chain]+(235,)
            pts = [rules.center(fp, h) for h in hops]
            pts = [(q[0]*s, H-q[1]*s) for q in pts if q is not None]
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                d.line((xa, ya, xb, yb), fill=col, width=4)
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                if math.hypot(xb-xa, yb-ya) < 14:
                    continue
                ang = math.atan2(yb-ya, xb-xa)
                mx, my = (xa+xb)/2, (ya+yb)/2
                for sgn in (1, -1):
                    d.line((mx, my, mx-11*math.cos(ang+sgn*0.45), my-11*math.sin(ang+sgn*0.45)), fill=col, width=4)
        y = H-150
        d.rectangle((W-470, y-6, W-8, y+6+16*len(CHAIN_COLOR)), fill=(255, 255, 255, 230), outline='black')
        for chain, colr in CHAIN_COLOR.items():
            d.line((W-462, y+7, W-430, y+7), fill=colr, width=5)
            d.text((W-424, y), CHAIN_LABEL[chain], fill='black', font=f11)
            y += 16
    # Optional dimension annotations (work/annotations.json: [{"from": [x, y], "to": [x, y], "text": "..."}]), e.g. the
    # register distances of floorplan v4.
    ann = work/'annotations.json'
    if ann.exists():
        for a_ in json.loads(ann.read_text()):
            (xa, ya), (xb, yb) = [(q[0]*s, H-q[1]*s) for q in (a_['from'], a_['to'])]
            col = tuple(a_.get('color', (200, 0, 120)))+(255,)
            d.line((xa, ya, xb, yb), fill=col, width=3)
            for (x_, y_) in ((xa, ya), (xb, yb)):
                d.ellipse((x_-4, y_-4, x_+4, y_+4), fill=col)
            tag(((xa+xb)/2+6, (ya+yb)/2-8), a_['text'], col[:3], f11)
    d.text((6, H+8), title or ('pt_chip_top floorplan - '+Path(work).name), fill='black', font=f13)
    im.save(out)


if __name__ == '__main__':
    a = sys.argv
    bg = a[a.index('--bg')+1] if '--bg' in a else None
    title = a[a.index('--title')+1] if '--title' in a else None
    render(a[1], a[2], flow='--flow' in a, bg=bg, title=title)
