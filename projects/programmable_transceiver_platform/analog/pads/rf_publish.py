"""Publish a checked integrated RF build as the current first-pass pad design."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from design import PROJECT


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(work, destination, assembly_report):
    manifest=json.loads((work/'integrated-screen.json').read_text())
    for section in ('source_sha256','report_sha256'):
        for name,value in manifest[section].items():
            if digest(Path(name))!=value:raise ValueError('Stale RF build input: '+name)
    assembly=json.loads(assembly_report.read_text())
    if assembly['status'] not in ('current_families_with_connected_RF_placement_and_local_rails_pass','current_families_placement_and_local_rails_pass'):
        raise ValueError('RF assembly check incomplete')
    pad=work/'pad';routed=work/'routed'
    if assembly['source_sha256'].get(str((pad/'pad.gds').resolve()))!=digest(pad/'pad.gds'):
        raise ValueError('Assembly did not check this RF GDS')
    layout=json.loads((pad/'pad-layout.json').read_text())
    audit=json.loads((pad/'independent-device-audit.json').read_text())
    if layout['drc_count'] or not layout['fits_assigned_area'] or not audit['device_graph_matches']:
        raise ValueError('RF construction checks failed')
    base=destination/'rf-pad-base';base.mkdir(exist_ok=True)
    if not json.loads((destination/'rf-receive-layout.json').read_text()).get('connected_protection'):
        for family in ('rf-receive','rf-transmit'):
            for suffix in ('.gds','-layout.json','-extracted-c.spice'):
                shutil.copyfile(destination/(family+suffix),base/(family+suffix))
        shutil.copyfile(destination/'wire-resistance.json',base/'wire-resistance.json')
    for family in ('rf_receive','rf_transmit'):
        stem=family.replace('_','-')
        base_metadata=json.loads((base/(stem+'-layout.json')).read_text())
        # Preserve provider placement inputs, not obsolete four-device geometry.
        shared=('family','bond_template','bond_pitch_um','active_origin_um','escape_width_um',
                'area_ceiling_um2','reference_pair_size_um','near_bond_ground_landings_um')
        metadata={key:base_metadata[key] for key in shared if key in base_metadata}
        regions=layout['geometry']['allocation_regions_um']
        bounds=[min(r[0] for r in regions),min(r[1] for r in regions),
                max(r[2] for r in regions),max(r[3] for r in regions)]
        metadata['allocation_bbox_um']=bounds
        metadata['candidate_size_um']=[bounds[2]-bounds[0],bounds[3]-bounds[1]]
        metadata['allocation_union_um2']=layout['geometry']['allocation_union_um2']
        metadata.update(status='connected_RF_first_pass_core_protection_unqualified',
            connected_protection=True,flat_cell='rf_protected_pad_pair',device_count=audit['physical_devices'],
            escape_width_um=layout['configuration']['escape_width_um'],
            allocation_regions_um=layout['geometry']['allocation_regions_um'],
            fits_assigned_area=layout['fits_assigned_area'],
            integrated_model_scope='Extracted physical network plus the published high-resistance routing overlay; core boundaries behavioral.')
        metadata['sources_sha256']={}
        for source,value in layout['source_sha256'].items():
            path=Path(source).resolve()
            if path.is_relative_to(PROJECT):metadata['sources_sha256'][str(path.relative_to(PROJECT))]=value
        metadata['sources_sha256'].update({str(Path(__file__).relative_to(PROJECT)):digest(Path(__file__)),
            'analog/pads/protection_pad.py':digest(Path(__file__).with_name('protection_pad.py')),
            'analog/pads/protection_device_audit.py':digest(Path(__file__).with_name('protection_device_audit.py'))})
        (destination/(stem+'-layout.json')).write_text(json.dumps(metadata,indent=2)+'\n')
        for source,suffix in ((pad/'pad.gds','.gds'),(pad/'pad.png','.png'),
                (routed/'physical.spice','-extracted-c.spice'),
                (routed/family/'screen-report.json','-screen.json'),
                (routed/'route-resistance.json','-route-resistance.json'),
                (pad/'independent-device-audit.json','-device-audit.json')):
            shutil.copyfile(source,destination/(stem+suffix))
        # generate() imports the streamed GDS into Magic before independent audit.
        roundtrip=dict(drc_count=0,device_graph_match=True,
            gds_sha256=digest(pad/'pad.gds'),reference_sha256=digest(routed/'physical.spice'),
            independent_audit=audit,scope='Streamed GDS physical devices audited, with explicit nonlinear well replacement separately checked; routing resistance is a modeled overlay, not extracted geometry.')
        (destination/(stem+'-gds-roundtrip.json')).write_text(json.dumps(roundtrip,indent=2)+'\n')
    shutil.copyfile(work/'integrated-screen.json',destination/'rf-integrated-screen.json')
    shutil.copyfile(assembly_report,destination/'rf-assembly-screen.json')
    template=destination/'provider-assembly-inputs';template.mkdir(exist_ok=True)
    for name in ('assembly-report.json','custom-map.json','retained-binding.json','provider-reference-ring.gds','placement-transforms.json'):
        shutil.copyfile(assembly_report.parent/name,template/name)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build-dir','generated','assembly-report'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();publish(a.build_dir.resolve(),a.generated.resolve(),a.assembly_report.resolve())
