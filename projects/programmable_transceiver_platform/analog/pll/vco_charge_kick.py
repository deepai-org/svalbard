"""Loaded open-loop ring supply sensitivity; deterministic diagnostic only."""
import hashlib,json,subprocess,sys

from pathlib import Path
O=Path('/work');B=Path('/baseline/v1.08.spice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(variant='charge', *, entrypoint=None):
 FINE="--fine" in sys.argv
 nodes,description={
     'charge': (['XRX.CP','XRX.CN'], 'differential output charge perturbation'),
     'internal': (['XRX.XVCO.N0P','XRX.XVCO.N0N'], 'differential internal-stage charge perturbation'),
     'channel': (['XRX.XVCO.N0P','XRX.XVCO.X0.TAIL'], 'drain-source charge perturbation of XRX.XVCO.X0.XMP'),
 }[variant]
 r=json.loads((B.parent/'result.json').read_text());c=next(c for c in r['cases'] if c['control_v']==1.08)
 assert sha(B)==c['artifacts_sha256']['.spice']
 original=B.read_text()
 if variant=='charge':
  assert 'XD1 XRX.CP XRX.CN ' in original
 else:
  assert '.ic v(XRX.XVCO.N0P)=' in original and 'v(XRX.XVCO.N0N)=' in original
 if variant=='channel':
  cell=Path('/screen/pll/ring_vco_split.spice').read_text()
  assert 'XMP OUTP INP TAIL VSS nfet_03v3' in cell
  assert 'X0 N2P N2N N0P N0N VCTRL REGEN VDD VSS pt_split_delay' in cell
 assert original.count('VPLL PLLVDD 0 3.3')==1
 paths={B,Path(__file__),Path(entrypoint or __file__)}
 from spice_dependencies import dependencies

 dependencies(original,B.parent,paths)
 before={str(p):sha(p) for p in sorted(paths)}
 (O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,max_step_ps=.5 if FINE else 2,baseline_deck_sha256=sha(B),pulse_nodes=nodes,pulse_times_ns=[20,20.001,20.011,20.012],amplitudes_a=[0,1e-4,-1e-4],scope=f'Deterministic {description}; no intrinsic noise or autonomous PLL claim'),indent=2)+'\n')
 rows=[]
 for name,amplitude in [('quiet',0),('positive',1e-4),('negative',-1e-4)]:
  pulse=f'IKICK {nodes[0]} {nodes[1]} PWL(0n 0 20n 0 20.001n {amplitude} 20.011n {amplitude} 20.012n 0)\n'
  d=original.replace('.control',pulse+'.control').replace('/work/v1.08.dat',f'/work/{name}.dat')
  assert d.replace(pulse,'').replace(f'/work/{name}.dat','/work/v1.08.dat')==original
  if FINE:d=d.replace('tran 2p 41n 0 2p uic','tran .5p 41n 0 .5p uic')
  p=O/(name+'.spice');p.write_text(d);h=sha(p)
  with (O/(name+'.log')).open('w') as log:
   try:
    result=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600 if FINE else 300);code=result.returncode;timeout=False
   except subprocess.TimeoutExpired:code=None;timeout=True
  assert sha(p)==h
  rows.append(dict(name=name,pulse_a=amplitude,returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
 after={str(p):sha(p) for p in sorted(paths)};assert before==after
 (O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')

if __name__ == '__main__':
 main()
