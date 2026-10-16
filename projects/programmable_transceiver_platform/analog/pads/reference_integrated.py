"""Build and publish the selected protected reference pad and retained-state model.

Publication selects an implemented first-pass model, not electrical acceptance.
The receiver boundary, long bias startup and protection qualification remain open.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from design import PROJECT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(work, generated, pdk, publish=True):
    from layout import generate as base_layout
    from wired_protection_layout import generate as connect_primary
    from analog_screen import screen
    from protected_assembly import run as assemble
    work.mkdir(parents=True, exist_ok=False)
    spec = PROJECT/'spec/schematic-implementation.json'
    origin = json.loads(spec.read_text())['io_pad_first_pass']['primary_placement_um']['reference_clock']
    base_layout(work/'base', 'reference_clock', external_primary=True)
    pad = work/'pad'
    connect_primary(pad, work/'base', generated/'protection-network', origin, pdk)
    physical = pad/'physical.spice'
    layout = json.loads((pad/'placement-layout.json').read_text())
    audit = json.loads((pad/'model-audit.json').read_text())
    check = json.loads((pad/'layout-screen.json').read_text())
    if not (layout['fits_assigned_area'] and audit['device_graph_matches']
            and check['drc_count'] == 0 and check['device_lvs_match']
            and check['simulation_model_sha256'] == digest(physical)):
        raise ValueError('Reference construction checks failed')
    screens = {}
    for name, termination in [('electrical', None), ('terminated', 100.)]:
        screens[name] = screen(work/name, pdk, physical, 'reference_clock', termination)
        if not screens[name]['transient_complete']:
            raise ValueError('Incomplete reference retained-state screen')
    assemble(work/'assembly', generated, generated/'provider-assembly-inputs',
             reference=pad, tx=generated/'wired-primary-protection/double-tails',
             receive=generated/'receive-primary-protection/fs-sizing')
    subprocess.run([sys.executable, str(Path(__file__).with_name('render.py')),
        str(pad/'combined_flat.mag'), '--output', str(pad/'layout.png'),
        '--title', 'Protected differential reference pad'], check=True)
    reports = [pad/'layout-screen.json', pad/'model-audit.json', pad/'placement-layout.json',
               work/'electrical/screen-report.json', work/'terminated/screen-report.json',
               work/'assembly/assembly-screen.json']
    result = dict(status='selected_reference_model_built_not_electrically_qualified',
        device_count=audit['physical_devices'], area_um2=layout['area_um2'],
        source_sha256={str(p.resolve()):digest(p) for p in
            [Path(__file__), spec, PROJECT/'spec/analog-architecture.json', PROJECT/'spec/contract.json']},
        report_sha256={str(p):digest(p) for p in reports},
        limitations=['Reference receiver is a behavioral boundary.',
                    'Short lifecycle does not establish common-mode bias startup or clock reception.',
                    'No whole-ring device LVS, distributed route resistance, current-capacity or ESD qualification.'])
    (work/'integrated-screen.json').write_text(json.dumps(result, indent=2)+'\n')
    if publish:
        stem = 'reference-clock'
        metadata = dict(layout)
        metadata.update(status=result['status'], connected_protection=True,
                        integrated_model_scope='Extracted primary protection and bias resistors; behavioral receiver boundary.')
        metadata['sources_sha256'] = {}
        # Preserve actual layout provenance, including base generation dependencies.
        for provenance in [json.loads((work/'base/layout-report.json').read_text()).get('sources_sha256', {}),
                           check['source_sha256'], result['source_sha256']]:
            for name, value in provenance.items():
                p = Path(name)
                if not p.is_absolute(): p = PROJECT/p
                if p.is_relative_to(PROJECT): metadata['sources_sha256'][str(p.relative_to(PROJECT))] = value
        (generated/(stem+'-layout.json')).write_text(json.dumps(metadata, indent=2)+'\n')
        for source, suffix in [(physical,'-extracted-c.spice'), (pad/'combined.gds','.gds'),
                (pad/'layout.png','.png'), (pad/'model-audit.json','-device-audit.json'),
                (work/'electrical/screen-report.json','-screen.json'),
                (work/'terminated/screen-report.json','-terminated-screen.json'),
                (work/'electrical/lifecycle.spice','-lifecycle.spice'),
                (work/'integrated-screen.json','-integrated-screen.json'),
                (work/'assembly/assembly-screen.json','-assembly-screen.json')]:
            shutil.copyfile(source, generated/(stem+suffix))
        roundtrip = dict(drc_count=0, device_graph_match=True,
            gds_sha256=digest(pad/'combined.gds'), reference_sha256=digest(physical),
            independent_audit=audit,
            scope='Combined streamed GDS imported into Magic and independently audited; explicit nonlinear well replacement checked separately. No protection qualification.')
        (generated/(stem+'-gds-roundtrip.json')).write_text(json.dumps(roundtrip,indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir', 'generated', 'pdk-model-dir'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.output_dir.resolve(), a.generated.resolve(), a.pdk_model_dir.resolve()), indent=2))
