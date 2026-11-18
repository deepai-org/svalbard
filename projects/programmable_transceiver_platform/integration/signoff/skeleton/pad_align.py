# KLayout: for every custom pad of the skeleton (placed so that its bond openings sit exactly on the template mask),
# the shift along the edge that would make its Via3 pattern coincide with the provider rail cell under it.
# Non-zero = the family's opening and its rail structure cannot both be aligned to the template.  kl.sh skeleton/pad_align.py
import json
import klayout.db as db
man = json.load(open('/run/skel/manifest.json'))
ly = db.Layout(); ly.read('/run/skel/pt_chip_skel.gds'); top = ly.top_cell()
ring = ly.cell('retained_provider_ring'); v3 = ly.layer(40, 0)
out = {}
for i in man['instances']:
    if not i['name'].startswith('pad_'): continue
    bb = db.Box(*[int(round(v*1000)) for v in i['bbox']])
    band = db.Box(bb.left if bb.left > 1e6 else 0, bb.bottom, bb.right if bb.left < 1e6 else 3932000, bb.top)
    rail = db.Region(ring.begin_shapes_rec_touching(v3, band)).merged() & db.Region(band)
    fam = db.Region(ly.cell(i['cell']).begin_shapes_rec(v3)).merged().transformed(db.Trans.from_s(i['trans']))
    fam &= rail.sized(400)
    if rail.is_empty() or fam.is_empty(): out[i['name']] = None; continue
    best = min(range(-200, 201, 5), key=lambda d: (fam.transformed(db.Trans(db.Vector(0, d))) ^ (rail & fam.sized(400))).area())
    out[i['name']] = dict(master=i['master'], shift_nm=best, overlapping_via3=(fam & rail).count())
    print(i['name'], i['master'], 'via3-to-rail shift (nm):', best)
json.dump(out, open('/run/skel/pad_align.json', 'w'), indent=0)
