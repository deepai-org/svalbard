"""Output conduction direction at SAR clocks; not full rail-current balance."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/sar-reference-devices.json';d=json.loads(e.read_text())
assert d['completed'] and d['reproduction_pass']
p=R/'scratch/transceiver-sar-reference-devices/baseline.dat'
assert sha(p)==d['waveform_sha256']
contract=P/'evidence/device-probe-contract.json'
assert json.loads(contract.read_text())['status']=='device_probe_conventions_verified_at_selected_DC_points'
with p.open() as f:h=f.readline().lower().split()
a=np.loadtxt(p,skiprows=1)
def at(name,ns):return float(np.interp(ns*1e-9,a[:,0],a[:,h.index(name)]))
rows=[]
for hold in (70,120,170):
 for j in range(8):
  ns=hold+.5+5*j
  for rail,node,target in [('xhigh','vh',2.15),('xlow','vl',1.15)]:
   def dev(name,param):return at(f'@m.xref.{rail}.{name}.m0[{param}]',ns)
   # Both model ID reports are positive forward-conduction magnitudes.
   assert dev('xout','vds')>0 and dev('xload','vds')>0
   output=dev('xout','id');load=dev('xload','id')
   net=output-load if rail=='xhigh' else load-output
   error=at('v('+node+')',ns)-target
   rows.append(dict(hold_ns=hold,bit=7-j,rail=rail,error_v=error,
    output_id_a=output,load_id_a=load,net_conduction_into_rail_a=net,
    restorative_conduction=bool(error*net<0),
    backward_rail_slope_v_per_ns=(at('v('+node+')',ns)-at('v('+node+')',ns-.2))/.2))
out=dict(source_sha256=sha(e),waveform_sha256=sha(p),probe_contract_sha256=sha(contract),
 script_sha256=sha(Path(__file__)),rows=rows,limitations=[
 'Original 100ohm sample-driver baseline only, not the newer 2kohm candidate.',
 'Output-device ID omits displacement, compensation, CDAC and reservoir terminal currents; not KCL.',
 'Instantaneous restorative direction does not establish adequate settling or loop stability.',
 'DC sign convention checked only for forward conduction; selected transient VDS positivity is verified.'])
(P/'evidence/reference-restoring-current.json').write_text(json.dumps(out,indent=2)+'\n')
for rail in ('xhigh','xlow'):
 selected=[r for r in rows if r['rail']==rail]
 print(rail,'restorative clocks',sum(r['restorative_conduction'] for r in selected),'of',len(selected))
 for r in selected:
  if r['bit']<=1:print(r)
