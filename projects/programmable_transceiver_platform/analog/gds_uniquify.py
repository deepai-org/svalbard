"""Make a block GDS safe to merge into the chip: prefix every non-top cell with the block's top name.

Generators name subcells generically (`prim_0`, `p_nfet_03v3_w2_l0p28`, `ct_ring8`, `wtx_p1`,
`protection_network`, ...).  The chip assembly reads all block GDS files into one layout, where two
different cells with one name are silently merged -- one block then carries another block's
device.  `uniquify(gds, top)` renames every cell below `top` to `<top>__<name>` (already-prefixed
cells are left alone) and optionally renames the top cell itself; geometry is untouched, so DRC
and LVS of the published GDS are unchanged (the caller's round-trip LVS still applies).

Host-side helper: runs KLayout in the pinned analog image, rewriting the file in place.
verification/gds_cell_collisions.py is the chip-level check that this was done everywhere.
"""
import json
import os
import subprocess
from pathlib import Path

IMAGE = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'

_INNER = r'''
import pya, json
ly = pya.Layout(); ly.read('/g/' + fname)
top = ly.cell(topname)
if top is None:
    raise RuntimeError('no top cell ' + topname)
ren = {}
for ci in top.called_cells():
    c = ly.cell(ci)
    if not c.name.startswith(prefix + '__'):
        old = c.name
        c.name = prefix + '__' + old
        ren[old] = c.name
if newtop:
    top.name = newtop
opts = pya.SaveLayoutOptions(); opts.add_cell(top.cell_index())
ly.write('/g/' + fname + '.tmp', opts)
print('UNIQUIFY ' + json.dumps(dict(top=top.name, renamed=len(ren))))
'''


def uniquify(gds, top, prefix=None, new_top=None):
    """Rename every cell under `top` in `gds` to `<prefix or top>__<name>`; returns {top, renamed}."""
    gds = Path(gds).resolve()
    script = gds.parent / '.gds_uniquify.py'
    script.write_text(_INNER)
    try:
        r = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
                            '-v', f'{gds.parent}:/g', '--entrypoint', '/foss/tools/klayout/klayout', IMAGE,
                            '-b', '-r', '/g/.gds_uniquify.py', '-rd', f'fname={gds.name}', '-rd', f'topname={top}',
                            '-rd', f'prefix={prefix or top}', '-rd', f'newtop={new_top or ""}'],
                           capture_output=True, text=True, timeout=600)
    finally:
        script.unlink(missing_ok=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith('UNIQUIFY ')), None)
    if r.returncode or line is None:
        raise RuntimeError('gds_uniquify failed: ' + (r.stdout + r.stderr)[-1500:])
    os.replace(str(gds) + '.tmp', gds)
    return json.loads(line[len('UNIQUIFY '):])


def publish_checked(gds, block, top, threads=3):
    """Publish step every block flow calls on its final GDS: block-unique subcell names, then the
    required KLayout precheck record (verification/kl_block_drc.py, tapeout-precheck DRC + antenna
    decks) written to <gds dir>/<block>-kldrc.json.  Returns {clean, main, antenna}."""
    import sys
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / 'projects/programmable_transceiver_platform/verification'))
    import kl_block_drc
    uniquify(gds, top)
    r = kl_block_drc.run(block, gds, top, out=repo / 'scratch' / 'kl-block-drc' / 'flows', threads=threads,
                         do_publish=True)
    return dict(clean=r['clean'], **{k: v.get('total') for k, v in r['decks'].items()})
