#!/usr/bin/env python3
"""Stage `floorplan` (host python): legal block placement of one chip with the die-fit packer on real geometry.

  floorplan.py <chip>          reads <run>/pads.json and <run>/masters.json (stage abstract), writes <run>/floorplan.json + .png

The packer and its rules are scratch/reviews/die-fit/fit.py (signal-flow targets, keep-aways incl. the INT23 QVCO rule,
island-switch ring positions, decap bank and tiles, digital macro on the north edge), run as-built (scenario S) with two
inputs replaced: PADS_JSON = the footprints of the pad cells as placed on the template openings (grown by PAD_CLEAR into
the core so the core ring can pass round them), SIZES_JSON = the outline of every master's GDS. Legality is re-checked
here independently (no overlap of blocks, pads, provider cells; inside the core)."""
import json, os, subprocess, sys
A = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, A)
import common as C
chip = sys.argv[1]; RUN = os.environ.get('ASM_RUN', f'{C.ROOT}/scratch/integration/assembly-{chip}')
pads = json.load(open(RUN+'/pads.json')); MJ = json.load(open(RUN+'/masters.json'))
inst, ports, masters = C.load(chip)

g = C.PAD_CLEAR
pj = {}
for n, v in pads['pads'].items():
    pj[n] = [[r[0]-g if v['side'] == 'east' else r[0], r[1]-g, r[2]+g if v['side'] == 'west' else r[2], r[3]+g] for r in v['footprint']]
sizes = {m: [round(v['w'], 2), round(v['h'], 2)] for m, v in MJ.items() if v.get('w')}
json.dump(pj, open(RUN+'/fp_pads.json', 'w')); json.dump(sizes, open(RUN+'/fp_sizes.json', 'w'))
macro = {'rf': '1716:1108', 'wired': '1716:1108,1716:1262'}[chip]
env = dict(os.environ, CHIP=chip, SCEN='S', TAG='s', TRIES=os.environ.get('TRIES', '6'), PADS_JSON=RUN+'/fp_pads.json',
           SIZES_JSON=RUN+'/fp_sizes.json', RUNDIR=RUN+'/fit', OMP_NUM_THREADS='1', MACRO=os.environ.get('MACRO', macro))
fit = C.ROOT+'/scratch/reviews/die-fit'
r = subprocess.run(['true'] if os.environ.get('REUSE_FIT') else ['nice', '-n', '10', 'python3', 'fit.py'], cwd=fit, env=env, capture_output=True, text=True)
if not os.environ.get('REUSE_FIT'): open(RUN+'/fit/fit.log', 'w').write(r.stdout+r.stderr)
if r.returncode: print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit(1)
F = json.load(open(RUN+'/fit/fit-s.json'))
L = {x['item']: x for x in json.load(open(f'{fit}/{chip}/ledger.json'))['rows']}

blocks = {}
for n, v in F['placed_rects'].items():
    m = 'decap' if n.startswith(('decap_bank', 'decap_tile')) else L.get(n, {}).get('master', n)
    if m == '(booked)': m = n
    blocks[n] = dict(master=m, rect=v['rect'], rot=v['rot'], in_conn=n in inst, gds=bool(MJ.get(m, {}).get('w')))
blocks['digital'] = dict(master='pt_digital_macro', rect=F['fixed']['digital'], rot=False, in_conn=True, gds=False)
reserves = {n: r for n, r in F['fixed'].items() if n != 'digital'}
core_blocks = {n for n, i in inst.items() if not i['master'].startswith(C.PROVIDER) and n not in pads['pads']}
missing = sorted(core_blocks-set(blocks))
# conn blocks the ledger does not book (new or retiring instances): second pass of the same packer into what is left,
# pulled to the block they connect to most (shared nets), 10 um halo
sys.path.insert(0, fit); from packer import Packer
pk = Packer(C.CORE, G=2.0)
for n, v in pj.items(): pk.fixed(n, v)
for n, b in blocks.items(): pk.fixed(n, [b['rect']], halo=10.0 if not n.startswith('decap') else 0.0)
for n, r in reserves.items(): pk.fixed(n, [r])
def partner(n):
    mine = {net for k, net in inst[n]['pins'].values()} - {'VDD', 'VSS', '-'}
    sc = {}
    for o, i in inst.items():
        if o != n and o in blocks: sc[o] = len(mine & {net for k, net in i['pins'].values()})
    for o, v in pads['pads'].items():
        sc[o] = len(mine & {net for k, net in inst[o]['pins'].values()}) if o in inst else 0
    return max(sc, key=sc.get) if sc and max(sc.values()) else None
second = {}; dropped = []
def ov(a, b): return min(a[2], b[2])-max(a[0], b[0]) > 1e-6 and min(a[3], b[3])-max(a[1], b[1]) > 1e-6
for n in sorted(missing, key=lambda n: -(sizes.get(inst[n]['master'], [50, 50])[0]*sizes.get(inst[n]['master'], [50, 50])[1])):
    m = inst[n]['master']; w, h = sizes.get(m, [100.0, 100.0]); t = partner(n)
    if t in pads['pads']: pk.rects[t] = tuple(pads['pads'][t]['footprint'][0])
    r = pk.place(n, w, h, halo=10.0, targets=[(t, 1.0)] if t else [], anchor=None, lam=0.6, step=2)
    if r is None:          # no hole: decap tiles give way (conn blocks before decap; the shortfall is reported)
        pk2 = Packer(C.CORE, G=2.0)
        for k, v in pj.items(): pk2.fixed(k, v)
        for k, b in blocks.items():
            if not k.startswith(('decap_tile', 'decap_bank')): pk2.fixed(k, [b['rect']], halo=10.0 if not k.startswith('decap') else 0.0)
        for k, rr in reserves.items(): pk2.fixed(k, [rr])
        if t in pads['pads']: pk2.rects[t] = tuple(pads['pads'][t]['footprint'][0])
        r = pk2.place(n, w, h, halo=10.0, targets=[(t, 1.0)] if t else [], anchor=None, lam=0.6, step=2)
        if r:
            for k in [k for k in blocks if k.startswith(('decap_tile', 'decap_bank')) and ov([r[0]-10, r[1]-10, r[2]+10, r[3]+10], blocks[k]['rect'])]:
                dropped.append(k); del blocks[k]
            pk.mark(r, 10.0); pk.rects[n] = r; pk.placed[n] = pk2.placed[n]
    print("pass2", n, m, w, h, t, r)
    if r: blocks[n] = dict(master=m, rect=list(r), rot=pk.placed[n]['rot'], in_conn=True, gds=bool(MJ.get(m, {}).get('w')), pass2=t); second[n] = t
missing = sorted(core_blocks-set(blocks))

# independent legality check
def ov(a, b): return min(a[2], b[2])-max(a[0], b[0]) > 1e-6 and min(a[3], b[3])-max(a[1], b[1]) > 1e-6
bad = []
names = list(blocks)
padr = [(n, r) for n, v in pads['pads'].items() for r in v['footprint']]+[('io:'+s, v['bbox']) for s, v in pads['io'].items()]
for i, a in enumerate(names):
    ra = blocks[a]['rect']
    if ra[0] < C.CORE[0]-1e-6 or ra[1] < C.CORE[1]-1e-6 or ra[2] > C.CORE[2]+1e-6 or ra[3] > C.CORE[3]+1e-6: bad.append((a, 'outside core'))
    for b in names[i+1:]:
        if ov(ra, blocks[b]['rect']): bad.append((a, b))
    for p, rp in padr:
        if ov(ra, rp): bad.append((a, p))
out = dict(chip=chip, die=C.DIE, core=C.CORE, macro=F['macro'], blocks=blocks, reserves=reserves, unplaced=F['unplaced'],
           relaxed=F['relaxed'], rule_audit=F['rule_audit'], rule_fails=F['rule_fails'], conn_not_placed=missing, second_pass=second, decap_tiles_given_up=dropped, decap_tiles_unplaced=[u[0] for u in F['unplaced'] if u[0].startswith('decap')],
           overlaps=bad, switches=F['switches'], pad_clear_um=g)
json.dump(out, open(RUN+'/floorplan.json', 'w'), indent=0)
print(f"{chip}: placed {len(blocks)} (conn blocks without a place: {missing}), unplaced {F['unplaced']}, relaxed {len(F['relaxed'])}, "
      f"keep-away fails {len(F['rule_fails'])}, overlaps {len(bad)} {bad[:6]}")
