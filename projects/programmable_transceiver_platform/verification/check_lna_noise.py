#!/usr/bin/env python3
"""Stationary LNA evidence; passive load surrogate is not periodically switched noise."""
import hashlib,json,re,sys
BYPASS="--bypass" in sys.argv
MIM=next((a.split("=",1)[1] for a in sys.argv if a.startswith("--mim=")),None)
assert MIM in (None,"clean","lossy","inductive")
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-lna-mim-'+MIM if MIM else 'scratch/transceiver-lna-bypass' if BYPASS else 'scratch/transceiver-lna-noise')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
assert [c['name'] for c in r['cases']]==[s+f'_f{f}' for s in ('unloaded','snapshot','heavy') for f in (0,1)]
rows=[]
for c in r['cases']:
 n=c['name'];assert c['returncode']==0 and len(c['artifacts_sha256'])==6
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 log=(W/(n+'.log')).read_text().lower();assert not any(s in log for s in ('error','aborted','unknown parameter'))
 def data(ext):
  a=np.loadtxt(W/(n+ext),skiprows=1);assert np.isfinite(a).all();return a
 a=data('.dat');ac=data('-ac.dat');op=data('-op.dat');allnoise=data('-contributors.dat')
 assert a.shape==(101,3) and ac.shape==(101,5) and op.shape==(7,)
 assert np.array_equal(a[:,0],ac[:,0]) and np.all(np.diff(a[:,0])>0)
 assert np.isclose(a[0,0],2.4e9) and np.isclose(a[-1,0],2.6e9)
 with (W/(n+'-contributors.dat')).open() as f:h=f.readline().split()
 def v(name):return allnoise[:,h.index(name)]
 devices=[x for x in h if re.fullmatch(r'onoise\.m\..*\.m0',x) or (x.startswith('onoise_r') and not x.endswith(('_thermal','_1overf')))]
 assert len([x for x in devices if x.startswith('onoise.m.')])==16
 total=a[:,1]**2;closure=float(np.max(abs(sum(v(x)**2 for x in devices)/total-1)));assert closure<1e-10
 gain=np.hypot(ac[:,1],ac[:,2]);gate=np.hypot(ac[:,3],ac[:,4]);assert np.allclose(a[:,1]/a[:,2],gain,rtol=1e-10)
 # Actual RRF contribution must equal its Johnson ASD propagated by source gain.
 expected=np.sqrt(4*1.380649e-23*300.15*50)*gain
 assert np.max(abs(v('onoise_rrf')/expected-1))<.001
 k=50;assert np.isclose(a[k,0],2.5e9)
 groups={}
 for x in devices:
  key='MOS' if x.startswith('onoise.m.') else x.removeprefix('onoise_')
  groups[key]=groups.get(key,0)+float(v(x)[k]**2/total[k])
 rows.append(dict(name=n,scenario=c['scenario'],gate_v=float(op[1]),source_v=float(op[2]),drain_v=float(op[3]),power_w=float(-3.3*op[4]),selected_finger_vds_margin_v=float(op[5]-op[6]),source_gain_2p5g=float(gain[k]),drain_over_gate_gain_2p5g=float(gain[k]/gate[k]),input_asd_v_per_sqrt_hz_2p5g=float(a[k,2]),output_asd_v_per_sqrt_hz_2p5g=float(a[k,1]),stationary_noise_factor_db_2p5g=float(10*np.log10(total[k]/v('onoise_rrf')[k]**2)),noise_power_fractions_2p5g=groups,sum_closure_max_relative_error=closure))
for scenario in ('unloaded','snapshot','heavy'):
 p0=(W/(scenario+'_f0.spice')).read_text();p1=(W/(scenario+'_f1.spice')).read_text()
 assert p1.replace('.param fnoicor=1','.param fnoicor=0').replace(scenario+'_f1',scenario+'_f0')==p0
out=dict(completed=True,provenance=r,cases=rows,limitations=['TT27C3.3V stationary DC-linearized circuit with ideal1.5V gate bias; no actual mixer or autonomous clock.','Snapshot uses conditional RF admittance and average DC current measured in an earlier periodic mixer fixture. It does not preserve mixer noise or dynamic conversion.','Load resistor contributes thermal noise; ideal DC sink is noiseless. Cases are diagnostic scenarios, not fab bounds.','Stationary source-referred noise factor is not a receiver noise figure or proof of RF model accuracy.','No package, matching network, process/mismatch, linearity or signal-quality qualification.'])
(P/('evidence/lna-mim-'+MIM+'.json' if MIM else 'evidence/lna-bypass.json' if BYPASS else 'evidence/lna-noise.json')).write_text(json.dumps(out,indent=2)+'\n')
for c in rows:print(json.dumps(c))
