"""Rebuild the selected protected TX layout and its connected circuit fixture.

Construction is verified independently of electrical acceptance. Buffer and
interlock are extracted component inputs, not placed in this pad reservation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from design import PROJECT


def run(work, generated, pdk, publish=True):
    from layout import generate
    from wired_protection_layout import generate as protect
    from transmit_fixture import build
    work.mkdir(parents=True, exist_ok=False)
    spec = PROJECT/'spec/schematic-implementation.json'
    cfg = json.loads(spec.read_text())['io_pad_first_pass']
    generate(work/'base', 'wired_transmit', external_primary=True,
             **cfg['generation_parameters']['wired_transmit'])
    protect(work/'pad', work/'base', generated/'protection-network',
            cfg['primary_placement_um']['wired_transmit'], pdk)
    pad = work/'pad'
    layout = json.loads((pad/'placement-layout.json').read_text())
    audit = json.loads((pad/'model-audit.json').read_text())
    checks = json.loads((pad/'layout-screen.json').read_text())
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if not (layout['fits_assigned_area'] and audit['device_graph_matches']
            and checks['drc_count'] == 0 and checks['device_lvs_match']
            and checks['simulation_model_sha256'] == digest(pad/'physical.spice')):
        raise ValueError('Protected TX construction failed')
    build(work/'fixture.spice', pdk, pad_override=pad/'physical.spice')
    subprocess.run([sys.executable, str(Path(__file__).with_name('render.py')),
                    str(pad/'combined_flat.mag'), '--output', str(pad/'layout.png'),
                    '--title', 'Protected wired TX pad'], check=True)
    from transmit_sequence_connected import run as replay
    from protected_assembly import run as assemble
    seed = generated/'termination-buffer-candidate/source-headroom/reference-reset/feedback/screen.json'
    from transmit_feedback_closure import verify as verify_closure
    for iteration in range(1, 5):
        electrical = work/f'replay-{iteration}'
        replay(electrical, work/'fixture.spice', seed, spice_timeout_s=240 if audit['physical_devices']>500 else 120)
        observed = json.loads((electrical/'screen.json').read_text())
        closure_dir=work/f'closure-{iteration}'
        closure=verify_closure(closure_dir,electrical)
        if closure['controls_identical']:
            break
        seed = electrical/'screen.json'
    else:
        raise ValueError('TX feedback controls did not converge within four iterations')
    if (not closure['lifecycle_gate_pass'] or observed['busy_commit_events'] or not observed['disabled_end_observed']
            or observed['loaded_traffic_ready_without_detector_ready_s'] != 0
            or not all(v['qualified'] and v['traffic_ready'] for v in observed['mode_coverage'].values())
            or not all(v['samples'] for v in observed['states'].values())):
        raise ValueError('TX retained-state coverage incomplete')
    assemble(work/'assembly', generated, generated/'provider-assembly-inputs', tx=pad)
    result = dict(status='constructed_not_electrically_accepted',
                  device_count=audit['physical_devices'], area_um2=layout['area_um2'],
                  source_sha256={str(p.resolve()):digest(p) for p in [Path(__file__), spec]},
                  artifact_sha256={str(p):digest(p) for p in [pad/'physical.spice',
                      pad/'combined.gds', pad/'layout-screen.json', pad/'model-audit.json',
                      work/'fixture.spice', work/'fixture.json']},
                  remaining=['Nominal sampled replay is not sustained operation or protocol electrical acceptance.',
                             'Combined buffer/interlock placement and area remain unresolved.',
                             'Protection limits, physical readiness and protocol electrical acceptance remain open.'])
    (work/'integration.json').write_text(json.dumps(result, indent=2)+'\n')
    if publish:
        stem = 'wired-transmit'
        metadata = dict(layout)
        metadata.update(connected_protection=True,
                        integrated_model_scope='Protected pad plus extracted buffer/interlock in connected lifecycle fixture; core macros not placed here.')
        metadata['sources_sha256'] = {}
        for sources in [json.loads((work/'base/layout-report.json').read_text()).get('sources_sha256', {}),
                        checks['source_sha256'], result['source_sha256']]:
            for name, value in sources.items():
                path = Path(name)
                if not path.is_absolute(): path = PROJECT/path
                if path.is_relative_to(PROJECT):
                    metadata['sources_sha256'][str(path.relative_to(PROJECT))] = value
        (generated/(stem+'-layout.json')).write_text(json.dumps(metadata, indent=2)+'\n')
        for source, suffix in [(pad/'physical.spice','-extracted-c.spice'),
                (pad/'combined.gds','.gds'), (pad/'layout.png','.png'),
                (pad/'model-audit.json','-device-audit.json'),
                (electrical/'screen.json','-screen.json'),
                (closure_dir/'closure.json','-feedback-closure.json'),
                (electrical/'connected.spice','-lifecycle.spice'),
                (work/'integration.json','-integration.json'),
                (work/'assembly/assembly-screen.json','-assembly-screen.json')]:
            shutil.copyfile(source, generated/(stem+suffix))
        roundtrip = dict(drc_count=0, device_graph_match=True,
            gds_sha256=digest(pad/'combined.gds'), reference_sha256=digest(pad/'physical.spice'),
            independent_audit=audit,
            scope='Combined GDS imported and independently audited; no whole-ring LVS or protection qualification.')
        (generated/(stem+'-gds-roundtrip.json')).write_text(json.dumps(roundtrip,indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir', 'generated', 'pdk-model-dir'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(run(a.output_dir.resolve(), a.generated.resolve(), a.pdk_model_dir.resolve()), indent=2))
