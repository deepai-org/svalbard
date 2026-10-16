"""Measure every MOS terminal pair in an existing retained-network fixture.

This is a voltage-exposure inventory, not a reliability or ESD qualification.
The original circuit, sources and transient analysis are preserved.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
from screen import control, run_spice


def run(work, fixture, physical, instance="xpad"):
    text = fixture.read_text()
    if text.count('.control') != 1:
        raise ValueError('Expected exactly one control block')
    analysis = [s.strip() for s in text.splitlines() if s.strip().startswith('tran ')]
    if len(analysis) != 1:
        raise ValueError('Expected one transient analysis')
    token = analysis[0].split()[2]
    match = re.fullmatch(r'([0-9.eE+-]+)([pnum]?)', token)
    if not match:
        raise ValueError('Unsupported transient stop time: '+token)
    stop_s = float(match[1]) * {'':1., 'p':1e-12, 'n':1e-9, 'u':1e-6, 'm':1e-3}[match[2]]
    model = physical.read_text()
    if model not in text:
        raise ValueError('Fixture does not contain the exact supplied physical model')
    devices = []
    definition = next(l.split() for l in model.splitlines() if l.startswith('.subckt '))
    ports = definition[2:]
    logical = re.sub(r'\n\s*\+\s*', ' ', text.split('.control')[0])
    instances = [l.split() for l in logical.splitlines() if l.split() and l.split()[0].lower() == instance.lower()]
    if len(instances) != 1 or instances[0][-1].lower() != definition[1].lower() or len(instances[0]) != len(ports)+2:
        raise ValueError('Expected one explicit instance with matching physical port order')
    port_nodes = dict(zip(ports, instances[0][1:-1]))
    for line in model.splitlines():
        t = line.split()
        if t and t[0].startswith('X') and len(t) > 5 and t[5].startswith(('nfet_', 'pfet_')):
            devices.append(dict(name=t[0], model=t[5], nodes=t[1:5]))
    if not devices:
        raise ValueError('No MOS devices found')
    nodes = sorted({n for d in devices for n in d['nodes']})
    def vector(n):
        return 'v('+ (port_nodes[n] if n in ports else instance+'.'+n) + ')'
    work.mkdir(parents=True, exist_ok=False)
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    deck = text.split('.control')[0] + control(work, 'exposure', analysis[0],
                                              ' '.join(vector(n) for n in nodes))
    previous = Path.cwd()
    try:
        os.chdir(work)
        rows = run_spice(work, 'exposure', deck)
    finally:
        os.chdir(previous)
    if rows[-1, 0] < stop_s*(1-1e-5) or not np.isfinite(rows).all():
        raise ValueError('Incomplete retained-network exposure run')
    index = {n: i+1 for i, n in enumerate(nodes)}
    result = []
    for d in devices:
        terminal = dict(zip('DGSB', d['nodes']))
        pairs = {}
        for a, b in ('GS', 'GD', 'GB', 'DS', 'DB', 'SB'):
            voltage = rows[:, index[terminal[a]]] - rows[:, index[terminal[b]]]
            hi = int(np.argmax(voltage)); lo = int(np.argmin(voltage))
            pairs[a+b] = dict(min_v=float(voltage[lo]), max_v=float(voltage[hi]),
                              min_time_s=float(rows[lo, 0]), max_time_s=float(rows[hi, 0]))
        result.append(dict(**d, terminal_pairs=pairs))
    summary = {}
    for model_name in sorted({d['model'] for d in result}):
        group = [d for d in result if d['model'] == model_name]
        summary[model_name] = {}
        for pair in ('GS', 'GD', 'GB', 'DS', 'DB', 'SB'):
            candidates = [(abs(d['terminal_pairs'][pair][bound]), d['name'],
                           d['terminal_pairs'][pair][bound], d['terminal_pairs'][pair][time])
                          for d in group for bound, time in [('min_v','min_time_s'), ('max_v','max_time_s')]]
            magnitude, name, signed, time = max(candidates)
            summary[model_name][pair] = dict(max_absolute_v=magnitude, device=name,
                                             signed_v=signed, time_s=time)
    report = dict(status='terminal_voltage_exposure_not_safe_stress_verdict',
        transient_complete=True, instance=instance, port_nodes=port_nodes, stop_time_s=stop_s, transistor_count=len(devices), node_count=len(nodes),
        original_network_and_stimuli_preserved=True, per_model=summary, devices=result,
        limitations=['No reliability limits inferred from device model names.',
                     'No junction current-density, avalanche, thermal or ESD qualification.',
                     'Ideal supply waveform is retained; package supply impedance is absent.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (fixture, physical, Path(__file__), Path(__file__).with_name('screen.py'))})
    (work/'terminal-exposure.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--physical', type=Path, required=True)
    parser.add_argument('--instance', default='xpad')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.fixture.resolve(), args.physical.resolve(), args.instance)
