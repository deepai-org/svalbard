"""Separate sustained current capability from loaded feedback settling.

Uses an exact supplied buffer netlist, retained 10pF load and shared current
limits. Ideal bias/reference isolate buffer dynamics; not pad acceptance.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from design import PROJECT
from screen import run_spice


def run(work, physical, pdk, compensation_scale=1., load_edge_ns=1.):
    work.mkdir(parents=True, exist_ok=False)
    ap=PROJECT/'spec/analog-architecture.json'
    a=json.loads(ap.read_text())
    tx=a['blocks']['wiredtx']['parameters']
    load=max(tx['current_range_a'])*(1+max(tx['postcursor_fraction']))
    reference=a['blocks']['bias']['parameters']['common_mode_v']
    if not 0<load_edge_ns<=50:raise ValueError('Invalid diagnostic current edge')
    model=physical.read_text()
    if not 0<compensation_scale<=4:raise ValueError('Invalid compensation area scale')
    if compensation_scale!=1:
        def resize(m):
            return m[1]+str(float(m[2])*np.sqrt(compensation_scale))+'u'+m[3]+str(float(m[4])*np.sqrt(compensation_scale))+'u'
        model,count=re.subn(r'(cap_mim_2f0_m4m5_noshield c_width=)([0-9.]+)u( c_length=)([0-9.]+)u',resize,model)
        if count!=1:raise ValueError('Expected one compensation MIM')
    (work/'model.spice').write_text(model)
    definition=next(l.split() for l in model.splitlines() if l.startswith('.subckt '))
    if definition[2:]!=['VDD','VSS','REF','BIAS','OUT','ENABLE']:
        raise ValueError('Unexpected buffer ports')
    deck=(f'Buffer sustained load step diagnostic\n.include {pdk}/design.ngspice\n'
          f'.lib {pdk}/sm141064.ngspice typical\n.lib {pdk}/sm141064.ngspice res_typical\n'
          f'.lib {pdk}/sm141064.ngspice mimcap_typical\n.temp 27\n'+model+
          f'\nXBUF VDD 0 REF BIAS OUT ENABLE {definition[1]}\n'
          f'VSUP VDD 0 3.3\nVEN ENABLE 0 3.3\nVREF REF 0 {reference}\nVBIAS BIAS 0 .9\n'
          f'CLOAD OUT 0 10p\nILOAD OUT 0 PWL(0 0 20n 0 {20+load_edge_ns:g}n {load} 150n {load} {150+load_edge_ns:g}n {-load} 280n {-load} {280+load_edge_ns:g}n 0)\n'
          '.control\nset wr_singlescale\nset wr_vecnames\ntran 20p 400n\n'
          f'wrdata {work}/step.dat v(OUT) v(xbuf.GAIN) v(xbuf.LOCAL_OUT) i(VSUP)\nquit\n.endc\n.end\n')
    x=run_spice(work,'step',deck)
    if not np.isfinite(x).all() or x[-1,0]<399.99e-9:
        raise ValueError('Incomplete load step')
    windows={}
    for name,start,stop in [('early_source',25,30),('settled_source',140,149),('settled_sink',270,279),('recovered',390,400)]:
        z=x[(x[:,0]>=start*1e-9)&(x[:,0]<=stop*1e-9)]
        windows[name]={'output_min_v':float(z[:,1].min()),'output_max_v':float(z[:,1].max()),
                       'max_reference_error_v':float(abs(z[:,1]-reference).max()),
                       'gain_range_v':[float(z[:,2].min()),float(z[:,2].max())]}
    report={'status':'standalone_sustained_load_diagnostic','load_a':load,'windows':windows,
            'output_extrema_v':[float(x[:,1].min()),float(x[:,1].max())],
            'compensation_area_scale':compensation_scale,'load_edge_ns':load_edge_ns,
            'scope':'Supplied extracted model; scaled MIM geometry when requested retains original wiring parasitics and is not a new layout. Uses, ideal fixed reference/bias/enable, retained 10pF output load. No pad, power-state or stability-margin acceptance.',
            'source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ap,physical,work/'step.spice']}}
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output-dir','physical','pdk-model-dir']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--compensation-scale',type=float,default=1.)
    p.add_argument('--load-edge-ns',type=float,default=1.)
    a=p.parse_args();run(a.output_dir.resolve(),a.physical.resolve(),a.pdk_model_dir.resolve(),a.compensation_scale,a.load_edge_ns)
