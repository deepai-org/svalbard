"""Ideal sinusoidal drive at observed swing scale; intrinsic chain diagnostic only."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(self_bias=False, *, entrypoint=None, analysis='sine'):
 assert analysis in ('sine','dc','ac','mixer')
 self_bias=self_bias or analysis in ('ac','mixer')
 node='SIG' if self_bias else 'IN'
 bias=2.24 if self_bias else 1.530318
 body='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/lo_buffer.spice
.include /screen/quadrature/lo_final_stage.spice
.temp 27
.options reltol=1e-5 vntol=1e-8 abstol=1e-14
VDD VDD 0 3.3
VIN IN 0 1.5
XB IN PRE VDD 0 pt_lo_buffer
XF PRE OUT VDD 0 pt_lo_final_stage
CL OUT 0 50f
'''
 if self_bias:
  body=body.replace('.temp 27', '.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical\n.include /screen/reference/reservoir_mim.spice\n.temp 27').replace('VIN IN 0 1.5', 'VIN SIG 0 1.5\nXC SIG IN pt_ref_reservoir_4\nRFB IN XB.MID 100k')
 if analysis=='ac':body=body.replace('VIN SIG 0 1.5','VIN SIG 0 DC 2.24 AC 1')
 if analysis=='mixer':body+='''.include /wifi/rf_switch_mixer/mixer.spice
VINB SIGB 0 1.5
XCB SIGB INB pt_ref_reservoir_4
RFBB INB XBB.MID 100k
XBB INB PREB VDD 0 pt_lo_buffer
XFB PREB OUTB VDD 0 pt_lo_final_stage
CLB OUTB 0 50f
VRF RFS 0 1.5
RRF RFS RF 300
XM RF OUT OUTB MP MN 0 wifi_rf_switch_mixer
RP MP 0 1k
RN MN 0 1k
CP MP 0 1p
CN MN 0 1p
'''
 paths={Path(__file__)}
 if entrypoint is not None:paths.add(Path(entrypoint))
 def scan(s,parent):
  for line in s.splitlines():
   m=re.match(r'\s*\.(?:include|lib)\s+(\S+)',line,re.I)
   if not m:continue
   p=Path(m[1].strip(chr(34)+chr(39)));p=p if p.is_absolute() else parent/p
   if not p.is_file():assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2;continue
   p=p.resolve()
   if p not in paths:paths.add(p);scan(p.read_text(),p.parent)
 scan(body,O);before={str(p):sha(p) for p in paths};rows=[]
 cases=([('up',1.3,1.8,.001),('down',1.8,1.3,-.001)] if analysis=='dc' else
        [('ac',0,0,0)] if analysis=='ac' else [('small',.095,0,0),('large',.108,0,0)])
 for name,start,stop,step in cases:
  d=body
  if analysis in ('sine','mixer'):
   d=d.replace(f'VIN {node} 0 1.5',f'VIN {node} 0 SIN({bias} {start} 2.5g)')
   if analysis=='mixer':d=d.replace('VINB SIGB 0 1.5',f'VINB SIGB 0 SIN(2.24 {-start} 2.5g)')
  if analysis=='ac':
   commands=f"op\nwrdata /work/op.dat v(IN) v(XB.MID) v(PRE) v(OUT) i(VDD)\nac dec 40 1k 10G\nlet ir=real(v(IN))\nlet ii=imag(v(IN))\nlet mr=real(v(XB.MID))\nlet mi=imag(v(XB.MID))\nwrdata /work/{name}.dat ir ii mr mi\n"
  else:
   commands=(f'dc VIN {start} {stop} {step}' if analysis=='dc' else 'tran 1p 100n 0 1p')+f'\nwrdata /work/{name}.dat v(IN) v(XB.MID) v(PRE) v(OUT) i(VDD)\n'
  d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\n'+commands+'.endc\n.end\n'
  p=O/(name+'.spice');p.write_text(d)
  with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
  rows.append(dict(name=name,returncode=q.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 after={n:sha(Path(n)) for n in before};assert before==after
 result=dict(cases=rows,sources_before=before,sources_after=after)
 if analysis=='ac':result['op_sha256']=sha(O/'op.dat')
 (O/'result.json').write_text(json.dumps(result,indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])

if __name__=='__main__':main()
