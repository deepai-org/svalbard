"""Independent static loading check; not dynamic ADC qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-top-load'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert (W/'load.spice').read_bytes()==(P/'analog/adc/top_load.spice').read_bytes()
log=(W/'load.log').read_text().lower();assert 'ngspice-46 done' in log
assert not any(x in log for x in ['error','warning','aborted'])
a=np.loadtxt(W/'load.dat',skiprows=1);assert a.shape==(10,7) and np.isfinite(a).all()
assert np.allclose(a[:,1:3],-a[:,3:5],atol=1e-15,rtol=1e-6)
c=-a[:,2]/(np.pi*a[:,0]);unit=-a[:,6]/(2*np.pi*a[:,0]);assert np.all(c>0) and np.all(unit>0)
gain=float(256*unit[0]/(256*unit[0]+c[0]))
source=P/'evidence/fast-cdac-charge.json';d=json.loads(source.read_text())
anchors={(r['case'],r['hold_ns']):r['measured_residue_v'] for r in d['cases'] if r['anchor']}
errors=[];wrong=0
for r in d['cases']:
 if r['anchor']:continue
 anchor=anchors[r['case'],r['hold_ns']]
 predicted=anchor+gain*(r['msb_corrected_prediction_v']-anchor)
 errors.append(predicted-r['measured_residue_v']);wrong+=(predicted>=0)!=(r['measured_residue_v']>=0)
files=[W/'load.spice',W/'load.log',W/'load.dat',P/'analog/adc/comparator.spice',R/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice',source,Path(__file__)]
report=dict(status='static_loading_supports_gain_hypothesis',simulator_image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',files_sha256={str(p.relative_to(R)):sha(p) for p in files},capacitance_per_side_ff=(c*1e15).tolist(),unit_capacitance_ff=float(unit[0]*1e15),predicted_gain=gain,nonanchor_samples=len(errors),residue_rms_v=float(np.sqrt(np.mean(np.array(errors)**2))),residue_max_abs_v=float(max(abs(x) for x in errors)),sign_disagreements=int(wrong),limitations=['Nominal symmetric1.65V bias, comparator reset, sampling gate off; no switching or extracted layout.', 'Array denominator assumes256 equal capacitors; additional CDAC parasitics omitted.', 'Gain from independent AC test, but residue validation reuses previously inspected records and measured frame anchors.', 'PDK supplied by pinned image; no independent fab capacitance validation.'])
(P/'evidence/adc-top-load.json').write_text(json.dumps(report,indent=2)+'\n')
print(gain,report['residue_rms_v'],report['sign_disagreements'])
