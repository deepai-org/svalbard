#!/usr/bin/env python3
"""Exercise pt_chip SPI/pad binding; analog inputs remain explicit test stimuli.

Fetches the unmodified provider Verilog from the installed offline PDK image,
or accepts --io-model. Does not qualify physical power-up or fallback data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
IMAGE = 'svalbard/librelane-gf180-canary:2026.08'
PROVIDER_PATH = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v'


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, capture_output=True,
                          timeout=120, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--io-model', type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/chip-io')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out/'report.json'
    # A failed rerun must not leave an old passing report at the output path.
    report_path.write_text(json.dumps({'status': 'incomplete'})+'\n')
    for name in ('compile.log', 'sim.log', 'chip-io.vcd'):
        (out/name).unlink(missing_ok=True)
    image_id = None
    if args.io_model:
        model = args.io_model.resolve()
    else:
        image_id = run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}']).stdout.strip()
        container = run(['docker', 'create', '--network', 'none', image_id]).stdout.strip()
        model = out/'gf180mcu_fd_io.v'
        try:
            run(['docker', 'cp', f'{container}:{PROVIDER_PATH}', str(model)])
        finally:
            run(['docker', 'rm', container])
    sources = [PROJECT/'sim/tb_chip_io.sv', PROJECT/'integration/pt_chip.sv',
               PROJECT/'integration/pt_provider_io.sv', *sorted((PROJECT/'rtl').glob('*.sv'))]
    compile_command = ['iverilog', '-g2012', '-Dfunctional', '-DPT_EXTERNAL_IO',
                       '-I', str(PROJECT/'rtl'), '-s', 'tb_chip_io', '-o', str(out/'chip.vvp'),
                       *map(str, sources), str(model)]
    compile_result = subprocess.run(compile_command, cwd=out, text=True,
                                    capture_output=True, timeout=120)
    (out/'compile.log').write_text(compile_result.stdout+compile_result.stderr)
    compile_result.check_returncode()
    sim = subprocess.run(['vvp', '-n', str(out/'chip.vvp')], cwd=out, text=True,
                         capture_output=True, timeout=120)
    (out/'sim.log').write_text(sim.stdout+sim.stderr)
    sim.check_returncode()
    if 'CHIP_IO_PASS' not in sim.stdout.splitlines():
        raise RuntimeError('chip IO simulation did not finish its assertions')
    sources += list((PROJECT/'rtl').glob('*.svh'))
    sources.append(Path(__file__).resolve())
    report = {
        'status': 'pass', 'scope': 'digital_integration_through_provider_functional_pad_models',
        'goal_complete': False,
        'provider': {'image': IMAGE if image_id else None, 'image_id': image_id,
                     'file': PROVIDER_PATH if image_id else str(model), 'sha256': digest(model)},
        'source_hashes': {str(p.relative_to(ROOT)): digest(p) for p in sources},
        'checks': ['SPI ID and ABI reads through provider pads with payload clocks stopped',
                   'SPI shadow write and commit drives only the selected island enable',
                   'effective island enable waits for power-good and isolates on its loss',
                   'power-good boundary stimulus reaches SPI status and DBG_OBS0 pad',
                   'reset clears island enables and ATB selects, tristates host/debug outputs',
                   'CS_N low during RESET_N or POR assertion leaves MISO tristated',
                   'reset interrupts an active SPI transaction without additional clocks',
                   'SPI recovers after reset and CS_N release'],
        'excluded': ['analog power ramp, brownout, POR circuit and board supervisor',
                     'physical island power switch, pgood generation and isolation clamps',
                     'analog test bus and fallback data path',
                     'floating RESET_N: provider in_c functional model ignores PU/PD',
                     'pad electrical loading, backfeed, timing signoff and full-chip physical assembly'],
        'simulator': run(['iverilog', '-V']).stdout.splitlines()[0],
        'trace': 'chip-io.vcd',
    }
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(sim.stdout.strip())
    print(f'Report: {report_path}')


if __name__ == '__main__':
    main()
