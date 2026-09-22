"""Check whether zero-amplitude injection placement changes retained waveforms."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
roots=[R/'scratch'/n for n in ('transceiver-vco-charge-kick-fine','transceiver-vco-internal-kick-v2','transceiver-vco-channel-kick')]
rows=[];reference=None;base=None
for root in roots:
 record=root/('result.json' if (root/'result.json').exists() else 'progress.json');r=json.loads(record.read_text());c=next(x for x in r['cases'] if x['name']=='quiet')
 assert c['returncode']==0 and not c['timed_out']
 for ext,h in c['artifacts_sha256'].items():assert sha(root/('quiet'+ext))==h
 deck=(root/'quiet.spice').read_text();pulse=next(x for x in deck.splitlines() if x.startswith('IKICK '));assert pulse.endswith('PWL(0n 0 20n 0 20.001n 0 20.011n 0 20.012n 0)')
 normalized=deck.replace(pulse+'\n','')
 if base is None:base=normalized
 else:assert base==normalized
 with (root/'quiet.dat').open() as f:header=f.readline().split()
 a=np.loadtxt(root/'quiet.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]+1e-21>=41e-9
 if reference is None:reference=a;refheader=header
 assert header==refheader
 samegrid=a.shape==reference.shape and np.array_equal(a[:,0],reference[:,0])
 rows.append(dict(root=str(root.relative_to(R)),artifacts_sha256=c['artifacts_sha256'],rows=len(a),same_time_grid=samegrid,all_saved_vectors_identical=bool(samegrid and np.array_equal(a,reference)),max_abs_vector_difference=float(abs(a[:,1:]-reference[:,1:]).max()) if samegrid else None))
out=dict(completed=True,cases=rows,limitations=['Only zero-current controls at matched0.5ps timestep and41ns horizon; positive/negative cases remain separate.', 'Bit-identical zero controls do not establish noise accuracy, pulse linearity or convergence of perturbed histories.'])
(P/'evidence/vco-quiet-controls.json').write_text(json.dumps(out,indent=2)+'\n');print([(x['root'],x['same_time_grid'],x['all_saved_vectors_identical'],x['max_abs_vector_difference']) for x in rows])
