import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');base=Path('/screen/rf_candidate_bias_tb.spice').read_text();rows=[]
for restored in (False,True):
 name='restored' if restored else 'direct'
 extra='''.include /vco/divider.spice
.include /vco/clock_restorer_cascade.spice
VDIV VDIV 0 3.3
VBID BID 0 .95
VBIR BIR 0 1.0
VRESET RST 0 PWL(0 3.3 5n 3.3 5.1n 0)
'''
 if restored:extra+='XREST XRX.CP XRX.CN BIR VDIV 0 DP DN cml_clock_restorer_cascade\n'
 cp,cn=('DP','DN') if restored else ('XRX.CP','XRX.CN')
 extra+=f'XDIV {cp} {cn} RST BID VDIV 0 QP QN cml_divider_by_2\nCQP QP 0 25f\nCQN QN 0 25f\n'
 d=base.replace('.control',extra+'.control').replace('tran 2p 81n','tran 2p 41n')
 start=d.index('wrdata ');end=d.index('\n',start)
 d=d[:start]+f'let divided=v(QP)-v(QN)\nlet drive=v({cp})-v({cn})\nwrdata /work/{name}.dat cml divided drive v(XRX.GATE) i(VPLL) i(VDIV)'+d[end:]
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a.shape[1]==7
 w=a[(a[:,0]>=20e-9)&(a[:,0]<=40e-9)];t=w[:,0]
 def freq(col):
  v=w[:,col];i=np.where((v[:-1]<0)&(v[1:]>=0))[0];e=t[i]+(t[i+1]-t[i])*(-v[i])/(v[i+1]-v[i]);return (float((len(e)-1)/(e[-1]-e[0])) if len(e)>3 else None,len(e),float(np.ptp(np.diff(e))) if len(e)>3 else None)
 f,n,j=freq(1);g,m,k=freq(2)
 row=dict(restored=restored,vco_hz=f,divider_hz=g,divider_edges=m,divider_period_span_s=k,ratio=f/g if f and g else None,divider_diff_range_v=[float(w[:,2].min()),float(w[:,2].max())],divider_branch_current_a=float(-np.trapezoid(w[:,6],t)/(t[-1]-t[0])),gate_range_v=[float(w[:,4].min()),float(w[:,4].max())],artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')});rows.append(row);print(json.dumps(row),flush=True)
r=dict(status='nominal_loaded_first_divider_stage_not_feedback_chain',cases=rows,limitations=['Seeded VCO/prebiased LNA; external divider/reset/restorer bias sources.', 'One divider stage with 25fF per output, not full feedback divisor or PFD loading.', 'Nominal TT 3.3V 27C; no phase noise, process/mismatch or startup guarantee.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
