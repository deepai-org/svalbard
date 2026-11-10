#!/usr/bin/env python3
"""Check exclusive RTL against the independent normative frame codec.

Uses finite source queues, both owners, count boundaries, same-frame FIFO
consumption, all single header-bit corruptions, inactive-source/count/command
violations, destination refusal, sticky faults and reset/retraining boundaries.
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
    vectors, expected = [], []
    random_source = random.Random(93218)
    frames = 0
    full_frames = 0
    full_by_owner = [0, 0]

    def add(row, tx=None, rx=None):
        vectors.append(row)
        expected.append((tx, rx))

    # Source queue accounting is external to RTL. A word is consumed exactly
    # on its payload beat, with no early bank filling or hidden staging delay.
    for owner in (0, 1):
        add((1, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1), rx=(0, 0, 0, 0, 0))
        count = 0
        source_index = 0
        word_list = []
        next_count = 0
        next_op = next_arg = 0
        receiver_command = 0
        for frame in range(420):
            if frame < 80:
                # Counts at and around every legal quota, including saturation.
                target = min(frame, 63 if owner else 127)
                count = max(count, target)
            elif frame < 160:
                count = 63 if owner else 127
            else:
                count = min((63 if owner else 127), count+random_source.randrange(0, 64))
            snapshot_words = list(word_list)
            frame_command = (next_op << 8) | next_arg
            plan = encode(0, [] if owner else snapshot_words, snapshot_words if owner else [],
                          frame % 64, next_op, next_arg, owner='iq' if owner else 'wire')
            # An independent receiver must also accept exactly the generated
            # normative frame, and exercises the RTL receive half in lockstep.
            decoder = Receiver(0, owner='iq' if owner else 'wire')
            decoder.sequence = frame % 64
            capacity_before = count
            reserved = len(word_list)
            assert reserved <= capacity_before
            if reserved == 59:
                full_frames += 1
                full_by_owner[owner] += 1
            for pos in range(64):
                if frame >= 160 and pos % 7 == 0:
                    count = min(63 if owner else 127, count+random_source.randrange(0, 4))
                selected_pop = int(pos >= 5 and pos-5 < reserved)
                current_data = (source_index*37+19) % 1024
                value = current_data if selected_pop else plan[pos] if pos < 5 else 0
                assert value == plan[pos]
                wcount = (63 if owner else count)
                qcount = (count if owner else 63)
                command = (frame % 3, 0 if frame % 3 == 0 else frame % 2)
                # The advertised count must reserve what remains after this
                # frame, including the eight final same-frame pops.
                if pos == 56:
                    next_count = min(59, count-max(0, reserved-(pos-5)))
                    assert next_count >= 0
                    next_op, next_arg = command
                event = decoder.feed(plan[pos])
                rx = (int(event is not None and event[0] == 'wire'),
                      int(event is not None and event[0] == 'iq'),
                      int(pos == 5), 0, receiver_command)
                # command_valid is a registered pulse one beat after guard.
                add((0, owner, wcount, qcount, current_data, current_data,
                     *command, plan[pos], 1, 1),
                    tx=(value, selected_pop if not owner else 0, selected_pop if owner else 0), rx=rx)
                if pos == 4:
                    receiver_command = frame_command
                if selected_pop:
                    assert count > 0, 'external finite source underflow'
                    count -= 1
                    source_index += 1
            word_list = [((source_index+i)*37+19) % 1024 for i in range(next_count)]
            frames += 1

    negative_cases = 0
    # Independently encoded RX negatives start at frame zero after reset.
    for owner in (0, 1):
        base = encode(0, [] if owner else [17, 39], [17, 39] if owner else [], 0,
                      owner='iq' if owner else 'wire')
        cases = []
        for bit in range(50):
            words = list(base)
            words[bit//10] ^= 1 << (bit % 10)
            cases.append((words, None))
        for wc, qc, seq, op, arg in [(1, 1, 0, 0, 0),
                                      (0 if owner else 60, 60 if owner else 0, 0, 0, 0),
                                      (0, 0, 1, 0, 0), (0, 0, 0, 15, 0), (0, 0, 0, 1, 2)]:
            cases.append((metadata(wc, qc, seq, op, arg)+[0]*59, None))
        cases.append((base, 5))
        for words, refuse_at in cases:
            add((1, owner, 0, 0, 0, 0, 0, 0, 0, 1, 1), rx=(0, 0, 0, 0, 0))
            fault = False
            command = 0
            command_valid = 0
            for pos, word in enumerate(words+[0]*8):
                refused = pos == refuse_at
                wv = int(not fault and pos in (5, 6) and not owner and not refused)
                qv = int(not fault and pos in (5, 6) and owner and not refused)
                # Header negatives must never release payload. Refusal case
                # accepts the header, then must stop at its refused first beat.
                if refuse_at is None:
                    wv = qv = 0
                add((0, owner, 0, 0, 0, 0, 0, 0, word,
                     int(not refused or owner), int(not refused or not owner)),
                    rx=(wv, qv, command_valid, int(fault), command))
                command_valid = 0
                if pos == 4:
                    if refuse_at is None:
                        fault = True
                    else:
                        command_valid = 1
                if refused:
                    fault = True
            negative_cases += 1

    with (out/'vectors.txt').open('w') as f:
        for row in vectors:
            f.write(' '.join(f'{value:x}' for value in row)+'\n')
    sources = [PROJECT/'rtl/pt_dense_header.sv', PROJECT/'sim/reference/pt_dense_transport.sv',
               PROJECT/'sim/tb_dense_transport.sv']
    subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_transport',
                    '-o', str(out/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, check=True, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    rows = (out/'actual.txt').read_text().splitlines()
    assert len(rows) == len(expected)
    for cycle, (line, (tx, rx)) in enumerate(zip(rows, expected)):
        values = [int(v, 16) for v in line.split()]
        if tx is not None:
            assert tuple(values[:3]) == tx, (cycle, 'TX', values[:3], tx)
        if rx is not None:
            actual = (values[4], values[5], values[6], values[7], values[8])
            assert actual[:4] == rx[:4], (cycle, 'RX', actual, rx)
            if rx[4] is not None:
                assert actual[4] == rx[4], (cycle, 'command', actual, rx)
            if actual[0] or actual[1]:
                assert values[3] == vectors[cycle][8], (cycle, 'RX data')
    assert full_frames > 100
    assert all(full_by_owner), 'Both owners must exercise full payload quota'
    sources.extend([Path(__file__).resolve(), PROJECT/'verification/stream_codec.py',
                    PROJECT/'verification/transport_model.py'])
    data = dict(status='pass', frames=frames, cycles=len(rows), owners=['wire', 'iq'],
                full_59_word_frames=full_frames, negative_cases=negative_cases,
                full_59_word_frames_by_owner=dict(wire=full_by_owner[0], iq=full_by_owner[1]),
                scope='RTL dense framing and same-frame source consumption; physical rate/CDC signoff separate',
                source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'report.json').write_text(json.dumps(data, indent=2)+'\n')
    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-transport')
    check(parser.parse_args().output_dir.resolve())
