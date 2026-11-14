#!/usr/bin/env python3
"""Layout / DRC / LVS / KLayout DRC for the circuits_ext.py cells, through the unchanged generate_dist flow.
usage: generate_ext.py --scratch DIR [--publish DIR] [cells...]"""
import argparse, json
import circuits_dist as cd
import circuits_ext
cd.CELLS.update(circuits_ext.EXTRA)
import generate_dist as gd

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--scratch', required=True)
    ap.add_argument('--publish', default=str(gd.HERE / 'generated'))
    ap.add_argument('cells', nargs='*')
    a = ap.parse_args()
    for n in a.cells or sorted(circuits_ext.EXTRA):
        r = gd.generate(n, a.scratch, a.publish)
        r['hashes']['circuits_ext.py'] = gd.sha(gd.HERE / 'circuits_ext.py')
        print(json.dumps({k: r[k] for k in ('cell', 'magic_drc_errors', 'klayout_drc', 'lvs_final', 'area_um2')}))
