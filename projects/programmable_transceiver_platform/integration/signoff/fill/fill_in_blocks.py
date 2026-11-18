# KLayout: what the fill put into each keep-out candidate block.  kl.sh fill/fill_in_blocks.py -rd gds=fill/none_filled.gds
# Per instance named in keepouts.json: dummy shapes and dummy area share (% of the outline) on COMP, Poly2, Metal1..5,
# and the drawn + dummy density inside the outline.  -> /run/fill/fill_in_blocks.json
import json
import klayout.db as db
man = json.load(open('/run/skel/manifest.json'))
rows = json.load(open('/so/fill/keepouts.json'))['rows']
masters = {r['master'] for r in rows}
ly = db.Layout(); ly.read('/run/'+gds); top = ly.top_cell()
LAY = dict(COMP=22, Poly2=30, M1=34, M2=36, M3=42, M4=46, M5=81)
out = {}
for i in man['instances']:
    if i['master'] not in masters or not i.get('bbox'): continue
    b = i['bbox']; bx = db.Box(*[int(round(v*1000)) for v in b]); a = bx.area(); d = dict(master=i['master'], kind=i['kind'], area_um2=round(a*1e-6))
    for n, l in LAY.items():
        dm = db.Region(top.begin_shapes_rec_touching(ly.layer(l, 4), bx)) & db.Region(bx)
        dr = (db.Region(top.begin_shapes_rec_touching(ly.layer(l, 0), bx)) & db.Region(bx)).merged()
        d[n] = dict(dummies=dm.count(), dummy_pct=round(100*dm.area()/a, 1), drawn_pct=round(100*dr.area()/a, 1))
    out[i['name']] = d
json.dump(out, open('/run/fill/fill_in_blocks.json', 'w'), indent=0)
print('instance            kind         ' + ' '.join(f'{n:>13s}' for n in LAY) + '   (drawn% + dummy%, dummy count)')
for k, d in sorted(out.items(), key=lambda kv: -kv[1]['area_um2']):
    print(f"{k:18s} {d['kind']:12s} " + ' '.join(f"{d[n]['drawn_pct']:4.0f}+{d[n]['dummy_pct']:<4.0f}{d[n]['dummies']:>5d}"[:13].rjust(13) for n in LAY))
