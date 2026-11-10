#!/usr/bin/env python3
"""Collect the register-file simulation, formal and synthesis results into
evidence/regfile-verification.json with source hashes.

Run after `make transceiver-regfile transceiver-regfile-formal transceiver-regfile-synth`.
Fails if any input result is missing or not passing.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[1]
S = ROOT / 'scratch/pt_regfile'
SOURCES = ['spec/analog-architecture.json', 'spec/debug-controls.json', 'spec/register-map.json',
           'rtl/gen/gen_regfile.py', 'rtl/gen/regmap_runtime.py', 'rtl/pt_regfile.sv', 'rtl/pt_regmap_defs.svh',
           'rtl/pt_spi.sv', 'rtl/pt_digital.sv', 'integration/pt_chip.sv', 'sim/tb_regfile.sv',
           'sim/tb_regfile_legacy.sv', 'sim/reference/pt_control.sv', 'verification/check_regfile.py', 'verification/formal/pt_regfile.sby',
           'verification/formal/pt_regfile_fv.sv', 'verification/run_regfile_formal.sh',
           'verification/run_regfile_synth.sh', 'integration/macro-contract.md']
FORMAL_IMAGE = 'docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'


def main():
    sim = json.loads((S / 'sim/report.json').read_text())
    formal = {}
    for task in ('prove', 'cover'):
        status = (S / f'formal/work/pt_regfile_{task}/status').read_text().split()
        formal[task] = status[0]
    log = (S / 'formal/sby.log').read_text()
    formal['method'] = 'k-induction (smtbmc yices), depth 3' if 'successful proof by k-induction' in log else 'unknown'
    formal['covers_reached'] = len(re.findall(r'summary:\s+reached cover statement', log))
    formal['image'] = FORMAL_IMAGE
    formal['yosys'] = next((ln.strip() for ln in log.splitlines() if ln.startswith('Yosys ')), None)
    stat = (S / 'synth/stat.txt').read_text()
    cells = {m.group(2): int(m.group(1)) for m in re.finditer(r'^\s+(\d+)\s+\S+\s+(gf180mcu_\S+)', stat, re.M)}
    area = float(re.search(r"Chip area for module '\\pt_mgmt': ([0-9.]+)", stat).group(1))
    synth = dict(top='pt_mgmt (pt_spi + pt_regfile)', image=(S / 'synth/image.txt').read_text().strip(),
                 image_tag=__import__('os').environ.get('SVALBARD_DIGITAL_IMAGE', 'svalbard/librelane-gf180-canary:2026.08'),
                 yosys=(S / 'synth/yosys_version.txt').read_text().strip(),
                 liberty='gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30', standard_cells=sum(cells.values()),
                 flip_flops=sum(v for k, v in cells.items() if '__dff' in k), cell_area_um2=round(area, 1),
                 scope='Generic yosys synth + abc mapping; no placement, timing or utilization.')
    ok = (sim['status'] == 'pass' and formal['prove'] == 'PASS' and formal['cover'] == 'PASS')
    report = dict(
        status='pass' if ok else 'fail',
        scope=('Generated SPI register file (control path of the must-work core): register map, reset '
               'defaults, write/readback, rule-based commit rejection, island isolation, fault release, '
               'break-before-make, commit while running, legacy pt_control equivalence, formal safety '
               'invariants and rough GF180 size. Not hardened: no DRC/LVS, no STA, no gate-level simulation.'),
        simulation={k: sim[k] for k in ('seed', 'random_operations', 'commands', 'reads_checked',
                    'snapshots_checked', 'commits_accepted', 'commits_rejected', 'registers', 'fields', 'rules',
                    'registers_swept', 'rejected_value_writes', 'directed_rule_violations_rejected',
                    'all_rule_codes_exercised', 'legacy_equivalence', 'chip_integration')} |
                   {sim_name: sim[sim_name]['status'] for sim_name in ('iverilog', 'verilator') if sim_name in sim},
        formal=formal,
        formal_properties=['P1 asynchronous reset: every shadow/active field at its declared default; island switches, '
                           'ATB switches, observation output enables, receiver enables and island-gated outputs off',
                           'P2 every rule (pad, ownership, legality, ATB force/override) holds on the active configuration; '
                           'every active and non-split shadow field holds an accepted encoding',
                           'P3 every pad/ownership rule holds on the pad-facing outputs for all island, power-good and '
                           'fault inputs; at most one ATB switch per bus; ATB0 never closes on a sense-only node and '
                           'closes on an overridable node exactly when its bias override is active',
                           'P4 island-gated outputs are 0 while their island is off; fault forces released values',
                           'P5 non-live fields never change while ENABLE=1; break-before-make fields never move '
                           'directly between two non-zero codes',
                           'P6 reset-cause flags: POR sets both RESET_STATUS flags; any reset sets the reset flag'],
        synthesis=synth,
        sources_sha256={name: hashlib.sha256((P / name).read_bytes()).hexdigest() for name in SOURCES})
    out = P / 'evidence/regfile-verification.json'
    out.write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(dict(status=report['status'], simulation=report['simulation'].get('iverilog'),
                          formal=formal['prove'], cells=synth['standard_cells'], area_um2=synth['cell_area_um2'])))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
