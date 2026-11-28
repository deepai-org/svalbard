#!/usr/bin/env python3
"""Block pin-edit batch (coordinator 2026-11-28): edge supply pins added to published analog blocks, then the same
must-not-regress gate as the pads (pads/pad_publish.py): block DRC 0 (shuttle deck, main + antenna), KLayout read-back
LVS match against the block's schematic, record sha256. The published block GDS (git-ignored) is rewritten in place
through this script; rerun it after the block's generator rewrites the block (edits are idempotent: an edit whose shapes
are already present is skipped).

    python3 block_pins.py [block ...]          (default: every block in EDITS)    SVALBARD_DATA = data checkout

Coordinates are block-local in the LEF frame (origin at the cell's lower-left bbox corner, unflipped). Each edit:
  pin   Metal5 rectangle, edge-flush, labelled with the pin name on 81/10 (kl_abstract makes it a second shape of that pin)
  via   region where a Via4 array joins the pin to the block's own same-net Metal4 strap (0.26 um cuts, 0.36 um space,
        0.2 um inside the region)"""
import json, hashlib, os, sys, subprocess, tempfile, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get('SVALBARD_DATA', HERE.parents[2]))
AN = REPO / 'projects/programmable_transceiver_platform/analog'
sys.path.insert(0, str(HERE / 'pads')); import pad_publish as PP          # noqa: E402  (kl(), lvs_file())
DECK = Path(os.environ.get('PDK_LIVE', '/home/ubuntu/svalbard/scratch/integration/signoff-gap/precheck/pdk_792ef67')) / 'drc'

# floorplan spec (af39a07a2a611402e, fp-plan-code 53e00abf); currents avg / rms incl. x1.2 for 85 C
EDITS = {
    'pt_txsum': dict(gds='rf_tx/generated/txsum.gds', ref='rf_tx/txsum.spice', rtop='pt_txsum', rec='rf_tx/generated/txsum-kldrc.json',
                     edits=[dict(net='VDD', pin=[20.0, 0.0, 30.0, 8.52], via=[20.0, 7.52, 30.0, 8.52], why='south VDD facing the RAIL_rf_tx bus, 2.4 mA')]),
    'pt_txmix_q': dict(gds='rf_tx/generated/txmix_q.gds', ref='rf_tx/txmix_q.spice', rtop='pt_txmix_q', rec='rf_tx/generated/txmix_q-kldrc.json',
                       edits=[dict(net='VDD', pin=[231.9, 9.9, 234.9, 60.0], via=[231.9, 9.9, 234.9, 10.9], why='east VDD facing the trunk lane, 2.4 / 3.7 mA')]),
    'pt_rfdriver': dict(gds='rf_tx/generated/rfdriver.gds', ref='rf_tx/rfdriver.spice', rtop='pt_rfdriver', rec='rf_tx/generated/rfdriver-kldrc.json',
                        edits=[dict(net='VDD', pin=[224.0, 0.0, 257.8, 8.82], via=[224.0, 6.82, 257.8, 8.82],
                                    why='south VDD at the trunk end, 29.1 / 32.0 mA; spec x 197.8-257.8 narrowed to 224.0-257.8: three internal Metal5 signal stubs at local x 210-222.7 reach the south edge')]),
}
CUT, SP, IN = 0.26, 0.36, 0.2


def edit_script(blk, e):
    return f'''
import pya
ly = pya.Layout(); ly.read('/b/in.gds'); t = ly.cell('{blk}'); dbu = ly.dbu; b = t.dbbox()
L = lambda a, d: ly.layer(a, d)
done = 0
for e in {json.dumps(e['edits'])}:
    px0, py0, px1, py1 = e['pin']; vx0, vy0, vx1, vy1 = e['via']
    P = pya.DBox(b.left + px0, b.bottom + py0, b.left + px1, b.bottom + py1)
    m5 = pya.Region(t.begin_shapes_rec(ly.find_layer(81, 0)))
    if (pya.Region(P.to_itype(dbu)) - m5).is_empty(): continue          # already drawn
    t.shapes(L(81, 0)).insert(P)
    V = pya.DBox(b.left + vx0 + {IN}, b.bottom + vy0 + {IN}, b.left + vx1 - {IN}, b.bottom + vy1 - {IN})
    nx = max(1, int((V.width() + {SP}) // ({CUT} + {SP}))); ny = max(1, int((V.height() + {SP}) // ({CUT} + {SP})))
    ox = V.left + (V.width() - (nx * {CUT} + (nx - 1) * {SP})) / 2; oy = V.bottom + (V.height() - (ny * {CUT} + (ny - 1) * {SP})) / 2
    for i in range(nx):
        for j in range(ny):
            x = ox + i * ({CUT} + {SP}); y = oy + j * ({CUT} + {SP})
            t.shapes(L(41, 0)).insert(pya.DBox(x, y, x + {CUT}, y + {CUT}))
    t.shapes(L(81, 10)).insert(pya.DText(e['net'], pya.DTrans(P.center())))
    done += 1
opt = pya.SaveLayoutOptions(); opt.gds2_write_timestamps = False
ly.write('/b/out.gds', opt); print('EDITS', done)
'''


def drc(gds, top):
    out = {}
    for d, dk in (('main', 'all,-antenna,-density,-cup'), ('antenna', 'antenna')):
        r = PP.kl([f'{gds.parent}:/g:ro', f'{DECK}:/deck:ro'],
                  f"cd /tmp; klayout -b -zz -r /deck/gf180mcu.drc -rd input=/g/{gds.name} -rd topcell={top} -rd report=/tmp/r.lyrdb "
                  f"-rd decks='{dk}' -rd variant=gf180mcuD -rd workers=1 -rd threads=1 > /tmp/log 2>&1; grep -q 'Total Run time' /tmp/log && echo DONE; "
                  "grep -c '<item>' /tmp/r.lyrdb; grep -o \"'[A-Za-z0-9._]*'[ ]*: *[1-9][0-9]* violation\" /tmp/log | head -20")
        lines = r.stdout.split('\n')
        out[d] = dict(done='DONE' in lines[0], total=int(lines[1]) if len(lines) > 1 and lines[1].strip().isdigit() else None, rules=[l for l in lines[2:] if l])
    return out


def main(blocks):
    bad = 0
    for blk in blocks:
        E = EDITS[blk]; gds = AN / E['gds']; old = hashlib.sha256(open(gds, 'rb').read()).hexdigest()
        w = Path(tempfile.mkdtemp(prefix=f'blk_{blk}_')); shutil.copy(gds, w / 'in.gds'); (w / 'e.py').write_text(edit_script(blk, E))
        r = PP.kl([f'{w}:/b'], 'klayout -b -zz -r /b/e.py')
        if 'EDITS' not in r.stdout: print(blk, 'edit FAILED', r.stdout[-300:], r.stderr[-300:]); bad += 1; continue
        n = int(r.stdout.split('EDITS')[1].split()[0])
        cand = w / f'{gds.name}'; shutil.copy(w / 'out.gds', cand)
        D = drc(cand, blk); Lv = PP.lvs_file(cand, blk, AN / E['ref'], E['rtop'])
        ok = all(v['done'] and v['total'] == 0 for v in D.values()) and Lv['result'] == 'match'
        print(f"{blk}: {n} edit(s); DRC main {D['main']['total']} {D['main']['rules']} antenna {D['antenna']['total']}; read-back LVS {Lv['result']} "
              f"({Lv['layout_devices']} / {Lv['reference_devices']})")
        if not ok: print(f'{blk}: NOT published (gate failed)'); bad += 1; shutil.rmtree(w, ignore_errors=True); continue
        if n: shutil.copy(cand, gds)
        new = hashlib.sha256(open(gds, 'rb').read()).hexdigest()
        res = dict(block=blk, gds=E['gds'], sha256_before=old, sha256=new, edits=E['edits'], drc=D, lvs={k: v for k, v in Lv.items() if k != 'log_tail'})
        open(HERE / os.path.dirname(E['gds']) / f'{blk}-pins.json', 'w').write(json.dumps(res, indent=1) + '\n')
        rec = HERE / E['rec']
        if rec.exists():
            j = json.load(open(rec))
            for k in ('gds_sha256', 'sha256'):
                if isinstance(j.get(k), str): j[k] = new
            j['pin_edit'] = f"2026-11-28 block_pins.py: {', '.join(e['net'] + ' ' + e['why'] for e in E['edits'])}; shuttle DRC main 0 / antenna 0, KLayout read-back LVS match"
            open(rec, 'w').write(json.dumps(j, indent=1) + '\n')
        print(f'{blk}: published sha256 {old[:12]} -> {new[:12]}')
        shutil.rmtree(w, ignore_errors=True)
    print('BLOCK PINS', 'PASS' if not bad else f'FAIL ({bad})'); return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or list(EDITS)))
