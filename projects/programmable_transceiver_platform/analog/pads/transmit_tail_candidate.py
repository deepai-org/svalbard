"""Lower-overdrive MAIN/POST tail candidate, retaining the full extracted pad.

Replicated tail fingers need new placement/routes before physical adoption.
Calibrate against the original external-pullup load, then use the independent
source-termination headroom bench without retuning to its load.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from design import PROJECT
from screen import run_spice


def run(work,fixture,multiplier):
    if type(multiplier) is not int or multiplier<2:raise ValueError('Multiplier must be integer >=2')
    work.mkdir(parents=True,exist_ok=False)
    source=fixture.read_text();lines=source.splitlines();added=[];count={'MAIN':0,'POST':0}
    for line in lines:
        f=line.split()
        if len(f)<6 or not f[0].startswith('X') or f[5]!='nfet_03v3':continue
        for branch in count:
            if f[1].startswith(branch+'_TAIL_') and f[2:5]==[branch+'_BIAS','VSS','VSS']:
                count[branch]+=1
                for i in range(multiplier-1):added.append(' '.join([f'XBOOST_{branch}_{count[branch]}_{i}']+f[1:]))
    if count!={'MAIN':16,'POST':16}:raise ValueError('Unexpected tail topology')
    start=next(i for i,line in enumerate(lines) if line.startswith('.subckt combined_flat '))
    end=next(i for i in range(start+1,len(lines)) if lines[i].startswith('.ends'))
    lines[end:end]=added;candidate=work/'candidate.spice';candidate.write_text('\n'.join(lines)+'\n')
    source=candidate.read_text().split('.control')[0]
    a=json.loads((PROJECT/'spec/analog-architecture.json').read_text());tx=a['blocks']['wiredtx']['parameters']
    main_max=max(tx['current_range_a']);post_max=main_max*max(tx['postcursor_fraction'])
    calibrated={}
    for branch in ['MAIN','POST']:
        s=source;values={'VDD':3.3,'VTERM_ENABLE':0.,'VDATA':3.3,'VPOSTDATA':0.,'VEN_TMDS':0.,'VEN_MAIN':float(branch=='MAIN'),'VEN_POST':float(branch=='POST'),'VEN_DETECT':0.,'VTX_RESET':0.}
        for key,value in values.items():
            line=next(line for line in s.splitlines() if line.startswith(key+' '));s=s.replace(line,' '.join(line.split()[:3])+f' {value:g}')
        s,n=re.subn(r'(?m)^BBIAS_'+branch+r' .*$',f'VBIAS {branch}_BIAS 0 0',s);assert n==1
        s+=f'.control\nset wr_singlescale\nset wr_vecnames\ndc VBIAS .6 1.8 .005\nwrdata {work}/{branch}.dat i(VPULL)\nquit\n.endc\n.end\n'
        x=run_spice(work,branch,s);currents=-x[:,1]
        if len(x)!=241 or not np.isfinite(x).all():raise ValueError('Incomplete calibration')
        targets=[.008,main_max] if branch=='MAIN' else [post_max]
        calibrated[branch]={}
        for target in targets:
            i=int(np.argmin(abs(currents-target)));calibrated[branch][target]=dict(target_a=target,bias_v=float(x[i,0]),calibration_current_a=float(currents[i]))
            if abs(currents[i]-target)>.03*target:raise ValueError('Calibration target not reached')
    result={'status':'replicated_tail_candidate_calibrated_not_laid_out','multiplier':multiplier,'added_device_count':len(added),
        'cases':{'main_nominal':{'programmed':{'MAIN':calibrated['MAIN'][.008]},'total_target_current_a':.008},'main_post_maximum_aligned':{'programmed':{'MAIN':calibrated['MAIN'][main_max],'POST':calibrated['POST'][post_max]},'total_target_current_a':main_max+post_max}},
        'scope':'MAIN/POST tails replicated; shared pad cascodes, steering devices and original extraction retained. New tail device junctions included, new placement/routes absent. Calibration uses external pullups, not internal termination.',
        'source_sha256':{str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),fixture,candidate,PROJECT/'spec/analog-architecture.json']}}
    (work/'calibration.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--multiplier',type=int,default=4)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.multiplier)
