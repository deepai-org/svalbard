"""Connect extracted static TX interlock to retained full pad/buffer lifecycle.

Termination is driven directly. Serializer and analog-bias boundary translators
remain ideal and therefore do not qualify physical fanout on those outputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from screen import control, run_spice
from transmit_control_circuit import build, REQUESTS
from design import PROJECT


def run(work, fixture, physical):
    work.mkdir(parents=True, exist_ok=False)
    deck = fixture.read_text().split('.control')[0]
    model = physical.read_text()
    definition = next(l.split() for l in model.splitlines() if l.startswith('.subckt '))
    if definition[2:] != build().ports:
        raise ValueError('Extracted control port order mismatch')
    lines = deck.splitlines()
    expected = {'BTX_CONFLICT', 'BTX_VALID', 'BTX_TERM'} | {'BTX_'+n for n in REQUESTS if n != 'TERM'}
    found = {l.split()[0] for l in lines if l.startswith('BTX_')}
    if found != expected:
        raise ValueError('Unexpected behavioral interlock topology')
    deck = '\n'.join(l for l in lines if l.split() and l.split()[0] not in expected)+'\n'+model+'\n'
    low, high = json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['monitor']['parameters']['supply_window_v']
    deck += f'BCTL_OK CTL_OK VSS V=V(VDD)*(V(VDD)>={low})*(V(VDD)<={high})\n'
    for n in REQUESTS:
        if n != 'TERM':
            deck += f'BCTL_REQ_{n} CTL_REQ_{n} VSS V=V(VDD)*V(REQ_EN_{n})\n'
            deck += f'BCTL_BOUNDARY_{n} EN_{n} VSS V=V(CTL_EN_{n})/3.3\n'
    deck += 'BCTL_VALID_BOUNDARY TX_VALID VSS V=V(CTL_VALID)/3.3\n'
    deck += ('XCTL VDD VSS CTL_REQ_MAIN CTL_REQ_POST CTL_REQ_TMDS CTL_REQ_DETECT REQ_TERM_ENABLE '
             'TX_RESET TX_QUALIFIED CTL_OK CTL_CONFLICT CTL_VALID '
             'CTL_EN_MAIN CTL_EN_POST CTL_EN_TMDS CTL_EN_DETECT TERM_ENABLE '+definition[1]+'\n')
    vectors = 'v(TERM_VCM) i(VDD) v(CTL_VALID) v(TERM_ENABLE) '+ ' '.join('v(CTL_EN_'+n+')' for n in REQUESTS if n != 'TERM')
    deck += control(work, 'connected', 'tran 5p 220n', vectors)
    x = run_spice(work, 'connected', deck)
    if not np.isfinite(x).all() or x[-1,0] < 219.99e-9:
        raise ValueError('Incomplete connected transient')
    windows = {}
    for name,start,end in [('reset',27,30),('unpowered',36,43),('main_settled',140,147),('post_settled',184,191),('release',196,199),('disabled',214,219)]:
        z = x[(x[:,0]>=start*1e-9)&(x[:,0]<=end*1e-9)]
        windows[name] = {'vcm_min_v':float(z[:,1].min()),'vcm_max_v':float(z[:,1].max()),'peak_supply_draw_a':float(-z[:,2].min()),'termination_enable_max_v':float(z[:,4].max())}
    r = {'status':'connected_extracted_control_diagnostic','windows':windows,
         'scope':'Same extracted pad/buffer and external network; static interlock replaced with extracted88MOS circuit. Direct TERM_ENABLE loading. Other outputs retain ideal serializer/bias boundary translation and do not exercise actual fanout. Supply monitor and qualification remain behavioral; no implemented blanking or readiness sequencer. Not adoption or protocol acceptance.',
         'source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),fixture,physical,PROJECT/'spec/analog-architecture.json',work/'connected.spice']}}
    (work/'screen.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output-dir','fixture','physical'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.physical.resolve())
