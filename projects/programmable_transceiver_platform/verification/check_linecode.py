#!/usr/bin/env python3
"""IX-2 8b/10b offload (rtl/pt_linecode.sv) against the reference code (verification/linecode_8b10b.py).

TX: random data/control symbols (every valid K, random bytes), packed 9-bit LSB-first into 40-bit
quads, through pt_lc_tx with random consumer stalls; the encoded stream must equal the reference
encoder's (running disparity carried across symbols and quads).
RX: the reference-encoded stream (K28.5 commas sprinkled), slipped by every bit offset 0..39,
with random valid gaps, through pt_lc_rx; the decoded symbols must be a contiguous run of the
original symbols from the second K28.5 on (two agreeing commas align), with no code error; one case injects an
invalid code group and must flag code_error and decode it as {K=1, 0x00}.
Then sim/tb_linecode_stream.sv: 3.125 Gb/s wired loopback with the offload in both directions through
the host link and core at 97.6 % host load. Prints LINECODE_PASS."""
import random, subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'verification'))
from linecode_8b10b import encode, decode, VALID_K

def pack(vals, width):
    bits = 0
    for i, v in enumerate(vals):
        bits |= v << (width * i)
    n = (len(vals) * width) // 40
    return [(bits >> (40 * i)) & ((1 << 40) - 1) for i in range(n)]

def unpack(quads, width):
    bits = 0
    for i, q in enumerate(quads):
        bits |= q << (40 * i)
    n = (len(quads) * 40) // width
    return [(bits >> (width * i)) & ((1 << width) - 1) for i in range(n)]

def symbols(rng, n, comma_every=7):
    out = []
    for i in range(n):
        if i % comma_every == 0:
            out.append(0x1BC)
        elif rng.random() < 0.08:
            out.append(0x100 | rng.choice(sorted(VALID_K - {0xFC})))   # K28.7 is a test pattern only
        else:
            out.append(rng.randrange(256))
    return out

def run(work, tx_quads, rx_quads):
    (work / 'tx_in.hex').write_text(''.join(f'{q:010x}\n' for q in tx_quads) or '0\n')
    (work / 'rx_in.hex').write_text(''.join(f'{q:010x}\n' for q in rx_quads) or '0\n')
    r = subprocess.run(['vvp', str(work / 'b.vvp'), f'+NTX={len(tx_quads)}', f'+NRX={len(rx_quads)}'],
                       cwd=work, capture_output=True, text=True)
    assert 'LC_BENCH_DONE' in r.stdout, r.stdout + r.stderr
    tx = [int(l, 16) for l in (work / 'tx_out.hex').read_text().split()]
    lines = (work / 'rx_out.hex').read_text().splitlines()
    st = [l for l in lines if l.startswith('S')][0].split()
    rx = [int(l, 16) for l in lines if not l.startswith('S')]
    return tx, rx, int(st[1]), int(st[2])

def main():
    rng = random.Random(2026)
    work = Path(tempfile.mkdtemp(prefix='linecode-'))
    subprocess.run(['iverilog', '-g2012', '-I', str(P / 'rtl'), '-s', 'tb_linecode', '-o', str(work / 'b.vvp'),
                    str(P / 'sim/tb_linecode.sv'), str(P / 'rtl/pt_linecode.sv')], check=True)
    # TX
    syms = symbols(rng, 40 * 30)
    tx, _, _, _ = run(work, pack(syms, 9), [])
    rd, ref = -1, []
    for v in syms:
        c, rd = encode(v & 255, bool(v >> 8), rd)
        ref.append(c)
    ref_q = pack(ref, 10)
    assert len(tx) >= len(ref_q) - 2, (len(tx), len(ref_q))
    assert tx == ref_q[:len(tx)], 'TX encoded stream mismatch'
    cases = 0
    for slip in range(40):
        for bad in ((False, True) if slip in (0, 13, 27) else (False,)):
            syms = symbols(rng, 400)
            rd, codes = -1, []
            for v in syms:
                c, rd = encode(v & 255, bool(v >> 8), rd)
                codes.append(c)
            if bad:
                codes[200] = 0b1111111111 & ~0b0000000011 if decode(0b1111111100) == 0x100 else 0
            bits = sum(c << (10 * i) for i, c in enumerate(codes)) << slip
            nb = 10 * len(codes) + slip
            quads = [(bits >> (40 * i)) & ((1 << 40) - 1) for i in range(nb // 40)]
            _, rx, aligned, cerr = run(work, [], quads)
            out = unpack(rx, 9)
            assert aligned == 1, slip
            want = [decode(c) for c in codes]
            # contiguous run starting at or before the first comma
            first = [i for i, v in enumerate(want) if v == 0x1BC][1]
            # delivery starts at a symbol boundary after the second agreeing comma (the aligning quad
            # itself is not delivered); every delivered symbol must follow without a gap
            hit = next((st for st in range(first + 8) if want[st:st + len(out)] == out), None)
            assert hit is not None and len(out) >= len(want) - 28, (slip, bad, len(out), out[:6], want[:6])
            assert cerr == (1 if bad else 0), (slip, bad, cerr)
            if bad:
                assert 0x100 in out
            cases += 1
    # end to end: 3.125 Gb/s wired loopback through the host link and core with the offload on
    rtl = ['pt_host_link.sv', 'pt_core.sv', 'pt_quad_link.sv', 'pt_quad_gearbox.sv', 'pt_linecode.sv',
           'pt_dense_header.sv', 'pt_fifo.sv', 'pt_cells.sv', 'pt_pattern.sv']
    subprocess.run(['iverilog', '-g2012', '-I', str(P / 'rtl'), '-s', 'tb_linecode_stream', '-o', str(work / 's.vvp'),
                    str(P / 'sim/tb_linecode_stream.sv'), str(P / 'sim/pt_transport_harness.sv'),
                    str(P / 'sim/reference/pt_dense_transport.sv'), *[str(P / 'rtl' / r) for r in rtl]],
                   check=True, capture_output=True)
    r = subprocess.run(['vvp', '-n', str(work / 's.vvp')], cwd=work, capture_output=True, text=True)
    stream = [l for l in r.stdout.splitlines() if 'LINECODE_STREAM' in l or 'ERROR' in l]
    assert any('LINECODE_STREAM_PASS' in l for l in stream), stream
    print(stream[-1])
    print(f'LINECODE_PASS tx_symbols={len(syms)} rx_cases={cases} slips=0..39 stream=3.125Gb/s')

if __name__ == '__main__':
    main()
