"""Measure connected static TX regulation separately from startup settling.

Exact extracted pad/buffer/control and external network; only source settings
are held in active DC states. Does not replace retained-state transient tests.
"""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from screen import control,run_spice
from design import PROJECT

def run(work,fixture):
    work.mkdir(parents=True,exist_ok=False)
    original=fixture.read_text().split('.control')[0];results={}
    limit=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['txpad']['parameters']['termination_readiness']['max_reference_error_v']
    for post in (0,1):
        deck=original
        sources={'VDD':'VDD VDD 0 3.3','VTERM_ENABLE':'VTERM_ENABLE REQ_TERM_ENABLE 0 3.3','VEN_MAIN':'VEN_MAIN REQ_EN_MAIN 0 1','VEN_POST':f'VEN_POST REQ_EN_POST 0 {post}','VEN_TMDS':'VEN_TMDS REQ_EN_TMDS 0 0','VEN_DETECT':'VEN_DETECT REQ_EN_DETECT 0 0','VTX_RESET':'VTX_RESET TX_RESET 0 0','VTX_QUALIFIED':'VTX_QUALIFIED TX_QUALIFIED 0 3.3','VBUF_REQUEST':'VBUF_REQUEST BUF_REQUEST VSS 3.3','VDATA':'VDATA DATA 0 0','VPOSTDATA':'VPOSTDATA POSTDATA 0 0'}
        for source,new in sources.items():
            deck,count=re.subn(r'^'+source+r' .*$',new,deck,flags=re.M)
            if count!=1:raise ValueError('Unexpected source '+source)
        name='main_post' if post else 'main'
        deck+=control(work,name,'dc VDATA 0 3.3 3.3','v(TERM_VCM) v(BUF_REF) v(BUF_BIAS) v(xbuf.GAIN) v(xbuf.LOCAL_OUT) v(PAD_P) v(PAD_N) i(VDD)')
        x=run_spice(work,name,deck)
        if len(x)!=2 or not np.isfinite(x).all():raise ValueError('Incomplete DC cases')
        results[name]={'error_limit_v':limit,'max_reference_error_v':float(abs(x[:,1]-x[:,2]).max()),'within_nominal_window':bool(np.all(abs(x[:,1]-x[:,2])<=limit)),'states':[dict(zip(['data_v','vcm_v','reference_v','bias_v','gain_v','local_out_v','pad_p_v','pad_n_v','supply_source_current_a'],map(float,row))) for row in x]}
    r={'status':'connected_static_regulation_not_startup_acceptance','cases':results,'scope':__doc__,'source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),fixture,PROJECT/'spec/analog-architecture.json',work/'main.spice',work/'main_post.spice']}}
    (work/'screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve())
