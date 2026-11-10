#!/usr/bin/env python3
"""Check the extracted control macro's truth table, timing and powered-off state.

The physical builder and its artifacts must be fresh. Sweep 512 input states
at three process corners, three voltages and three temperatures. A separate
loaded transient exercises each input's effect on the intended logic.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INPUTS = ['L_BRANCH0', 'L_BRANCH1', 'L_STATE0', 'L_STATE1', 'L_IDLE',
          'L_STAGE_TMDS', 'L_EXT_ENABLE', 'ISO_wired', 'FORCE_LEAF']
OUTPUTS = ['TMDS_REQUEST', 'WIRED_ON', 'FORCE_SELECTED']
TOP = 'pt_wtx_fallback_control'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected(bits):
    b0, b1, s0, s1, idle, stage, external, iso, force = bits
    return [bool(b1 and not b0 and s1 and not s0 and not idle and stage and external),
            not iso, bool(force and not iso)]


def instance(text):
    joined = re.sub(r'\n\+\s*', ' ', text)
    pins = re.search(rf'^\.subckt {TOP} ([^\n]+)', joined, re.M).group(1).split()
    connections = dict(RAIL_wired='WIRE_SUPPLY', VDD='CORE_SUPPLY', VSS='0')
    return 'Xcontrol '+' '.join(connections.get(p, p) for p in pins)+' '+TOP


def characterize(generated, work, pdk, ngspice):
    work.mkdir(parents=True, exist_ok=True)
    target = generated/'characterization.json'
    target.write_text('{"status":"incomplete"}\n')
    physical = json.loads((generated/'evidence.json').read_text())
    assert physical['status'] == 'pass'
    for path, digest in {**physical['source_hashes'], **physical['artifact_hashes']}.items():
        assert sha(path) == digest, f'stale physical evidence: {path}'
    extraction = generated/(TOP+'.ext.spice')
    text = extraction.read_text()
    model = pdk/'ngspice/sm141064.ngspice'
    design = pdk/'ngspice/design.ngspice'
    envelope_path = HERE.parents[1]/'spec/tapeout-readiness.json'
    envelope = json.loads(envelope_path.read_text())['operating_envelope']['function_check_points']
    temperatures = sorted(set(envelope['temperature_c']+[envelope['nominal']['temperature_c']]))
    voltages = sorted(set(envelope['die_rail_v']+[envelope['nominal']['die_rail_v']]))
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    cases, max_delay = [], 0.
    states = [[(index >> k) & 1 for k in range(9)] for index in range(512)]
    truth = np.array([expected(bits) for bits in states])
    def run(deck, stem, sweep):
        (work/(stem+'.spice')).write_text('\n'.join(deck)+'\n')
        with (work/(stem+'.log')).open('w') as log:
            subprocess.run([str(ngspice), '-b', stem+'.spice'], cwd=work,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
                           env={**os.environ, 'OMP_NUM_THREADS': '1'})
        log = (work/(stem+'.log')).read_text()
        assert not re.search(r'(?im)^error|Timestep too small|simulation\(s\) aborted', log), log[-1500:]
        wave = np.atleast_2d(np.loadtxt(work/(stem+'.dat'), skiprows=1))
        assert np.isfinite(wave).all() and wave.ndim == 2 and wave.shape[1] == 4
        if sweep:
            assert wave.shape[0] == 512 and np.array_equal(wave[:, 0], np.arange(512))
        return wave
    def header(corner, voltage, temp, wire=None):
        return ['Extracted fallback control characterization',
                f'.include {design}', f'.lib {model} {corner}', f'.temp {temp}', text,
                f'VCORE CORE_SUPPLY 0 {voltage}',
                f'VWIRE WIRE_SUPPLY 0 {voltage if wire is None else wire}', instance(text),
                '.options klu method=gear reltol=1e-4 rshunt=1e12 cshunt=1e-17']
    def control(stem, analysis):
        return ['.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
                'save '+ ' '.join(f'v({n})' for n in OUTPUTS), analysis,
                f'wrdata {stem}.dat '+ ' '.join(f'v({n})' for n in OUTPUTS),
                'quit', '.endc', '.end']
    valid = [0, 1, 0, 1, 0, 1, 1, 0, 1]
    sequence = [valid[:]]
    for k in range(9):
        state = valid[:]
        state[k] ^= 1
        sequence += [state, valid[:]]
    period, rise, stop = 50e-9, .1e-9, len(sequence)*50e-9
    for process in envelope['process']:
        corner = 'typical' if process == 'tt' else process
        for voltage in voltages:
            for temp in temperatures:
                label = f'{corner}-{voltage:g}-{temp}'
                dc = header(corner, voltage, temp)+['VINDEX INDEX 0 0']
                for k, pin in enumerate(INPUTS):
                    dc.append(f'B{k} {pin} 0 V={voltage}*(floor(v(INDEX)/{2**k})-2*floor(v(INDEX)/{2**(k+1)}))')
                stem = 'dc-'+label
                w = run(dc+control(stem, 'dc VINDEX 0 511 1'), stem, True)
                limits = np.where(truth, w[:, 1:] >= voltage-.3, w[:, 1:] <= .3)
                assert limits.all(), f'{label}: static truth table mismatch'
                tran = header(corner, voltage, temp)
                for k, pin in enumerate(INPUTS):
                    points = [(0., voltage*sequence[0][k])]
                    previous = sequence[0][k]
                    for i, bits in enumerate(sequence[1:], 1):
                        if bits[k] != previous:
                            points += [(i*period, voltage*previous), (i*period+rise, voltage*bits[k])]
                            previous = bits[k]
                    tran.append(f'V{k} {pin} 0 PWL('+ ' '.join(f'{t:.15g} {v:g}' for t, v in points)+')')
                tran += [f'C{k} {pin} 0 50f' for k, pin in enumerate(OUTPUTS)]
                stem = 'tran-'+label
                w = run(tran+control(stem, f'tran 10p {stop:.15g} 0 100p'), stem, False)
                assert w[-1, 0] >= stop*(1-1e-9)
                for i, bits in enumerate(sequence):
                    wanted = np.array(expected(bits))
                    sample = np.array([np.interp((i+.8)*period, w[:, 0], w[:, k+1]) for k in range(3)])
                    assert np.where(wanted, sample >= voltage-.3, sample <= .3).all(), (label, i, sample)
                    if i:
                        old = expected(sequence[i-1])
                        for k in range(3):
                            if old[k] == wanted[k]:
                                continue
                            use = (w[:, 0] >= i*period)&(w[:, 0] < (i+1)*period)
                            ts, values = w[use, 0], w[use, k+1]
                            crossed = np.flatnonzero(values >= voltage/2 if wanted[k] else values <= voltage/2)
                            assert len(crossed), (label, i, k)
                            max_delay = max(max_delay, float(ts[crossed[0]]-i*period))
                cases.append(dict(corner=corner, voltage_v=voltage, temp_c=temp,
                                  static_vectors=512, dynamic_vectors=len(sequence)))
        print(f'{corner}: {len(voltages)*len(temperatures)} voltage/temperature points passed DC and loaded transient', flush=True)
    # The wired-domain controls are clamped low while its rail is off. Core
    # force must stay disabled when the actual switch's ISO is asserted.
    off = header('typical', 3.3, 27, wire=0)
    for k, pin in enumerate(INPUTS):
        off.append(f'V{k} {pin} 0 {3.3 if pin in ("ISO_wired", "FORCE_LEAF") else 0}')
    off += ['VINDEX INDEX 0 0']
    w = run(off+control('power-off', 'dc VINDEX 0 0 1'), 'power-off', False)
    assert np.max(np.abs(w[:, 1:])) < .3, 'power-off request or force not low'
    inputs = [Path(__file__).resolve(), generated/'evidence.json', extraction, ngspice, envelope_path,
              *sorted((pdk/'ngspice').glob('*spice'))]
    report = dict(status='pass', static_vectors=512*len(cases), dynamic_vectors=len(sequence)*len(cases),
                  operating_points=cases, output_load_f=50e-15, maximum_observed_50pct_delay_s=max_delay,
                  outputs_settled_within_s=.8*period, wired_power_off_force_disabled=True,
                  power_off_conditions=dict(core_v=3.3, wired_v=0, temp_c=27, corner='typical',
                                            controls_clamped_low=True, iso_asserted=True, force_requested=True),
                  source_hashes={str(p): sha(p) for p in inputs},
                  excluded=['rebinding extracted control into the assembled run',
                            'full-chip physical signoff, mismatch and analog input threshold sweeps'])
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'static_vectors', 'dynamic_vectors',
                     'maximum_observed_50pct_delay_s', 'wired_power_off_force_disabled')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated', type=Path, default=HERE/'generated')
    parser.add_argument('--work', type=Path, default=ROOT/'scratch/bringup-control-characterization')
    parser.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    parser.add_argument('--ngspice', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47/src/ngspice')
    args = parser.parse_args()
    characterize(args.generated.resolve(), args.work.resolve(), args.pdk.resolve(), args.ngspice.resolve())
