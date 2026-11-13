#!/usr/bin/env python3
"""Foundry fast-bound Liberty for the hardening flow (pre-mortem item 5).

Copies the PDK's gf180mcu_fd_sc_mcu7t5v0__ff_n40C_3v60.lib UNCHANGED except that cells absent from the
characterized in-window libraries (liberty/*_ff_022C_3v35.lib) are dropped: OpenSTA needs the same cell set
in every corner, and the full foundry library would also offer synthesis cells the other corners lack
(TC16 pC6: STA-1112 on addh_2). No timing value is touched.
Usage: foundry_subset.py [<pdk lib dir>]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import liberty_io as L  # noqa: E402

HERE = Path(__file__).resolve().parent
SC = 'gf180mcu_fd_sc_mcu7t5v0'
libdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/home/ubuntu/svalbard/scratch/digital-libchar/pdk/libs.ref')/SC/'lib'
ref = L.parse((HERE/'liberty'/f'{SC}__ff_022C_3v35.lib').read_text())
keep = {L.unq(c.args[0]) for c in ref.groups('cell')}
lib = L.parse((libdir/f'{SC}__ff_n40C_3v60.lib').read_text())
have = {L.unq(c.args[0]) for c in lib.groups('cell')}
assert keep <= have, sorted(keep-have)
lib.children = [c for c in lib.children if not (isinstance(c, L.Group) and c.name == 'cell' and L.unq(c.args[0]) not in keep)]
out = HERE/'liberty'/f'{SC}__ff_n40C_3v60.lib'
with out.open('w') as fh:
    L.write(lib, fh)
print(f'{out.name}: kept {len(keep)} of {len(have)} cells')
