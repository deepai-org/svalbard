"""Reproduce diode sidewall charge discontinuity; never a chip acceptance test."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np


def check(work,pdk,before,after):
    work.mkdir(parents=True,exist_ok=False);results={}
    for name,binary in [('before',before),('after',after)]:
        results[name]={}
        for kind,dc in [('transient',0),('ac_low',.2),('ac_high',.4),('dc',0)]:
            stem=name+'_'+kind
            prefix=(f'Diode sidewall boundary regression\n.include {pdk}/design.ngspice\n'
                    f'.lib {pdk}/sm141064.ngspice diode_typical\n.temp 25\n')
            if kind=='transient':
                source='VDR DRIVE 0 PWL(0 0 1u 0 10u 1)\nRS DRIVE PAD 1k\nCP PAD 0 1p\n'
                analysis='tran 1n 10u';vectors='v(PAD) i(VDR)'
            else:
                source=f'VDR PAD 0 DC {dc} AC 1\n'
                analysis='dc VDR 0 1 .01' if kind=='dc' else 'ac lin 1 1G 1G'
                vectors='i(VDR)' if kind=='dc' else 'real(i(VDR)) imag(i(VDR))'
            deck=prefix+source+'D1 PAD 0 diode_pd2nw_06v0 area=22.5e-12 pj=51.8e-6\n'
            deck+=f'.control\nset numdgt=15\nset wr_vecnames\nset wr_singlescale\n{analysis}\nwrdata {work}/{stem}.dat {vectors}\nquit\n.endc\n.end\n'
            (work/(stem+'.spice')).write_text(deck)
            run=subprocess.run([str(binary),'-b',str(work/(stem+'.spice'))],capture_output=True,text=True,timeout=30)
            (work/(stem+'.log')).write_text(run.stdout+run.stderr)
            data=np.atleast_2d(np.loadtxt(work/(stem+'.dat'),skiprows=1))
            if not np.isfinite(data).all():raise ValueError('Nonfinite diode regression')
            results[name][kind]=dict(returncode=run.returncode,last_independent_value=float(data[-1,0]),rows=len(data))
            if kind!='transient':results[name][kind]['data']=data.tolist()
    unchanged={}
    for case in ('dc','ac_low','ac_high'):
        a=np.array(results['before'][case]['data']);b=np.array(results['after'][case]['data'])
        unchanged[case]=bool(a.shape==b.shape and np.allclose(a,b,rtol=1e-10,atol=1e-18))
    passed=(results['before']['transient']['last_independent_value']<10e-6 and
            results['after']['transient']['last_independent_value']>=10e-6*(1-1e-9) and all(unchanged.values()))
    report=dict(status='simulator_regression_not_chip_evidence',regression_pass=passed,
        measurements=results,dc_and_ac_unchanged=unchanged,
        conclusion='Sidewall forward continuation must use its own potential/grading/transition parameters, not the area-junction F1 constant. No PDK device parameter is changed.',
        sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__).resolve(),before,after,pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice',
             Path(__file__).with_name('ngspice-diode-charge.patch').resolve())})
    (work/'diode-model-check.json').write_text(json.dumps(report,indent=2)+'\n')
    if not passed:raise RuntimeError('Diode correction regression failed')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('output-dir','pdk-model-dir','before','after'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();check(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.before.resolve(),a.after.resolve())
