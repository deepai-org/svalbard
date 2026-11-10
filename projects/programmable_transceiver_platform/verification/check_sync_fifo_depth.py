#!/usr/bin/env python3
"""Check non-power-of-two queues and full simultaneous push/pop semantics."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import random
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


def check(out):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    rng = random.Random(92017)
    models = [(6, True, deque()), (12, False, deque()), (7, False, deque())]
    flags = [[0, 0] for _ in models]
    rows, wants = [], []
    full_replace = [0 for _ in models]
    for cycle in range(16000):
        reset = cycle % 977 == 0
        push = int(rng.random() < (.85 if cycle % 200 < 100 else .2))
        pop = int(rng.random() < (.2 if cycle % 200 < 100 else .85))
        data = rng.getrandbits(20)
        rows.append((int(reset), push, pop, data))
        expected = []
        for index, (depth, lookahead, queue) in enumerate(models):
            if reset:
                queue.clear();flags[index] = [0, 0]
            full, empty = len(queue) == depth, not queue
            expected += [int(full), int(empty), len(queue), *flags[index], queue[0] if queue else None]
            if not reset:
                take = pop and not empty
                put = push and (not full or lookahead and take)
                flags[index][0] |= int(push and full and not (lookahead and take))
                flags[index][1] |= int(pop and empty)
                full_replace[index] += int(full and take and put)
                if take:
                    queue.popleft()
                if put:
                    queue.append(data)
        wants.append(expected)
    (out/'vectors.txt').write_text(''.join(' '.join(f'{n:x}' for n in row)+'\n' for row in rows))
    sources = [PROJECT/'sim/tb_sync_fifo_depth.sv', PROJECT/'rtl/pt_fifo.sv', Path(__file__).resolve()]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    subprocess.run(['iverilog', '-g2012', '-s', 'tb_sync_fifo_depth', '-o', str(out/'bench.vvp'),
                    *map(str, sources[:2])], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, check=True, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    actual = (out/'actual.txt').read_text().splitlines()
    assert len(actual) == len(wants)
    for cycle, (line, want) in enumerate(zip(actual, wants)):
        fields = line.split()
        assert len(fields) == len(want), (cycle, len(fields), len(want))
        for field, (raw, expected) in enumerate(zip(fields, want)):
            if expected is not None:
                assert int(raw, 16) == expected, (cycle, field, raw, expected)
    assert full_replace[0] > 500 and full_replace[1:] == [0, 0]
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    result = dict(status='pass', cycles=len(rows), accepted_full_replacements=full_replace,
                  scope='depth6 lookahead and depth7/12 conservative queues against independent deques', source_hashes=hashes)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/sync-fifo-depth')
    check(parser.parse_args().output_dir.resolve())
