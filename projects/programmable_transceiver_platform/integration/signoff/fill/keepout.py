# KLayout: add top-level fill keep-out markers over the instances a set of keepouts.json names.
#   kl.sh fill/keepout.py -rd inp=skel/pt_chip_skel.gds -rd out=fill/<tag>_ko.gds -rd kset=must|rf|analog|none|allblocks
# allblocks = every block instance that is not the digital macro or a pad (upper bound of what could be excluded).
import json
import klayout.db as db
man = json.load(open('/run/skel/manifest.json'))
rows = json.load(open('/so/fill/keepouts.json'))['rows']
LAY = {'PMNDMY': (152, 5), 'NDMY': (111, 5), 'IND_MK': (151, 5)}
ly = db.Layout(); ly.read('/run/'+inp)
top = ly.top_cell()
um = lambda v: int(round(v*1000))
area = 0.0; n = 0; reg = db.Region(); named = []
for i in man['instances']:
    m = i['master']
    if kset == 'allblocks':
        r = None if (m == 'pt_digital_macro' or i['name'].startswith('pad_') or i['kind'] == 'reserve') else dict(layers=['PMNDMY'], margin_um=0)
    else:
        r = next((r for r in rows if r['master'] == m and kset in r['sets']), None)
    if not r: continue
    b = i['bbox']; g = r['margin_um']
    box = db.Box(um(b[0]-g), um(b[1]-g), um(b[2]+g), um(b[3]+g))
    for l in r['layers']:
        top.shapes(ly.layer(*LAY[l])).insert(box)
    reg.insert(box); n += 1; named.append(i['name'])
ly.write('/run/'+out)
json.dump(dict(kset=kset, instances=named, area_mm2=reg.merged().area()*1e-12), open('/run/'+out.replace('.gds', '.json'), 'w'))
print(f'keep-out set {kset}: {n} instances, {reg.merged().area()*1e-12:.3f} mm2 -> {out}')
