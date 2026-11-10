#!/usr/bin/env python3
"""Import the exact qualified core-support extractions for chip assembly."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


def prepare(clean):
    evidence_path = PROJECT/'analog/core_support/evidence/core_support_evidence.json'
    evidence = json.loads(evidence_path.read_text())
    out = PROJECT/'integration/models/core_bias'
    out.mkdir(parents=True, exist_ok=True)
    models = {}
    for name in ('biasgen_patched', 'bandgap'):
        source = clean/name/'layout_pex.spice'
        expected = evidence['clean'][name]['pex_netlist']['sha256']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected, f'Unqualified extraction: {source}'
        target = out/(name+'.pex.spice')
        shutil.copy2(source, target)
        models[name] = dict(file=target.name, sha256=expected,
                            qualified_geometry_sha256=evidence['clean'][name]['gds_checked']['sha256'],
                            extraction='capacitance only; resistance extraction unsupported',
                            simulation_transform='pnp_10p00x00p42 -> pnp_05p00x05p00' if name == 'bandgap' else None)
    manifest = dict(models=models, evidence=str(evidence_path.relative_to(PROJECT)),
                    evidence_sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                    preparation_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Imported exact qualified biasgen and bandgap extractions into '+str(out))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean', type=Path, default=ROOT/'scratch/core_support/work/clean')
    prepare(parser.parse_args().clean.resolve())
