"""Nominal edge/reset functionality of recovered storage cells, not timing signoff.
Usage: python register_sim.py DFF.json RESET_DFF.json MODELDIR
"""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
models=Path(sys.argv[3]).resolve();rows=[]
with tempfile.TemporaryDirectory(prefix='afe-register-') as tmp:
 for path in map(Path,sys.argv[1:3]):
  j=json.loads(path.read_text());reset=j['cell']=='lib_dff_wreset'
  assert not j['disconnected_label_aliases']
  for step in [.01,.005]:
   lines=['Recovered storage functional replay','.include design.ngspice','.lib sm141064.ngspice typical','.temp 25',
    'VDD vdd 0 3.3','VSS vss 0 0',
    'VCLK clk 0 PULSE(0 3.3 2n .1n .1n 1.9n 4n)',
    'VD d 0 PWL(0 0 1n 0 1.1n 3.3 3n 3.3 3.1n 0 7n 0 7.1n 3.3 16n 3.3)',
    'CQ q 0 10f','.options reltol=1e-6 abstol=1e-13 vntol=1e-9']
   if reset:lines+=['VR rstb 0 PWL(0 0 .5n 0 .6n 3.3 3.3n 3.3 3.4n 0 5n 0 5.1n 3.3 11n 3.3 11.1n 0 13n 0 13.1n 3.3 16n 3.3)']
   for i,d in enumerate(j['devices']):
    t=d['terminals'];p=d['parameters'];ty=d['type'];assert ty in ['nmos','pmos']
    nodes=' '.join(t[n].replace('$','net_') for n in ['D','G','S','B'])
    lines.append(f"M{i} {nodes} {ty}_3p3 W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
   deck=Path(tmp)/'cell.cir';out=Path(tmp)/'wave.txt'
   lines+=['.control','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step}n 16n 0 {step}n',f'wrdata {out} v(q) v(d) v(clk)','.endc','.end']
   deck.write_text('\n'.join(lines)+'\n');r=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=20)
   assert r.returncode==0 and out.exists(),r.stdout+r.stderr
   a=np.loadtxt(out,skiprows=1)
   times=[2.8,3.8,4.8,5.8,6.8,8.8,10.8,11.8,13.8,14.8]
   q=[float(np.interp(t*1e-9,a[:,0],a[:,1])) for t in times]
   expected=[1,0,0,0,0,0,1,0,0,1] if reset else [1,1,1,1,0,0,1,1,1,1]
   assert all(v>2.64 if bit else v<.66 for v,bit in zip(q,expected)),(j['cell'],q)
   rows.append(dict(cell=j['cell'],raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),maximum_timestep_ns=step,
    observation_ns=times,q_volts=q,expected_logic=expected))
print(json.dumps(dict(cases=rows,model_sha256={n:hashlib.sha256((models/n).read_bytes()).hexdigest() for n in ['design.ngspice','sm141064.ngspice']},
 conclusions=['Both cells capture on rising clock edges in these nominal tests.',
 'lib_dff_wreset clears with rstb low without waiting for a clock edge; releasing reset does not itself capture data in the tested low-clock interval.'],
 limitations=['3.3V25C nominal models,100ps input edges,10fF output load; extracted MOS geometry without routing parasitics.',
 'Widely separated transitions do not characterize setup/hold, reset recovery/removal, metastability, startup or PVT margins.']),indent=2))
