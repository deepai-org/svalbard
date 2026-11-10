#!/usr/bin/env python3
"""Check sample/pair conversion against independent ordered bit queues."""
import argparse
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
    rng = random.Random(3817021)
    rows, expected = [], []
    transfers = [[0, 0], [0, 0]]
    simultaneous = [0, 0]
    occupancy = [set(), set()]
    for mode in (0, 1):
        queues = [[], []]
        held = [rng.getrandbits(24), rng.getrandbits(20)]
        widths = [(16 if mode else 24, 20), (20, 16 if mode else 24)]
        for cycle in range(18000):
            reset = cycle in (0, 2117, 9139)
            if reset:
                queues = [[], []]
            valid = [int(cycle % 97 < 70 and rng.random() < .85) for _ in (0, 1)]
            ready = [int(cycle % 131 < 95 and rng.random() < .8) for _ in (0, 1)]
            row = (int(reset), mode, held[0], valid[0], ready[0], held[1], valid[1], ready[1])
            result = []
            for index, (incoming, outgoing) in enumerate(widths):
                queue = queues[index]
                available = len(queue) >= outgoing
                take = available and ready[index]
                space = len(queue)-(outgoing if take else 0)+incoming <= 40
                value = sum(bit << position for position, bit in enumerate(queue[:outgoing]))
                result += [int(space), int(available), value if available else None]
                occupancy[index].add(len(queue))
                if not reset:
                    if take:
                        del queue[:outgoing]
                        transfers[index][1] += 1
                    if space and valid[index]:
                        queue.extend((held[index] >> bit) & 1 for bit in range(incoming))
                        held[index] = rng.getrandbits(incoming)
                        transfers[index][0] += 1
                    simultaneous[index] += int(take and space and valid[index])
            rows.append(row)
            expected.append(result)
    with (out/'vectors.txt').open('w') as f:
        for row in rows:
            f.write(' '.join(f'{value:x}' for value in row)+'\n')
    sources = [PROJECT/'sim/tb_pair_gearbox.sv', PROJECT/'rtl/pt_pair_gearbox.sv']
    subprocess.run(['iverilog', '-g2012', '-s', 'tb_pair_gearbox', '-o', str(out/'bench.vvp'),
                    *map(str, sources)], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, check=True, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    lines = (out/'actual.txt').read_text().splitlines()
    assert len(lines) == len(expected)
    for cycle, (line, want) in enumerate(zip(lines, expected)):
        actual = [int(value, 16) for value in line.split()]
        for index, value in enumerate(want):
            if value is not None:
                assert actual[index] == value, (cycle, index, actual[index], value)
    assert min(simultaneous) > 5000 and min(max(v) for v in occupancy) == 40
    result = dict(status='pass', cycles=len(rows), transfers=transfers, simultaneous=simultaneous,
                  occupancies_bits=[sorted(v) for v in occupancy],
                  scope='16/24-bit sample to 20-bit pair RTL with backpressure and reset flushing',
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sources+[Path(__file__).resolve()]})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/pair-gearbox')
    check(parser.parse_args().output_dir.resolve())
