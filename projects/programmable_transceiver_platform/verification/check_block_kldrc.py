#!/usr/bin/env python3
"""Block evidence gate: every block in kl_block_drc_blocks.json needs a published, current and
clean KLayout precheck record (<gds dir>/<block>-kldrc.json written by kl_block_drc.py --publish).

  check_block_kldrc.py [--json OUT]      exit 1 unless every block is CLEAN
States: CLEAN, FAIL (record has violations), STALE (GDS changed since the run), MISSING.
"""
import argparse, hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json')
    a = ap.parse_args()
    reg = json.loads((HERE / 'kl_block_drc_blocks.json').read_text())['blocks']
    rows, bad = [], 0
    for name, b in reg.items():
        gds = pathlib.Path(b['gds'])
        gds = gds if gds.is_absolute() else REPO / gds
        rec_p = gds.parent / f'{name}-kldrc.json'
        row = dict(block=name, owner=b.get('owner'), gds=str(gds.relative_to(REPO)) if gds.is_relative_to(REPO) else str(gds))
        if not gds.exists():
            row['state'] = 'NO_GDS'
        elif not rec_p.exists():
            row['state'] = 'MISSING'
        else:
            rec = json.loads(rec_p.read_text())
            row.update(main=rec['decks'].get('main', {}).get('total'), antenna=rec['decks'].get('antenna', {}).get('total'))
            row['state'] = 'STALE' if rec['gds_sha256'] != sha(gds) else 'CLEAN' if rec['clean'] else 'FAIL'
        bad += row['state'] != 'CLEAN'
        rows.append(row)
        print(f"{row['state']:8s} {name:28s} main={row.get('main')} antenna={row.get('antenna')}  ({row['owner']})")
    print(f'{len(rows) - bad}/{len(rows)} blocks KLayout-precheck clean')
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rows, indent=1) + '\n')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
