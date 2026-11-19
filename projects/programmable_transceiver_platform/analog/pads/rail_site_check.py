#!/usr/bin/env python3
"""Pad family on the provider rail cell at its mask-snapped site: shuttle precheck main deck + antenna.

Why: a custom pad family replaces the provider IO cell at its site, and the chip assembly puts the provider
`5LM_METAL_RAIL` cell there instead (skeleton/build.py). A family that is clean alone can violate the precheck
against that rail cell (SO-1: Via3 / Via4 rules at every custom site). This check reproduces the site exactly:

1. Site frame from the template. For every provider cell of `retained_provider_ring` in
   `generated/packaging-assembly.gds` the overlapping golden-mask bond opening (precheck assets, mask_1x1.gds,
   layer 37/0) is transformed into the cell's local frame. All of them must agree (today: (7.5, 2.0)-(67.5, 62.0) um
   in all 64 provider cells), otherwise the check stops. West and east families and ring cells have the same local
   orientation (family M45 / R90, ring cells m45 / r90: relative r0), so one unmirrored local frame covers both edges.
2. Every bond opening of the family (layer 37/0, merged, 60 x 60 um) gets one rail cell (copied from the same
   packaging GDS, texts removed) placed so that the template opening lands exactly on the family opening, in BOTH
   axes. Rail cells that would overlap each other, or an opening of another size, stop the check.
3. The composite `asm` (family + rail cells) goes through verification/kl_block_drc.py (precheck decks: main =
   all,-antenna,-density,-cup and antenna). PASS = both decks 0.

  rail_site_check.py --gds G --top CELL [--name N] [--out DIR] [--threads 1]
  rail_site_check.py --family pad_hspad [--family ...|all]   (GDS / top from verification/kl_block_drc_blocks.json)
  rail_site_check.py --selftest [--out DIR]
      synthetic cells on the real rail cell: (a) bare opening -> must be CLEAN; (b) the same plus one Via3 cut with
      its Metal3 / Metal4 landings 0.175 um off a rail Via3 cut (the SO-1 mechanism) -> must FAIL with a Via3 rule;
      (c) an opening of the wrong size -> must be refused. Exit 0 only if all three behave.
Writes <out>/<name>/{asm.gds, site.json, kldrc.json, main/antenna lyrdb}; the asm.gds is deleted on PASS unless --keep.
"""
import argparse, json, os, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REPO = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT / 'verification'))
import kl_block_drc as kbd  # noqa: E402

IMAGE = kbd.IMAGE
PACKAGING = PROJECT / 'analog/pads/generated/packaging-assembly.gds'
MASK = REPO / 'scratch/integration/signoff-gap/dl/precheck-live/assets/golden_masks/mask_1x1.gds'
DEFAULT_OUT = REPO / 'scratch/pads-core/railcheck/out'

# KLayout python run inside the pinned image. argv: mode family.gds top out.gds [selftest-kind]
ASM = r'''
import sys, json, klayout.db as db
mode, fam_gds, fam_top, out_gds = sys.argv[1:5]
PAD, V3, M3, M4 = (37, 0), (40, 0), (42, 0), (46, 0)
# 1. site frame from the template
pk = db.Layout(); pk.read('/pk/packaging-assembly.gds'); ring = pk.cell('retained_provider_ring')
mk = db.Layout(); mk.read('/mask/mask_1x1.gds')
masks = [q.bbox() for q in db.Region(mk.top_cell().begin_shapes_rec(mk.layer(*PAD))).merged().each()
         if q.bbox().width() < 100000 and q.bbox().height() < 100000]
frames = {}
for inst in ring.each_inst():
    n = inst.cell.name
    if 'fill' in n or '__cor' in n or n.startswith('5LM'): continue
    hit = [m for m in masks if m.overlaps(inst.bbox())]
    if len(hit) == 1: frames.setdefault(str(inst.trans.inverted() * hit[0]), []).append(n)
if len(frames) != 1: print(json.dumps(dict(error='template openings not in one site frame', frames={k: len(v) for k, v in frames.items()}))); sys.exit(2)
frame = db.Box.from_s(next(iter(frames)))
rail_src = next(pk.cell(i) for i in ring.each_child_cell() if pk.cell(i).name.startswith('5LM_METAL_RAIL'))
# 2. family (or a synthetic cell) + rail cells
ly = db.Layout(); ly.dbu = 0.001
if mode == 'family':
    ly.read(fam_gds); fam = ly.cell(fam_top)
    if fam is None: print(json.dumps(dict(error='no cell ' + fam_top))); sys.exit(2)
else:
    fam = ly.create_cell(fam_top)
    size = 60000 if mode != 'selftest_badsize' else 50000
    fam.shapes(ly.layer(*PAD)).insert(db.Box(100000 + 7500, 2000, 100000 + 7500 + size, 2000 + size))
rail = ly.create_cell('5LM_METAL_RAIL'); rail.copy_tree(rail_src)
for ci in [rail.cell_index()] + list(rail.called_cells()):
    c = ly.cell(ci)
    for li in ly.layer_indexes():
        for s in list(c.each_shape(li)):
            if s.is_text(): s.delete()
ops = list(db.Region(fam.begin_shapes_rec(ly.layer(*PAD))).merged().each())
bad = [str(o.bbox()) for o in ops if (o.bbox().width(), o.bbox().height()) != (frame.width(), frame.height()) or not o.is_box()]
if not ops or bad: print(json.dumps(dict(error='bond openings not %s x %s um boxes' % (frame.width() / 1e3, frame.height() / 1e3), openings=[str(o.bbox()) for o in ops]))); sys.exit(3)
origins = sorted((o.bbox().left - frame.left, o.bbox().bottom - frame.bottom) for o in ops)
rb = rail.bbox()
for a, b in zip(origins, origins[1:]):
    if b[0] - a[0] < rb.width() and abs(b[1] - a[1]) < rb.height(): print(json.dumps(dict(error='rail cells overlap', origins=origins))); sys.exit(3)
if mode == 'selftest_fail':
    # one Via3 cut 0.175 um off a rail Via3 cut, with Metal3 / Metal4 landings (the SO-1 mechanism)
    cut = sorted((s.bbox() for s in db.Region(rail.begin_shapes_rec(ly.layer(*V3))).each()), key=lambda b: (b.left, b.bottom))[0]
    c = cut.moved(origins[0][0] + 175, origins[0][1])
    fam.shapes(ly.layer(*V3)).insert(c)
    for l in (M3, M4): fam.shapes(ly.layer(*l)).insert(c.enlarged(300, 300))
top = ly.create_cell('asm'); top.insert(db.CellInstArray(fam.cell_index(), db.Trans()))
for x, y in origins: top.insert(db.CellInstArray(rail.cell_index(), db.Trans(db.Vector(x, y))))
for li in ly.layer_indexes():            # family labels on the top so that nets keep their names
    for s in fam.each_shape(li):
        if s.is_text(): top.shapes(li).insert(s)
o = db.SaveLayoutOptions(); o.add_cell(top.cell_index()); ly.write(out_gds, o)
print(json.dumps(dict(frame_um=[frame.left / 1e3, frame.bottom / 1e3, frame.right / 1e3, frame.top / 1e3],
                      provider_cells_in_frame=len(next(iter(frames.values()))), rail_cell=rail_src.name,
                      rail_origins_um=[[x / 1e3, y / 1e3] for x, y in origins], openings=len(ops))))
'''


def assemble(mode, gds, top, work):
    work.mkdir(parents=True, exist_ok=True)
    (work / 'asm_script.py').write_text(ASM)
    mounts = ['-v', f'{work}:/w', '-v', f'{PACKAGING.parent}:/pk:ro', '-v', f'{MASK.parent}:/mask:ro']
    fam = '/w/none.gds'
    if gds:
        gds = pathlib.Path(gds).resolve(); mounts += ['-v', f'{gds.parent}:/fam:ro']; fam = f'/fam/{gds.name}'
    p = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--user', f'{os.getuid()}:{os.getgid()}',
                        '-e', 'HOME=/tmp', '-e', 'OMP_NUM_THREADS=1', *mounts, '--entrypoint', '/bin/bash', IMAGE, '-lc',
                        f'python3 /w/asm_script.py {mode} {fam} {top} /w/asm.gds'], capture_output=True, text=True)
    (work / 'asm_script.py').unlink()
    line = next((l for l in reversed(p.stdout.splitlines()) if l.startswith('{')), None)
    info = json.loads(line) if line else dict(error=f'assembly exit {p.returncode}: {p.stderr[-800:]}')
    info['assembly_exit'] = p.returncode
    return info


def check(name, gds, top, out, threads=1, keep=False, mode='family'):
    work = pathlib.Path(out).resolve() / name
    info = assemble(mode, gds, top, work)
    info.update(name=name, gds=str(gds) if gds else None, top=top)
    if info['assembly_exit'] != 0:
        info['result'] = 'REFUSED'
    else:
        if gds: info['gds_sha256'] = kbd.sha256(gds)
        res = kbd.run('asm', work / 'asm.gds', 'asm', work, threads, ('main', 'antenna'))
        info['decks'] = {k: dict(total=v.get('total'), rules=v.get('rules'), error=v.get('error')) for k, v in res['decks'].items()}
        info['result'] = 'PASS' if res['clean'] else 'FAIL'
        if res['clean'] and not keep: (work / 'asm.gds').unlink(missing_ok=True)
    (work / 'site.json').write_text(json.dumps(info, indent=1) + '\n')
    print(f"RAIL-SITE {name}: {info['result']}", json.dumps({k: info.get(k) for k in ('rail_origins_um', 'decks', 'error')}))
    return info


def selftest(out):
    a = check('selftest_clean', None, 'st_clean', out, mode='selftest_clean')
    b = check('selftest_fail', None, 'st_fail', out, mode='selftest_fail', keep=True)
    c = check('selftest_badsize', None, 'st_bad', out, mode='selftest_badsize')
    v3 = sum(n for r, n in ((b.get('decks') or {}).get('main', {}).get('rules') or {}).items() if r.startswith('V3'))
    ok = (a['result'] == 'PASS' and a['rail_origins_um'] == [[100.0, 0.0]] and b['result'] == 'FAIL' and v3 > 0
          and c['result'] == 'REFUSED')
    print(f"SELFTEST {'OK' if ok else 'BROKEN'}: clean={a['result']} fail={b['result']} (Via3 items {v3}) badsize={c['result']}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gds'); ap.add_argument('--top'); ap.add_argument('--name')
    ap.add_argument('--family', action='append', default=[])
    ap.add_argument('--out', default=str(DEFAULT_OUT)); ap.add_argument('--threads', type=int, default=1)
    ap.add_argument('--keep', action='store_true'); ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest: sys.exit(0 if selftest(a.out) else 1)
    jobs = []
    if a.gds: jobs.append((a.name or pathlib.Path(a.gds).stem, pathlib.Path(a.gds), a.top))
    reg = json.loads(kbd.REGISTRY.read_text())['blocks']
    fams = [k for k, v in reg.items() if v.get('owner') == 'pads' and k.startswith('pad_')]
    for f in a.family:
        for n in (fams if f == 'all' else [f]): jobs.append((n, kbd.resolve(reg[n]['gds']), reg[n]['top']))
    if not jobs: ap.error('give --gds/--top, --family or --selftest')
    ok = all([check(n, g, t, a.out, a.threads, a.keep)['result'] == 'PASS' for n, g, t in jobs])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
