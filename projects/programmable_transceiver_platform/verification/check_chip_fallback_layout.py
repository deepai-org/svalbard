#!/usr/bin/env python3
"""Run the existing fallback checks with the DRC/LVS-clean control extraction.

This separate entry point preserves any running schematic-control experiment.
All check_chip_fallback.py arguments are accepted. --physical-preflight-only
builds the fixture and checks its operating-point probes without claiming a
functional pass. --bridge-manifest reuses an existing, source-checked bridge.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import check_chip_fallback as base

CONTROL = base.power.PROJECT/'analog/bringup_control'
GENERATED = CONTROL/'generated'
TOP = 'pt_wtx_fallback_control'
original_extension = base.route.extension


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def physical_evidence():
    physical = json.loads((GENERATED/'evidence.json').read_text())
    functional = json.loads((GENERATED/'characterization.json').read_text())
    assert physical['status'] == functional['status'] == 'pass', 'control macro not qualified'
    hashes = {**physical['source_hashes'], **physical['artifact_hashes'], **functional['source_hashes']}
    assert all(sha(p) == h for p, h in hashes.items()), 'stale control-macro evidence'
    return physical, functional


def layout_extension(read, support, pdk, library, scenario):
    physical_evidence()
    extra = original_extension(read, support, pdk, library, scenario)
    assert extra['models'].count(base.route.GLUE) == 1
    extra['models'].remove(base.route.GLUE)
    text = read(GENERATED/(TOP+'.ext.spice'))
    for path in [Path(__file__).resolve(), CONTROL/'build.py', CONTROL/'characterize.py',
                 GENERATED/'evidence.json', GENERATED/'characterization.json']:
        read(path)
    joined = re.sub(r'\n\+\s*', ' ', text)
    pins = re.search(rf'^\.subckt {TOP} ([^\n]+)', joined, re.M).group(1).split()
    assert set(pins) == set(physical_evidence()[0]['ports']), 'extracted control port mismatch'
    removed = [line for line in extra['analog_body']
               if line.split()[-1] in ('bringup_inv', 'bringup_and')]
    assert len(removed) == 11, 'changed schematic control topology'
    extra['analog_body'] = [line for line in extra['analog_body'] if line not in removed]
    extra['models'].append(base.route.namespace(text, 'layout_'))
    extra['analog_body'].append('Xphysical_control '+' '.join(pins)+' layout_'+TOP)
    return extra


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--physical-preflight-only', action='store_true')
    p.add_argument('--bridge-manifest', type=Path)
    p.add_argument('--output-dir', type=Path, default=base.power.ROOT/'scratch/chip-fallback-layout')
    p.add_argument('--ngspice-source', type=Path, default=base.power.ROOT/'scratch/pad-ngspice47/ngspice-47')
    own, remaining = p.parse_known_args()
    if '--help' in remaining or '-h' in remaining:
        print(__doc__)
        sys.argv = [sys.argv[0], '--help']
        base.main()
        return
    out = own.output_dir.resolve()
    physical, functional = physical_evidence()
    out.mkdir(parents=True, exist_ok=True)
    forwarded = ['--output-dir', str(out), '--ngspice-source', str(own.ngspice_source.resolve()), *remaining]
    if own.bridge_manifest:
        assert (own.bridge_manifest.resolve().parents[1] != out), 'use a separate output directory'
        (out/'bridge').mkdir(exist_ok=True)
        (out/'bridge/ports.json').write_bytes(own.bridge_manifest.resolve().read_bytes())
        forwarded.append('--reuse-bridge')
    if own.physical_preflight_only and '--build-only' not in forwarded:
        forwarded.append('--build-only')
    base.route.extension = layout_extension
    sys.argv = [sys.argv[0], *forwarded]
    base.main()
    if own.physical_preflight_only:
        ng = own.ngspice_source.resolve()
        cm = ng/'src/xspice/icm'
        (out/'.spiceinit').write_text('set ngbehavior=hs\n'+
            '\n'.join(f'codemodel {cm}/{n}/{n}.cm' for n in ('analog', 'digital'))+'\n')
        base.preflight(out, ng, 'route.spice' if '--route-only' in forwarded else 'pt_chip.spice')
    physical_evidence()
    built_only = '--build-only' in forwarded
    result = dict(status='prepared' if built_only else 'pass',
                  physical_control=TOP, transistor_count=physical['transistor_count'],
                  magic_drc_errors=physical['macro']['drc_errors'],
                  klayout_drc_errors=physical['macro']['klayout']['violations'],
                  unique_lvs_match=physical['macro']['lvs']['unique_match'],
                  extracted_static_vectors=functional['static_vectors'],
                  functional_simulation_completed=not built_only,
                  operating_point_preflight=own.physical_preflight_only,
                  source_files={str(p): sha(p) for p in [Path(__file__).resolve(),
                     GENERATED/'evidence.json', GENERATED/'characterization.json',
                     GENERATED/(TOP+'.ext.spice'), GENERATED/(TOP+'.gds')]})
    (out/'physical-control-binding.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
