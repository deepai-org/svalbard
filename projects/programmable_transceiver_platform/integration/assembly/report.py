#!/usr/bin/env python3
"""Stage `report` (host python): floorplan and congestion pictures, routing completion, wire length per net and class.

  report.py <chip>     reads <run>/floorplan.json, place.json, nets.json, route/{routed,groute}.def, route/congestion.rpt,
                       route/drt.rpt, route/*.log; writes <run>/report/{floorplan.png, congestion.png, route.json, summary.md}
"""
import collections, json, os, re, sys
from PIL import Image, ImageDraw, ImageFont
A = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, A)
import common as C
chip = sys.argv[1]; RUN = os.environ.get('ASM_RUN', f'{C.ROOT}/scratch/integration/assembly-{chip}')
os.makedirs(RUN+'/report', exist_ok=True)
FP = json.load(open(RUN+'/floorplan.json')); PL = json.load(open(RUN+'/place.json')); PADS = json.load(open(RUN+'/pads.json'))
NETS = json.load(open(RUN+'/nets.json'))

def parse_def(path):
    """net -> dict(wl_um per layer, vias, routed)"""
    out = {}
    if not os.path.exists(path): return out
    txt = open(path).read()
    m = re.search(r'\nNETS \d+ ;(.*?)\nEND NETS', txt, re.S)
    if not m: return out
    for blk in m.group(1).split(';'):
        blk = blk.strip()
        if not blk.startswith('-'): continue
        name = blk.split()[1]
        wl = collections.Counter(); vias = 0
        for seg in re.split(r'\+ ROUTED|\bNEW\b|\+ FIXED', blk)[1:]:
            t = seg.split()
            if not t: continue
            layer = t[0]; pts = re.findall(r'\(\s*(\S+)\s+(\S+)(?:\s+\S+)?\s*\)', seg)
            vias += len([w for w in t[1:] if not w.startswith(('(', ')', '*')) and not re.match(r'^-?\d+$', w) and w not in ('RECT', 'MASK', 'TAPER', 'TAPERRULE', 'STYLE', 'VIRTUAL')])
            if 'RECT' in seg: pts = pts[:1]
            px = py = None
            for x, y in pts:
                x = px if x == '*' else int(x); y = py if y == '*' else int(y)
                if px is not None: wl[layer] += (abs(x-px)+abs(y-py))/1000.0
                px, py = x, y
        out[name] = dict(wl=sum(wl.values()), by_layer=dict(wl), vias=vias, routed='ROUTED' in blk)
    return out

R = parse_def(RUN+'/route/routed.def'); G = parse_def(RUN+'/route/groute.def')
log = open(RUN+'/route/route.log').read() if os.path.exists(RUN+'/route/route.log') else ''
drv = re.findall(r'Number of violations = (\d+)', log)
drt_items = collections.Counter()
if os.path.exists(RUN+'/route/drt.rpt'):
    for line in open(RUN+'/route/drt.rpt'):
        if line.startswith('violation type:'): drt_items[line.split(':', 1)[1].strip()] += 1
cong = []
if os.path.exists(RUN+'/route/congestion.rpt'):
    for line in open(RUN+'/route/congestion.rpt'):
        m = re.search(r'bbox = \(\s*([\d.]+),\s*([\d.]+)\s*\) - \(\s*([\d.]+),\s*([\d.]+)\s*\)', line)
        if m: cong.append([float(v) for v in m.groups()])
gr_over = re.findall(r'Total\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)', log)
by_cls = collections.defaultdict(lambda: dict(nets=0, routed=0, wl=0.0))
rows = []
for n, v in NETS.items():
    r = R.get(n, {}); c = v['cls']
    by_cls[c]['nets'] += 1; by_cls[c]['routed'] += bool(r.get('routed')); by_cls[c]['wl'] += r.get('wl', 0.0)
    rows.append(dict(net=n, cls=c, pins=len(v['ends']), wl_um=round(r.get('wl', 0.0), 1), vias=r.get('vias', 0), routed=bool(r.get('routed')),
                     ends=[f'{a}.{b}' for a, b in v['ends']][:6]))
unrouted = [r['net'] for r in rows if not r['routed']]
crit = sorted([r for r in rows if r['cls'] in ('clock', 'hs', 'rf', 'supply')], key=lambda r: -r['wl_um'])
longest = sorted(rows, key=lambda r: -r['wl_um'])[:25]
res = dict(chip=chip, nets=len(rows), routed=len(rows)-len(unrouted), unrouted=unrouted, total_wl_mm=round(sum(r['wl_um'] for r in rows)/1000, 2),
           by_class={k: dict(v, wl=round(v['wl']/1000, 2)) for k, v in by_cls.items()}, drt_violations_by_iter=drv[-6:],
           drt_final_by_type=dict(drt_items), gr_congested_gcells=len(cong), gr_overflow_line=gr_over[-1] if gr_over else None,
           longest=longest, critical=crit[:40], hooks=len(PL['hooks']), unconnectable=PL['unconnectable'], single_pin_nets=len(PL['single_pin_nets']),
           pdn=PL['pdn'])
# layout status per instance: placeholder (no GDS) or not yet published (staged / scratch / handoff), with the source
MJ = json.load(open(RUN+'/masters.json'))
status = []
for n, b in sorted(PL['blocks'].items()):
    m = b['master']
    if m == 'decap': continue
    g = MJ.get(m, {}).get('gds') or ''
    k = 'placeholder' if b['kind'] == 'placeholder' else ('published' if g.startswith('projects/') and '/generated/' in g and 'staged' not in b['kind'] else 'staged')
    if k != 'published': status.append(dict(inst=n, master=m, status=k, gds=g))
for n, v in PADS['pads'].items():
    if not v['gds'].startswith('projects/'): status.append(dict(inst=n, master=v['master'], status='staged', gds=v['gds']))
res['layout_status'] = status
json.dump(res, open(RUN+'/report/route.json', 'w'), indent=0)

# ---------------------------------------------------------------------------------------------------- pictures
S = 0.25; W, H = int(C.DIE[2]*S), int(C.DIE[3]*S)
try: F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
except Exception: F = FB = ImageFont.load_default()
def P(x, y): return (x*S, (C.DIE[3]-y)*S+30)
COL = dict(rf_rx='#f6d5d5', rf_tx='#f9c9c0', conv='#ead9f2', lo='#fde6c8', lod='#fbd9a8', pll='#fff1c4', wired_rx='#d6efdc', wired_cap='#c2e8cc',
           wired_tx='#d0ecd0', core='#dde7f5', debug='#d4eef0', chip='#e9f27a')
inst, ports, masters = C.load(chip)
def base(title):
    im = Image.new('RGB', (W+2, H+34), 'white'); d = ImageDraw.Draw(im)
    def box(r, fill, outline, w=1):
        a, b = P(r[0], r[3]), P(r[2], r[1]); d.rectangle([a, b], fill=fill, outline=outline, width=w)
    box(C.DIE, '#f4f4ee', '#555', 2); box(C.CORE, '#ffffff', '#bbb')
    for s, v in PADS['io'].items(): box(v['bbox'], '#e0e0e0' if 'dv' not in v['cell'] else '#c8c8ff', '#888')
    for n, v in PADS['pads'].items():
        for r in v['footprint']: box(r, '#bdbdbd', '#444')
        r = v['footprint'][0]; d.text(P(r[0]+8, r[3]-8), n, fill='#000', font=F)
    for n, r in PL.get('booked', {}).items(): box(r, '#f0f0f0', '#d000d0')
    for n, b in PL['blocks'].items():
        r = b['bbox']; m = b['master']
        g = inst[n]['group'] if n in inst else 'core'
        fill = '#c9dcf2' if m == 'decap' else '#404040' if m.startswith('isw') else COL.get(g, '#eee')
        out = '#c00000' if m in C.NO_OVER else '#d000d0' if b['kind'] == 'placeholder' and m != 'decap' else '#333'
        box(r, fill, out, 2 if out != '#333' else 1)
        if (r[2]-r[0])*S > 30 and m != 'decap': d.text(P(r[0]+4, r[3]-4), n[:int((r[2]-r[0])*S/6)], fill='#fff' if m.startswith('isw') else '#000', font=F)
    d.text((6, 6), title, fill='#000', font=FB)
    return im, d, box
im, d, box = base(f'pt_{chip} floorplan (assembly flow): red = no routing over, magenta = placeholder / booking')
im.save(RUN+'/report/floorplan.png')
im, d, box = base(f'pt_{chip} global-route congestion: {len(cong)} overflowing gcells (red)')
for r in cong: box(r, '#ff0000', '#ff0000')
im.save(RUN+'/report/congestion.png')
print(json.dumps({k: v for k, v in res.items() if k not in ('longest', 'critical', 'unconnectable')}, indent=0)[:2500])
