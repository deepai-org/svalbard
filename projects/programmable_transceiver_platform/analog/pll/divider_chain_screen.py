import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');base=Path('/screen/rf_candidate_bias_tb.spice').read_text()
extra='''.include /vco/divider.spice
.include /screen/pll/pfd.spice
VDIV VDIV 0 3.3
VBID BID 0 .95
VRESET RST 0 PWL(0 3.3 5n 3.3 5.1n 0)
'''
cp,cn='XRX.CP','XRX.CN'
for k in range(1,8):
 extra+=f'XD{k} {cp} {cn} RST BID VDIV 0 Q{k}P Q{k}N cml_divider_by_2\n';cp,cn=f'Q{k}P',f'Q{k}N'
extra+='''CFB Q7P FBG 1p
RFB FBG XFB.MID 100k
XFB FBG FB VDIV 0 pt_lo_buffer S=1
VREF REF 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)
VRN RN 0 PWL(0 0 90n 0 90.1n 3.3)
XPFD REF FB RN UP DN VDIV 0 pt_pfd
CU UP 0 50f
CD DN 0 50f
'''
d=base.replace('.control',extra+'.control').replace('tran 2p 81n','tran 2p 321n')
start=d.index('wrdata ');end=d.index('\n',start)
lets=''.join(f'let d{k}=v(Q{k}P)-v(Q{k}N)\n' for k in range(1,8))
d=d[:start]+lets+'wrdata /work/chain.dat cml '+' '.join(f'd{k}' for k in range(1,8))+' v(FB) v(XRX.GATE) i(VDIV) v(UP) v(DN)'+d[end:]
p=O/'chain.spice';p.write_text(d)
with (O/'chain.log').open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
a=np.loadtxt(O/'chain.dat',skiprows=1);assert a.shape[1]==14 and np.isfinite(a).all() and a[-1,0]>320e-9
w=a[(a[:,0]>=100e-9)&(a[:,0]<=320e-9)];t=w[:,0]
rows=[]
for col in range(1,10):
 lev=1.65 if col==9 else 0;v=w[:,col];i=np.where((v[:-1]<lev)&(v[1:]>=lev))[0];e=t[i]+(t[i+1]-t[i])*(lev-v[i])/(v[i+1]-v[i])
 rows.append(dict(node='FB' if col==9 else ('VCO' if col==1 else f'div{2**(col-1)}'),edges=len(e),frequency_hz=float((len(e)-1)/(e[-1]-e[0])) if len(e)>2 else None,min_v=float(v.min()),max_v=float(v.max())))
r=dict(status='transistor_divide128_and_pfd_input_open_loop',nodes=rows,divider_interface_pfd_current_a=float(-np.trapezoid(w[:,11],t)/(t[-1]-t[0])),gate_range_v=[float(w[:,10].min()),float(w[:,10].max())],artifacts_sha256={s:hashlib.sha256((O/('chain'+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')},limitations=['Nominal seeded/prebiased run; external control and bias, no charge pump feedback.', 'Fixed divide128 test architecture; reference19.53125MHz is a fixture, not frozen product reference.', 'Only a few late final-stage cycles; no acquisition, jitter, mismatch or process proof.', 'AC-coupled CMOS interface needs startup/duty/supply sensitivity qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
