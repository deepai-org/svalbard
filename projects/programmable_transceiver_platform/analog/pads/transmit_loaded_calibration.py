"""Calibrate MAIN/POST together with the actual internal-termination DC load.

Zero-volt branch sensors expose tail currents without changing their voltages.
This checks reachability at one operating point, not current-source compliance
or transient performance across other loads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from design import PROJECT
from screen import run_spice


def run(work,fixture):
    work.mkdir(parents=True,exist_ok=False)
    ap=PROJECT/'spec/analog-architecture.json';arch=json.loads(ap.read_text());tx=arch['blocks']['wiredtx']['parameters']
    targets={'MAIN':max(tx['current_range_a']),'POST':max(tx['current_range_a'])*max(tx['postcursor_fraction'])}
    s=fixture.read_text().split('.control')[0]
    old='RLP PULL BOARD_P 50\nRLN PULL BOARD_N 50\n';assert s.count(old)==1
    s=s.replace(old,f"RDIFF BOARD_P BOARD_N {arch['blocks']['termination']['parameters']['differential_ohm']}\n")
    lines=s.splitlines();counts={'MAIN':0,'POST':0}
    for i,line in enumerate(lines):
        f=line.split()
        if len(f)<6 or not f[0].startswith('X') or f[5]!='nfet_03v3':continue
        for branch in counts:
            if f[1].startswith(branch+'_TAIL_') and f[2:5]==[branch+'_BIAS','VSS','VSS']:
                f[3]=branch+'_RETURN';lines[i]=' '.join(f);counts[branch]+=1
    if counts['MAIN']<16 or counts['MAIN']!=counts['POST'] or counts['MAIN']%16:raise ValueError('Unexpected branch graph')
    start=next(i for i,l in enumerate(lines) if l.startswith('.subckt combined_flat '));end=next(i for i in range(start+1,len(lines)) if lines[i].startswith('.ends'))
    lines[end:end]=['VSENSE_MAIN MAIN_RETURN VSS 0','VSENSE_POST POST_RETURN VSS 0'];s='\n'.join(lines)+'\n'
    values={'VDD':3.3,'VTERM_VCM':arch['blocks']['bias']['parameters']['common_mode_v'],'VTERM_ENABLE':3.3,'VDATA':3.3,'VPOSTDATA':0.,'VEN_TMDS':0.,'VEN_MAIN':1.,'VEN_POST':1.,'VEN_DETECT':0.,'VTX_RESET':0.}
    for key,value in values.items():
        line=next(line for line in s.splitlines() if line.startswith(key+' '));s=s.replace(line,' '.join(line.split()[:3])+f' {value:g}')
    for branch in targets:
        s,count=re.subn(r'(?m)^BBIAS_'+branch+r' .*$',f'VBIAS_{branch} {branch}_BIAS 0 BIAS_{branch}_VALUE',s);assert count==1
    biases={'MAIN':1.61,'POST':1.3};history=[]
    for iteration in range(3):
        for branch in ['MAIN','POST']:
            name=f'{iteration}_{branch}';deck=s
            for b,v in biases.items():deck=deck.replace('BIAS_'+b+'_VALUE',str(v))
            deck+=f'.control\nset wr_singlescale\nset wr_vecnames\ndc VBIAS_{branch} .8 3.3 .005\nwrdata {work}/{name}.dat i(v.xpad.xphysical.vsense_main) i(v.xpad.xphysical.vsense_post) v(PAD_P) v(PAD_N)\nquit\n.endc\n.end\n'
            x=run_spice(work,name,deck)
            if len(x)!=501 or not np.isfinite(x).all():raise ValueError('Incomplete bias sweep')
            col=1 if branch=='MAIN' else 2;idx=int(np.argmin(abs(x[:,col]-targets[branch])))
            biases[branch]=float(x[idx,0]);history.append(dict(iteration=iteration,adjusted=branch,bias_v=biases[branch],main_a=float(x[idx,1]),post_a=float(x[idx,2]),pad_p_v=float(x[idx,3]),pad_n_v=float(x[idx,4])))
    last=history[-1]
    report=dict(status='joint_loaded_bias_calibration_not_compliance_or_transient_acceptance',tail_device_counts=counts,biases_v=biases,targets_a=targets,history=history,
        both_currents_within_3_percent=all(abs(last[b.lower()+'_a']-t)<=.03*t for b,t in targets.items()),
        scope='Complete existing pad and protection, ideal1.65V common-mode source, actual enabled source switches/resistors and shared differential load; complementary states and lifecycle remain to test with these new biases.',
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),fixture,ap]})
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output-dir','fixture']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve())
