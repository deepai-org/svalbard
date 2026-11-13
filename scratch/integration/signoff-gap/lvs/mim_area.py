# klayout -b -r mim_area.py -rd jobs=/w/kljobs.txt -rd out=/w/mim_area.json
# Independent MIM check (the PDK KLayout LVS deck needs a MIM_L_MK marker that no project GDS carries, so it extracts no MIM):
# merged FuseTop (75/0) area inside CAP_MK (117/5), per block, to compare with the reference netlist's sum of c_width*c_length.
import klayout.db as db, json, gzip, os
res = {}
for ln in open(jobs):
    name, gds, top = ln.split()[:3]
    g = gds.replace('/home/ubuntu/svalbard', '/repo')
    ly = db.Layout(); ly.read(g)
    c = ly.cell(top) or ly.top_cell()
    i, j = ly.find_layer(75, 0), ly.find_layer(117, 5)
    if i is None:
        res[name] = dict(fusetop_um2=0.0, n=0); continue
    r = db.Region(c.begin_shapes_rec(i)); r.merge()
    k = db.Region(c.begin_shapes_rec(j)) if j is not None else db.Region()
    res[name] = dict(fusetop_um2=round(r.area() * ly.dbu ** 2, 3), n=r.count(), in_cap_mk_um2=round((r & k).area() * ly.dbu ** 2, 3))
json.dump(res, open(out, 'w'), indent=0)
