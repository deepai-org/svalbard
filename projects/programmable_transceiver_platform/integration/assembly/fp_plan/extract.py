#!/usr/bin/env python3
"""extract.py <run> <out.json>: blocks (rect, size), net endpoints in die um, classes, from a placed run (DEF + LEF)."""
import json, re, sys, glob, os, collections
RUN, OUT = sys.argv[1], sys.argv[2]
lef = {}
for f in glob.glob(RUN + '/lef/*.lef'):
    cur = pin = None; layer = None
    for l in (q for L_ in open(f) for q in L_.split(';')):
        t = l.split()
        if not t: continue
        if t[0] == 'MACRO': cur = t[1]; lef[cur] = dict(w=0, h=0, pins={})
        elif t[0] == 'SIZE' and cur: lef[cur]['w'] = float(t[1]); lef[cur]['h'] = float(t[3])
        elif t[0] == 'PIN' and cur: pin = t[1]
        elif t[0] == 'LAYER' and pin: layer = t[1]
        elif t[0] == 'RECT' and pin and pin not in lef[cur]['pins']:
            x0, y0, x1, y1 = map(float, t[1:5]); lef[cur]['pins'][pin] = ((x0 + x1) / 2, (y0 + y1) / 2, layer)
        elif t[0] == 'END' and len(t) > 1 and t[1] == pin: pin = None
def tr(o, x, y, w, h):
    return {'N': (x, y), 'S': (w - x, h - y), 'W': (h - y, x), 'E': (y, w - x), 'FN': (w - x, y), 'FS': (x, h - y),
            'FW': (y, x), 'FE': (h - y, w - x)}[o]
def dims(o, w, h): return (h, w) if o in ('W', 'E', 'FW', 'FE') else (w, h)
d = open(RUN + '/design.def').read()
comp = {}
for m in re.finditer(r'^- (\S+) (\S+) \+ (?:FIXED|PLACED) \( (-?\d+) (-?\d+) \) (\S+) ;', d, re.M):
    n, ms, x, y, o = m.group(1), m.group(2), int(m.group(3)) / 1000, int(m.group(4)) / 1000, m.group(5)
    L = lef.get(ms, dict(w=0, h=0, pins={}))
    W, H = dims(o, L['w'], L['h'])
    comp[n] = dict(master=ms, o=o, rect=[x, y, x + W, y + H], w=L['w'], h=L['h'])
nets = json.load(open(RUN + '/nets.json'))
out = dict(comp=comp, nets={})
miss = collections.Counter()
for n, v in nets.items():
    ends = []
    for i, p in v['ends']:
        c = comp.get(i)
        if not c: miss[i] += 1; continue
        pp = lef.get(c['master'], {}).get('pins', {}).get(p)
        if pp is None: miss[(i, p)] += 1; ends.append([i, p, (c['rect'][0] + c['rect'][2]) / 2, (c['rect'][1] + c['rect'][3]) / 2, None]); continue
        x, y = tr(c['o'], pp[0], pp[1], c['w'], c['h'])
        ends.append([i, p, round(c['rect'][0] + x, 1), round(c['rect'][1] + y, 1), pp[2]])
    out['nets'][n] = dict(cls=v['cls'], ends=ends)
json.dump(out, open(OUT, 'w'))
print('comps', len(comp), 'nets', len(nets), 'missing', list(miss.items())[:10])
