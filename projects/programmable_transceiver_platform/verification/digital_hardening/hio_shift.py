#!/usr/bin/env python3
"""hio_shift.py <rows>: outline height and FIRM hand placements for a macro that is <rows> x 7.84 um taller (or, negative, shorter) than
the 1716 x 1640 um base floorplan. Rewrites hio_placement.cfg (MACRO_PLACEMENT_CFG) and DIE_AREA in config.json.

1. Host-link I/O block (hio_placement_1640.cfg, generated for the base floorplan): the D2H block sits on the
   south edge and does not move; every entry above y = 1000 um (the H2D capture block under the north pins)
   moves up with the edge. One unit is two cell rows, so the row orientations (N / FS) stay as placed.
2. Clock sources (CLOCK_ROOTS below): each divider flop or clock mux is fixed directly under the buffer that
   drives its clock net. Without this, clock tree synthesis moves the root buffer to the centroid of its sinks
   and leaves the source cell behind: 0.7 - 1 mm of wire on a flop output (3.5 - 5 ns clock-to-Q at ss), which
   lands in the insertion delay of every derived clock. Positions are x in um and y as a fraction of the
   outline height; they are snapped to the site grid and kept clear of the tap columns.
"""
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
X0, Y0, SITE, ROW = 6.72, 15.68, 0.56, 3.92          # core origin, site and row pitch of the floorplan
TAP_W, TAP_PITCH, TAP_EVEN, TAP_ODD = 1.12, 39.2, 26.32, 45.92   # tap columns of even / odd rows
WIDTH = {'dffrnq_4': 22.40, 'clkbuf_8': 28.00}   # room kept: a root buffer may be upsized to clkbuf_16 in place
# (x um, y fraction, [(instance, cell), ...] stacked in consecutive rows, source cell first)
CLOCK_ROOTS = [
    (501.0, 0.554, [('host.divider.cdiv.cell', 'dffrnq_4'), ('host.divider.core_root.cell', 'clkbuf_8')]),        # hcore
    (1630.0, 0.938, [('digital.fca.fjc.cell', 'dffrnq_4'), ('digital.fca.blk_clock_buf.cell', 'clkbuf_8')]),      # counter a prescaler
    (1580.0, 0.871, [('digital.fcb.fjc.cell', 'dffrnq_4'), ('digital.fcb.blk_clock_buf.cell', 'clkbuf_8')]),      # counter b prescaler
]

def legal_x(row, x, width):
    """first site at or right of x in `row` where [x, x + width] misses the tap column"""
    t0 = TAP_EVEN if row % 2 == 0 else TAP_ODD
    k = round((x - X0) / SITE)
    while True:
        xs = X0 + k * SITE
        j = round((xs - t0) / TAP_PITCH)
        if all(xs + width <= t or xs >= t + TAP_W for t in (t0 + (j + d) * TAP_PITCH for d in (-1, 0, 1))):
            return round(xs, 2)
        k += 1

def main():
    rows = int(sys.argv[1]); assert rows >= -40
    dy = round(rows * 7.84, 2); height = round(1640 + dy, 2)
    out = []
    for line in (H / 'hio_placement_1640.cfg').read_text().splitlines():
        p = line.split()
        if len(p) == 4 and float(p[2]) > 1000:
            p[2] = f'{float(p[2]) + dy:.2f}'; line = ' '.join(p)
        out.append(line)
    for x, yf, cells in CLOCK_ROOTS:
        r = round((yf * height - Y0) / ROW)
        for n, (inst, cell) in enumerate(cells):
            row = r + n
            out.append(f'{inst} {legal_x(row, x, WIDTH[cell]):.2f} {Y0 + row * ROW:.2f} {"N" if row % 2 == 0 else "FS"}')
    (H / 'hio_placement.cfg').write_text('\n'.join(out) + '\n')
    c = json.loads((H / 'config.json').read_text())
    c['DIE_AREA'] = [0, 0, 1716, height]
    (H / 'config.json').write_text(json.dumps(c, indent=2) + '\n')
    print('outline 1716 x', height, 'um =', round(1716 * height / 1e6, 4), 'mm2;', len(out), 'fixed cells')

if __name__ == '__main__':
    main()
