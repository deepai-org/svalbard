#!/usr/bin/env python3
"""Qualify all channels of the complete extracted ATB tree.

This is a physical-tree fixture with finite Thevenin node sources and a board
meter/force source. Per-block observation and SPI-controlled assembly still
require the parent to bind the actual node and control ports.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'integration'))
import atb_tree
from check_chip_power import instance


def check(out, pdk, support, ng):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    sources = {}
    def read(path):
        path = Path(path).resolve()
        sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text()
    library = read(pdk/'gf180mcu_fd_io.spice')
    tree = atb_tree.build(read, support, library)
    read(PROJECT/'integration/atb_tree.py')
    read(Path(__file__))
    (out/'pt_atb_tree.spice').write_text(tree['text'])
    metadata = {k: v for k, v in tree.items() if k != 'text'}
    (out/'tree.json').write_text(json.dumps(metadata, indent=2)+'\n')
    nodes = [leaf for leaf in tree['leaves'] if leaf['bus'] == 1]
    signals = {pin: pin for pin in tree['pins']}
    signals.update(VSS='0')
    deck = ['* Complete extracted ATB physical-tree qualification',
            f'.include {pdk}/ngspice/design.ngspice']
    deck += [f'.lib {pdk}/ngspice/sm141064.ngspice {corner}' for corner in
             ['typical', 'res_typical', 'diode_typical', 'mimcap_typical', 'moscap_typical']]
    deck += ['.temp 27', library, tree['text'], 'Vdd VDD 0 3.3', 'Vaddress ADDRESS 0 0',
             'Vmode FORCE_MODE 0 0', 'Vboard FORCE_BOARD 0 1.25',
             'Rforce FORCE_BOARD ATB0 100', 'Rmeter ATB1 0 1g', 'Cmeter ATB1 0 10p',
             instance('Xtree', 'pt_atb_tree', tree['text'], signals)]
    for node in nodes:
        code, pin = node['code'], node['node_port']
        deck += [f'Vnode{code} SOURCE{code} 0 {0.3+code*.03:.8f}',
                 f'Rnode{code} SOURCE{code} {pin} 100k', f'Cnode{code} {pin} 0 1p']
    for leaf in tree['leaves']:
        term = f'(abs(V(ADDRESS)-{leaf["code"]})<.25)'
        if leaf['bus'] == 0:
            term = f'(V(FORCE_MODE)>.5)&&{term}'
        deck.append(f'Bselect{leaf["bus"]}_{leaf["code"]} {leaf["select_port"]} 0 V=3.3*({term})')
    controls = json.loads((PROJECT/'spec/debug-controls.json').read_text())
    for bus in (0, 1):
        all_codes = []
        for index, group in enumerate(controls['atb_groups'][f'atb{bus}']):
            all_codes += group['codes']
            terms = '||'.join(f'(abs(V(ADDRESS)-{code})<.25)' for code in group['codes'])
            enable = '(V(FORCE_MODE)>.5)&&' if bus == 0 else ''
            deck.append(f'Bgroup{bus}_{index} ATB{bus}_GRP_{index} 0 V=3.3*({enable}({terms}))')
        terms = '||'.join(f'(abs(V(ADDRESS)-{code})<.25)' for code in all_codes)
        enable = '(V(FORCE_MODE)>.5)&&' if bus == 0 else ''
        deck.append(f'Benable{bus} ATB{bus}_EN 0 V=3.3*({enable}({terms}))')
    probes = ' '.join(['v(ATB1)', 'v(ATB0)']+[f'v({n["node_port"]})' for n in nodes])
    deck += ['.options reltol=0.0002 abstol=1e-13 vntol=1e-6 gmin=1e-12', '.control',
             'set wr_singlescale', 'set wr_vecnames', 'dc Vaddress 0 57 1',
             'wrdata sense-wave.txt '+probes, 'alter Vmode 1', 'dc Vaddress 0 57 1',
             'wrdata force-wave.txt '+probes, 'quit', '.endc', '.end']
    (out/'fixture.spice').write_text('\n'.join(deck)+'\n')
    with (out/'ngspice.log').open('w') as log:
        subprocess.run([str(ng), '-b', 'fixture.spice'], cwd=out, stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=300)
    waves = {name: np.loadtxt(out/(name+'-wave.txt'), skiprows=1) for name in ['sense', 'force']}
    legal_force = {n['code'] for n in tree['leaves'] if n['bus'] == 0}
    positions = {node['code']: index+3 for index, node in enumerate(nodes)}
    max_meter_error = 0
    max_force_error = 0
    max_unselected_change = 0
    for mode, wave in waves.items():
        assert wave.shape == (58, 3+len(nodes)) and np.isfinite(wave).all(), 'Incomplete DC sweep'
        for code in range(58):
            row = wave[code]
            assert row[0] == code
            if code in positions:
                error = abs(row[1]-row[positions[code]])
                assert error < .005, (mode, code, 'sense path error', error)
                max_meter_error = max(max_meter_error, error)
            else:
                assert abs(row[1]) < .02, (mode, code, 'unselected sense pad not discharged', row[1])
            for node in nodes:
                target = .3+node['code']*.03
                actual = row[positions[node['code']]]
                if mode == 'force' and code == node['code'] and code in legal_force:
                    error = abs(actual-1.25)
                    assert error < .05, (code, 'force compliance error', error)
                    max_force_error = max(max_force_error, error)
                elif code != node['code']:
                    error = abs(actual-target)
                    assert error < .005, (mode, code, node['code'], 'unselected node disturbed', error)
                    max_unselected_change = max(max_unselected_change, error)
    for path in sorted((pdk/'ngspice').glob('*')):
        if path.is_file():
            sources[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    sources[str(ng)] = hashlib.sha256(ng.read_bytes()).hexdigest()
    result = dict(status='pass', scope='nominal complete extracted ATB physical tree with provider pads',
                  sense_channels=len(nodes), force_channels=len(legal_force),
                  dc_addresses_per_mode=58, group_sizes=tree['group_sizes'],
                  max_meter_to_selected_node_error_v=max_meter_error,
                  max_force_node_to_board_target_error_v=max_force_error,
                  max_unselected_node_change_v=max_unselected_change,
                  fixture=dict(node_source_ohm=100000, node_capacitance_f=1e-12,
                               meter_ohm=1e9, meter_capacitance_f=10e-12,
                               force_source_v=1.25, force_source_ohm=100),
                  excluded=['block source bindings', 'SPI controls and island transition sequencing',
                            'transient settling, PVT and routed interconnect'],
                  source_hashes=sources,
                  artifact_hashes={name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name in
                                   ['fixture.spice', 'pt_atb_tree.spice', 'tree.json', 'sense-wave.txt', 'force-wave.txt', 'ngspice.log']})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_hashes', 'artifact_hashes')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/atb-tree')
    parser.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    parser.add_argument('--island-pex', type=Path, default=ROOT/'scratch/island-support-20261108-075605')
    parser.add_argument('--ngspice', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47/src/ngspice')
    args = parser.parse_args()
    check(args.output_dir.resolve(), args.pdk.resolve(), args.island_pex.resolve(), args.ngspice.resolve())
