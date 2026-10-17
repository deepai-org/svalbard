"""Measure connected static TX regulation separately from startup settling.

Exact extracted pad/buffer/control and external network; only source settings
are held in active DC states. Does not replace retained-state transient tests.
"""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from screen import control,run_spice
from design import PROJECT
from loading_audit import anchor_floating_conductors

def run(work,fixture):
    work.mkdir(parents=True,exist_ok=False)
    original=fixture.read_text().split('.control')[0];results={}
    provenance={}
    manifest_path=fixture.with_suffix('.json')
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest['fixture_sha256']!=hashlib.sha256(fixture.read_bytes()).hexdigest():
            raise ValueError('Fixture differs from build manifest')
        provenance=dict(manifest['source_sha256'])
        for name,digest in provenance.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Stale fixture component: '+name)
        provenance[str(manifest_path)]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    limit=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['txpad']['parameters']['termination_readiness']['max_reference_error_v']
    original,anchors=anchor_floating_conductors(original,1e12)
    lines=original.splitlines();counts={'MAIN':0,'POST':0}
    for i,line in enumerate(lines):
        fields=line.split()
        if len(fields)<6 or not fields[0].startswith('X') or fields[5]!='nfet_03v3':continue
        for branch in counts:
            if fields[2]!=branch+'_BIAS' or fields[4]!='VSS':continue
            if fields[1].startswith(branch+'_TAIL_') and fields[3]=='VSS':ground=3
            elif fields[3].startswith(branch+'_TAIL_') and fields[1]=='VSS':ground=1
            else:continue
            fields[ground]=branch+'_RETURN';lines[i]=' '.join(fields);counts[branch]+=1
    if not counts['MAIN'] or counts['MAIN']!=counts['POST']:
        raise ValueError('Unexpected MAIN/POST tail graph')
    start=next(i for i,l in enumerate(lines) if l.startswith('.subckt combined_flat '))
    end=next(i for i in range(start+1,len(lines)) if lines[i].startswith('.ends'))
    lines[end:end]=['VSENSE_MAIN MAIN_RETURN VSS 0','VSENSE_POST POST_RETURN VSS 0']
    original='\n'.join(lines)+'\n'
    tx=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['wiredtx']['parameters']
    targets={'MAIN':max(tx['current_range_a']),'POST':max(tx['current_range_a'])*max(tx['postcursor_fraction'])}
    for post in (0,1):
        deck=original
        sources={'VDD':'VDD VDD 0 3.3','VTERM_ENABLE':'VTERM_ENABLE REQ_TERM_ENABLE 0 3.3','VEN_MAIN':'VEN_MAIN REQ_EN_MAIN 0 1','VEN_POST':f'VEN_POST REQ_EN_POST 0 {post}','VEN_TMDS':'VEN_TMDS REQ_EN_TMDS 0 0','VEN_DETECT':'VEN_DETECT REQ_EN_DETECT 0 0','VTX_RESET':'VTX_RESET TX_RESET 0 0','VTX_QUALIFIED':'VTX_QUALIFIED TX_QUALIFIED 0 3.3','VBUF_REQUEST':'VBUF_REQUEST BUF_REQUEST VSS 3.3','VDATA':'VDATA DATA 0 0','VPOSTDATA':'VPOSTDATA POSTDATA 0 0'}
        for source,new in sources.items():
            deck,count=re.subn(r'^'+source+r' .*$',new,deck,flags=re.M)
            if count!=1:raise ValueError('Unexpected source '+source)
        name='main_post' if post else 'main'
        deck+=control(work,name,'dc VDATA 0 3.3 3.3','v(TERM_VCM) v(BUF_REF) v(BUF_BIAS) v(xbuf.GAIN) v(xbuf.LOCAL_OUT) v(PAD_P) v(PAD_N) i(VDD) i(v.xpad.xphysical.vsense_main) i(v.xpad.xphysical.vsense_post)')
        x=run_spice(work,name,deck,reject_transient_op=True)
        if len(x)!=2 or not np.isfinite(x).all():raise ValueError('Incomplete DC cases')
        results[name]={'error_limit_v':limit,'max_reference_error_v':float(abs(x[:,1]-x[:,2]).max()),'within_nominal_window':bool(np.all(abs(x[:,1]-x[:,2])<=limit)),'states':[dict(zip(['data_v','vcm_v','reference_v','bias_v','gain_v','local_out_v','pad_p_v','pad_n_v','supply_source_current_a','main_tail_current_a','post_tail_current_a'],map(float,row))) for row in x]}
        results[name]['tail_targets_a']={**targets,'POST':targets['POST'] if post else 0.0}
        results[name]['tail_current_error_fraction']={'MAIN':(x[:,9]/targets['MAIN']-1).tolist(),'POST':(x[:,10]/targets['POST']-1).tolist() if post else None}
    r={'status':'connected_static_regulation_not_startup_acceptance','cases':results,'scope':__doc__,'numerical_floating_conductor_anchors':anchors,'tail_device_counts':counts,'source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('loading_audit.py'),Path(__file__).with_name('screen.py'),fixture,PROJECT/'spec/analog-architecture.json',work/'main.spice',work/'main_post.spice']}}
    r['source_sha256'].update(provenance)
    (work/'screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

def probe_headroom(work, dc_work):
    """Diagnostic overrides only: fixed POST bias, sampled MAIN bias/reference.

    Keeps the extracted pad/buffer/interlock and external network. A sampled
    minimum is not proof of a globally optimal or impossible circuit.
    """
    work.mkdir(parents=True,exist_ok=False)
    source=dc_work/'main_post.spice'
    previous=json.loads((dc_work/'screen.json').read_text())
    for name,digest in previous['source_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Stale connected DC input: '+name)
    s=source.read_text().split('.control')[0]
    reports=[]
    for ref in (1.65,1.8,2.0,2.2):
        deck,n=re.subn(r'^RREF1 .*$',f'RREF1 VDD BUF_REF {1000*(3.3/ref-1)}',s,flags=re.M);assert n==1
        deck,n=re.subn(r'^BBIAS_MAIN .*$','VMAINBIAS MAIN_BIAS 0 1.5',deck,flags=re.M);assert n==1
        name=str(ref).replace('.','p')
        deck+=control(work,name,'dc VDATA 0 3.3 3.3 VMAINBIAS 1.3 1.8 .025','v(MAIN_BIAS) v(TERM_VCM) v(BUF_REF) v(PAD_P) v(PAD_N) i(v.xpad.xphysical.vsense_main) i(v.xpad.xphysical.vsense_post)')
        x=run_spice(work,name,deck,reject_transient_op=True)
        assert len(x)==42
        pairs=x.reshape(-1,2,8)
        scores=np.max(abs(pairs[:,:,6]/.016-1),axis=1)
        i=int(np.argmin(scores));best=pairs[i]
        reports.append(dict(reference_target_v=ref,main_bias_v=float(best[0,1]),worst_main_error_fraction=float(scores[i]),main_a=best[:,6].tolist(),post_a=best[:,7].tolist(),vcm_v=best[:,2].tolist(),pad_p_v=best[:,4].tolist(),pad_n_v=best[:,5].tolist()))
    report=dict(status='sampled_bias_headroom_diagnostic_not_selected_design',cases=reports,
        scope='Reference-divider and MAIN bias overrides only; POST remains at selected bias. Full extracted connected network retained. No layout change, dynamic qualification or global optimization claim.',
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),source,dc_work/'screen.json']})
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--probe-headroom',action='store_true')
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve())
    if a.probe_headroom:probe_headroom(a.output_dir.resolve()/'headroom-probe',a.output_dir.resolve())
