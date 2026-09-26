"""Hierarchical metal-only amplifier-to-pad trace, retaining the entire chip.
Usage: python pad_trace.py submitted.gds > pad-routing.json
Requires KLayout. No implicit global label joins or transistor conduction.
"""
import klayout.db as k,json,hashlib,sys
path=sys.argv[1];l=k.Layout();l.read(path);c=l.cell('TOP_HARNESS_minimum_v4_TO_VERSION');x=k.LayoutToNetlist(c.begin_shapes_rec(l.layer(34,0)));rs={}
for n in [34,35,36,38,42,40,46,41,81,75]:
 rs[n]=x.make_polygon_layer(l.layer(n,0),str(n))
rs['v4b']=rs[41]-rs[75];rs['v4t']=rs[41]&rs[75]
for n in ['v4b','v4t']:x.register(rs[n],n)
for r in rs.values():x.connect(r)
for a,v,b in [(34,35,36),(36,38,42),(42,40,46),(46,'v4b',81),(75,'v4t',81)]:x.connect(rs[a],rs[v]);x.connect(rs[v],rs[b])
x.extract_netlist()
def labels(cell,trans):
 for layer in [34,36,42,46,81]:
  for s in cell.shapes(l.layer(layer,10)).each():
   if s.is_text():
    t=s.text.transformed(trans);net=x.probe_net(rs[layer],t.trans.disp)
    yield dict(label=t.string,layer=layer,xy_um=[t.x*l.dbu,t.y*l.dbu],cluster=[net.circuit().name,net.cluster_id] if net else None)
top=list(labels(c,k.Trans()));rows=[]
for inst in c.each_inst():
 if inst.cell.name in ['opamp1_v2_to_fix','opamp2_to_fix']:
  for tr in inst.cell_inst.each_trans():
   for row in labels(inst.cell,tr):
    row.update(cell=inst.cell.name,top_labels=[t['label'] for t in top if row['cluster'] is not None and t['cluster']==row['cluster']]);rows.append(row)
pad_rows=[]
for inst in c.each_inst():
 if inst.cell.name=='RING_PAD':
  for outer in inst.cell_inst.each_trans():
   for pad in inst.cell.each_inst():
    if pad.cell.name=='gf180mcu_fd_io__asig_5p0':
     for inner in pad.cell_inst.each_trans():
      for row in labels(pad.cell,outer*inner):
       if row['label']=='ASIG5V' and row['layer']==81:
        row.update(cell=pad.cell.name,top_labels=sorted(set(t['label'] for t in top if row['cluster'] is not None and t['cluster']==row['cluster'])))
        pad_rows.append(row)
print(json.dumps(dict(source_sha256=hashlib.sha256(open(path,'rb').read()).hexdigest(),cell=c.name,amplifier_terminals=rows,analog_pad_terminals=pad_rows,scope='Metal/via-only trace to top-cell labels; no pad transistor, package or PCB extraction.'),indent=2))
