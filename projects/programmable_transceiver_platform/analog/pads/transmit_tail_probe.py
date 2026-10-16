"""Diagnostic tail-device multiplicity sweep on a verified connected TX DC fixture.

Device multiplicity scales intrinsic devices, not extracted routing. No changed
layout, AC loading or transient qualification is implied.
"""
from pathlib import Path
import argparse,hashlib,json,re,numpy as np
from design import PROJECT
from screen import control,run_spice
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',type=Path,required=True)
parser.add_argument('--dc-screen-dir',type=Path,required=True)
args=parser.parse_args();work=args.output_dir.resolve();work.mkdir(parents=True,exist_ok=False)
dc=args.dc_screen_dir.resolve();report=json.loads((dc/'screen.json').read_text())
for name,digest in report['source_sha256'].items():
    if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Stale source '+name)
source=(dc/'main_post.spice').read_text().split('.control')[0]
arch=PROJECT/'spec/analog-architecture.json'
tx=json.loads(arch.read_text())['blocks']['wiredtx']['parameters']
targets=np.array([max(tx['current_range_a']),max(tx['current_range_a'])*max(tx['postcursor_fraction'])])
results=[]
for multiplier in (8,):
    lines=source.splitlines();count=0
    for i,line in enumerate(lines):
        f=line.split()
        if len(f)>6 and f[0].startswith('X') and f[5]=='nfet_03v3' and f[1].startswith(('MAIN_TAIL_','POST_TAIL_')) and f[2] in ('MAIN_BIAS','POST_BIAS'):
            assert not any(v.startswith('m=') for v in f)
            lines[i]=line+f' m={multiplier}';count+=1
    assert count==64
    base='\n'.join(lines)+'\n'
    for branch in ('MAIN','POST'):
        base,n=re.subn(r'^BBIAS_'+branch+r' .*$',f'V{branch}BIAS {branch}_BIAS 0 1',base,flags=re.M);assert n==1
    curves=[]
    for data in (0,3.3):
        deck,n=re.subn(r'^VDATA .*$',f'VDATA DATA 0 {data}',base,flags=re.M);assert n==1
        label=f'm{multiplier}_d{int(data)}'
        deck+=control(work,label,'dc VMAINBIAS .868 .878 .001 VPOSTBIAS .798 .808 .001','v(MAIN_BIAS) v(POST_BIAS) i(v.xpad.xphysical.vsense_main) i(v.xpad.xphysical.vsense_post) v(TERM_VCM)')
        x=run_spice(work,label,deck,reject_transient_op=True);assert len(x)==121
        curves.append(x)
    a,b=curves;score=np.max(abs(np.stack([a[:,3:5],b[:,3:5]])/targets-1),axis=(0,2));idx=int(np.argmin(score))
    results.append(dict(multiplier=multiplier,main_bias_v=float(a[idx,1]),post_bias_v=float(a[idx,2]),worst_error_fraction=float(score[idx]),states=[r[idx].tolist() for r in curves]))
result=dict(status='tail_multiplicity_diagnostic_not_selected_layout',cases=results,
    targets_a=targets.tolist(),scope=__doc__,
    columns=['sweep_main_bias_v','main_bias_v','post_bias_v','main_a','post_a','vcm_v'],
    source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),dc/'main_post.spice',dc/'screen.json',arch]})
(work/'screen.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
