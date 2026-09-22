import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work');rows=[]
for state,up,dn in [('off',0,0),('up',3.3,0),('down',0,3.3),('both',3.3,3.3)]:
 for voltage in (.3,.8,1.3,1.8,2.3,2.8,3.0):
  name=f'{state}_{voltage}'
  d=f'''* Charge pump DC compliance scenario
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/pll/pfd.spice
.include /screen/pll/charge_pump.spice
.temp 27
VDD VDD 0 3.3
VU UP 0 {up}
VD DN 0 {dn}
IP BP 0 20u
IN VDD BN 20u
VOUT OUT 0 {voltage}
XCP UP DN OUT BP BN VDD 0 pt_charge_pump
.control
set numdgt=15
op
print i(VOUT) v(BP) v(BN) i(VDD)
.endc
.end
'''
  p=O/(name+'.spice');p.write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
  text=(O/(name+'.log')).read_text();values={k:float(v) for k,v in re.findall(r'^([iv]\([^\n=]+\))\s*=\s*([-+\d.eE]+)',text,re.M)};assert len(values)==4
  rows.append(dict(state=state,output_v=voltage,measurements=values,deck_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
r=dict(status='nominal_charge_pump_dc_screen_not_dynamic_or_pll_qualification',cases=rows,source_sha256=hashlib.sha256(Path('/screen/pll/charge_pump.spice').read_bytes()).hexdigest(),limitations=['Two ideal external 20uA references; no reference generation circuit.', 'Ideal DC controls and clamped output; no PFD drive or switching charge measured.', 'TT 3.3V 27C only; no mismatch, noise or extraction.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
