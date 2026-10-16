"""Cold bias startup followed by an RF burst without resetting retained state."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re

import numpy as np
from design import PROJECT
from screen import control, run_spice


def run(work, fixture, physical, gain, rise_s, samples_per_cycle):
    architecture = PROJECT / 'spec/analog-architecture.json'
    blocks = json.loads(architecture.read_text())['blocks']
    guard = blocks['monitor']['parameters']['qualification_guard_s']
    driver = blocks['rfdriver']['parameters']
    if not driver['gain_range'][0] <= gain <= driver['gain_range'][1]:
        raise ValueError('Gain outside shared design range')
    if not np.isfinite(rise_s) or rise_s <= 0 or samples_per_cycle < 32:
        raise ValueError('Positive rise time and at least 32 samples/cycle required')
    text = fixture.read_text().split('.control')[0]
    assert physical.read_text() in text, 'Fixture must contain exact supplied model'
    gates = Counter()
    for line in physical.read_text().splitlines():
        fields = line.split()
        if len(fields) > 5 and fields[0].startswith('X') and fields[5] == 'nfet_06v0' and {fields[1], fields[3]} == {'ESD_RAIL', 'VSS'}:
            gates[fields[2]] += 1
    gate, count = gates.most_common(1)[0]
    assert count >= 40, 'Expected distributed protection clamp'
    frequency = 2.4e9  # Explicit fixture carrier, not a supported-band limit.
    target_w = 1e-3 * 10**(driver['target_mean_power_dbm']/10)
    load = driver['load_ohm_differential']
    peak = np.sqrt(2*target_w*load)*(1+driver['source_r_ohm_differential']/load)*gain/driver['nominal_gain']/2
    start = 2e-9 + rise_s + guard
    stop = start + 192/frequency
    def replace(pattern, replacement):
        nonlocal text
        text, matches = re.subn(pattern, replacement, text, flags=re.M)
        assert matches == 1, pattern
    replace(r'^VDD VDD 0 .*$', f'VDD VDD 0 PWL(0 0 2n 0 {2e-9+rise_s} 3.3 {stop} 3.3)')
    # Bias driver remains active, but signal command is zero until the guard.
    replace(r'^VEN ENABLE .*$', 'VEN ENABLE 0 1')
    for leg, sign in (('P', 1), ('N', -1)):
        replace(rf'^VEXT_{leg} .*$', f'VEXT_{leg} EXT_{leg} 0 0')
        replace(rf'^BCORE_{leg} .*$', f'BCORE_{leg} CORE_{leg} 0 V=V(VCM)+V(STARTUP_DRIVE_{leg})')
        points = '0 0 ' + ' '.join(
            f'{start+i/(samples_per_cycle*frequency):.15g} {sign*peak*np.sin(2*np.pi*i/samples_per_cycle):.15g}'
            for i in range(192*samples_per_cycle+1))
        text += f'VSTARTUP_{leg} STARTUP_DRIVE_{leg} 0 PWL({points})\n'
    work.mkdir(parents=True, exist_ok=False)
    (work / '.spiceinit').write_text('set ngbehavior=hs\n')
    vectors = f'v(BOARD_P) v(BOARD_N) v(EXT_P) v(EXT_N) v(xpad.xphysical.{gate},xpad.LOCAL_PAD_RETURN)'
    deck = text + control(work, 'startup', f'tran 1n {stop}', vectors)
    previous = Path.cwd()
    try:
        os.chdir(work)
        data = run_spice(work, 'startup', deck)
    finally:
        os.chdir(previous)
    assert data[-1, 0] >= stop*(1-1e-9) and np.isfinite(data).all()
    times = start + 160/frequency + np.arange(32*128)/(128*frequency)
    voltage = np.interp(times, data[:, 0], data[:, 1]-data[:, 2]-data[:, 3]+data[:, 4])
    voltage -= voltage.mean()
    phase = 2*np.pi*frequency*(times-start)
    fundamental = np.hypot(2*np.mean(voltage*np.cos(phase)), 2*np.mean(voltage*np.sin(phase)))
    power = fundamental**2/(2*load)
    report = dict(status='shared_guard_RF_startup_characterization', transient_complete=True,
                  guard_s=guard, supply_rise_s=rise_s, frequency_hz=frequency,
                  gain=gain, command_peak_per_leg_v=float(peak), samples_per_cycle=samples_per_cycle,
                  power_dbm=float(10*np.log10(power/1e-3)), meets_tone_target=bool(power >= target_w),
                  gate_at_guard_v=float(np.interp(start, data[:, 0], data[:, 5])),
                  limitations=['Bias driver active during guard; external peer silent, passive network retained.',
                               'Ideal supply, nominal devices and PWL carrier; not complete startup or reliability qualification.'],
                  source_sha256={str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                                 for f in (fixture, physical, architecture, Path(__file__).resolve(),
                                           Path(__file__).with_name('screen.py').resolve())})
    (work / 'startup-screen.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir', 'fixture', 'physical'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--gain', type=float, required=True)
    parser.add_argument('--rise-s', type=float, default=1e-8)
    parser.add_argument('--samples-per-cycle', type=int, default=64)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.fixture.resolve(), args.physical.resolve(),
        args.gain, args.rise_s, args.samples_per_cycle)
