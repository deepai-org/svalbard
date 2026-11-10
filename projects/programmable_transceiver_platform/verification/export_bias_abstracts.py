#!/usr/bin/env python3
"""Export physical placement abstracts for the qualified bias distribution.

Only annotate working copies. Check every pin against the real subcircuit,
parse the LEF in OpenROAD, and XOR the re-export against the qualified GDS.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'analog/bringup_control'))
from export_lef import XOR_SCRIPT, OPENROAD_SCRIPT

ANALOG = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
DIGITAL = 'sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(image, work, command, log):
    shell, flag = ('/bin/bash', '-lc') if image == ANALOG else ('/bin/sh', '-c')
    result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2',
                             '--memory', '4g', '--entrypoint', shell, '-v', f'{work}:/work',
                             '-w', '/work', image, flag, command], capture_output=True,
                            text=True, timeout=180)
    (work/log).write_text(result.stdout+result.stderr)
    result.check_returncode()


def export(out):
    out.mkdir(parents=True, exist_ok=True)
    assert not (out/'report.json').exists(), 'Use a fresh output directory'
    evidence = PROJECT/'analog/core_support/evidence/core_support_evidence.json'
    qualified = json.loads(evidence.read_text())['distribution']['layout']
    generated = PROJECT/'analog/core_support/distribution/generated'
    inputs = [evidence, Path(__file__).resolve(), PROJECT/'analog/bringup_control/export_lef.py']
    cells = {}
    for name, physical in sorted(qualified.items()):
        assert physical['magic_drc_errors'] == physical['klayout_drc']['violations'] == 0
        assert 'match uniquely' in physical['lvs_final']
        work = out/name
        work.mkdir()
        gds, mag, spice, extraction = [generated/(name+suffix) for suffix in
                                     ('.gds.gz', '.mag', '.spice', '.ext.spice')]
        inputs.extend([gds, mag, spice, extraction])
        reference = gzip.decompress(gds.read_bytes())
        assert hashlib.sha256(reference).hexdigest() == physical['hashes'][name+'.gds']
        for path in (spice, extraction):
            assert sha(path) == physical['hashes'][path.name], path
        before = {str(p): sha(p) for p in (gds, mag, spice, extraction)}
        (work/'reference.gds').write_bytes(reference)
        shutil.copyfile(mag, work/mag.name)
        (work/mag.name).chmod(0o666)
        ports = re.search(r'^\.subckt\s+'+name+r'\s+([^\n]+)', spice.read_text(), re.M)[1].split()
        magic_ports = {pin: int(index) for pin, index in re.findall(
            r'^flabel[^\n]*\s(\S+)\nport (\d+)\b', mag.read_text(), re.M)}
        assert set(magic_ports) == set(ports), name
        expected = {}
        commands = ['crashbackups stop', f'load {name}', 'units microns',
                    'box values 0 0 1 1', 'property LEFclass BLOCK']
        for pin in ports:
            if pin in ('VDD', 'VSS'):
                direction, use = 'inout', 'power' if pin == 'VDD' else 'ground'
            elif pin.startswith('EN') or pin in ('TRK', 'ROOT_REF', 'VBG'):
                direction, use = 'input', 'signal'
            else:
                assert pin.startswith(('OUT', 'TRK_')) or pin in ('VREF0', 'VCM'), pin
                direction, use = 'output', 'signal'
            commands += [f'port {magic_ports[pin]} class {direction}',
                         f'port {magic_ports[pin]} use {use}']
            expected[pin] = dict(direction=direction.upper(), use=use.upper())
        commands += [f'lef write {name}.lef -hide', 'cif ostyle gdsii',
                     f'gds write {name}.export.gds', 'quit -noprompt']
        (work/'export.tcl').write_text('\n'.join(commands)+'\n')
        for filename, template in [('xor.py', XOR_SCRIPT), ('pins.py', OPENROAD_SCRIPT)]:
            (work/filename).write_text(template.replace('pt_wtx_fallback_control', name))
        run(ANALOG, work, 'magic -dnull -noconsole -rcfile '
            '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/export.tcl', 'export.log')
        run(ANALOG, work, 'klayout -b -r /work/xor.py', 'xor.log')
        run(DIGITAL, work, 'openroad -exit -python /work/pins.py', 'pins.log')
        xor = json.loads((work/'gds-xor.json').read_text())
        parsed = json.loads((work/'openroad-pins.json').read_text())
        assert xor['status'] == 'pass' and set(parsed['pins']) == set(expected)
        for pin, roles in expected.items():
            assert all(parsed['pins'][pin][key] == value for key, value in roles.items()), pin
        bbox = [int(v)*xor['gds_dbu_um'] for v in re.findall(r'-?\d+', xor['reference_bbox_dbu'])]
        origin = list(map(float, re.search(r'\bORIGIN\s+([-\d.]+)\s+([-\d.]+)',
                                          (work/(name+'.lef')).read_text()).groups()))
        assert len(bbox) == 4
        assert all(abs(a-b) < 1e-6 for a, b in zip(origin, [-bbox[0], -bbox[1]]))
        assert all(abs(a-b) < 1e-6 for a, b in zip(parsed['size_um'],
                    [bbox[2]-bbox[0], bbox[3]-bbox[1]])), 'LEF misses physical geometry'
        assert all(sha(p) == h for p, h in before.items()), 'Qualified source changed'
        cells[name] = dict(status='pass', gds_bbox_um=bbox, lef_origin_um=origin,
                           openroad=parsed, geometry_xor=xor,
                           source_hashes=before,
                           artifact_hashes={f: sha(work/f) for f in
                                            [name+'.lef', 'gds-xor.json', 'openroad-pins.json']})
        print(name, parsed['size_um'], len(expected), 'pins, zero GDS XOR', flush=True)
    result = dict(status='pass', scope='six bias-distribution cell abstracts (root, vref, four banks)', cells=cells,
                  source_hashes={str(p): sha(p) for p in inputs},
                  images=dict(analog=ANALOG, digital=DIGITAL),
                  excluded=['full-chip placement and routing', 'pin access and power-grid closure',
                            'fresh assembled DRC/LVS and analog performance qualification'])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')


def publish(out, destination):
    report = json.loads((out/'report.json').read_text())
    assert report['status'] == 'pass'
    assert all(sha(p) == h for p, h in report['source_hashes'].items())
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name, cell in report['cells'].items():
        source = out/name/(name+'.lef')
        assert sha(source) == cell['artifact_hashes'][source.name]
        target = destination/source.name
        shutil.copyfile(source, target)
        artifacts[str(target)] = sha(target)
    report['published_artifact_hashes'] = artifacts
    report['export_report'] = dict(path=str(out/'report.json'), sha256=sha(out/'report.json'))
    (destination/'abstract-evidence.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/bias-distribution-abstracts')
    parser.add_argument('--publish-dir', type=Path)
    args = parser.parse_args()
    export(args.output_dir.resolve())
    if args.publish_dir:
        publish(args.output_dir.resolve(), args.publish_dir.resolve())
