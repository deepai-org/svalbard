"""Two feedback-resistor values at two source common modes; no stability claim."""
import hashlib,json,re,subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spice_sources import collect_sources, __file__ as source_scanner_file
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(*, programmable=False, probe=False, large_input=False, entrypoint=None):
 base='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/bb_filter_section.spice
.temp 27
VDD VDD 0 3.3
VB BIAS 0 2.25
XDUT IP IN OP ON BIAS VDD 0 pt_bb_filter RFB=20k C=20p
'''
 if programmable:
  base=base.replace('/screen/bb_filter_section.spice','/screen/bb_filter_programmable.spice').replace('0 pt_bb_filter RFB=20k C=20p','0 SEL SELB pt_bb_filter_programmable C=20p')
 common_modes=(1.177,) if programmable or large_input else (.9,1.177)
 feedback_values=(20000,) if large_input else (20000,40000)
 paths=set()
 paths.add(Path(source_scanner_file))
 collect_sources(base, O, paths);before={str(p):sha(p) for p in sorted(paths)};before[str(Path(__file__))]=sha(Path(__file__));before[str(Path(entrypoint or __file__))]=sha(Path(entrypoint or __file__))
 probes=[f'v({n})' for n in ('IP','IN','XDUT.GP','XDUT.GN','XDUT.MP','XDUT.MN','OP','ON','XDUT.T1','XDUT.T2')]+['i(VIP)','i(VIN)','i(VDD)']+[f'@m.xdut.{stage}.{dev}.m0[{p}]' for stage in ('xa','xb') for dev in ('xip','xin','xtail') for p in ('vds','vdsat')]
 if probe:probes += ['v(XDUT.FBP)','v(XDUT.FBN)']
 (O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,common_mode_v=list(common_modes),source_ohm_per_leg=[1000],feedback_ohm=list(feedback_values),op_probes=probes,scope='TT27C3.3V external bias2.25V; original RFB20k/C20p; source/load scenarios not fab bounds'),indent=2)+'\n')
 rows=[]
 for cm in common_modes:
  for feedback in feedback_values:
   rs=1000
   name=f'cm{cm:g}_fb{feedback}'
   stim=f'VIP {"SP" if rs else "IP"} 0 DC {cm} AC .5\nVIN {"SN" if rs else "IN"} 0 DC {cm} AC .5 180\n'
   if rs:stim+=f'RP SP IP {rs}\nRN SN IN {rs}\n'
   if programmable:
    stim+=f'VSEL SEL 0 {3.3 if feedback==20000 else 0}\nVSELB SELB 0 {0 if feedback==20000 else 3.3}\n'
   d='* Actual filter interface screen\n'+base.replace('RFB=20k',f'RFB={feedback}')+stim+'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\n'+f'wrdata /work/{name}-op.dat '+' '.join(probes)+'\nac lin 100 1meg 100meg\nlet gr=real(v(OP)-v(ON))\nlet gi=imag(v(OP)-v(ON))\nlet ir=real(v(IP)-v(IN))\nlet ii=imag(v(IP)-v(IN))\n'+f'wrdata /work/{name}.dat gr gi ir ii\n.endc\n.end\n'
   if large_input:
    gain=Path('/screen/bb_pmos_gain.spice').read_text()
    new=gain.replace('pt_bb_pmos_gain','pt_bb_pmos_gain_large_input')
    for line in gain.splitlines():
     if line.startswith(('XIP ','XIN ')):new=new.replace(line,line.replace('w=4u l=0.28u','w=8u l=0.56u'))
    cell=Path('/screen/bb_filter_section.spice').read_text().replace('XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain','XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain_large_input')
    d=d.replace('.include /screen/bb_filter_section.spice',new+cell)
   p=O/(name+'.spice');p.write_text(d);h=sha(p)
   with (O/(name+'.log')).open('w') as f:s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=60)
   assert sha(p)==h
   rows.append(dict(name=name,common_mode_v=cm,source_ohm_per_leg=rs,feedback_ohm=feedback,returncode=s.returncode,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat','-op.dat') if (O/(name+e)).exists()}))
 assert before=={name:sha(Path(name)) for name in before}
 (O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=before),indent=2)+'\n');print([(c['name'],c['returncode']) for c in rows])

if __name__ == '__main__':
 main()
