"""Metal-only connectivity and capacitor geometry, not a capacitance extractor.
Usage: python cap_geometry.py submitted.gds > cap-geometry.json
Layer mapping: GF180 design manual drm_04_1 (M1..M5 and vias).
"""
import hashlib
import json
import sys
import klayout.db as k

path = sys.argv[1]
l = k.Layout()
l.read(path)
c = l.cell(sys.argv[2] if len(sys.argv)>2 else 'lib_cap_array')
label_cell=l.cell('lib_cap_array')
def find_arrays(cell, transform):
    if cell.name == 'lib_cap_array':
        return [transform]
    found=[]
    for inst in cell.each_inst():
        for t in inst.cell_inst.each_trans():
            found.extend(find_arrays(inst.cell, transform*t))
    return found
transforms=find_arrays(c,k.Trans())
label_transform=transforms[int(sys.argv[3]) if len(sys.argv)>3 else 0]
x = k.LayoutToNetlist('caps', l.dbu)
regs, ids = {}, {}
for n in [34,35,36,38,42,40,46,41,81,75]:
    r = k.Region(c.begin_shapes_rec(l.layer(n,0)))
    r.merge()
    ids[n] = x.register(r,str(n))
    regs[n] = r
    x.connect(r)
# GF180 five-metal MIM Option B: Via4 over FuseTop lands on the
# capacitor's upper plate, not the M4 lower electrode beneath it.
regs['via4bottom']=regs[41]-regs[75]
regs['via4top']=regs[41]&regs[75]
for key in ['via4bottom','via4top']:
    ids[key]=x.register(regs[key],key)
    x.connect(regs[key])
for a,v,b in [(34,35,36),(36,38,42),(42,40,46),(46,'via4bottom',81),(75,'via4top',81)]:
    x.connect(regs[a],regs[v])
    x.connect(regs[v],regs[b])
x.extract_netlist()

def labels(n):
    return [s.text.transformed(label_transform) for s in label_cell.shapes(l.layer(n,10)).each() if s.is_text()]

def polygons(net,n):
    return x.polygons_of_net(net,ids[n],True)

t = next(t for t in labels(46) if t.string == 'top')
net = x.probe_net(regs[46],t.trans.disp)
assert net is not None
common = polygons(net,46)
rows, missing = {}, []
for t in labels(42):
    nt = x.probe_net(regs[42],t.trans.disp)
    if nt is None:
        missing.append(t.string)
        continue
    assert nt != net
    r = polygons(nt,42)
    rows[t.string] = dict(m3_area_um2=r.area()*l.dbu**2,
                         m3_perimeter_um=r.perimeter()*l.dbu,
                         m3_m4_overlap_um2=(r&common).area()*l.dbu**2,
                         m2_area_um2=polygons(nt,36).area()*l.dbu**2,
                         adjacent_overlap_um2={f'{a}-{b}':((polygons(nt,a)&polygons(net,b)).area()+(polygons(nt,b)&polygons(net,a)).area())*l.dbu**2 for a,b in [(34,36),(36,42),(42,46),(46,81)]})
assert len(rows) == 13
# Cross-net adjacent-layer overlaps locate possible inter-bit coupling paths.
# Cache connected shapes; no overlap density or fringe coefficient is assigned.
bit_shapes={}
for t in labels(42):
 nt=x.probe_net(regs[42],t.trans.disp)
 if nt is not None:bit_shapes[t.string]={n:polygons(nt,n) for n in [34,36,42,46,81]}
inter_bit=[]
names=sorted(bit_shapes,key=lambda name:int(name[1:]))
for i,left in enumerate(names):
 for right in names[i+1:]:
  overlaps={f'{a}-{b}':float(((bit_shapes[left][a]&bit_shapes[right][b]).area()+(bit_shapes[left][b]&bit_shapes[right][a]).area())*l.dbu**2) for a,b in [(34,36),(36,42),(42,46),(46,81)]}
  if sum(overlaps.values())>0:inter_bit.append(dict(left=left,right=right,adjacent_layer_overlap_um2=overlaps))
# DRC-style proximity is a geometric locator, not an electrostatic solver.
# Default Euclidean partial-edge check; third-net/vertical shielding is absent.
lateral=[]
for i,left in enumerate(names):
 for right in names[i+1:]:
  for layer in [34,36,42,46,81]:
   pairs=bit_shapes[left][layer].separation_check(bit_shapes[right][layer],round(1/l.dbu))
   if pairs.is_empty():continue
   lateral.append(dict(left=left,right=right,layer=layer,threshold_um=1.,
     edge_pair_count=pairs.size(),paired_edge_mean_length_sum_um=float(sum((pair.first.length()+pair.second.length())/2 for pair in pairs.each())*l.dbu)))
parent_aliases={}
for layer in [34,36,42,46,81]:
 for shape in c.shapes(l.layer(layer,10)).each():
  if shape.is_text():
   nn=x.probe_net(regs[layer],shape.text.trans.disp)
   if nn:
    for t in labels(42)+labels(46):
     mm=x.probe_net(regs[46 if t.string=='top' else 42],t.trans.disp)
     if mm and nn.cluster_id==mm.cluster_id:parent_aliases.setdefault(t.string,[]).append(shape.text.string)
print(json.dumps(dict(source_sha256=hashlib.sha256(open(path,'rb').read()).hexdigest(),
    cell=c.name, common_m4_area_um2=common.area()*l.dbu**2,
    inter_bit_lateral_proximity=lateral,
    inter_bit_adjacent_overlap=inter_bit,
    bit_geometry=rows, unresolved_label_probes=missing,parent_aliases=parent_aliases,array_count=len(transforms),
    scope='Selected cell metal/via connectivity. No higher-parent routing, dielectric, fringe, substrate or transistor extraction.'),indent=2))
