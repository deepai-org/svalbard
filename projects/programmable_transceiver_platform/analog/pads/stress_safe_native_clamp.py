"""Selected rail shunt on the canonical clamp as laid out (no gate discharge).

The canonical protection-network layout does not contain the schematic 100 kohm
gate-discharge resistor used by the stress-safe sweep. This check reuses the
recorded unmodified long-hold fixture (stuck-clamp baseline) with the same
pulse, windows and screens, to show whether the shunt alone is sufficient.
"""
import argparse
import hashlib
import json
from pathlib import Path

import stress_safe_clamp as s

NATIVE_DECK = 'clamp_long_hold.spice'
NATIVE_DECK_SHA256 = '8a60cea559bf5b79dcec9553cefb60be64940988da0e99c02da063620ad01d75'

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--fixture-dir', type=Path, default=s.SCRATCH / 'pad-supervised-receive')
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--variants', nargs='*', default=['released_baseline', 'stack3_w12000'])
    p.add_argument('--corners', nargs='*', default=['typical:27', 'ss:0'])
    a = p.parse_args()
    source = a.fixture_dir.resolve() / NATIVE_DECK
    if s.sha(source) != NATIVE_DECK_SHA256:
        raise ValueError('Native long-hold fixture differs from the recorded deck')
    base = source.read_text().split('.control')[0]
    out = [s.pulse_variant(a.output_dir.resolve(), base, v, s.VARIANTS[v], c.split(':')[0], int(c.split(':')[1]))
           for v in a.variants for c in a.corners]
    a.report.write_text(json.dumps(dict(fixture=str(source), fixture_sha256=NATIVE_DECK_SHA256, gate_discharge=False,
                                        pulses=out, source_sha256={Path(f).name: s.sha(f) for f in (__file__, s.__file__)}), indent=1) + '\n')
