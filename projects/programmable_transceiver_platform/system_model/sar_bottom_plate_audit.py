"""Test saved MSB bottom-plate lag against unexplained SAR residue."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
source=P/'evidence/sar-physical-divergence.json';d=json.loads(source.read_text())
physical=json.loads((P/'evidence/sar-driver-physical.json').read_text())
hashes={c['name']:c['waveform_sha256'] for c in physical['cases']}
rows=[]
for name in hashes:
    path=R/'scratch'/('transceiver-'+name)/'baseline.dat'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[name]
    with path.open() as f:header=f.readline().lower().split()
    a=np.loadtxt(path,skiprows=1)
    def at(node,t):return float(np.interp(t*1e-9,a[:,0],a[:,header.index('v('+node+')')]))
    for frame in [r for r in d['results'] if r['case']==name]:
        events=[];initial=None
        for j,s in enumerate(frame['steps']):
            t=frame['hold_ns']+.5+5*j
            sign=1 if s['actual_trial']&128 else -1
            span=at('vh',t)-at('vl',t)
            error=at('xd.xp7.bot',t)-at('xd.xn7.bot',t)-sign*span
            if initial is None:initial=error
            # 128 MSB units of 256 total per side. Subtract anchor error.
            contribution=.5*(error-initial)
            events.append(dict(bit=s['bit'],msb_differential_lag_v=error,
                estimated_msb_residue_contribution_v=contribution,
                prior_unexplained_v=s['unexplained_residue_v'],
                remaining_unexplained_v=s['unexplained_residue_v']-contribution))
        rows.append(dict(case=name,hold_ns=frame['hold_ns'],steps=events,
            maximum_msb_contribution_v=max(abs(e['estimated_msb_residue_contribution_v']) for e in events),
            maximum_remaining_residue_v=max(abs(e['remaining_unexplained_v']) for e in events)))
report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),waveform_hashes=hashes,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results=rows,
    limitations=['Only MSB bottom plates were saved; cannot close total charge balance.',
      'Half-weight estimate assumes equal linear capacitor units and ignores top-node parasitics.',
      'Observed-history attribution only; not a predictive converter model.'])
(P/'evidence/sar-bottom-plate-audit.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r['case'],r['hold_ns'],r['maximum_msb_contribution_v'],r['maximum_remaining_residue_v'])
