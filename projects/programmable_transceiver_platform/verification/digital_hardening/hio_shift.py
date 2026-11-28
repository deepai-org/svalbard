#!/usr/bin/env python3
"""hio_shift.py <chip> <out.cfg>: FIRM hand placements (MACRO_PLACEMENT_CFG) for the outline of <chip>/config.json
(rf or wired). run_digital_hardening.sh calls it for every run, so the placement always follows the chip's DIE_AREA.
The height must be 1640 um plus a whole number of 7.84 um steps (two cell rows; negative = shorter).

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
WIDTH = {'dffrnq_4': 22.40, 'clkbuf_8': 28.00, 'clkinv_8': 20.16}   # room kept: a root buffer may be upsized to clkbuf_16 in place
# (x um, y fraction, [(instance, cell), ...] stacked in consecutive rows, source cell first)
CLOCK_ROOTS = [
    (501.0, 0.554, [('host.divider.cdiv.cell', 'dffrnq_4'), ('host.divider.core_root.cell', 'clkbuf_8'),
                     ('host.divider.core_inv.cell', 'clkinv_8')]),        # hcore + hcoreb (PDN-02 two-phase)
    (1630.0, 0.938, [('digital.fca.fjc.cell', 'dffrnq_4'), ('digital.fca.blk_clock_buf.cell', 'clkbuf_8')]),      # counter a prescaler
    (1580.0, 0.871, [('digital.fcb.fjc.cell', 'dffrnq_4'), ('digital.fcb.blk_clock_buf.cell', 'clkbuf_8')]),      # counter b prescaler
]

# Output-stage flops fixed next to their macro pins (west edge), y in um per chip outline: the pin positions come from
# pin_order.cfg for that outline (routed DEFs of 33bba1e3: c_cdr_fup / fdn at y = 1133.7 / 1130.4 um on pt_rf,
# 1379.0 / 1374.5 um on pt_wired). Re-derive if the outline or the pin order changes.
PIN_FLOPS = {'rf': 1120.0, 'wired': 1365.0}
PIN_FLOP_CELLS = [('fup_out.cell', 'dffrnq_4'), ('fdn_out.cell', 'dffrnq_4')]

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
    chip, dst = sys.argv[1], Path(sys.argv[2])
    c = json.loads((H / chip / 'config.json').read_text())
    x0, y0, width, height = c['DIE_AREA']
    assert (x0, y0) == (0, 0) and 1600 <= width <= 1716, 'host-link blocks fit widths 1600-1716 um'
    dx = 1716 - width   # narrower outline: cells right of mid-width (clock roots) move left with the east edge
    rows = round((height - 1640) / 7.84)
    dy = round(rows * 7.84, 2)
    assert abs(1640 + dy - height) < 0.01, f'height {height} is not 1640 + n x 7.84 um'
    # the H2D block (north edge, y > 1000 in the base) must stay clear of the D2H block and the hcore root
    assert 1591.52 + dy > 0.554 * height + 40 and height >= 900, f'outline height {height} too small for the host-link blocks'
    out = []
    for line in (H / 'hio_placement_1640.cfg').read_text().splitlines():
        p = line.split()
        if len(p) == 4 and float(p[2]) > 1000:
            p[2] = f'{float(p[2]) + dy:.2f}'; line = ' '.join(p)
        out.append(line)
    for x, yf, cells in CLOCK_ROOTS:
        if x > 858: x -= dx
        r = round((yf * height - Y0) / ROW)
        for n, (inst, cell) in enumerate(cells):
            row = r + n
            out.append(f'{inst} {legal_x(row, x, WIDTH[cell]):.2f} {Y0 + row * ROW:.2f} {"N" if row % 2 == 0 else "FS"}')
    r = round((PIN_FLOPS[chip] - Y0) / ROW)
    for n, (inst, cell) in enumerate(PIN_FLOP_CELLS):
        row = r + n
        out.append(f'{inst} {legal_x(row, 12.0, WIDTH[cell]):.2f} {Y0 + row * ROW:.2f} {"N" if row % 2 == 0 else "FS"}')
    dst.write_text('\n'.join(out) + '\n')
    print(f'{chip}: outline {width} x {height} um = {round(width * height / 1e6, 4)} mm2; {len(out)} fixed cells -> {dst}')

if __name__ == '__main__':
    main()
