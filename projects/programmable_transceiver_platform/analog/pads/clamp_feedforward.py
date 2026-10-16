"""Attach the checked MIM primitive to an extracted isolated-rail clamp gate.

Circuit hypothesis; capacitor has physical layout, connecting routes do not.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def attach(physical, mim, output):
    metadata=json.loads((mim/'layout.json').read_text());capacitor=mim/'physical.spice'
    if metadata['drc_count'] or not metadata['gds_roundtrip_device_and_capacitance_match']:
        raise ValueError('MIM primitive lacks physical checks')
    if hashlib.sha256(capacitor.read_bytes()).hexdigest()!=metadata['physical_sha256']:
        raise ValueError('Changed MIM extraction')
    for name,value in metadata['source_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=value:raise ValueError('Stale MIM primitive')
    lines=physical.read_text().splitlines();counts=Counter();owners={};owner=None
    for index,line in enumerate(lines):
        fields=line.split()
        if fields and fields[0]=='.subckt':owner=fields[1]
        if len(fields)>5 and fields[0].startswith('X') and fields[5]=='nfet_06v0' and {fields[1],fields[3]}=={'ESD_RAIL','VSS'}:
            counts[(owner,fields[2])]+=1
        if fields and fields[0]=='.ends':owners[owner]=index
    (owner,gate),count=counts.most_common(1)[0]
    if count<40:raise ValueError('Expected the large isolated-rail clamp')
    if 'XFEEDFORWARD' in physical.read_text():raise ValueError('Feed-forward already present')
    lines.insert(owners[owner],f'XFEEDFORWARD ESD_RAIL {gate} VSS feedforward_mim')
    output.write_text('\n'.join(lines)+'\n'+capacitor.read_text())
    report=dict(status='physical_MIM_attached_in_circuit_not_combined_layout',clamp_cell=owner,clamp_gate=gate,
        parallel_clamp_units=count,capacitor_envelope_um2=metadata['envelope_area_um2'],
        limitations=['No added connecting-route parasitics; pulse response is not ESD qualification.',
                     'Cold start and normal signal false-trigger behavior require retained-network checks.'],
        output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (physical,capacitor,mim/'layout.json',Path(__file__))})
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('physical','mim-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();attach(a.physical.resolve(),a.mim_dir.resolve(),a.output.resolve())
