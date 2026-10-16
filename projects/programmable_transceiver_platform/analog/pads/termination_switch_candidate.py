"""Attach a floating-well PMOS complement to the physical TX termination.

Uses explicit restoration and a supply-qualified existing enable. This is a
circuit hypothesis until combined extraction and retained-state tests agree.
"""
import argparse
import hashlib
import json
from pathlib import Path
from circuits import Mos,Resistor


def link(name,a,b,enable,units=8):
    well=name+'_WELL';gate=name+'_GATE';d=[]
    for i in range(units):
        for tag,node in [('A',a),('B',b)]:
            d.append(Mos(f'{name}_{tag}_{i}',(node,gate,well,well),'pfet_03v3',20.,.28))
    d += [Mos(name+'_ENABLE',(gate,enable,'VSS','VSS'),'nfet_06v0',4.,.7),
          Mos(name+'_RESTORE',(gate,enable,well,well),'pfet_03v3',4.,.28)]
    previous=well
    for i in range(8):
        following=gate if i==7 else f'{name}_BLEED_{i}'
        d.append(Resistor(f'{name}_BLEED_{i}',(previous,following,'VSS'),'ppolyf_u_1k',1.,12.5));previous=following
    return d


def attach(fixture,output):
    s=fixture.read_text();lines=s.splitlines();start=next(i for i,line in enumerate(lines) if line.startswith('.subckt combined_flat '))
    end=next(i for i in range(start+1,len(lines)) if lines[i].startswith('.ends'))
    body='\n'.join(lines[start:end]);devices=[]
    for leg in ['P','N']:
        if f'TERM_{leg}_R' not in body or 'TERM_ENABLE_LOCAL' not in body:raise ValueError('Missing termination node')
        devices += link('TERM_COMPLEMENT_'+leg,f'TERM_{leg}_R','TERM_VCM','TERM_ENABLE_LOCAL')
    lines[end:end]=[d.spice() for d in devices]
    output.write_text('\n'.join(lines)+'\n')
    report={'status':'PMOS_termination_complement_circuit_candidate','added_device_count':len(devices),'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'source_sha256':{str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [fixture,Path(__file__)]},'scope':'Existing extracted TX, NMOS switches, source resistors and external network retained. Added device junction geometry is modeled, but new layout/routes and safe-state qualification are absent.'}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();attach(a.fixture.resolve(),a.output.resolve())
