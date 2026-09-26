"""Extract geometric MOS fingers; no connected circuit or foundry LVS claim.
Usage: python device_geometry.py submitted.gds
"""
import json, sys, hashlib
import klayout.db as k
l=k.Layout();l.read(sys.argv[1]); results={}
for name in ['adc_comp_miyahara_offcal','adc_preamp_v2','adc_bootsw_debug5','opamp1_v2_to_fix','opamp2_to_fix']:
 c=l.cell(name);x=k.LayoutToNetlist(name,l.dbu)
 def r(n):return k.Region(c.begin_shapes_rec(l.layer(n,0))).merged()
 active,poly,nwell=r(22),r(30),r(21)
 for typ,implant,diff in [('nmos',32,active-nwell),('pmos',31,active&nwell)]:
  diff=diff&r(implant);gate=diff&poly;sd=diff-poly
  x.register(gate,typ+'g');x.register(sd,typ+'sd')
  x.extract_devices(k.DeviceExtractorMOS3Transistor(typ),{'SD':sd,'G':gate})
 x.extract_netlist()
 from collections import Counter
 ds=Counter((d.device_class().name,round(d.parameter('W'),4),round(d.parameter('L'),4)) for ci in x.netlist().each_circuit() for d in ci.each_device())
 results[name]=[dict(type=a[0],width_um=a[1],length_um=a[2],fingers=b) for a,b in sorted(ds.items())]

print(json.dumps(dict(source_sha256=hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest(),blocks=results,limitations=["Generic geometric extractor, no device-model assignment or electrical connectivity.","Finger counts are not circuit transistor counts; parallel fingers remain separate.","MOS capacitor structures may be recognized as devices; not foundry LVS.","Well and implant classification used; oxide and special device markers not yet classified."]),indent=2))
