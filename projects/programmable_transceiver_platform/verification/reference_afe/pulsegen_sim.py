"""Recovered pulse generator with full-parent net joins; nominal bias sensitivity.
Usage: python pulsegen_sim.py RAW.json PARENT_MAPPING.json MODELDIR [MAX_STEP_NS]
"""
import hashlib,json,sys,subprocess,tempfile
from pathlib import Path
import numpy as np
raw,mapping,models=map(Path,sys.argv[1:4]);models=models.resolve()
j=json.loads(raw.read_text());m=json.loads(mapping.read_text());assert all(len(v)==1 for v in m.values())
def node(n):return m[n][0].replace('$','net_')
step=float(sys.argv[4]) if len(sys.argv)>4 else .01
assert 0<step<=.01
rows=[]
with tempfile.TemporaryDirectory(prefix='afe-pulse-') as tmp:
 for bias in [.6,.8,1.,1.2]:
  for load in [10,100]:
   lines=['Recovered pulse generator','.include design.ngspice','.lib sm141064.ngspice typical','.temp 25',
    'VDD vdd 0 3.3','VSS vss 0 0',f'VB {node("bias")} 0 {bias}',
    f'VI {node("in")} 0 PULSE(0 3.3 5n .1n .1n 24.9n 50n)',f'CO {node("out")} 0 {load}f',
    '.options reltol=1e-6 abstol=1e-13 vntol=1e-9']
   for i,d in enumerate(j['devices']):
    t=d['terminals'];p=d['parameters'];ty=d['type'];assert ty in ['nmos','pmos']
    lines.append(f"M{i} {' '.join(node(t[n]) for n in ['D','G','S','B'])} {ty}_3p3 W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
   deck=Path(tmp)/'pulse.cir';out=Path(tmp)/'wave.txt'
   lines+=['.control','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step}n 45n 0 {step}n',f'wrdata {out} v({node("out")})','.endc','.end']
   deck.write_text('\n'.join(lines)+'\n');proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=20)
   assert proc.returncode==0 and out.exists(),proc.stdout+proc.stderr
   a=np.loadtxt(out,skiprows=1);v=a[:,1];t=a[:,0];cross=[]
   for i in np.flatnonzero((v[:-1]-1.65)*(v[1:]-1.65)<0):
    cross.append(dict(time_ns=float((t[i]+(1.65-v[i])*(t[i+1]-t[i])/(v[i+1]-v[i]))*1e9),rising=bool(v[i+1]>v[i])))
   edges=[c for c in cross if 5<c['time_ns']<30]
   width=edges[1]['time_ns']-edges[0]['time_ns'] if len(edges)==2 and edges[0]['rising'] and not edges[1]['rising'] else None
   rows.append(dict(maximum_timestep_ns=step,output_high_duration_ns=cross[1]['time_ns']-cross[0]['time_ns'] if len(cross)==2 else None,self_terminated_before_input_fall=width is not None,bias_v=bias,load_ff=load,pulse_width_ns=width,crossings=cross,peak_v=float(max(v)),output_at_29ns_v=float(np.interp(29e-9,t,v))))
print(json.dumps(dict(source_gds_sha256=j['source_sha256'],source_hashes={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in [raw,mapping,models/'design.ngspice',models/'sm141064.ngspice']},cases=rows,
 limitations=['3.3V25C typical models; assigned10/100fF output loads and100ps input edges, no wire parasitics or bias-source impedance.',
 'Parent mapping restores isolated source/body supply islands; child-only extraction is insufficient.',
 'Pulse widths are conditional, not published bias settings, reset timing margins or closed-loop conversion results.']),indent=2))
