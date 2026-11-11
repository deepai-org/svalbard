#!/usr/bin/env python3
"""Check sample <-> quad conversion against independent ordered bit queues.

pt_sample_pack: one 24-bit (or mode8 16-bit) sample per valid clock in, a
40-bit quad out whenever 40 bits are held, no backpressure. pt_sample_unpack:
quads in when no more than 20 bits remain after this clock's output, one
sample out per accepted request. Random valid/ready with reset flushing.
(Make target name kept from the paired engine: transceiver-pair-gearbox.)
"""
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
    simultaneous = 0
    occupancy = [set(), set()]
    for mode in (0, 1):
        width = 16 if mode else 24
        pack, unpack = [], []
        sample, quad = rng.getrandbits(24), rng.getrandbits(40)
        for cycle in range(18000):
            reset = cycle in (0, 2117, 9139)
            if reset:
                pack, unpack = [], []
            pvalid = int(cycle % 97 < 70 and rng.random() < .85)
            uvalid = int(cycle % 89 < 70 and rng.random() < .85)
            uready = int(cycle % 131 < 95 and rng.random() < .8)
            rows.append((int(reset), mode, sample, pvalid, quad, uvalid, uready))
            occupancy[0].add(len(pack))
            occupancy[1].add(len(unpack))
            push = len(pack) >= 40
            qvalue = sum(bit << i for i, bit in enumerate(pack[:40]))
            out_valid = len(unpack) >= width
            take = out_valid and uready
            remaining = len(unpack)-(width if take else 0)
            in_ready = remaining <= 20
            svalue = sum(bit << i for i, bit in enumerate(unpack[:width]))
            expected.append((int(push), qvalue if push else None, int(in_ready), int(out_valid),
                             svalue if out_valid else None))
            if not reset:
                if push:
                    del pack[:40]
                    transfers[0][1] += 1
                if pvalid:
                    value = sample & ((1 << width)-1)
                    pack.extend((value >> b) & 1 for b in range(width))
                    transfers[0][0] += 1
                if take:
                    del unpack[:width]
                    transfers[1][1] += 1
                if in_ready and uvalid:
                    unpack.extend((quad >> b) & 1 for b in range(40))
                    transfers[1][0] += 1
                    quad = rng.getrandbits(40)
                simultaneous += int(take and in_ready and uvalid)
                sample = rng.getrandbits(24)
    with (out/'vectors.txt').open('w') as f:
        for row in rows:
            f.write(' '.join(f'{value:x}' for value in row)+'\n')
    sources = [PROJECT/'sim/tb_pair_gearbox.sv', PROJECT/'rtl/pt_quad_gearbox.sv']
    subprocess.run(['iverilog', '-g2012', '-s', 'tb_pair_gearbox', '-o', str(out/'bench.vvp'),
                    *map(str, sources)], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, check=True, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    actual = (out/'actual.txt').read_text().splitlines()
    assert len(actual) == len(expected)
    for cycle, (line, want) in enumerate(zip(actual, expected)):
        po, pq, ui, uo, uq = (int(v, 16) for v in line.split())
        assert po == want[0] and (want[1] is None or pq == want[1]), (cycle, 'pack', line, want)
        assert ui == want[2] and uo == want[3] and (want[4] is None or uq == want[4]), (cycle, 'unpack', line, want)
    result = dict(status='pass', cycles=len(rows), transfers=transfers, simultaneous_unpack=simultaneous,
                  occupancies_bits=[sorted(o) for o in occupancy],
                  scope='sample/quad converter RTL (both widths) with random valid/ready and reset flushing',
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sources+[Path(__file__).resolve()]})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/pair-gearbox')
    check(parser.parse_args().output_dir.resolve())
