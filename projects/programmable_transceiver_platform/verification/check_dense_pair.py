#!/usr/bin/env python3
"""Verify the paired transport against the normative ten-bit frame codec.

Finite pair FIFOs, odd-word carry between frames, both exclusive owners,
changing count/command inputs, single-bit header damage, invalid ownership,
refusal and reset. This is functional RTL, not clock/physical qualification.
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


def check(out):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    rows, tx_expected = [], []
    rng = random.Random(1234490)
    full = [0, 0]
    odd_carry_frames = 0
    frames = 0
    def add(row, expected=None):
        rows.append(row)
        tx_expected.append(expected)
    def sample(index):
        return (index*37+19) % 1024
    for owner in (0, 1):
        add((1, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1))
        pairs = 0
        word_index = 0
        reserve = 0
        frame_op = frame_arg = 0
        for frame in range(360):
            pairs = min(64, pairs+(frame if frame < 65 else 64 if frame < 100 else rng.randrange(0, 40)))
            payload = [sample(word_index+i) for i in range(reserve)]
            words = encode(0, [] if owner else payload, payload if owner else [], frame % 64,
                           frame_op, frame_arg, owner='iq' if owner else 'wire')
            left = reserve
            if reserve == 59:
                full[owner] += 1
            odd_carry_frames += word_index % 2
            for beat in range(32):
                if frame > 100 and beat % 5 == 0:
                    pairs = min(64, pairs+rng.randrange(0, 3))
                amount = 0 if beat < 2 else min(left, 1 if beat == 2 else 2)
                pop = int((word_index+amount+1)//2 > (word_index+1)//2)
                pair_index = (word_index+1)//2
                head = sample(2*pair_index) | (sample(2*pair_index+1) << 10)
                op = (frame+beat) % 3
                arg = 0 if op == 0 else (frame+beat) % 2
                if beat == 24:
                    reserve_next = min(59, 2*pairs+(word_index % 2)-left)
                    assert reserve_next >= 0
                    op_next, arg_next = op, arg
                pair = words[2*beat] | (words[2*beat+1] << 10)
                add((0, owner, pairs if not owner else 64, pairs if owner else 64,
                     head, head, op, arg, pair, 1, 1),
                    (pair, pop if not owner else 0, pop if owner else 0))
                if pop:
                    assert pairs > 0, 'Reference source underflow'
                    pairs -= 1
                word_index += amount
                left -= amount
            reserve = reserve_next
            frame_op, frame_arg = op_next, arg_next
            frames += 1
        # Drain the RX input register's final pair before changing owner/reset.
        add((0, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1))
    negatives = 0
    for owner in (0, 1):
        base = encode(0, [] if owner else [17, 39, 61], [17, 39, 61] if owner else [],
                      0, owner='iq' if owner else 'wire')
        cases = []
        for bit in range(50):
            words = list(base)
            words[bit//10] ^= 1 << (bit % 10)
            cases.append((words, None))
        for wc, qc, seq, op, arg in [(1, 1, 0, 0, 0), (0 if owner else 60, 60 if owner else 0, 0, 0, 0),
                                      (0, 0, 1, 0, 0), (0, 0, 0, 15, 0), (0, 0, 0, 1, 2)]:
            cases.append((metadata(wc, qc, seq, op, arg)+[0]*59, None))
        cases += [(base, 3), (base, 4)]  # guard payload / following pair refusals
        for words, refuse_processing_cycle in cases:
            add((1, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1))
            for beat in range(36):
                pair = (words[2*beat] | (words[2*beat+1] << 10)) if beat < 32 else 0
                refused = beat == refuse_processing_cycle
                add((0, owner, 0, 0, 0, 0, 0, 0, pair,
                     int(owner or not refused), int(not owner or not refused)))
            negatives += 1
    with (out/'vectors.txt').open('w') as f:
        for row in rows:
            f.write(' '.join(f'{value:x}' for value in row)+'\n')
    sources = [PROJECT/'sim/tb_dense_pair.sv', PROJECT/'rtl/pt_dense_pair.sv', PROJECT/'rtl/pt_dense_header.sv']
    subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_pair',
                    '-o', str(out/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, check=True, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    lines = (out/'actual.txt').read_text().splitlines()
    assert len(lines) == len(rows)
    decoder = None
    pending_pair = None
    received = 0
    for cycle, (line, row, expected) in enumerate(zip(lines, rows, tx_expected)):
        values = [int(value, 16) for value in line.split()]
        if expected is not None:
            assert tuple(values[:3]) == expected, (cycle, 'TX', values[:3], expected)
        if row[0]:
            decoder = Receiver(0, owner='iq' if row[1] else 'wire')
            pending_pair = None
            fault_before = False
            words_out = []
            command = None
        else:
            fault_before = decoder.fault
            words_out = []
            command = None
            if pending_pair is not None and not decoder.fault:
                for word in (pending_pair & 1023, pending_pair >> 10):
                    try:
                        event = decoder.feed(word)
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
            pending_pair = row[8]
        count = len(words_out)
        expected_rx = (count if not row[1] else 0, count if row[1] else 0,
                       int(command is not None), int(fault_before))
        assert tuple(values[4:8]) == expected_rx, (cycle, 'RX flags', values[4:8], expected_rx)
        if count:
            mask = (1 << (10*count))-1
            packed = sum(word << (10*i) for i, word in enumerate(words_out))
            assert values[3] & mask == packed, (cycle, 'RX data', values[3], packed)
            received += count
        if command is not None:
            assert values[8] == (command[0] << 8 | command[1]), (cycle, 'command')
    assert all(full) and odd_carry_frames > 100
    sources += [Path(__file__).resolve(), PROJECT/'verification/stream_codec.py', PROJECT/'verification/transport_model.py',
                PROJECT/'rtl/pt_schedule.vh']
    result = dict(status='pass', frames=frames, engine_cycles=len(rows), received_words=received,
                  full_quota_frames=dict(wire=full[0], iq=full[1]), odd_carry_frames=odd_carry_frames,
                  negative_cases=negatives,
                  scope='paired-engine functional RTL; no physical timing or hierarchy integration claimed',
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-pair')
    check(parser.parse_args().output_dir.resolve())
