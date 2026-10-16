"""Separate buffer output-isolation headroom from feedback-loop dynamics."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from design import PROJECT
from screen import run_spice
from termination_switch_candidate import link


def run(work,physical,pdk):
    work.mkdir(parents=True,exist_ok=False)
    source=physical.read_text();cell=next(l.split()[1] for l in source.splitlines() if l.startswith('.subckt '))
    ap=PROJECT/'spec/analog-architecture.json';a=json.loads(ap.read_text());tx=a['blocks']['wiredtx']['parameters'];load=max(tx['current_range_a'])*(1+max(tx['postcursor_fraction']))
    reference=a['blocks']['bias']['parameters']['common_mode_v'];results={}
    source_devices=[l.split() for l in source.splitlines() if l.startswith('X') and l.split()[1:6]==['LOCAL_OUT','GAIN','TOP','VDD','pfet_03v3']]
    if len(source_devices)!=16:raise ValueError('Unexpected source-stage topology')
    def extra_sources(multiplier):
        return ''.join(' '.join([f'XSOURCE_EXTRA_{k}_{i}']+d[1:])+'\n' for k in range(multiplier-1) for i,d in enumerate(source_devices))
    complement='\n'.join(d.spice() for d in link('BUFFER_COMPLEMENT','LOCAL_OUT','OUT','ENABLE'))+'\n'
    for name,extra in [('double_source_complement',extra_sources(2)+complement),('quad_source_complement',extra_sources(4)+complement),('double_source',extra_sources(2)),('quad_source',extra_sources(4)),('original',''),('ideal_bypass','VISOLATION_DIAGNOSTIC LOCAL_OUT OUT 0\n'),('pmos_complement','\n'.join(d.spice() for d in link('BUFFER_COMPLEMENT','LOCAL_OUT','OUT','ENABLE'))+'\n')]:
        model,n=re.subn(r'(?m)^\.ends(?: '+re.escape(cell)+r')?[ \t]*$',extra+'.ends '+cell,source)
        if n!=1:raise ValueError('Ambiguous buffer model')
        (work/(name+'-model.spice')).write_text(model)
        s=(f'Buffer isolation DC diagnostic {name}\n.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice typical\n.lib {pdk}/sm141064.ngspice res_typical\n.lib {pdk}/sm141064.ngspice mimcap_typical\n.temp 27\n'+model+
           f'\nXBUF VDD 0 REF BIAS OUT ENABLE {cell}\nVEN ENABLE 0 3.3\nVSUP VDD 0 3.3\nVREF REF 0 {reference}\nVBIAS BIAS 0 .9\nILOAD OUT 0 0\n.control\nset wr_singlescale\nset wr_vecnames\ndc ILOAD {-load} {load} {load/24}\nwrdata {work}/{name}.dat v(OUT) v(xbuf.LOCAL_OUT) v(xbuf.GAIN) i(VSUP)\nquit\n.endc\n.end\n')
        x=run_spice(work,name,s)
        if len(x)!=49 or not np.isfinite(x).all():raise ValueError('Incomplete DC sweep')
        results[name]={'load_range_a':[float(x[0,0]),float(x[-1,0])], 'source_endpoint':{'output_v':float(x[-1,1]),'local_output_v':float(x[-1,2]),'gain_v':float(x[-1,3]),'supply_draw_a':float(-x[-1,4])},'sink_endpoint':{'output_v':float(x[0,1]),'local_output_v':float(x[0,2]),'gain_v':float(x[0,3]),'supply_draw_a':float(-x[0,4])},'max_reference_error_v':float(abs(x[:,1]-reference).max())}
    report={'status':'buffer_isolation_DC_diagnostic_not_lifecycle_acceptance','cases':results,'scope':'Extracted compensated core and fixed DC sources. Source-size hypotheses replicate real MOS fingers including junctions but omit new layout parasitics. Ideal bypass is a diagnostic only. PMOS complement is a new transistor/passive hypothesis with junction loading, no new wiring/well extraction; disable, power-off, dynamics and layout remain to test.','source_sha256':{str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),Path(__file__).with_name('termination_switch_candidate.py'),physical,ap]}}
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output-dir','physical','pdk-model-dir']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.physical.resolve(),a.pdk_model_dir.resolve())
