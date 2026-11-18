#!/usr/bin/env python3
"""Attribute the violations of a KLayout report to the blocks of the skeleton.
The deck runs in deep mode: an item is reported in the cell it occurs in, in that cell's coordinates. Items in a cell
below the top are attributed to the top-level child that contains the cell (skel/cell_owner.json); items in the top cell
by position, as follows.
  locate.py <report.lyrdb[.gz]> [manifest.json]   -> prints rule x owner counts, writes <report dir>/by_owner.json
Owner = the instance whose placed outline contains the violation's centre (smallest outline wins); otherwise the region:
ring (pad ring band), seal (outer 26 um), or top (core area outside every block)."""
import sys, gzip, json, re, collections, os, xml.etree.ElementTree as ET
rep = sys.argv[1]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
man = json.load(open(sys.argv[2] if len(sys.argv) > 2 else ROOT+'/scratch/integration/signoff-run/skel/manifest.json'))
inst = [(i['name'], i['master'], i['bbox']) for i in man['instances'] if i.get('bbox') and i.get('cell')]
inst.sort(key=lambda t: (t[2][2]-t[2][0])*(t[2][3]-t[2][1]))
def owner(x, y):
    for n, m, b in inst:
        if b[0] <= x <= b[2] and b[1] <= y <= b[3]: return n, m
    if x < 26 or y < 26 or x > 3906 or y > 5096: return 'seal', 'sealring'
    if x < 442 or y < 442 or x > 3490 or y > 4680: return 'ring', 'provider pad ring'
    return 'top', 'between blocks'
cnt = collections.Counter(); ex = {}
co = json.load(open(os.path.join(os.path.dirname(sys.argv[2]) if len(sys.argv) > 2 else ROOT+'/scratch/integration/signoff-run/skel', 'cell_owner.json')))
TOPS = ('pt_chip_top', 'pt_fixture')
f = gzip.open(rep) if rep.endswith('.gz') else open(rep, 'rb')
num = re.compile(r'(-?[\d.]+),(-?[\d.]+)')
for ev, el in ET.iterparse(f):
    if el.tag == 'item':
        cat = (el.findtext('category') or '').strip("'").split(':')[0].strip("' ")
        cell = (el.findtext('cell') or '').split(':')[0]
        v = el.find('values')
        pts = num.findall(v[0].text or '') if v is not None and len(v) else []
        if pts:
            xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
            cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
            o = owner(cx, cy)
            if cell not in TOPS:
                ow = co.get(cell, ['cell '+cell]); o = (cell, ow[0] if len(ow) == 1 else f'{len(ow)} blocks ({ow[0]}, ..) via cell {cell}'[:60])
        else: o = ('?', '?'); cx = cy = 0
        cnt[(cat, o[1])] += 1; ex.setdefault((cat, o[1]), [o[0], round(cx, 1), round(cy, 1)])
        el.clear()
rows = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
out = [dict(rule=r, owner=o, count=c, example=ex[(r, o)]) for (r, o), c in rows]
json.dump(out, open(os.path.join(os.path.dirname(rep), 'by_owner.json'), 'w'), indent=0)
for d in out[:int(os.environ.get('N', '60'))]: print(f"{d['count']:7d}  {d['rule']:22s} {d['owner']:28s} e.g. {d['example']}")
print('total', sum(cnt.values()), 'in', len({o for (r, o) in cnt}), 'owners')
