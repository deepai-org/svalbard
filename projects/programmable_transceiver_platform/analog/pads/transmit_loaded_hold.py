"""Extend loaded TX plateaus without restarting the circuit or external network.

A sequencing diagnostic, not permission to relax a protocol response deadline.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from screen import run_spice,control


def run(work,fixture):
    work.mkdir(parents=True,exist_ok=False)
    original=fixture.read_text();deck=original.split('.control')[0]
    for token in ['100n 0 100.1n 1 116n 1','108n 0 108.1n 1 112n 1','XBUF ']:
        if token not in deck:raise ValueError('Unexpected lifecycle schedule or buffer')
    def shift(m):
        fields=m[1].split()
        if len(fields)%2:raise ValueError('Malformed PWL')
        for i in range(0,len(fields),2):
            if not re.fullmatch(r'[0-9.]+n',fields[i]):raise ValueError('Expected explicit ns events')
            t=float(fields[i][:-1]);fields[i]=f'{t+(40 if t>=108 else 0)+(40 if t>=112 else 0):g}n'
        return 'PWL('+' '.join(fields)+')'
    deck=re.sub(r'PWL\(([^)]*)\)',shift,deck,flags=re.I)
    deck+=control(work,'hold','tran 5p 220n','v(PAD_P) v(PAD_N) v(VDD) i(VDD) v(TERM_VCM) v(BUF_REF)')
    x=run_spice(work,'hold',deck)
    if not np.isfinite(x).all() or x[-1,0]<219.99e-9:raise ValueError('Incomplete sustained lifecycle')
    windows={}
    for name,start,stop in [('original_main_early',104,107),('main_settled',140,147),('post_early',149,151),('post_settled',184,191),('reconfiguration',196,198),('recovered',214,219)]:
        y=x[(x[:,0]>=start*1e-9)&(x[:,0]<=stop*1e-9)]
        windows[name]={'start_ns':start,'stop_ns':stop,'vcm_min_v':float(y[:,5].min()),'vcm_max_v':float(y[:,5].max()),'max_reference_error_v':float(abs(y[:,5]-y[:,6]).max()),'differential_pad_min_v':float((y[:,1]-y[:,2]).min()),'differential_pad_max_v':float((y[:,1]-y[:,2]).max()),'peak_supply_draw_a':float(max(0,-y[:,4].min()))}
    report={'status':'sustained_loaded_TX_diagnostic_not_deadline_acceptance','transient_complete':True,'windows':windows,'scope':'Exact connected extracted TX/buffer and external differential load retained. Only PWL events at/after108ns and112ns shifted40ns each. Data clocks/edges, biases, compensation and loading unchanged. Original main early failure remains measured. No new ready detector, muted startup, physical sequencer or protocol deadline qualification.','source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),fixture,work/'hold.spice']}}
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve())
