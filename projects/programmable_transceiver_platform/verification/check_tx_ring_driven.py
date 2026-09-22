#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-ring-driven';B=R/'scratch/transceiver-tx-buffered-lo'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():print('Pending terminal ring-driven result');raise SystemExit(0)
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];assert [c['name'] for c in r['cases']]==['nmos_c255','tg_c255']
add=m['addition'];assert len(add.splitlines())==15
required=['VPLL PLLVDD 0 3.3','VCTRL CTRL 0 1.08','VREGEN REGEN 0 1.08','XVCO CTRL REGEN PLLVDD 0 CP CN pt_split_ring LOAD_L=5.25u CAP_W=4u CAP_L=3u','CLOADP CP 0 25f','CLOADN CN 0 25f','CCP CP LOIN 200f','CCN CN LOBIN 200f','RFBP LOIN XLP.MID 100k','RFBN LOBIN XLN.MID 100k']
assert all(x in add.splitlines() for x in required)
remove=['VLO LOIN 0 PULSE(0 3.3 1n 20p 20p 180p 400p)\n','VLOB LOBIN 0 PULSE(3.3 0 1n 20p 20p 180p 400p)\n'];assert m['removed_lines']==remove
rows=[]
for c in r['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['baseline_deck_sha256'];expected=src.read_text()
 for line in remove:expected=expected.replace(line,'')
 expected=expected.replace('.control',add+'.control').replace('i(VLO) i(VLOB)','v(CP) v(CN) i(VPLL)').replace('tran 2p 10n 0 2p','tran 2p 40n 0 2p uic')
 assert (W/(name+'.spice')).read_text()==expected and sha(W/(name+'.spice'))==c['deck_sha256_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 log=(W/(name+'.log')).read_text().lower();row=dict(name=name,completed=False,returncode=c['returncode'])
 if (W/(name+'.dat')).exists():
  with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
  assert h==['time']+'v(op) v(on) v(rfp) v(rfn) v(lo) v(lob) v(cp) v(cn) i(vpll) i(vdd) i(vdrv) v(loin) v(lobin) i(vlobuf)'.split()
  a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and 'aborted' not in log and a[-1,0]>=40e-9))
  if row['completed']:
   a=a[(a[:,0]>=30e-9)&(a[:,0]<=40e-9)];t=a[:,0]
   def v(k):return a[:,h.index(k)]
   def freq(y,level):
    ix=np.where((y[:-1]<level)&(y[1:]>=level))[0];ts=t[ix]+(t[ix+1]-t[ix])*(level-y[ix])/(y[ix+1]-y[ix]);return dict(rising_edges=len(ts),mean_hz=float((len(ts)-1)/(ts[-1]-ts[0])) if len(ts)>1 else None)
   def mean(y):return float(np.trapezoid(y,t)/(t[-1]-t[0]))
   row.update(ring_frequency=freq(v('v(cp)')-v('v(cn)'),0),lo_frequency=freq(v('v(lo)'),1.65),lo_range_v=[float(v('v(lo)').min()),float(v('v(lo)').max())],buffer_input_range_v=[float(v('v(loin)').min()),float(v('v(loin)').max())],rf_peak_to_peak_v=float(np.ptp(v('v(rfp)')-v('v(rfn)'))),ring_average_power_w=-3.3*mean(v('i(vpll)')),buffer_average_power_w=-3.3*mean(v('i(vlobuf)')))
 rows.append(row)
out=dict(status='terminal_seeded_ring_TX_diagnostic',cases=rows,provenance=r,limitations=['Seeded UIC and ideal control/bias supplies; no cold startup, PLL lock or intrinsic phase noise.', 'Open-loop frequency is measured, not assumed2.5GHz. No modulated RF or quadrature qualification.', 'One load, typical only, ideal coupling capacitors and feedback resistors; no extracted/coexistence evidence.'])
(P/'evidence/tx-ring-driven.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
