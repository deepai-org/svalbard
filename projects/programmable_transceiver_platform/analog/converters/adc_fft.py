#!/usr/bin/env python3
"""Coherent single-tone FFT of the extracted ADC (benches.adc_fft).

    python3 adc_fft.py adc_i [--n 1024] [--cycles 487] [--corner ss,32,3.15]
                             [--ilen 1] [--refbuf] [--workers 2] [--tag name]

Default: 2-way interleaved, 40 MS/s (25 ns clock, 6 ns acquisition), 1024
points, tone in bin 487 (19.02 MHz, near Nyquist), 1.6 V diff peak (-0.75 dBFS),
tt/27C/3.3V, ideal VREF. The run is split into N/64 chunks of 64 (+2 warm-up)
conversions that run in parallel on one continuous sine. Each chunk takes
~45-60 min of extracted transient; results go to generated/<block>-fft-<tag>.json
and are merged into generated/<block>-fft.json. Chunk outputs are kept under
scratch/converters/<block>_fft_<tag>/ so an interrupted run resumes.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'lib'))
sys.path.insert(0, str(HERE))
import benches  # noqa: E402
import convkit as ck  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('block', nargs='?', default='adc_i')
ap.add_argument('--n', type=int, default=1024)
ap.add_argument('--cycles', type=int, default=487)
ap.add_argument('--corner', default='typical,27,3.3')
ap.add_argument('--ilen', type=int, default=1)
ap.add_argument('--period', type=float, default=25e-9)
ap.add_argument('--acq', type=float, default=6e-9)
ap.add_argument('--amp', type=float, default=1.6)
ap.add_argument('--refbuf', action='store_true')
ap.add_argument('--workers', type=int, default=2)
ap.add_argument('--tag', default=None)
ap.add_argument('--chunk', type=int, default=64,
                help='conversions per parallel deck; 16 keeps one extracted deck well inside the 7200 s sim timeout')
a = ap.parse_args()
p_, t_, v_ = a.corner.split(',')
corner = (p_, float(t_), float(v_))
tag = a.tag or f"{p_}_{t_}C_{v_}V_b{a.cycles}{'_rb' if a.refbuf else ''}{'' if a.ilen else '_single'}"
work = HERE.parents[3] / 'scratch' / 'converters' / f'{a.block}_fft_{tag}'
work.mkdir(parents=True, exist_ok=True)
net = HERE / 'generated' / f'{a.block}.ext.spice'
if (work / 'ext.spice').exists() and ck.sha256(work / 'ext.spice') != ck.sha256(net):
    shutil.rmtree(work)          # netlist changed: chunks are stale
    work.mkdir(parents=True)
shutil.copy(net, work / 'ext.spice')
if a.refbuf:
    shutil.copy(HERE / 'generated' / 'refbuf.ext.spice', work / 'refbuf.ext.spice')
m = benches.adc_fft(work, 'ext.spice', f'pt_{a.block}', corner=corner, n=a.n, cycles=a.cycles, period=a.period,
                    acq=a.acq, amp=a.amp, ilen=a.ilen, refbuf=a.refbuf, workers=a.workers, chunk=a.chunk)
m['netlist_sha256'] = ck.sha256(net)
m['bench_sha256'] = ck.sha256(HERE / 'benches.py')
if a.refbuf:
    m['refbuf_netlist_sha256'] = ck.sha256(HERE / 'generated' / 'refbuf.ext.spice')
(HERE / 'generated' / f'{a.block}-fft-{tag}.json').write_text(json.dumps(m, indent=2) + '\n')
merged = HERE / 'generated' / f'{a.block}-fft.json'
allr = {}
if merged.exists():
    try:
        old = json.loads(merged.read_text())
        allr = old.get('runs', {}) if isinstance(old, dict) else {}
    except ValueError:
        allr = {}
allr[tag] = {k: v for k, v in m.items() if k != 'codes'}
merged.write_text(json.dumps(dict(note='per-run summaries; codes in <block>-fft-<tag>.json', runs=allr), indent=2) + '\n')
print(json.dumps({k: v for k, v in m.items() if k != 'codes'}))
