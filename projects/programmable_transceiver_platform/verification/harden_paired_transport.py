#!/usr/bin/env python3
"""Place and route a frozen paired transport screen, independently of the chip.

Uses its exact mapped-screen RTL and related-clock constraints. Results are
an integration experiment: whole-chip CDC, pad timing and area remain open.
The run never writes the project's digital signoff evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]


def prepare(screen, out):
    report = json.loads((screen/'report.json').read_text())
    top = report['top']
    assert top in ('pt_dense_pair_word_tx', 'pt_dense_pair_word_rx')
    assert not (out/'manifest.json').exists(), 'Use a new output directory'
    out.mkdir(parents=True, exist_ok=True)
    design = out/'design'
    design.mkdir()
    shutil.copytree(screen/'rtl', design/'rtl')
    timing = (screen/'timing.tcl').read_text()
    constraints = timing.split(f'link_design {top}\n', 1)[1].split('set_input_transition', 1)[0]
    assert 'create_generated_clock' in constraints and 'set_false_path' not in constraints
    constraints += 'set_input_transition 0.15 [all_inputs]\nset_load 0.02 [all_outputs]\n'
    (design/'paired.sdc').write_text(constraints)
    config_path = PROJECT/'verification/digital_hardening/config.json'
    config = json.loads(config_path.read_text())
    config.update(DESIGN_NAME=top,
                  VERILOG_FILES=['dir::rtl/'+name for name in
                                 ['pt_dense_pair.sv', 'pt_dense_pair_link.sv',
                                  'pt_dense_pair_word.sv', 'pt_dense_header.sv']],
                  CLOCK_PORT=['clk'], CLOCK_PERIOD=3.2,
                  PNR_SDC_FILE='dir::paired.sdc', SIGNOFF_SDC_FILE='dir::paired.sdc',
                  DIE_AREA=[0, 0, 400, 400],
                  PL_MAX_DISPLACEMENT_X=100, PL_MAX_DISPLACEMENT_Y=100)
    (design/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    inputs = [p for p in design.rglob('*') if p.is_file()]
    manifest = dict(top=top, source_screen=str(screen),
                    image_id=report['image_id'],
                    screen_report_sha256=hashlib.sha256((screen/'report.json').read_bytes()).hexdigest(),
                    source_hashes=report['source_hashes'],
                    inputs={str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                    scope='standalone paired transport physical experiment; not full macro signoff')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screen-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    manifest = prepare(args.screen_dir.resolve(), out)
    if not args.prepare_only:
        for name in ('home', 'tmp'):
            (out/name).mkdir()
        command = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '4',
                   '--memory', '8g', '--pids-limit', '4096', '-e', 'HOME=/out/home',
                   '-e', 'TMPDIR=/out/tmp', '-e', 'OMP_NUM_THREADS=1',
                   '-v', f'{out}:/out', '-w', '/out/design', '--entrypoint', '/bin/sh',
                   manifest['image_id'], '-c',
                   'librelane --manual-pdk --pdk-root /pdk -p gf180mcuD '
                   '-s gf180mcu_fd_sc_mcu7t5v0 -j 4 --run-tag PAIRED '
                   '--hide-progress-bar config.json']
        with (out/'librelane.log').open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        (out/'run-result.json').write_text(json.dumps(dict(returncode=result.returncode))+'\n')
        print(json.dumps(dict(top=manifest['top'], returncode=result.returncode, output_dir=str(out))))
        raise SystemExit(result.returncode)
