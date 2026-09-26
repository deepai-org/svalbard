"""Compare released analog-pad geometry and evaluate its protection-junction load.
Usage: python pad_constraints.py SUBMITTED.gds RELEASED_PAD.gds PAD.cdl MODELDIR
Requires KLayout and ngspice. Does not extract pad metal/package parasitics.
"""
import hashlib,json,math,re,subprocess,sys,tempfile
from pathlib import Path
import klayout.db as k
import numpy as np
submitted,released,cdl,models=map(Path,sys.argv[1:]);models=models.resolve()
layouts=[]
for path in [submitted,released]:
 l=k.Layout();l.read(str(path));layouts.append(l)
assert layouts[0].dbu==layouts[1].dbu
cell='gf180mcu_fd_io__asig_5p0';differences=[]
for info in set(layouts[0].layer_infos())|set(layouts[1].layer_infos()):
 rr=[]
 for l in layouts:
  idx=l.find_layer(info);rr.append(k.Region() if idx is None else k.Region(l.cell(cell).begin_shapes_rec(idx)))
 if not (rr[0]^rr[1]).is_empty():differences.append(str(info))
# Read diode area, perimeter and multiplicity from the pinned published CDL.
diodes=[]
for line in cdl.read_text().splitlines():
 if line.startswith(('D2 ','D3 ')):
  tok=line.split();params={a.lower():float(b) for a,b in (t.split('=') for t in tok[4:])}
  diodes.append(dict(name=tok[0],terminals=tok[1:3],model=tok[3],**params))
assert len(diodes)==2 and {d['model'] for d in diodes}=={'diode_nd2ps_06v0','diode_pd2nw_06v0'}
mapping={'diode_nd2ps_06v0':'np_6p0','diode_pd2nw_06v0':'pn_6p0'}
nodes={'DVSS':'0','DVDD':'vdd','ASIG5V':'pad'}
rows=[]
with tempfile.TemporaryDirectory(prefix='afe-pad-') as td:
 for corner in ['typical','ss','ff']:
  for bias in [.1,.8,1.65,2.6,3.2]:
   lines=['Conditional analog pad junction replay',f'.lib sm141064.ngspice diode_{corner}',
          '.temp 25','.options tnom=25','VDD vdd 0 3.3',f'VIN pad 0 {bias} AC 1']
   for d in diodes:
    a,b=map(nodes.__getitem__,d['terminals'])
    lines.append(f"{d['name']} {a} {b} {mapping[d['model']]} area={d['area']*d['m']} pj={d['pj']*d['m']}")
   lines+=['.control','ac lin 1 1meg 1meg','let cap=-imag(i(VIN))/(2*3.141592653589793*1e6)','print cap','.endc','.end']
   deck=Path(td)/'pad.cir';deck.write_text('\n'.join(lines)+'\n')
   proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,text=True,capture_output=True,timeout=10)
   assert proc.returncode==0,proc.stderr
   match=re.search(r'cap\s*=\s*([-+\d.eE]+)',proc.stdout);assert match,proc.stdout
   cap=float(match.group(1));assert cap>0
   # Independent reverse-biased depletion-capacitance calculation from the
   # pinned model's area/sidewall coefficients (25C, before series R).
   expected=0.
   for d in diodes:
    if d['model']=='diode_nd2ps_06v0':
     reverse=bias;cj,cjs,pb,php,mj,mjs=.00095,1.33e-10,.606,.48,.296,.01
     cta,ctp,tpb,tphp=.000825,.0018,.00146,.00313
    else:
     reverse=3.3-bias;cj,cjs,pb,php,mj,mjs=.000912,1.4649e-10,.76836,.5,.32713,.056777
     cta,ctp,tpb,tphp=.001,.00071888,.0019314,.0017642
    # ngspice TLEVC=1 uses fixed REFTEMP=300.15K, not TNOM.
    cj*=1-2*cta;cjs*=1-2*ctp;pb+=2*tpb;php+=2*tphp
    expected+=d['m']*(d['area']*cj/(1+reverse/pb)**mj+d['pj']*cjs/(1+reverse/php)**mjs)
   expected*=dict(typical=1.,ss=1.1,ff=.9)[corner]
   assert abs(cap/expected-1)<1e-5,(cap,expected)
   rows.append(dict(corner=corner,pad_bias_v=bias,junction_capacitance_f=cap,analytic_capacitance_f=expected,
                    ideal_capacitive_reactance_2p4ghz_ohm=1/(2*math.pi*2.4e9*cap)))
transients=[]
with tempfile.TemporaryDirectory(prefix='afe-pad-transient-') as td:
 for resistance,step_ns,nonlinear in [(200,.25,True),(1000,.25,True),(10000,.25,True),(200,.125,True),(200,.25,False)]:
  out=Path(td)/'wave.txt';deck=Path(td)/'pad.cir'
  lines=['Conditional pad distortion screen','.lib sm141064.ngspice diode_typical',
         '.temp 25','.options reltol=1e-7 abstol=1e-14 vntol=1e-9',
         'VDD vdd 0 3.3','VIN source 0 SIN(1.65 1.5 5meg)',f'RS source pad {resistance}']
  if nonlinear:
   for d in diodes:
    a,b=map(nodes.__getitem__,d['terminals'])
    lines.append(f"{d['name']} {a} {b} {mapping[d['model']]} area={d['area']*d['m']} pj={d['pj']*d['m']}")
  else:lines.append('CL pad 0 0.8742358p')
  lines+=['.control','set wr_singlescale','set wr_vecnames','set numdgt=15',
          f'tran {step_ns}n 4u 0 {step_ns}n',f'wrdata {out} v(pad)','.endc','.end']
  deck.write_text('\n'.join(lines)+'\n')
  proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,text=True,capture_output=True,timeout=20)
  assert proc.returncode==0 and out.exists(),proc.stdout+proc.stderr
  data=np.loadtxt(out,skiprows=1)
  count=8192;times=2e-6+np.arange(count)*2e-6/count
  y=np.interp(times,data[:,0],data[:,1]);spectrum=abs(np.fft.rfft(y))*2/count
  fundamental=spectrum[10];spectrum[0]=0;spectrum[10]=0
  spur_bin=int(np.argmax(spectrum));spur=spectrum[spur_bin]
  transients.append(dict(source_r_ohm=resistance,max_step_ns=step_ns,nonlinear_diodes=nonlinear,
   fundamental_peak_v=float(fundamental),largest_spur_hz=spur_bin/2e-6,
   sfdr_db=float(20*np.log10(fundamental/spur)),
   deterministic_sndr_db=float(20*np.log10(fundamental/np.linalg.norm(spectrum)))))
assert abs(transients[0]['sfdr_db']-transients[3]['sfdr_db'])<.05
assert transients[-1]['sfdr_db']>transients[0]['sfdr_db']+20
print(json.dumps(dict(source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [submitted,released,cdl,models/'sm141064.ngspice']},
 pad_cell=cell,polygon_difference_layers=sorted(differences),published_signal_diodes=diodes,
 model_mapping=mapping,cases=rows,pad_distortion_screen=transients,
 limitations=['Release-to-submission comparison is polygon geometry, not foundry LVS; layer 63/63 differs.',
 'PDK diode corners are model scenarios, not measured capacitance or statistical confidence bounds.',
 '3.3V ideal AC-grounded rails,25C,1MHz small-signal capacitance; RF reactance is a lumped-capacitor extrapolation, not a GHz pad model.',
 'Signal diode multiplicity folded into total area/perimeter. Junction models mapped by 6V implant type.',
 'Rail decoupling and rail clamp do not load signal with ideal AC-grounded rails; supply impedance/coupling omitted.',
 'Transient: 5MHz 1.5V-peak single-ended sine about1.65V, ideal source resistance, deterministic diode dynamics only; not actual ADC sampling or confirmed bench amplitude.',
 'Pad metal, well/substrate coupling, interconnect and package parasitics are not included.']),indent=2))
