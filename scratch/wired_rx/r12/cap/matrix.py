"""Print the G1 gating matrix specs: matrix.py [corner ...]  ->  'tag key=val ...' lines."""
import sys
CORNERS = sys.argv[1:] or ['tt', 'ss', 'ss35', 'ff', 'sf', 'fs', 'pess']
for c in CORNERS:
    for f in (480, 625, 675, 810):
        print(f'{c}_{f}_q0 mode=q f={f} corner={c} rcs=0')
        print(f'{c}_{f}_q1 mode=q f={f} corner={c} rcs=1')
        print(f'{c}_{f}_h0 mode=h f={f} corner={c} rcs=0')
        print(f'{c}_{f}_f1 mode=f f={f} corner={c} rcs=1 psel=0')
