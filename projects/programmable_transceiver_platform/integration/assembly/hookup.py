#!/usr/bin/env python3
"""hookup.py <rf|wired> <place run dir> [--out report.md] [--gate]  |  hookup.py --selftest

Supply-hookup check: every block VDD / VSS supply pin of the chip against the connection the place stage drew for it.
The drawing is island_trunks._plates (kl_place, PLATES=1; plate, Via4 / Via3 arrays, 3x3 um holes on 24 um pitch over
28 um): this tool does not draw and does not copy that logic, it imports its limits and checks its result independently.

Per pin (currents: chips/<chip>/pin_currents.json, avg_ma, power owner; pin shapes: <run>/masters.json):
  * pin capacity: sum over the pin's shapes of narrow side x layer limit. Below the pin current the block pin itself is
    the limit -> NEEDS BLOCK EDIT (nothing outside the block can fix it). So is a Metal1/2-only pin with no landing.
  * connection (place.json grid_plates / direct_landings): width_eff x layer limit >= mA, Via4 cuts per layer change and
    Via3 cuts >= mA / 5.6, IR <= 10 mV recomputed here (Rs max from tech LEF over W_eff + 4.5 ohm per cut / cuts), and a
    landing must exist ('no path', 'landing clipped', 'no pin' fail).
Limits: MANDATE 2 (32 C, short life, 85 C DRM x 10 capped): Metal1-4 20.9 mA/um, Metal5 45 mA/um, 5.6 mA per cut.
Verdicts: FIXED (plate drawn, passes), OK (below 0.5 mA: router hook, 1 cut / 0.28 um carry 5.6 mA; or direct Via4
landing with enough cuts), BLOCK EDIT (pin limited), FAIL (fixable outside the block; generator work remains).
--gate: exit 1 on any FAIL or BLOCK EDIT."""
import sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import island_trunks as TRK          # limits and the plate threshold come from the plate generator (plates-hook)

K = TRK.K32
J = {'Metal1': 2.09*K, 'Metal2': 2.09*K, 'Metal3': 2.09*K, 'Metal4': 2.09*K, 'Metal5': 4.5*K}   # mA/um
V_CUT = TRK.V_LIM                   # mA per cut
DROP_MV = TRK.PLATE_DROP_MV
RS = TRK.RS                         # ohm/sq, tech LEF maximum (Metal4 / Metal5)
R_CUT = 4.5                         # ohm per via cut
ROUTER_HOOK_MA = min(J['Metal4']*0.28, V_CUT)   # one tech-default hook: 0.28 um Metal4, single cut
ADDENDUM1 = {'rf': {'lo_txbuf', 'lo_vreg', 'lo_mmd', 'rfdriver', 'pll_vreg2', 'rxmix_i', 'rxmix_q', 'adc_i', 'adc_q', 'lo_ext',
                    'vco_replica', 'bbfilter_i', 'bbfilter_q', 'lo_mmd_qdum', 'lna'},
             'wired': {'pll_vreg2', 'vco_replica', 'wrx_cap', 'usb_txdrv', 'ptrim', 'detect', 'slicer'}}


def pin_capacity(shapes):
    """shapes [(layer, [x0, y0, x1, y1])] -> (mA the pin can carry, layers, narrow side per shape)"""
    cap = 0.0; layers = set(); w = []
    for ln, r in sorted({(ln, tuple(r)) for ln, r in shapes}):      # abstracts repeat shapes (term_buffer VSS)
        n = min(r[2]-r[0], r[3]-r[1]); cap += n*J.get(ln, J['Metal4']); layers.add(ln); w.append((ln, round(n, 2)))
    return cap, layers, w


def edge_gap(shapes, info):
    """smallest distance (um) of any pin shape to the cell outline (masters.json pins are in the 0..w x 0..h abstract frame)"""
    W, H = info['w'], info['h']; g = 1e9
    for ln, r in shapes:
        g = min(g, r[0], r[1], W-r[2], H-r[3])
    return max(0.0, g)


GDSL = {'Metal3': 42, 'Metal4': 46, 'Metal5': 81}
REPO = '/repo' if os.path.isdir('/repo/projects') else os.path.abspath(os.path.join(HERE, '../../../..'))
CLEAR = 0.7                          # um: the landing rule's clearance to the block's other-net metal (island_trunks LP own)
_GDS = {}


def edge_blocked(info, shapes):
    """Block's own metal in the landing corridor (read from the block GDS). For each pin shape: the corridor from the pin to
    the nearest cell edge, pin wide. Candidate landing layers: the pin's layer and the one above (Metal4/5 only; a plate is
    Metal4/5 with Via4/Via3). A layer is blocked when block metal not joined to the pin lies within CLEAR of the corridor.
    Returns None (a layer is clear, or no klayout / GDS), else a text naming the blocking metal (cell coordinates)."""
    try: import klayout.db as db
    except ImportError: return None
    g = os.path.join(REPO, info.get('gds', ''))
    if not info.get('gds') or not os.path.exists(g): return None
    if g not in _GDS:
        ly = db.Layout(); ly.read(g); _GDS[g] = ly
    ly = _GDS[g]; c = ly.cell(info.get('cell', '')) or ly.top_cell(); o = info.get('origin', [0, 0]); W, H = info['w'], info['h']
    um = lambda v: int(round(v*1000)); out = []
    for ln, r in sorted({(ln, tuple(r)) for ln, r in shapes}):
        gap = {'W': r[0], 'S': r[1], 'E': W-r[2], 'N': H-r[3]}; e = min(gap, key=gap.get)
        x0, y0, x1, y1 = r[0]+o[0], r[1]+o[1], r[2]+o[0], r[3]+o[1]; ox0, oy0, ox1, oy1 = o[0], o[1], o[0]+W, o[1]+H
        cor = {'W': (ox0, y0, x1, y1), 'E': (x0, y0, ox1, y1), 'S': (x0, oy0, x1, y1), 'N': (x0, y0, x1, oy1)}[e]
        cb = db.Box(*[um(v) for v in cor]); pin = db.Region(db.Box(um(x0), um(y0), um(x1), um(y1)))
        cands = [l for l in (ln, {'Metal3': 'Metal4', 'Metal4': 'Metal5'}.get(ln)) if l in ('Metal4', 'Metal5')]
        if not cands: out.append(f'{ln} pin: no Metal4/5 landing layer'); continue
        why = []
        for L in cands:
            li = ly.find_layer(GDSL[L], 0)
            if li is None: return None
            win = cb.enlarged(um(CLEAR+1), um(CLEAR+1))
            m = db.Region(c.begin_shapes_rec_touching(li, win)).merged() & db.Region(win)
            own = m.interacting(pin) if L == ln else db.Region()
            foreign = (m - own) & db.Region(cb).sized(um(CLEAR))
            if foreign.is_empty(): return None
            bl = [p.bbox() for p in foreign.each()][:3]
            why.append(f'{L} block metal ' + ' '.join(f'({b.left/1000:.2f},{b.bottom/1000:.2f})-({b.right/1000:.2f},{b.top/1000:.2f})' for b in bl)
                       + f' within {CLEAR} um of the pin-wide corridor')
        out.append(f'{ln} pin edge {e}: ' + ', '.join(why))
    return '; '.join(out) if out else None


def check_conn(mA, rep):
    """rep: one grid_plates record. Returns (ok, [reasons], drop_mV recomputed)."""
    bad = []
    if 'error' in rep: return False, [f"no landing ({rep['error']})"], None
    W = rep['width_um']; We = rep.get('width_eff_um', W); L5 = rep.get('len_m5_um', 0.0); L4 = rep.get('len_m4_um', 0.0)
    ln = 'Metal4' if (L4 > 0 or L5 == 0) else 'Metal5'
    if mA > We*J[ln]: bad.append(f'strap {We} um {ln} carries {We*J[ln]:.1f} < {mA} mA (needs {mA/J[ln]:.2f} um)')
    nch = rep.get('layer_changes', 0); v4 = rep.get('via4', 0); v3 = rep.get('via3', 0)
    per = v4/nch if nch else None
    if nch and per*V_CUT < mA: bad.append(f'Via4 {per:.0f} cuts per layer change carry {per*V_CUT:.1f} < {mA} mA (needs {math.ceil(mA/V_CUT)})')
    if v3 and v3*V_CUT < mA: bad.append(f'Via3 {v3} cuts carry {v3*V_CUT:.1f} < {mA} mA (needs {math.ceil(mA/V_CUT)})')
    Wi = W/(1+(3/24)**2/(1-3/24)) if rep.get('slots') else W     # IR: holes take 3/24 of the width over 3/24 of the length
    R = RS['Metal5']*L5/Wi + RS['Metal4']*L4/Wi + (R_CUT/per if nch else 0.0) + (R_CUT/v3 if v3 else 0.0)
    drop = max(mA*R, rep.get('drop_mV', 0.0))
    if drop > DROP_MV: bad.append(f'IR {drop:.1f} mV > {DROP_MV} mV')
    if not rep.get('neck_ok', True) and not rep.get('neck_at_pin', False): bad.append('neck in the plate narrower than the current needs')
    return not bad, bad, round(drop, 2)


def verdict(mA, shapes, rep, direct_v4=None):
    """-> (verdict, detail). shapes: the pin's shapes; rep: grid_plates record or None; direct_v4: Via4 count of a direct landing."""
    if not shapes: return 'BLOCK EDIT', 'pin has no shapes in the abstract'
    cap, layers, w = pin_capacity(shapes)
    if cap < mA:
        need = mA/J[max(layers)]
        return 'BLOCK EDIT', f'pin {w} carries {cap:.1f} < {mA} mA: widen to >= {need:.2f} um on {max(layers)} (or Metal5 >= {mA/J["Metal5"]:.2f} um)'
    if direct_v4 is not None and (rep is None or 'error' in rep):
        if direct_v4*V_CUT >= mA: return 'OK', f'direct Via4 landing, {direct_v4} cuts'
        return 'FAIL', f'direct Via4 landing {direct_v4} cuts carry {direct_v4*V_CUT:.1f} < {mA} mA'
    if rep is None or str(rep.get('error', '')).startswith('below'):
        if mA <= TRK.PLATE_MIN_MA and mA <= ROUTER_HOOK_MA: return 'OK', 'router hook (below 0.5 mA)'
        if rep is None: return 'FAIL', 'no landing (no plate record, no direct landing)'
    ok, bad, drop = check_conn(mA, rep)
    if ok: return 'FIXED', f"plate {rep['width_eff_um']} um, Via4 {rep.get('via4', 0)}, Via3 {rep.get('via3', 0)}, {drop} mV"
    if layers <= {'Metal1', 'Metal2'} and 'error' in rep:
        return 'BLOCK EDIT', f'pin only on {sorted(layers)}: no plate layer reaches it; bring the pin to Metal3-5 at the edge'
    if rep.get('neck_at_pin') and not rep.get('neck_ok'):
        return 'BLOCK EDIT', 'neck inside the pin-wide landing corridor: block pin/edge limits it; ' + '; '.join(bad)
    return 'FAIL', '; '.join(bad)


def run(chip, rundir, out=None):
    rows = json.load(open(os.path.join(REPO, f'projects/programmable_transceiver_platform/integration/chips/{chip}/pin_currents.json')))['rows']
    MJ = json.load(open(os.path.join(rundir, 'masters.json'))); P = json.load(open(os.path.join(rundir, 'place.json')))
    gp = P.get('grid_plates', {}); dl = {(d['inst'], d['net']): d['via4'] for d in P.get('direct_landings', [])}
    pads = set(json.load(open(os.path.join(rundir, 'pads.json'))).get('pads', [])) if os.path.exists(os.path.join(rundir, 'pads.json')) else set()
    pins = {}
    for r in rows:
        if r['kind'] != 'supply' or r['net'] not in ('VDD', 'VSS') or r['inst'] in ('digital', 'host') or r['inst'] in pads or r['inst'].startswith('pad_'): continue
        k = (r['inst'], r['net'])
        if r['avg_ma'] > pins.get(k, (0,))[0]: pins[k] = (r['avg_ma'], r['pin'], r['master'])
    res = []
    for (inst, net), (mA, pin, master) in sorted(pins.items(), key=lambda kv: -kv[1][0]):
        if inst not in P['blocks']: res.append((inst, pin, net, mA, 'NOT IN RUN', 'instance not among the placed blocks (pad ring / not in this floorplan): not checked')); continue
        m = P['blocks'][inst]['master']; rep = gp.get(f'{inst}.{net}')
        if rep and rep.get('pin'): pin = rep['pin']
        shapes = MJ.get(m, {}).get('pins', {}).get(pin, [])
        v, d = verdict(mA, shapes, rep, dl.get((inst, net)))
        if v == 'FAIL' and d.startswith('no landing') and shapes:
            info = MJ[m]; e = edge_gap(shapes, info)
            eb = edge_blocked(info, shapes) if e <= 30.0 else None
            if e > 30.0: v, d = 'BLOCK EDIT', f'pin {e:.0f} um inside the cell edge (MANDATE 4a: supply pins on the cell edge); ' + d
            elif eb: v, d = 'BLOCK EDIT', f'landing corridor blocked by the block\'s own metal: {eb}; clear it or move the pin; ' + d
            else: d += ' (pin on the edge, corridor clear of block metal' + ('' if _GDS else ', GDS NOT CHECKED: no klayout') + '): top-level landing work'
        res.append((inst, pin, net, mA, v, d))
    cnt = {k: sum(1 for x in res if x[4] == k) for k in ('FIXED', 'OK', 'BLOCK EDIT', 'FAIL', 'NOT IN RUN')}
    lines = [f'# Supply hookup, pt_{chip}', '',
             f'Run: `{rundir}` (place level, not routed). Currents: chips/{chip}/pin_currents.json avg_ma. Limits: Metal1-4 {J["Metal4"]:.1f}, '
             f'Metal5 {J["Metal5"]:.0f} mA/um, {V_CUT:.1f} mA/cut, {DROP_MV:.0f} mV per connection. Generated by integration/assembly/hookup.py.', '',
             f'Pins: {len(res)}. FIXED {cnt["FIXED"]}, OK {cnt["OK"]}, BLOCK EDIT {cnt["BLOCK EDIT"]}, FAIL {cnt["FAIL"]}, NOT IN RUN {cnt["NOT IN RUN"]}.', '',
             '| Verdict | Pin | mA | Addendum 1 | Detail |', '|---|---|---|---|---|']
    order = {'BLOCK EDIT': 0, 'FAIL': 1, 'NOT IN RUN': 2, 'FIXED': 3, 'OK': 4}
    for inst, pin, net, mA, v, d in sorted(res, key=lambda x: (order[x[4]], -x[3])):
        lines.append(f'| {v} | {inst}.{pin} ({net}) | {mA:.2f} | {"yes" if inst in ADDENDUM1.get(chip, ()) and net == "VSS" else ""} | {d} |')
    txt = '\n'.join(lines) + '\n'
    if out: open(out, 'w').write(txt)
    print(txt if not out else f'{out}: ' + ', '.join(f'{k} {v}' for k, v in cnt.items()))
    return cnt


def selftest():
    """Negative tests: each must FAIL (or BLOCK EDIT); a tool that says OK/FIXED on any of them is broken."""
    good = dict(pin='VSS', width_um=10.0, width_eff_um=10.0, len_m5_um=20.0, len_m4_um=0.0, via4=40, via3=0, layer_changes=1, drop_mV=1.0, neck_ok=True)
    m5 = [('Metal5', [0, 0, 20.0, 30.0])]
    cases = [
        ('known-good control 30 mA, 10 um M5, 40 cuts', 30.0, m5, good, None, ('FIXED',)),
        ('too few cuts: 30 mA over 4 Via4 cuts', 30.0, m5, dict(good, via4=4), None, ('FAIL',)),
        ('strap too narrow: 30 mA on 0.5 um', 30.0, m5, dict(good, width_um=0.5, width_eff_um=0.5), None, ('FAIL',)),
        ('no landing: no path', 30.0, m5, dict(mA=30.0, error='no path'), None, ('FAIL',)),
        ('no landing: no record at all', 30.0, m5, None, None, ('FAIL',)),
        ('74 mA pin on a 2 um M4 landing', 74.0, [('Metal4', [0, 0, 2.0, 30.0])], good, None, ('BLOCK EDIT',)),
        ('74 mA pin fine, 2 um M4 strap', 74.0, m5, dict(good, width_um=2.0, width_eff_um=2.0, len_m4_um=5.0), None, ('FAIL',)),
        ('IR: 30 mA through 2000 um of 10 um M5', 30.0, m5, dict(good, len_m5_um=2000.0), None, ('FAIL',)),
        ('direct landing 1 cut for 20 mA', 20.0, m5, None, 1, ('FAIL',)),
        ('M1-only pin, no landing', 3.0, [('Metal1', [0, 0, 1.0, 30.0])], dict(mA=3.0, error='no path'), None, ('BLOCK EDIT',)),
    ]
    nf = 0
    for name, mA, sh, rep, dv, want in cases:
        v, d = verdict(mA, sh, rep, dv)
        st = 'pass' if v in want else 'BROKEN'; nf += st != 'pass'
        print(f'{st:6s} {name}: {v} ({d})')
    try:
        import klayout.db as db, tempfile
        for name, block, want in (('edge corridor crossed by block Metal5', True, True), ('edge corridor clear', False, False)):
            ly = db.Layout(); ly.dbu = 0.001; c = ly.create_cell('t'); l5 = ly.layer(81, 0)
            c.shapes(l5).insert(db.Box(8000, 15000, 12000, 20000))              # pin, top edge, Metal5
            if block: c.shapes(l5).insert(db.Box(0, 19000, 7700, 19800))       # foreign Metal5 0.3 um from the corridor
            fn = tempfile.mktemp(suffix='.gds'); ly.write(fn)
            info = dict(gds=fn, cell='t', origin=[0, 0], w=20.0, h=20.0)
            r = edge_blocked(info, [('Metal5', [8.0, 15.0, 12.0, 20.0])]); os.unlink(fn); _GDS.clear()
            st = 'pass' if (r is not None) == want else 'BROKEN'; nf += st != 'pass'
            print(f'{st:6s} {name}: {r}')
    except ImportError:
        print('SKIP   edge-corridor GDS tests (no klayout here; run through tool.sh)')
    print('selftest', 'OK' if nf == 0 else f'FAILED {nf}'); return nf == 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--selftest': sys.exit(0 if selftest() else 1)
    if len(a) < 2: print(__doc__); sys.exit(2)
    out = a[a.index('--out')+1] if '--out' in a else None
    c = run(a[0], a[1], out)
    sys.exit(1 if '--gate' in a and (c['FAIL'] or c['BLOCK EDIT']) else 0)
