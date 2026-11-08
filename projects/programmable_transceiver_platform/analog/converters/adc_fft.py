#!/usr/bin/env python3
"""Single-tone coherent FFT of the extracted ADC (tt, 27 C, 3.3 V, 20 MS/s).
Writes generated/<block>-fft.json. Runtime is hours (extracted transient)."""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'lib'))
sys.path.insert(0, str(HERE))
import benches  # noqa: E402
import convkit as ck  # noqa: E402

block = sys.argv[1] if len(sys.argv) > 1 else 'adc_i'
n = int(sys.argv[2]) if len(sys.argv) > 2 else 32
work = HERE.parents[3] / 'scratch' / 'converters' / f'{block}_fft'
shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True)
shutil.copy(HERE / 'generated' / f'{block}.ext.spice', work / 'ext.spice')
m = benches.adc_fft(work, 'ext.spice', f'pt_{block}', n=n)
m['netlist_sha256'] = ck.sha256(HERE / 'generated' / f'{block}.ext.spice')
(HERE / 'generated' / f'{block}-fft.json').write_text(json.dumps(m, indent=2) + '\n')
print(json.dumps({k: v for k, v in m.items() if k != 'codes'}))
