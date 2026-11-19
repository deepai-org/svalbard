#!/usr/bin/env python3
"""Freeze one die-fit packing of a chip as its skeleton floorplan.
    python3 from_fit.py <chip> <scratch/reviews/die-fit/run/<chip>/fit-<tag>.json>   -> floorplan-<chip>.json
Items (master, as-built area) come from the chip's ledger (scratch/reviews/die-fit/<chip>/ledger.json)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(HERE+'/../../../../..')
chip, fit = sys.argv[1], sys.argv[2]
J = json.load(open(fit)); L = json.load(open(f'{ROOT}/scratch/reviews/die-fit/{chip}/ledger.json'))
key = {'S': 'asbuilt_um2', 'T': 'target_um2', 'LB': 'lb_um2'}[J['scenario']]
out = dict(chip=chip, scenario=J['scenario'], macro=J['macro'], fixed=J['fixed'], pads=J['pads'],
           placed_rects=J['placed_rects'], unplaced=J['unplaced'], halo_um=J['halo_um'],
           items={r['item']: [r['master'], r[key]] for r in L['rows']},
           source=f'scratch/reviews/die-fit packer (fit.py) for pt_{chip}: {os.path.relpath(fit, ROOT)}, scenario {J["scenario"]}, '
                  f'macro {J["macro"]["w"]} x {J["macro"]["h"]} at x0 {J["macro"]["x0"]}, decap bank {J["bank"]}, halo {J["halo_um"]} um')
# the QVCO is booked at its drawn metal (848 x 628); its cell carries a 25 um keep-out on three sides (898 x 653): grow the
# rectangle into the spiral halo so that the published cell is placed (the fill keep-out study needs the inductor)
if 'qvco' in out['placed_rects']:
    r = out['placed_rects']['qvco']['rect']; rot = out['placed_rects']['qvco'].get('rot')
    gw, gh = (25.0, 50.0) if rot else (50.0, 25.0)
    out['placed_rects']['qvco']['rect'] = [r[0]-gw/2, r[1]-gh/2, r[2]+gw/2, r[3]+gh/2]
json.dump(out, open(f'{HERE}/floorplan-{chip}.json', 'w'), indent=0)
print('wrote', f'floorplan-{chip}.json', len(out['placed_rects']), 'placed,', len(out['unplaced']), 'unplaced')
