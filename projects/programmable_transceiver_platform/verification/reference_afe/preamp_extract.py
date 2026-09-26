"""Reconstruct preamp topology; generic extraction, not foundry LVS.
Usage: python preamp_extract.py submitted.gds
Assumes high-poly sheet resistance 1000 ohm/square; parasitics omitted.
Optional --bulk follows wells and taps with ideal conductivity (not substrate PEX).
Optional --voltage-classes splits 6V Dualgate (55/0) devices into nmos6/pmos6.
"""
import sys, json, hashlib
import klayout.db as k
l=k.Layout();l.read(sys.argv[1]);c=l.cell(sys.argv[2] if len(sys.argv)>2 else 'adc_preamp_v2');x=k.LayoutToNetlist(c.name,l.dbu)
def r(n,d=0):return k.Region(c.begin_shapes_rec(l.layer(n,d))).merged()
a,p,nw=r(22),r(30),r(21);rb=p&r(110,5);pc=p-rb
regs={'poly':pc,'m1':r(34),'m2':r(36),'contact':r(33),'via1':r(35),'res':rb}
for typ,imp,diff in [('nmos',32,a-nw),('pmos',31,a&nw)]:
 diff=diff&r(imp);regs[typ+'g']=diff&p;regs[typ+'sd']=diff-p
for n in [38,42,40,46,41,81]: regs[str(n)]=r(n)
regs['mimtop']=r(75);regs['via4bottom']=regs['41']-regs['mimtop'];regs['via4top']=regs['41']&regs['mimtop']
bulk='--bulk' in sys.argv
if bulk:
 # Deep Nwell isolates each local Pwell from the surrounding P substrate.
 dn,pw=r(12),r(204)
 regs['nbody']=nw|dn
 regs['pbody']=pw|(k.Region(c.bbox().enlarged(1000))-nw-dn)
 regs['ntap']=(a&r(32)&regs['nbody'])-pw-p
 regs['ptap']=(a&r(31)&regs['pbody'])-p
 regs['nmosbulk']=k.Region();regs['pmosbulk']=k.Region()
for n,v in regs.items():x.register(v,n)
for typ in ['nmos','pmos']:
 choices=[(typ,regs[typ+'sd'],regs[typ+'g'])]
 if '--voltage-classes' in sys.argv:
  dual=r(55)
  choices=[(typ,regs[typ+'sd']-dual,regs[typ+'g']-dual),
           (typ+'6',regs[typ+'sd']&dual,regs[typ+'g']&dual)]
 for name,sd,gate in choices:
  if gate.is_empty():continue
  if '--voltage-classes' in sys.argv:
   x.register(sd,name+'_extract_sd');x.register(gate,name+'_extract_gate')
   # Reconnect class-specific diffusion terminals to complete diffusion.
   x.connect(sd,regs[typ+'sd'])
  layers={'SD':sd,'G':gate,'tG':pc}
  if bulk:
   layers['W']=regs['pbody' if typ=='nmos' else 'nbody']
   layers['B']=regs[typ+'bulk']
  extractor=k.DeviceExtractorMOS4Transistor if bulk else k.DeviceExtractorMOS3Transistor
  x.extract_devices(extractor(name),layers)
x.extract_devices(k.DeviceExtractorResistor('resistor',1000),{'R':rb,'C':pc})
if not regs['mimtop'].is_empty():
 x.extract_devices(k.DeviceExtractorCapacitor('mim_2ff',2e-15),{'P1':regs['46'],'P2':regs['mimtop']})
for n in ['poly','m1','m2','contact','via1','nmossd','pmossd']:x.connect(regs[n])
for n in ['poly','nmossd','pmossd']:x.connect(regs[n],regs['contact'])
x.connect(regs['contact'],regs['m1']);x.connect(regs['m1'],regs['via1']);x.connect(regs['m2'],regs['via1'])
for a,v,b in [('m2','38','42'),('42','40','46'),('46','via4bottom','81'),('mimtop','via4top','81')]:
 for n in [a,v,b]:x.connect(regs[n])
 x.connect(regs[a],regs[v]);x.connect(regs[v],regs[b])
if bulk:
 for body,tap,mos in [('nbody','ntap','pmosbulk'),('pbody','ptap','nmosbulk')]:
  x.connect(regs[body]);x.connect(regs[tap]);x.connect(regs[mos])
  x.connect(regs[body],regs[tap]);x.connect(regs[tap],regs['contact'])
  x.connect(regs[body],regs[mos])
x.extract_netlist()
seen=set(); names={}; disconnected_aliases=[]
for layer, key in [(34,'m1'),(36,'m2'),(42,'42'),(46,'46'),(81,'81')]:
 for s in c.shapes(l.layer(layer,10)).each():
  if s.is_text():
   net=x.probe_net(regs[key],s.text.trans.disp)
   if net and net.cluster_id not in seen:
    name=s.text.string
    names[name]=names.get(name,0)+1
    if names[name]>1: disconnected_aliases.append(name)
    net.name=name if names[name]==1 else name+"__island"+str(names[name])
    ci=net.circuit(); pin=ci.create_pin(net.name);ci.connect_pin(pin,net)
    seen.add(net.cluster_id)
# Preserve externally driven supply/bias nodes before series/parallel reduction.
if '--raw' not in sys.argv:x.netlist().combine_devices()
if '--json' in sys.argv:
 devices=[]
 for ci in x.netlist().each_circuit():
  for d in ci.each_device():
   dc=d.device_class()
   devices.append(dict(type=dc.name, terminals={t.name:d.net_for_terminal(t.name).expanded_name() if d.net_for_terminal(t.name) else None for t in dc.terminal_definitions()},parameters={p.name:d.parameter(p.name) for p in dc.parameter_definitions()}))
 bulk_summary=None
 if bulk:
  from collections import Counter
  bulk_summary=dict(terminal_counts={typ:dict(Counter(d['terminals']['B'] for d in devices if d['type']==typ)) for typ in ['nmos','pmos','nmos6','pmos6'] if any(d['type']==typ for d in devices)},
   isolated_pwell_regions=r(204).count(),deep_nwell_regions=r(12).count(),
   uncovered_gate_area_um2={typ:float((regs[typ+'g']-regs[body]).area()*l.dbu**2) for typ,body in [('nmos','pbody'),('pmos','nbody')]})
 print(json.dumps(dict(bulk_audit=bulk_summary,source_sha256=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(),cell=c.name,devices=devices,disconnected_label_aliases=disconnected_aliases,limitations=[('Generic four-terminal extraction with ideal well conductivity; special device classes and parasitics omitted.' if bulk else 'Generic extraction; body, special device classes and parasitics omitted.'),'Repeated supply names on disconnected metal islands are explicitly distinguished; no implicit global connection.','Resistor sheet resistance assigned 1000 ohm/square; valid for ADC high-poly only, other resistor flavors need classification.','MIM Option B assumed M4 bottom/FuseTop top, assigned 2 fF/um2. No fringe or plate parasitics.']),indent=2))
else:
 print(x.netlist().to_s())
