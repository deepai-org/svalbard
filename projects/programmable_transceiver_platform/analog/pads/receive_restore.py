"""Sizing experiment for retained-peer high-side switch turn-off.

Uses the complete generated RX/USB transistor graph. This is pre-layout
evidence: no extracted wire capacitance or implemented reset supervisor.
"""
from dataclasses import replace
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from wired_receive import build
from design import PROJECT
from screen import header, control, run_spice


def run(work, pdk, physical=None, control_screen=False):
    work.mkdir(parents=True, exist_ok=False)
    (work / '.spiceinit').write_text('set ngbehavior=hs\n')
    previous = Path.cwd()
    results = {}
    architecture = PROJECT / 'spec/analog-architecture.json'
    core_cap = json.loads(architecture.read_text())['blocks']['rxlevel']['parameters']['output_cap_budget_f_per_leg']
    try:
        os.chdir(work)
        cases = [('stale', 4., None), ('pre_disable', 4., 30.),
                 ('trip_immediate', 4., 36.2), ('trip_0p5ns', 4., 36.7),
                 ('trip_2ns', 4., 38.2)] if control_screen else [(str(w), w, None) for w in (4., 8., 20.)]
        if physical is not None and not control_screen:
            raise ValueError('Sizing requires regenerated geometry; physical input is only for control screening')
        for case, width, disable_ns in cases:
            circuit = build()
            circuit.devices = [replace(d, w_um=width) if d.name.endswith('_RESTORE') else d
                               for d in circuit.devices]
            deck = header(circuit, pdk, physical)
            deck += 'VDD VDD 0 PWL(0 3.3 36n 3.3 37n 0 148n 0 149n 1.5 160n 1.5 161n 3.3 200n 3.3)\n'
            for port in circuit.ports:
                if port in ('PAD_P', 'PAD_N', 'VDD', 'VSS', 'RX_P', 'RX_N'):
                    continue
                value = 3.3 if port in ('FS_HIGH_P', 'PULLUP_N', 'HS_PBIAS') else 0
                if disable_ns is not None and port in ('FS_HIGH_P', 'PULLUP_N'):
                    deck += f'V{port} {port} 0 PWL(0 3.3 {disable_ns}n 3.3 {disable_ns+.1}n 0 170n 0 170.1n 3.3 200n 3.3)\n'
                else:
                    deck += f'V{port} {port} 0 {value}\n'
            for leg in ('P', 'N'):
                deck += (f'VEXT_{leg} EXT_{leg} 0 3.3\n'
                         f'RPULL_{leg} EXT_{leg} BOARD_{leg} 1500\n'
                         f'RLOAD_{leg} BOARD_{leg} 0 15000\n'
                         f'CBOARD_{leg} BOARD_{leg} 0 10p\n'
                         f'RBOND_{leg} BOARD_{leg} BOND_{leg} 1\n'
                         f'LBOND_{leg} BOND_{leg} PAD_{leg} 1n\n'
                         f'RCORE_{leg} RX_{leg} 0 1g\n'
                         f'CCORE_{leg} RX_{leg} 0 {core_cap}\n')
            name = 'control_'+case if control_screen else f'restore_{int(width)}'
            deck += control(work, name, 'tran 20p 200n',
                            'i(VDD) v(PAD_P) v(PAD_N)')
            rows = run_spice(work, name, deck)
            if rows[-1, 0] < 199.99e-9 or not np.isfinite(rows).all():
                raise ValueError('Incomplete or nonfinite retained-peer transient')
            windows = {}
            for state, (start, end) in dict(power_collapse=(36, 48),
                    late_unpowered=(130, 147), brownout=(152, 159),
                    recovered=(190, 199)).items():
                x = rows[(rows[:, 0] >= start*1e-9) & (rows[:, 0] <= end*1e-9)]
                if len(x) < 2:
                    raise ValueError('Missing state window: '+state)
                windows[state] = dict(peak_supply_backfeed_a=float(np.maximum(x[:, 1], 0).max()),
                    positive_supply_charge_c=float(np.trapezoid(np.maximum(x[:, 1], 0), x[:, 0])),
                    pad_min_v=float(x[:, 2:4].min()), pad_max_v=float(x[:, 2:4].max()))
            results[case] = dict(transient_complete=True, windows=windows,
                disable_request_time_ns=disable_ns,
                deck_sha256=hashlib.sha256(deck.encode()).hexdigest())
    finally:
        os.chdir(previous)
    report = dict(status='bounded_control_response_not_implemented_supervisor' if control_screen else 'schematic_restore_sizing_not_layout_or_reset_qualification',
        physical_capacitance_included=physical is not None,
        external_network_unchanged=True, cases=results,
        limitations=[('Extracted pad circuit retained.' if physical else 'No extracted metal capacitance.'),
                     'Controls are prescribed waveforms, not an implemented reset or power-good supervisor.',
                     'Supply-return current includes displacement charge.'],
        source_sha256={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (Path(__file__), architecture, Path(__file__).with_name('wired_receive.py'),
                                 Path(__file__).with_name('circuits.py'), Path(__file__).with_name('screen.py'),
                                 pdk/'design.ngspice', pdk/'sm141064.ngspice') + ((physical,) if physical else ())})
    (work / 'restore-screen.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--pdk-model-dir', type=Path, required=True)
    parser.add_argument('--physical', type=Path)
    parser.add_argument('--control-screen', action='store_true')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.pdk_model_dir.resolve(),
        args.physical.resolve() if args.physical else None, args.control_screen)
