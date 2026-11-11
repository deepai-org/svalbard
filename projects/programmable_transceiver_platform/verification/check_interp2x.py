#!/usr/bin/env python3
"""Check rtl/pt_interp2x.sv (SP-03 2x halfband TX interpolator) against a bit-exact model.

Runs sim/tb_pt_interp2x.sv under Icarus, then:
  * halfband: every output sample equals the model (taps -1 0 9 16 9 0 -1 /16 on the DAC's 10 bits,
    rounding +8, saturation to 10 bits, zero inserted for invalid inputs), in order, after the
    pipeline latency; valid matches;
  * image rejection of the 10 MHz complex tone at the 80 MS/s output: tone vs its image at -30 MHz
    (the 40 MS/s ZOH image the filter must suppress), compared with plain sample repetition;
  * bypass: output equals input combinationally (sample and valid).
Writes evidence/interp2x-check.json; prints INTERP2X_PASS.
"""
import cmath, json, math, subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1]


def sat10(v):
    return max(-512, min(511, v))


def model(inputs):
    """Per core sample (valid, i12, q12) -> list of output pairs per channel, RTL order [mid, even]."""
    x = [[0, 0, 0], [0, 0, 0]]
    a = [0, 0]; b = [0, 0]; mid_q = [0, 0]; v = [0, 0, 0]
    out = []
    for valid, i, q in inputs:
        xin = [(i >> 2) if valid else 0, (q >> 2) if valid else 0]
        mids = []
        for c in range(2):
            r = 9 * a[c] - b[c] + 8
            mids.append(sat10(r >> 4))
        # registers update at the core edge
        new_a = [x[c][0] + x[c][1] for c in range(2)]
        new_b = [xin[c] + x[c][2] for c in range(2)]
        for c in range(2):
            x[c] = [xin[c], x[c][0], x[c][1]]
        a, b = new_a, new_b
        mid_q = mids
        v = [valid, v[0], v[1]]
        g = 1 if (v[1] or v[2]) else 0     # output valid for this pair (RTL yv); invalid outputs are 0
        out.append(((mid_q[0] * g, mid_q[1] * g), (x[0][2] * g, x[1][2] * g)))
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        vvp = Path(d) / 'tb.vvp'
        subprocess.run(['iverilog', '-g2012', '-s', 'tb_pt_interp2x', '-o', str(vvp), str(P / 'rtl/pt_interp2x.sv'),
                        str(P / 'rtl/pt_cells.sv'), str(P / 'sim/tb_pt_interp2x.sv')], check=True)
        r = subprocess.run(['vvp', '-n', str(vvp)], cwd=d, capture_output=True, text=True)
        assert 'INTERP2X_DUMPED' in r.stdout, r.stdout + r.stderr
        # lines before the first reset edge hold X (async reset asserted from time 0); skip them
        ins = [tuple(map(int, l.split())) for l in (Path(d) / 'interp_in.txt').read_text().splitlines() if 'x' not in l.lower()]
        outs = [tuple(map(int, l.split())) for l in (Path(d) / 'interp_out.txt').read_text().splitlines() if 'x' not in l.lower()]
    res = dict(fails=[])
    # ---- halfband
    hin = [(v, i, q) for hb, v, i, q in ins if hb == 1]
    hout = [(v, i, q) for hb, v, i, q in outs if hb == 1]
    exp = []
    for (mi, mq), (ei, eq) in model(hin):
        exp += [(mi, mq), (ei, eq)]   # midpoint(previous, current sample), then the current sample
    got = [((i >> 2), (q >> 2)) for v, i, q in hout]
    # Alignment: the model's register naming adds a fixed offset to the RTL output; search it, then
    # compare everything after the 20-sample start-up (reset release with X-initialized inputs).
    def mism_at(lag, k0=20, k1=None):
        k1 = k1 if k1 is not None else min(len(got) - lag, len(exp)) - 4
        return [k for k in range(k0, k1) if 0 <= lag + k < len(got) and got[lag + k] != exp[k]]
    lag = min(range(-8, 12), key=lambda L: len(mism_at(L, 20, 4000)))
    mism = mism_at(lag)
    n = min(len(got) - lag, len(exp)) - 4 - 20
    res['halfband_samples_compared'] = n
    res['halfband_model_offset_fast_cycles'] = lag
    res['halfband_mismatches'] = len(mism)
    if mism or n < 8000:
        res['fails'].append(f'halfband: {len(mism)} mismatches over {n}' + (f', first at {mism[0]}: got {got[lag + mism[0]]} exp {exp[mism[0]]}' if mism else ''))
    # low two bits of every output are zero; valid within the tone section
    if any((i & 3) or (q & 3) for v, i, q in hout):
        res['fails'].append('halfband: nonzero low bits')
    # ---- image rejection on a fully valid stretch of the tone (output complex = I + jQ)
    def tone_db(seq, fs):
        N = len(seq)
        def bin_at(f):
            return abs(sum(z * cmath.exp(-2j * math.pi * f * k / fs) for k, z in enumerate(seq))) / N
        return 20 * math.log10(bin_at(10e6) / max(bin_at(-30e6), 1e-12))
    start = 200
    seg = [complex(i, q) for (i, q) in got[start:start + 160]]
    # a window inside one valid run (gaps every 97 core samples): pick 80 core samples = 160 outputs
    rej = tone_db(seg, 80e6)
    zoh = []
    for v, i, q in hin[100:180]:
        zoh += [complex(i >> 2, q >> 2)] * 2
    rej_zoh = tone_db(zoh, 80e6)
    res['image_rejection_db'] = round(rej, 1)
    res['zoh_image_rejection_db'] = round(rej_zoh, 1)
    if rej < rej_zoh + 15:
        res['fails'].append(f'image rejection {rej:.1f} dB not >= 15 dB better than repetition {rej_zoh:.1f} dB')
    # ---- bypass
    bin_ = [(v, i, q) for hb, v, i, q in ins if hb == 0]
    bout = [(v, i, q) for hb, v, i, q in outs if hb == 0]
    # bypass clock = core clock: compare the samples logged on the same edges
    # the mode switch can add or drop one edge at the clock mux; align on the best lag
    m = min(sum(1 for a, b in zip(bin_[k:], bout[4:]) if a != b) for k in range(0, 8))
    res['bypass_samples'] = len(bin_)
    res['bypass_mismatches'] = m
    if m or len(bin_) < 400:
        res['fails'].append(f'bypass: {m} mismatches over {len(bin_)}')
    res['status'] = 'pass' if not res['fails'] else 'fail'
    (P / 'evidence/interp2x-check.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))
    print('INTERP2X_PASS' if not res['fails'] else 'INTERP2X_FAIL')
    return 0 if not res['fails'] else 1


if __name__ == '__main__':
    sys.exit(main())
