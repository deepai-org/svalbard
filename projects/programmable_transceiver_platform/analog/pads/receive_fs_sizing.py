"""FS high-side sizing tradeoff on the complete protected RX extracted base.

Changes device geometry only; original routing/well parasitics are retained.
This is a pre-layout hypothesis, not a newly extracted implementation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from screen import run_spice,control
from loading_audit import anchor_floating_conductors
from design import PROJECT


def resize(source,width,resistor_width,resistor_length):
    lines=[];mos_count=0;res_count=0
    for line in source.splitlines():
        f=line.split()
        if len(f)>5 and f[0].startswith('X') and f[5]=='pfet_03v3' and f[2] in ('FS_P_GATE','FS_N_GATE') and f[1] in ('VDD','FS_P_OUT','FS_N_OUT'):
            if 'w=20u' not in f:raise ValueError('Unexpected initial FS width')
            replacements={'w':f'{width}u','ad':f'{.44*width}p','as':f'{.44*width}p','pd':f'{2*width+.88}u','ps':f'{2*width+.88}u'}
            f=[(k+'='+replacements[k]) if '=' in t and (k:=t.split('=')[0]) in replacements else t for t in f]
            line=' '.join(f);mos_count+=1
        elif len(f)>4 and f[0].startswith('X') and f[4]=='ppolyf_s' and any(t in ('FS_P_OUT','FS_N_OUT') for t in f[1:3]):
            line=re.sub(r'r_width=\S+',f'r_width={resistor_width}u',line)
            line=re.sub(r'r_length=\S+',f'r_length={resistor_length}u',line);res_count+=1
        lines.append(line)
    if (mos_count,res_count)!=(96,2):raise ValueError('Unexpected FS branch device count')
    return '\n'.join(lines)+'\n'


def run(work,physical,fixtures):
    work.mkdir(parents=True,exist_ok=False)
    source=physical.read_text();results={}
    for name,width,rw,rl in [('baseline',20,1,2.16),('small_short',14,2,2.16),('small_medium',14,2,3.5),('small_long',14,2,5.)]:
        model=resize(source,width,rw,rl)
        (work/(name+'-model.spice')).write_text(model)
        simulation,anchors=anchor_floating_conductors(model,1e12)
        row={'width_um':width,'series_resistor_geometry_um':[rw,rl],'numerical_anchors':anchors}
        for test in ('fs_high','loading_serial_bypass'):
            original=(fixtures/(test+'.spice')).read_text()
            if original.count(source)!=1:raise ValueError('Fixture does not contain exact source model')
            deck=original.split('.control')[0].replace(source,simulation)
            if test=='fs_high':
                deck+=control(work,name+'_'+test,'dc VPADP 0 3.6 .02','i(VPADP) v(RX_P) i(VDD)')
                x=run_spice(work,name+'_'+test,deck);i=int(np.argmin(abs(x[:,0]-3.2)))
                row['fs_high_ohm_at_3p2v']=float(-(x[i+1,0]-x[i-1,0])/(x[i+1,1]-x[i-1,1]))
            else:
                deck+=control(work,name+'_'+test,'ac lin 1 1G 1G','real(i(VPADP)) imag(i(VPADP)) real(i(VPADN)) imag(i(VPADN))')
                x=np.atleast_2d(run_spice(work,name+'_'+test,deck))[0]
                row['odd_capacitance_f_per_leg']=[float(-x[2]/(np.pi*1e9)),float(x[4]/(np.pi*1e9))]
        results[name]=row
    ap=PROJECT/'spec/analog-architecture.json';a=json.loads(ap.read_text())
    report={'status':'FS_sizing_DC_AC_hypothesis_not_layout_or_lifecycle_acceptance','cases':results,'shared_output_resistance_target_ohm':a['blocks']['usbfs']['parameters']['effective_output_r_ohm'],'scope':'Retained complete primary protection and inactive branches. Source MOS finger junction areas/perimeters scale with width; original extracted routing and well parasitics remain. Resistor geometry changes need new layout. Nominal DC at3.2V and AC at1GHz only. Numerical capacitor-only-node DC anchor reported.','source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),physical,ap,fixtures/'fs_high.spice',fixtures/'loading_serial_bypass.spice']}}
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','physical','fixture-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.physical.resolve(),a.fixture_dir.resolve())
