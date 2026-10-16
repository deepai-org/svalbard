"""Place current pad families with the connected RF protection candidate.

Preserves provider bond locations. Geometry/metal checks do not establish
whole-ring device connectivity, current capacity or package qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from layout import IMAGE


def run(work, generated, assembly, rf, tx=None, reference=None, receive=None):
    work.mkdir(parents=True,exist_ok=False)
    for name in ('assembly-report.json','custom-map.json','retained-binding.json',
                 'provider-reference-ring.gds','placement-transforms.json'):
        shutil.copyfile(assembly/name,work/name)
    inputs=[]
    rfmeta=json.loads((rf/'pad-layout.json').read_text())
    for family in ('wired_transmit','wired_receive_usb','reference_clock','rf_receive','rf_transmit'):
        stem=family.replace('_','-');meta=generated/(stem+'-layout.json')
        metadata=json.loads(meta.read_text());gds=generated/(stem+'.gds')
        if family.startswith('rf_'):
            gds=rf/'pad.gds'
            metadata.update(flat_cell='rf_protected_pad_pair',
                allocation_regions_um=rfmeta['geometry']['allocation_regions_um'],
                fits_assigned_area=rfmeta['geometry']['allocation_union_um2']<=metadata['area_ceiling_um2'],
                connected_protection_candidate=True)
        if family=='wired_transmit' and tx is not None:
            meta=tx/'placement-layout.json';metadata=json.loads(meta.read_text());gds=tx/'combined.gds'
        if family=='reference_clock' and reference is not None:
            meta=reference/'placement-layout.json';metadata=json.loads(meta.read_text());gds=reference/'combined.gds'
        if family=='wired_receive_usb' and receive is not None:
            meta=receive/'placement-layout.json';metadata=json.loads(meta.read_text());gds=receive/'combined.gds'
        shutil.copyfile(gds,work/('candidate_'+family+'.gds'))
        (work/('candidate_'+family+'-layout.json')).write_text(json.dumps(metadata,indent=2)+'\n')
        # Rail audit consumes the same physical files under the family names.
        shutil.copyfile(gds,work/(stem+'.gds'))
        (work/(stem+'-layout.json')).write_text(json.dumps(metadata,indent=2)+'\n')
        inputs.extend((meta,gds))
    for name in ('placement_audit.py','rail_connectivity.py'):
        shutil.copyfile(Path(__file__).with_name(name),work/name)
    command=['docker','run','--rm','--network','none','--entrypoint','python3',
             '--mount',f'type=bind,src={work},dst=/work',IMAGE]
    subprocess.run(command+['/work/placement_audit.py'],check=True)
    subprocess.run(command+['/work/rail_connectivity.py','--generated','/work','--output','/work/native-rail-screen.json'],check=True)
    placement=json.loads((work/'placement-audit.json').read_text())
    passed=(placement['roundtrip_all_bond_openings_match'] and not placement['custom_to_custom_metal_overlaps']
        and not any(v['unexpected_retained_metal_overlaps'] for v in placement['custom_cells'].values()))
    report=dict(status='current_families_placement_and_local_rails_pass' if passed else 'current_families_placement_failed',
        connected_tx_candidate=tx is not None,connected_reference_candidate=reference is not None,connected_receive_candidate=receive is not None,placement=placement,local_rails=json.loads((work/'native-rail-screen.json').read_text()),
        limitations=['No whole-ring extracted-device LVS, package-return model, or current-capacity qualification.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            inputs+[rf/'pad-layout.json',Path(__file__),Path(__file__).with_name('placement_audit.py'),Path(__file__).with_name('rail_connectivity.py')]})
    (work/'assembly-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    if not passed:raise ValueError('Provider placement failed; inspect assembly-screen.json')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','generated','assembly-dir','rf-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--tx-dir',type=Path)
    p.add_argument('--reference-dir',type=Path)
    p.add_argument('--receive-dir',type=Path)
    a=p.parse_args();run(a.output_dir.resolve(),a.generated.resolve(),a.assembly_dir.resolve(),a.rf_dir.resolve(),a.tx_dir.resolve() if a.tx_dir else None,a.reference_dir.resolve() if a.reference_dir else None,a.receive_dir.resolve() if a.receive_dir else None)
