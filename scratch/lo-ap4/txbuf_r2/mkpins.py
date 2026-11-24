"""pins.tcl for pt_lo_txbuf r2: every port's top-edge Metal5 label becomes a Metal4+Metal5 pad with a Via4 (as r1's txbuf_pins/pins.tcl)."""
import re, sys
mag = open(sys.argv[1]).read()
labs = re.findall(r'flabel metal5 (\d+) (\d+) (\d+) (\d+) 0 FreeSans \d+ 0 0 0 (\S+)', mag)
order = ['IP', 'IN', 'QP', 'QN', 'OIP', 'OIN', 'OQP', 'OQN', 'VDD', 'VSS']
L = {n: tuple(map(int, (a, b, c, d))) for a, b, c, d, n in labs}
out = ['crashbackups stop', 'addpath primitives', 'addpath fast', 'load lo_txbuf', 'snap internal']
for i, n in enumerate(order, 1):
    x1, y1, x2, y2 = L[n]; T = y2
    e = 160 if n in ('VDD', 'VSS') else 20
    out += [f'box {x1-e} {T-360} {x2+e} {T}', 'paint metal5', 'paint metal4',
            f'box {x1-e+40 if e==160 else x1} {T-300} {x2+e-40 if e==160 else x2} {T-60}', 'paint via4',
            f'box {x1} {y1} {x2} {y2}', 'select area label', 'delete',
            f'box {x1-e} {T-120} {x2+e} {T}', f'label {n} FreeSans 480 0 0 0 c metal4', f'port make {i}']
out += ['select top cell', 'drc catchup', 'drc check', 'drc catchup', 'set f [open drc.txt w]', 'puts $f [drc list count total]',
        'puts $f [drc listall why]', 'close $f', 'save lo_txbuf', 'quit -noprompt']
open('pins.tcl', 'w').write('\n'.join(out) + '\n')
print({n: L[n] for n in order})
