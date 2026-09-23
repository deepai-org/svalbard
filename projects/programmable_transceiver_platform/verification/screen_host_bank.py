#!/usr/bin/env python3
"""Native five/six-output bank: ideal versus candidate RC supply feedback."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

import numpy as np

from run_gpio_transient import output_instance, TECH, PAD


def deck(path, mode):
    lines = ['* Native host bank supply sensitivity; electrical SSO fixture',
        f'.include {TECH}/design.ngspice']
    lines += [f'.lib {TECH}/sm141064.ngspice {section}' for section in
        ('typical', 'res_typical', 'diode_typical', 'moscap_typical')]
    lines += [f'.include {PAD}', '.temp 25', 'VD BOARD 0 3.3', 'VC VDD 0 3.3',
        'VA A 0 PULSE(0 3.3 4n .5n .5n 2.7n 6.4n)']
    if mode in ('rc', 'feed'):
        lines += ['RA BOARD HOST_A 2', 'RB BOARD HOST_B 2']
    else:
        lines += ['VA_FEED BOARD HOST_A 0', 'VB_FEED BOARD HOST_B 0']
    lines += ['RG GRET 0 .1' if mode in ('rc', 'return') else 'VG GRET 0 0']
    lines += ['CA HOST_A GRET 100p', 'CB HOST_B GRET 100p',
        'IA_IDLE HOST_A GRET .002', 'IB_IDLE HOST_B GRET .002',
        'IOTHER BOARD GRET .040']
    pads = []
    for group, count in (('A', 5), ('B', 6)):
        for index in range(count):
            pad = f'P{group}{index}';out = f'Y{group}{index}'
            # Reuse the audited native pin map and drive-strength selection.
            instance = output_instance('X'+pad, 'A', pad, out, 8, 'GRET').split()
            assert instance[3] == 'DVDD'
            instance[3] = 'HOST_'+group
            lines += [' '.join(instance), f'C{pad} {pad} 0 10p', f'C{out} {out} 0 1f']
            pads.append(pad)
    vectors = ['v(a)', 'v(HOST_A)', 'v(HOST_B)', 'v(GRET)', 'i(VD)', 'i(VC)']
    vectors += [f'v({p})' for p in pads]
    lines += ['.control', 'set noaskquit', 'set wr_singlescale', 'set wr_vecnames',
        'tran 20p 32n 0 20p', f'wrdata {path}/wave.txt '+' '.join(vectors),
        'quit', '.endc', '.end']
    return '\n'.join(lines)+'\n', pads


def run_case(work, mode):
    name = mode+'_bank'
    path = work/name;path.mkdir()
    (path/'.spiceinit').write_text('set ngbehavior=hs\n')
    source, pads = deck(path, mode)
    (path/'tb.spice').write_text(source)
    start = time.monotonic()
    row = dict(case=name, status='incomplete', elapsed_s=None,
        deck_sha256=hashlib.sha256(source.encode()).hexdigest())
    with (path/'run.log').open('w') as log:
        try:
            process = subprocess.run(['ngspice', '-b', 'tb.spice'], cwd=path,
                stdout=log, stderr=subprocess.STDOUT, timeout=90)
            row['returncode'] = process.returncode
        except subprocess.TimeoutExpired:
            row['error'] = '90 second simulation timeout; not an electrical failure result'
    row['elapsed_s'] = time.monotonic()-start
    row['log_sha256'] = hashlib.sha256((path/'run.log').read_bytes()).hexdigest()
    wave = path/'wave.txt'
    if row.get('returncode') == 0 and wave.exists():
        array = np.loadtxt(wave, skiprows=1)
        if array.shape[1] != 7+len(pads) or array[-1, 0] < 31.999e-9:
            raise ValueError('Incomplete or malformed bank waveform')
        selected = array[array[:, 0] >= 12e-9]
        spans = selected[:, 2:4]-selected[:, 4, None]
        row.update(status='completed', waveform_sha256=hashlib.sha256(wave.read_bytes()).hexdigest(),
            measured_start_s=float(selected[0, 0]), measured_end_s=float(selected[-1, 0]),
            rail_span_min_v=np.min(spans, axis=0).tolist(),
            rail_span_max_v=np.max(spans, axis=0).tolist(),
            common_return_extrema_v=[float(np.min(selected[:, 4])), float(np.max(selected[:, 4]))],
            output_extrema_v={p:[float(np.min(selected[:, 7+i])), float(np.max(selected[:, 7+i]))]
                for i, p in enumerate(pads)},
            board_current_peak_a=float(np.max(-selected[:, 5])),
            below_2p5v_model_floor=bool(np.any(spans < 2.5)))
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--isolate', action='store_true')
    args = parser.parse_args()
    work = Path('/work')
    modes = ('feed', 'return') if args.isolate else ('ideal', 'rc')
    stem = 'host-bank-isolation' if args.isolate else 'host-bank'
    report = dict(status='running', cases=[], full_chip_closure=False, physical_qualification=False,
        source_tree_sha256=os.environ['ANALOG_SOURCE_SHA256'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), Path('/src/run_gpio_transient.py'), PAD)},
        assumptions=['Eleven native 8 mA output pads, 5/6 segmented output supplies; typical process, 3.3 V, 25 C.',
            'All outputs switch together into 10 pF each; this SSO stress is not a host protocol/timing test.',
            'Candidate PDN: 2 ohm per supply feed, 0.1 ohm shared return, 100 pF local capacitance per segment; isolation cases enable only feed or return resistance.',
            '2 mA assumed additional load per host segment and 40 mA other-chip load through the common return.',
            'Core pre-driver supply remains ideal. No package inductance, clamp ring, input bank, substrate network or mismatch.',
            '32 ns transient with a 12–32 ns measurement window; no sustained-current or jitter qualification.'])
    output = work/(stem+'.json')
    def save():output.write_text(json.dumps(report, indent=2)+'\n')
    save()
    for mode in modes:
        row = run_case(work, mode);report['cases'].append(row);save()
        print(json.dumps(row), flush=True)
    report['status'] = 'screen_completed' if all(r['status']=='completed' for r in report['cases']) else 'incomplete'
    save()
    with tarfile.open(work/(stem+'-waveforms.tar.gz'), 'w:gz') as bundle:
        for mode in modes:
            name = mode+'_bank';bundle.add(work/name, arcname=name)


if __name__ == '__main__':
    main()
