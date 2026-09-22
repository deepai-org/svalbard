#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-tg-dc';B=R/'scratch/transceiver-tx-dac-commutator-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);assert a.shape==(256,len(h)) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
 return h,a
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
# Independently check added transistor connectivity/geometry, not just deck name.
s=(P/'analog/tx/commutator_tg.spice').read_text();lines=[l for l in s.splitlines() if l.startswith('X')];assert len(lines)==33 and lines[0]=='XBASE BP BN RP RN LO LOB VSS pt_tx_commutator'
for bank,a,b,g in [('PP','RP','BP','LOB'),('PN','RP','BN','LO'),('NP','RN','BP','LO'),('NN','RN','BN','LOB')]:
 for i in range(8):
  d,t=(a,b) if i in (0,2,3,7) else (b,a)
  assert f'X{bank}{i} {d} {g} {t} VDD pfet_03v3 w=4u l=0.28u' in lines
assert sha(P/'analog/tx/commutator_tg.spice')==m['source_sha256_before']['/screen/tx/commutator_tg.spice']
assert [c['name'] for c in r['cases']]==['r50_lo0','r50_lo1','r200_lo0','r200_lo1'];rows=[]
for c in r['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['baseline_deck_sha256']
 d=(W/(name+'.spice')).read_text();assert d.replace('XM OP ON RFP RFN LO LOB VDD 0 pt_tx_commutator_tg','XM OP ON RFP RFN LO LOB 0 pt_tx_commutator').replace('.include /screen/tx/commutator_tg.spice\n','')==src.read_text()
 assert sha(W/(name+'.spice'))==c['deck_sha256_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['returncode']==0 and 'aborted' not in (W/(name+'.log')).read_text().lower()
 metrics={}
 for variant,path in [('nmos',B/(name+'.dat')),('tg',W/(name+'.dat'))]:
  h,a=read(path)
  def v(k):return a[:,h.index(k)]
  bb=v('v(op)')-v('v(on)');rf=v('v(rfp)')-v('v(rfn)');fit=rf[0]+np.arange(256)*(rf[-1]-rf[0])/255
  metrics[variant]=dict(rf_endpoint_magnitude_v=float(abs(rf[-1])),endpoint_voltage_ratio=float(abs(rf[-1]/bb[-1])),monotonic=bool(np.all(np.diff(rf)>0) or np.all(np.diff(rf)<0)),max_endpoint_fit_error_v=float(abs(rf-fit).max()))
 rows.append(dict(name=name,metrics=metrics))
out=dict(status='completed_static_candidate_comparison',cases=rows,provenance=r,limitations=['Matched typical DC with ideal LO and bias; no RF conversion or noise qualification.', 'Adds32 PMOS fingers,128um total gate width; gate drive burden not measured here.', 'No candidate adoption until dynamic LO loading and RF signal quality are evaluated.'])
(P/'evidence/tx-tg-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
