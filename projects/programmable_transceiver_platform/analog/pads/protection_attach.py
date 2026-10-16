"""Attach the existing physical primary-protection macro to a full pad circuit.

Circuit integration hypothesis only: original devices/capacitances stay present;
connecting-route parasitics and combined layout are not yet implemented.
"""
import argparse
import hashlib
import json
from pathlib import Path


def attach(pad, network, output, pdk, replace_small_clamps=False):
    manifest=json.loads((network/'network-layout.json').read_text())
    physical=network/'network-with-well.spice'
    if hashlib.sha256(physical.read_bytes()).hexdigest()!=manifest['extracted_spice_sha256']:
        raise ValueError('Protection macro differs from checked physical model')
    for name,value in manifest['source_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=value:
            raise ValueError('Stale protection macro input: '+name)
    text=pad.read_text();lines=text.splitlines()
    removed=[]
    if replace_small_clamps:
        for line in lines:
            fields=line.split()
            if len(fields)>5 and fields[0].startswith('X') and fields[5]=='nfet_06v0_dss':
                if fields[1] not in ('PAD_P','PAD_N') or fields[2:5]!=['VSS']*3:
                    raise ValueError('Unexpected grounded-gate topology')
                dimensions=dict(item.split('=') for item in fields[6:])
                if dimensions.get('w')!='16u' or dimensions.get('l')!='0.6u':
                    raise ValueError('Unexpected grounded-gate sizing')
                removed.append(line)
        if len(removed)!=4 or any(sum(line.split()[1]==leg for line in removed)!=2 for leg in ('PAD_P','PAD_N')):
            raise ValueError('Expected exactly two small protection devices per leg')
        lines=[line for line in lines if line not in removed]

    header=next(line.split() for line in lines if line.startswith('.subckt'))
    if not {'PAD_P','PAD_N','VSS'}<=set(header[2:]):raise ValueError('Missing pad interface')
    if 'network_flat' in text or 'ATTACHED_PROTECTION_RAIL' in text:
        raise ValueError('Protection macro already attached')
    end=next(i for i,line in enumerate(lines) if line.startswith('.ends'))
    lines.insert(end,'XATTACHED_PRIMARY VSS ATTACHED_PROTECTION_RAIL PAD_P PAD_N network_flat')
    model='\n'.join(lines)+'\n'+physical.read_text()+f'\n.lib {pdk}/sm141064.ngspice diode_typical\n.lib {pdk}/sm141064.ngspice mimcap_typical\n'
    output.write_text(model)
    report=dict(status='connected_primary_protection_circuit_hypothesis_no_combined_layout',
        existing_devices_retained=not replace_small_clamps,removed_small_clamps=removed,
        extracted_wiring_capacitance_retained=True,protection_rail_isolated_from_functional_supply=True,
        scope='Extracted pad and macro both retained. New connecting routes, local return impedance, substrate interaction and combined physical fit are absent.',
        model_sha256=hashlib.sha256(model.encode()).hexdigest(),
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (pad,physical,network/'network-layout.json',Path(__file__))})
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('pad','network','output','pdk-model-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--replace-small-clamps',action='store_true')
    a=p.parse_args();attach(a.pad.resolve(),a.network.resolve(),a.output.resolve(),a.pdk_model_dir.resolve(),a.replace_small_clamps)
