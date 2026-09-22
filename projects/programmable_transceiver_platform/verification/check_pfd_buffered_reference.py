#!/usr/bin/env python3
"""Check the actual input-buffer diagnostic, including unsuccessful horizons."""
import hashlib
import json
import re
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'projects/programmable_transceiver_platform'
WORK = ROOT / 'scratch/transceiver-pfd-buffered-reference'
BASE = ROOT / 'scratch/transceiver-pfd-pump-breakpoint'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def rising(t, v):
    ix = np.flatnonzero((v[:-1] < 1.65) & (v[1:] >= 1.65))
    return t[ix] + (1.65-v[ix])*(t[ix+1]-t[ix])/(v[ix+1]-v[ix])

manifest = json.loads((WORK/'manifest.json').read_text())
raw = json.loads((WORK/'result.json').read_text())
assert raw['source_sha256_before'] == raw['source_sha256_after'] == manifest['source_sha256_before']
for path, digest in raw['source_sha256_before'].items():
    if path.startswith('/screen/'):
        assert sha(PROJECT/'analog'/path.removeprefix('/screen/')) == digest
assert {c['name'] for c in raw['cases']} == {'pulse', 'pwl'}
rows = []
for case in raw['cases']:
    name = case['name']
    source = BASE/f'{name}_skew0.spice'
    assert sha(source) == case['baseline_deck_sha256']
    for ext, digest in case['artifacts_sha256'].items():
        assert sha(WORK/(name+ext)) == digest
    deck = (WORK/(name+'.spice')).read_text()
    addition = '.include /screen/pll/reference_input_buffer.spice\nXREFBUF REFRAW REF VDIV 0 pt_reference_input_buffer\n'
    circuit = deck.split('.control')[0]
    assert circuit.count(addition) == 1
    restored = circuit.replace(addition, '').replace('VREF REFRAW 0 ', 'VREF REF 0 ')
    assert restored == source.read_text().split('.control')[0]
    assert 'tran 2p 800n 0 2p uic' in deck
    wave = WORK/(name+'.dat')
    with wave.open() as stream:
        assert stream.readline().lower().split() == ['time','v(refraw)','v(ref)','v(fb)','v(up)','v(dn)','v(ctrl)','i(vsense)']
    a = np.loadtxt(wave, skiprows=1)
    assert a.shape[1] == 8 and np.isfinite(a).all()
    t = a[:,0]
    assert np.all(np.diff(t) > 0)
    log = (WORK/(name+'.log')).read_text()
    failure = re.search(r'Timestep too small; time = ([0-9.e+-]+)', log)
    done = case['returncode'] == 0 and 'aborted' not in log.lower() and t[-1] >= 800e-9
    inputs = rising(t, a[:,1]); outputs = rising(t, a[:,2])
    delays = []
    for edge in inputs[inputs >= 100e-9]:
        following = outputs[(outputs >= edge) & (outputs < edge+5e-9)]
        if following.size:
            delays.append(float((following[0]-edge)*1e12))
    window = (t >= 203e-9) & (t <= 305.4e-9)
    assert window.sum() > 10 and delays
    rows.append(dict(name=name, returncode=case['returncode'], completed_requested_horizon=bool(done),
        actual_stop_ns=float(t[-1]*1e9), failure_time_ns=float(failure.group(1))*1e9 if failure else None,
        rising_delay_ps_range=[min(delays),max(delays)], matched_rising_edges=len(delays),
        control_range_v=[float(a[:,6].min()),float(a[:,6].max())],
        measurement_window_ns=[203,305.4],
        pump_charge_fc=float(np.trapezoid(a[window,7],t[window])*1e15),
        up_range_v=[float(a[window,4].min()),float(a[window,4].max())],
        dn_range_v=[float(a[window,5].min()),float(a[window,5].max())],
        last_saved_state=dict(zip(['refraw_v','reference_v','feedback_v','up_v','dn_v','control_v','pump_current_a'],map(float,a[-1,1:])))))
result = dict(status='complete_buffered_reference_diagnostic', cases=rows,
    provenance=raw, declared_circuit_change_verified=True,
    limitations=['Actual two-inverter buffer; no pad, ESD, independent supply impedance or corner qualification.',
                 'Forced feedback excludes autonomous VCO/divider and RF loading.',
                 'Propagation delay changes physical phase; completion is not lock or jitter qualification.',
                 'Failed cases retain partial observations; no simulator defect or physical instability attribution.'])
(PROJECT/'evidence/pfd-buffered-reference-screen.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(rows,indent=2))
