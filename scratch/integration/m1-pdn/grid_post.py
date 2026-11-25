import json, sys, collections
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/integration/assembly')
ch = sys.argv[1]
txt = open(f'out/{ch}/grid_conn.txt').read(); d = json.loads(txt.split('\nJSON\n')[1])
import importlib; C = importlib.import_module('common')
core = C.CORE
def guess(p):
    x0, y0, x1, y1 = p['bbox']
    if (x1-x0) >= (y1-y0):   # Metal5 vertical straps: x axis; Metal4 horizontal: y axis
        pass
    cx = (x0+x1)/2; cy = (y0+y1)/2
    # vertical piece -> Metal5 strap: phase of x; else Metal4 strap: phase of y
    if (y1-y0) > (x1-x0): ph = (cx-(core[0]+10+5.25)) % 70
    else: ph = (cy-(core[1]+10+5.25)) % 70
    return 'VDD' if min(ph, 70-ph) < 17.5 else 'VSS'
fl = [p for p in d['pieces'] if not p['n_stubs'] and p['m4_mm2']+p['m5_mm2'] > 0]
bar = [p for p in fl if p['m5_mm2'] > 0.05 and p['m4_mm2'] == 0]
fl = [p for p in fl if p not in bar]
agg = collections.defaultdict(lambda: [0, 0.0, 0.0])
for p in fl:
    a = agg[guess(p)]; a[0] += 1; a[1] += p['m4_mm2']; a[2] += p['m5_mm2']
print(ch, 'island-bar-like pieces excluded:', [(p['id'], p['m5_mm2'], p['bbox']) for p in bar])
print(ch, 'floating by net (n, M4 mm2, M5 mm2):', {k: (v[0], round(v[1], 4), round(v[2], 4)) for k, v in agg.items()})
sz = [p['m4_mm2']+p['m5_mm2'] for p in fl]
for lim in (1e-4, 1e-3, 5e-3):
    print(f'  pieces > {lim*1e6:.0f} um2: {sum(s > lim for s in sz)}  area {sum(s for s in sz if s > lim):.4f} mm2')
print('  largest:', [(p['id'], guess(p), round((p['m4_mm2']+p['m5_mm2'])*1e6), p['bbox']) for p in sorted(fl, key=lambda p: -(p['m4_mm2']+p['m5_mm2']))[:12]])
json.dump(dict(floating=[dict(p, net=guess(p)) for p in fl], bar=bar, unfed=d['unfed']), open(f'out/{ch}/grid_floating.json', 'w'), indent=0)
man = json.load(open(f'../assembly-{ch}/chip/manifest.json'))
def near(bb, k=3):
    x0, y0, x1, y1 = bb
    ds = []
    for i in man['instances']:
        a = i['bbox']; d = max(a[0]-x1, x0-a[2], 0)+max(a[1]-y1, y0-a[3], 0); ds.append((d, i['name']))
    return [f'{n}@{d:.0f}' for d, n in sorted(ds)[:k]]
for p in sorted(fl, key=lambda p: -(p['m4_mm2']+p['m5_mm2']))[:15]:
    print('   ', p['id'], guess(p), round((p['m4_mm2']+p['m5_mm2'])*1e6), p['bbox'], near(p['bbox']))
