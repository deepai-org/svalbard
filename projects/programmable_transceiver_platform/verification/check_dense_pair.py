#!/usr/bin/env python3
"""Verify the AC-1 quad frame engines against the normative ten-bit codec.

pt_quad_tx / pt_quad_rx process four chronological words per engine clock
(16 quads per 64-word frame). Checked: finite quad FIFO sources, residual
words held across beats and frames (all four residual counts), both
exclusive owners, changing count/command inputs, every single header-bit
corruption, invalid ownership/sequence/command, destination refusal and
reset. Functional RTL, not clock/physical qualification.
(Make target name kept from the paired engine: transceiver-dense-pair.)
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

from stream_codec import Receiver, encode, metadata

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
MAXQ = 32


def sample(index):
    return (index*37+19) % 1024


def quad(words):
    return sum(w << (10*i) for i, w in enumerate(words))


def check(out):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    rows, tx_expected = [], []
    rng = random.Random(1234490)
    full = [0, 0]
    residual_frames = [0, 0, 0, 0]
    frames = 0

    def add(row, expected=None):
        rows.append(row)
        tx_expected.append(expected)
    for owner in (0, 1):
        add((1, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1))
        quads = popped = consumed = 0
        reserve = 0
        frame_op = frame_arg = 0
        for frame in range(360):
            quads = min(MAXQ, quads+(frame//2 if frame < 65 else MAXQ if frame < 100 else rng.randrange(0, 20)))
            payload = [sample(consumed+i) for i in range(reserve)]
            words = encode(0, [] if owner else payload, payload if owner else [], frame % 64,
                           frame_op, frame_arg, owner='iq' if owner else 'wire')
            left = reserve
            full[owner] += reserve == 59
            residual_frames[4*popped-consumed] += 1
            for beat in range(16):
                if frame > 100 and beat % 3 == 0:
                    quads = min(MAXQ, quads+rng.randrange(0, 2))
                rcnt = 4*popped-consumed
                n = 0 if beat == 0 else min(left, 3 if beat == 1 else 4)
                pop = int(n > rcnt)
                head = quad([sample(4*popped+k) for k in range(4)])
                op = (frame+beat) % 3
                arg = 0 if op == 0 else (frame+beat) % 2
                if beat == 11:   # credit snapshot beat (pt_quad_tx)
                    reserve_next = min(59, 4*quads+rcnt-left)
                    assert reserve_next >= 0
                if beat == 12:   # command capture beat (pt_quad_tx)
                    op_next, arg_next = op, arg
                out_quad = quad(words[4*beat:4*beat+4])
                add((0, owner, quads if not owner else MAXQ, quads if owner else MAXQ,
                     head, head, op, arg, out_quad, 1, 1),
                    (out_quad, pop if not owner else 0, pop if owner else 0))
                if pop:
                    assert quads > 0, 'Reference source underflow'
                    quads -= 1
                    popped += 1
                consumed += n
                left -= n
            reserve = reserve_next
            frame_op, frame_arg = op_next, arg_next
            frames += 1
        # Drain the RX input register's final quad before changing owner/reset.
        add((0, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1))
    negatives = 0
    for owner in (0, 1):
        base = encode(0, [] if owner else [17, 39, 61, 83, 105], [17, 39, 61, 83, 105] if owner else [],
                      0, owner='iq' if owner else 'wire')
        cases = []
        for bit in range(50):
            words = list(base)
            words[bit//10] ^= 1 << (bit % 10)
            cases.append((words, None))
        for wc, qc, seq, op, arg in [(1, 1, 0, 0, 0), (0 if owner else 60, 60 if owner else 0, 0, 0, 0),
                                      (0, 0, 1, 0, 0), (0, 0, 0, 15, 0), (0, 0, 0, 1, 2)]:
            cases.append((metadata(wc, qc, seq, op, arg)+[0]*59, None))
        cases += [(base, 2), (base, 3)]  # guard payload / following quad refusals
        for words, refuse_processing_cycle in cases:
            add((1, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1))
            for beat in range(18):
                q = quad(words[4*beat:4*beat+4]) if beat < 16 else 0
                refused = beat == refuse_processing_cycle
                add((0, owner, 0, 0, 0, 0, 0, 0, q,
                     int(owner or not refused), int(not owner or not refused)))
            negatives += 1
    with (out/'vectors.txt').open('w') as f:
        for row in rows:
            f.write(' '.join(f'{value:x}' for value in row)+'\n')
    sources = [PROJECT/'sim/tb_dense_pair.sv', PROJECT/'rtl/pt_quad_link.sv', PROJECT/'rtl/pt_dense_header.sv']
    subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_pair',
                    '-o', str(out/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, check=True, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    lines = (out/'actual.txt').read_text().splitlines()
    assert len(lines) == len(rows)
    decoder = None
    pending = None
    received = 0
    for cycle, (line, row, expected) in enumerate(zip(lines, rows, tx_expected)):
        values = [int(value, 16) for value in line.split()]
        if expected is not None:
            assert tuple(values[:3]) == expected, (cycle, 'TX', [hex(v) for v in values[:3]], [hex(e) for e in expected])
        if row[0]:
            decoder = Receiver(0, owner='iq' if row[1] else 'wire')
            pending = None
            fault_before = False
            words_out = []
            command = None
        else:
            fault_before = decoder.fault
            words_out = []
            command = None
            if pending is not None and not decoder.fault:
                for k in range(4):
                    try:
                        event = decoder.feed((pending >> (10*k)) & 1023)
                    except ValueError:
                        break
                    if event is None:
                        continue
                    if event[0] == 'command':
                        command = event[1]
                    else:
                        if not row[10 if row[1] else 9]:
                            decoder.fault = True
                            break
                        words_out.append(event[1])
            pending = row[8]
        count = len(words_out)
        expected_rx = (count if not row[1] else 0, count if row[1] else 0,
                       int(command is not None), int(fault_before))
        assert tuple(values[4:8]) == expected_rx, (cycle, 'RX flags', values[4:8], expected_rx)
        if count:
            mask = (1 << (10*count))-1
            assert values[3] & mask == quad(words_out), (cycle, 'RX data', hex(values[3]), words_out)
            received += count
        if command is not None:
            assert values[8] == (command[0] << 8 | command[1]), (cycle, 'command')
    assert all(full) and all(residual_frames), residual_frames
    sources += [Path(__file__).resolve(), PROJECT/'verification/stream_codec.py', PROJECT/'verification/transport_model.py',
                PROJECT/'rtl/pt_schedule.vh']
    result = dict(status='pass', frames=frames, engine_cycles=len(rows), received_words=received,
                  full_quota_frames=dict(wire=full[0], iq=full[1]),
                  frames_by_initial_residual_words=residual_frames, negative_cases=negatives,
                  scope='quad-engine functional RTL; no physical timing or hierarchy integration claimed',
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-pair')
    check(parser.parse_args().output_dir.resolve())
