"""nets.py <gds> <out.gds>: trace PAD_P, PAD_N, VSS, ESD_RAIL (netres.trace) and write per-net regions:
layer = metal/via GDS layer, datatype 1 PAD_P, 2 PAD_N, 3 VSS, 4 ESD_RAIL, 9 everything else."""
import sys, klayout.db as k
sys.path.insert(0, '/work/hsfix'); import netres as n
g = n.Geo(sys.argv[1], 'pad_hspad'); o = k.Layout(); o.dbu = g.dbu; t = o.create_cell('nets')
LY = dict(n.METAL); LY.update({v: x[0] for v, x in n.VIA.items()})
used = {m: k.Region() for m in LY}
for dt, name in ((1, 'PAD_P'), (2, 'PAD_N'), (3, 'VSS'), (4, 'ESD_RAIL')):
    seeds = g.labels(name); net, cuts = n.trace(g, seeds, None); net.update(cuts)
    for m, r in net.items():
        t.shapes(o.layer(LY[m], dt)).insert(r); used[m] += r
        print(name, m, r.count(), round(r.area() * g.dbu ** 2, 1))
for m in LY:
    r = g.region(LY[m]) - used[m]; t.shapes(o.layer(LY[m], 9)).insert(r)
o.write(sys.argv[2])
