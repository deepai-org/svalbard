"""Rebuild the selected protected TX layout and its connected circuit fixture.

Construction is verified independently of electrical acceptance. Buffer and
interlock are extracted component inputs, not placed in this pad reservation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from design import PROJECT


def run(work, generated, pdk):
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
    result = dict(status='constructed_not_electrically_accepted',
                  device_count=audit['physical_devices'], area_um2=layout['area_um2'],
                  source_sha256={str(p.resolve()):digest(p) for p in [Path(__file__), spec]},
                  artifact_sha256={str(p):digest(p) for p in [pad/'physical.spice',
                      pad/'combined.gds', pad/'layout-screen.json', pad/'model-audit.json',
                      work/'fixture.spice', work/'fixture.json']},
                  remaining=['Run retained-state replay against this exact regenerated model.',
                             'Combined buffer/interlock placement and area remain unresolved.',
                             'Protection limits, physical readiness and protocol electrical acceptance remain open.'])
    (work/'integration.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir', 'generated', 'pdk-model-dir'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(run(a.output_dir.resolve(), a.generated.resolve(), a.pdk_model_dir.resolve()), indent=2))
