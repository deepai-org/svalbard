"""Matched receiver replays: recorded P/N versus unchanged differential at fixed CM."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-lo-rf-only';e=json.loads((P/'evidence/lo-rf-only.json').read_text());assert e['completed']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(B/'latest.dat')==e['waveform_sha256']
with (B/'latest.dat').open() as f:h=f.readline().lower().split()
names=['v(p)','v(n)','v(bip)','v(bin)','v(bqp)','v(bqn)','v(lg)','v(ls)','v(fip)','v(fin)','v(fqp)','v(fqn)','v(oip)','v(oin)','v(oqp)','v(oqn)']
a=np.loadtxt(B/'latest.dat',skiprows=1,usecols=[0]+[h.index(n) for n in names]);t=np.r_[0,a[:,0]];values=np.vstack((a[0,1:],a[:,1:]));assert np.all(np.diff(t)>0)
cm=(values[:,0]+values[:,1])/2;diff=values[:,0]-values[:,1];mask=(t>=800e-9)&(t<=1000e-9)
fixed=float(np.trapezoid(cm[mask],t[mask])/(t[mask][-1]-t[mask][0]))
parent=(B/'latest.spice').read_text();body=parent.split('.include /vco/divider.spice')[0];removed=[]
for line in body.splitlines():
    if line.startswith('XVCO ') or line.startswith('.ic v(XVCO.') or line.startswith('.ic v(LG)'):
        removed.append(line);body=body.replace(line+'\n','')
assert len(removed)==5
for mode in ('recorded','fixed'):
    O=R/f'scratch/transceiver-lo-common-mode-{mode}-prepared';O.mkdir()
    pn=values[:,:2].copy()
    if mode=='fixed':pn=np.column_stack((fixed+diff/2,fixed-diff/2))
    assert np.max(abs((pn[:,0]-pn[:,1])-diff))<1e-14
    with (O/'ring_pwl.spice').open('w') as f:
        for k,node in enumerate(('P','N')):
            f.write(f'VREPLAY{node} {node} 0 PWL(\n')
            for ti,vi in zip(t,pn[:,k]):f.write(f'+ {ti:.16e} {vi:.16e}\n')
            f.write('+ )\n')
    seeds='\n'.join('.ic '+n+'='+format(values[0,k],'.16e') for k,n in enumerate(names) if n not in ('v(p)','v(n)'))
    vectors=' '.join(names+[f'v(XB{x}.{node})' for x in ('IP','IN','QP','QN') for node in ('MID','LOCAL')]+['v(PREIP)','v(PREIN)','v(PREQP)','v(PREQN)'])
    deck=body+'.include /prepared/ring_pwl.spice\n'+seeds+f'\n.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nsave {vectors}\ntran 2p 1001n 0 2p uic\nwrdata /work/replay.dat {vectors}\n.endc\n.end\n'
    (O/'replay.spice').write_text(deck)
    m=dict(mode=mode,fixed_common_mode_v=fixed,parent_waveform_sha256=e['waveform_sha256'],parent_deck_sha256=sha(B/'latest.spice'),removed_lines=removed,
        source_provenance=json.loads((B/'result.json').read_text())['sources_after'],
        artifacts_sha256={n:sha(O/n) for n in ('ring_pwl.spice','replay.spice')},
        limitations=['Replay removes bidirectional oscillator/receiver loading and feedback.','Initial saved nodes seeded, unsaved internal states not reconstructed.','Fixed CM removes all CM variation, including carrier-frequency components; not exclusively low-frequency rejection.','Recorded control must reproduce before causal interpretation.'])
    (O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
