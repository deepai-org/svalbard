#!/usr/bin/env python3
"""Collect 'name = value' measurements from <group>/*.log into <group>/results.json and print a table."""
import json, re, sys
from pathlib import Path
W = Path(__file__).resolve().parent
NUM = r'([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'
for g in sys.argv[1:]:
    res = {}
    for f in sorted((W / g).glob('*.log')):
        t = f.read_text(errors='replace')
        v = {m.group(1).lower(): float(m.group(2)) for m in re.finditer(r'^\s*([a-z_0-9]+)\s*=\s*' + NUM, t, re.M | re.I)}
        v['_aborted'] = bool(re.search(r'aborted|Timestep too small|singular', t))
        v['_failed_meas'] = re.findall(r'meas \w+ (\w+) .* failed!', t)
        res[f.stem] = v
    (W / g / 'results.json').write_text(json.dumps(res, indent=1, sort_keys=True))
    for k, v in res.items():
        print(k, ' '.join(f'{a}={b:.4g}' if isinstance(b, float) else f'{a}={b}' for a, b in v.items() if b not in (False, [])))
