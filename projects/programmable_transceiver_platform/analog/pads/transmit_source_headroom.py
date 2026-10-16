"""DC source-termination headroom with the complete retained TX pad circuit.

Ideal TERM_VCM deliberately separates pad compliance from buffer capability.
Every case retains the same shared differential load, bonds and protection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from design import PROJECT
from screen import run_spice


def run(work,fixture,compliance):
    work.mkdir(parents=True,exist_ok=False)
    architecture=PROJECT/'spec/analog-architecture.json';a=json.loads(architecture.read_text())
    calibration=json.loads(compliance.read_text())['cases']
    source=fixture.read_text().split('.control')[0]
    old='RLP PULL BOARD_P 50\nRLN PULL BOARD_N 50\n'
    if source.count(old)!=1:raise ValueError('Unrecognized load fixture')
    source=source.replace(old,f"RDIFF BOARD_P BOARD_N {a['blocks']['termination']['parameters']['differential_ohm']}\n")
    base={ 'VDD':3.3,'VTERM_ENABLE':3.3,'VDATA':3.3,'VPOSTDATA':0.,'VEN_TMDS':0.,'VEN_MAIN':0.,'VEN_POST':0.,'VEN_DETECT':0.,'VTX_RESET':0.}
    results={};currents={}
    for name,cal in [('off',None),('main_nominal',calibration['main_nominal']),('main_post_maximum_aligned',calibration['main_post_maximum_aligned'])]:
        s=source;values=dict(base)
        if cal:
            for branch in cal['programmed']:
                values['VEN_'+branch]=1.
                bias=cal['programmed'][branch]['bias_v']
                s,count=re.subn(r'(?m)^BBIAS_'+branch+r' .*$',f'BBIAS_{branch} {branch}_BIAS 0 V={bias}*V(EN_{branch})',s)
                if count!=1:raise ValueError('Missing branch bias')
        for key,value in values.items():
            line=next(line for line in s.splitlines() if line.startswith(key+' '));fields=line.split()
            s=s.replace(line,' '.join(fields[:3])+f' {value:g}')
        s+=f'.control\nset wr_singlescale\nset wr_vecnames\ndc VTERM_VCM 1.2 2.8 .05\nwrdata {work}/{name}.dat v(PAD_P) v(PAD_N) i(VTERM_VCM)\nquit\n.endc\n.end\n'
        x=run_spice(work,name,s)
        if len(x)!=33 or not np.isfinite(x).all():raise ValueError('Incomplete DC sweep')
        currents[name]=-x[:,3]
        if name=='off':continue
        incremental=currents[name]-currents['off'];target=cal['total_target_current_a'];passed=incremental>=.95*target
        nominal=a['blocks']['bias']['parameters']['common_mode_v']
        results[name]=dict(target_a=target,nominal_vcm_v=nominal,
            nominal_incremental_sink_a=float(np.interp(nominal,x[:,0],incremental)),
            nominal_pad_p_v=float(np.interp(nominal,x[:,0],x[:,1])),
            nominal_pad_n_v=float(np.interp(nominal,x[:,0],x[:,2])),
            minimum_sampled_vcm_for_95_percent_current_v=float(x[passed,0][0]) if passed.any() else None,
            vcm_v=x[:,0].tolist(),incremental_sink_a=incremental.tolist())
    report=dict(status='source_termination_DC_headroom_diagnostic',cases=results,
        scope='Ideal common-mode source; drive current inferred by subtracting identical enabled-termination, driver-off bias current. All devices, protection, bonds and shared differential load retained. No physical-buffer, timing, variation or protocol acceptance.',
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),fixture,compliance,architecture]})
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:{n:v for n,v in row.items() if n not in ('vcm_v','incremental_sink_a')} for k,row in results.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output-dir','fixture','compliance']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.compliance.resolve())
