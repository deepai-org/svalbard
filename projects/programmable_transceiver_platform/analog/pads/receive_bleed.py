"""Characterize core-side discharge loading without selecting a physical resistor.

The supplied retained-network fixture must contain the exact physical pad model.
Only its two explicitly named core resistors and output-control section change.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os

import numpy as np

from design import PROJECT
from screen import control, header, run_spice
from wired_receive import build


def characterize(output, physical, fixture, pdk):
    architecture = PROJECT / 'spec/analog-architecture.json'
    params = json.loads(architecture.read_text())['blocks']['rxlevel']['parameters']
    original = fixture.read_text()
    assert physical.read_text().strip() in original, 'Fixture does not contain supplied physical model'
    base = original.split('.control')[0]
    for leg in ('P', 'N'):
        assert base.count(f'RCORE_{leg} RX_{leg} 0 1g') == 1
    output.mkdir(parents=True, exist_ok=False)
    (output / '.spiceinit').write_text('set ngbehavior=hs\n')
    previous = Path.cwd()
    results = {}
    try:
        os.chdir(output)
        for resistance in (1e9, 1e5, 330e3, 1e6):
            name = str(int(resistance))
            circuit = build()
            deck = header(circuit, pdk, physical) + 'VDD VDD 0 3.3\n'
            for port in circuit.ports:
                if port not in ('PAD_P', 'PAD_N', 'VDD', 'VSS', 'RX_P', 'RX_N'):
                    value = 3.3 if port in ('BYPASS_ENABLE', 'DIFF_ENABLE', 'HS_PBIAS') else 0
                    deck += f'V{port} {port} 0 {value}\n'
            for leg, amplitude in (('P', .5), ('N', -.5)):
                deck += (
                    f'VSRC_{leg} SRC_{leg} 0 DC {params["output_common_mode_target_v"]} AC {amplitude}\n'
                    f'RSRC_{leg} SRC_{leg} PAD_{leg} 50\n'
                    f'RCORE_{leg} RX_{leg} 0 {resistance}\n'
                    f'CCORE_{leg} RX_{leg} 0 {params["output_cap_budget_f_per_leg"]}\n'
                )
            ac = np.atleast_2d(run_spice(output, 'ac_' + name, deck + control(
                output, 'ac_' + name, 'ac lin 1 1.25G 1.25G',
                'real(v(RX_P,RX_N)/v(PAD_P,PAD_N)) imag(v(RX_P,RX_N)/v(PAD_P,PAD_N))')))
            dc = np.atleast_2d(run_spice(output, 'dc_' + name, deck + control(
                output, 'dc_' + name, 'op', 'v(RX_P) v(RX_N)')))
            assert np.isfinite(ac).all() and np.isfinite(dc).all()
            entry = dict(resistance_ohm=resistance,
                         pad_to_core_gain_db=float(20 * np.log10(np.hypot(ac[0, 1], ac[0, 2]))),
                         active_receiver_v=dc[0, -2:].tolist())
            # This fixture contract is deliberately narrow: a 3 us retained-peer
            # lifecycle with the off observation window below, not arbitrary decks.
            transient = base
            for leg in ('P', 'N'):
                transient = transient.replace(f'RCORE_{leg} RX_{leg} 0 1g',
                                              f'RCORE_{leg} RX_{leg} 0 {resistance}')
            transient += control(output, 'tran_' + name, 'tran .2n 3u',
                                 'v(RX_P) v(RX_N) v(VDD) v(BYPASS_ENABLE)')
            data = run_spice(output, 'tran_' + name, transient)
            assert data[-1, 0] >= 2.9999e-6 and np.isfinite(data).all()
            off = data[(data[:, 0] >= 1.95e-6) & (data[:, 0] <= 2.205e-6)]
            assert len(off) > 1
            assert np.max(np.abs(off[:, 3:5])) < .01, 'Off window is not rail/bypass disabled'
            entry.update(transient_complete=True,
                         off_receiver_max_abs_v=float(np.max(np.abs(off[:, 1:3]))),
                         deck_sha256=hashlib.sha256(transient.encode()).hexdigest())
            results[name] = entry
    finally:
        os.chdir(previous)
    report = dict(status='attached_core_bleed_characterization_not_selected_layout', cases=results,
                  active_common_mode_v=params['output_common_mode_target_v'],
                  core_capacitance_f_per_leg=params['output_cap_budget_f_per_leg'],
                  frequency_hz=1.25e9, off_observation_s=[1.95e-6, 2.205e-6],
                  limitations=['Nominal bypass only; half-divider, corners and noise unqualified.',
                               'Discharge components and supervisor are not implemented physical circuitry.',
                               'Off voltage is a measurement, not a core reliability acceptance threshold.'],
                  source_sha256={str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                                 for f in (physical, fixture, architecture, Path(__file__).resolve(),
                                           Path(__file__).with_name('screen.py').resolve(),
                                           Path(__file__).with_name('wired_receive.py').resolve())})
    (output / 'receive-bleed-screen.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('output-dir', 'physical', 'fixture', 'pdk-model-dir'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    characterize(args.output_dir.resolve(), args.physical.resolve(),
                 args.fixture.resolve(), args.pdk_model_dir.resolve())
