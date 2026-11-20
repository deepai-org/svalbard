"""Per-chip configuration of the PDN model: apply('rf' | 'wired') sets the geometry, bonds, islands, switches, loads, victims
and the 5.4 nF decap plan of that chip. One model for both chips; nothing here is chip-specific except the data it reads.

Sources (read, never edited here):
  geometry, switch / decap positions  scratch/reviews/die-fit/run/<chip>/fit-s.json   (as-built packing, scenario S)
  decap split per part                scratch/reviews/die-fit/decap.json              (<chip>.scenarios.asbuilt)
  bonds                               integration/chips/<chip>/bond_map.txt + analog/pads/generated/provider-sites.json
  islands                             spec/chips.json
  currents, masters, macro current    spec/budgets/power_budget.py (MEASURED, ISLAND_SWITCH[chip], dig_meas(chip))
The interior grid, the switch-to-ring feed and the island straps are set to their REQUIREMENT limits
(spec/power-delivery.md), so a pass means "a floorplan that meets the requirement passes", not an extraction."""
import json, os, sys
import model as M, core as C, loads as LD
pb = LD.pb
DF = f'{M.ROOT}/scratch/reviews/die-fit'
CHIP = None
X_FEED = 1.0-pb.RFDRV_DIE_FRACTION           # share of the rfdriver current that enters through the RF_TX pads
STRAP_MV = 15.0                              # requirement: switch VISL bar -> any block supply pin, at the block's worst current
GRID = dict(cov_m5=0.15, cov_m4=0.15)        # requirement: per-net coverage, Metal5 vertical / Metal4 horizontal
# island-rail capacitance in the model (block-internal, lossy, 0.3 ohm): no decap is ADDED on any island rail by the plan
ISL_C = dict(wired_cap=100e-12, wired_rx=60e-12, wired_tx=50e-12, rf_rx=120e-12, rf_tx=80e-12, lod=150e-12, lo=100e-12, pll=150e-12,
             conv=250e-12, debug=100e-12)
# budget row -> floorplan rectangle that is its supply tap (the die-fit names), where the names differ
TAP = dict(qvco_pre='qvco', pll_misc='cdr', wiredtx8='wtx_mux8', wtx_post='wtx_mux8', wtx_padtail='pad_wire_tx', usbhs='usb_txdrv',
           bias='core_bias', usbfs='pad_usb', ctle_follower='ctle_follower_x2', wordclk=('wordclk_rx', 'clockmux'))   # tuple: first present
SPIRALS = ('qvco', 'lna_ind_p', 'lna_ind_n', 'lna_deg_p', 'lna_deg_n')
CASE_MODE = {'W': ('wired', None), 'U': ('usb', None), 'T': ('wired', None), 'RXe': ('rf_rx', 'rf_rx'), 'RXa': ('rf_rx', 'rf_rx'),
             'TXe': ('rf_tx', 'rf_tx'), 'TXa': ('rf_tx', 'rf_tx'), 'DXe': ('rf_rx', 'rf_duplex'), 'DXa': ('rf_rx', 'rf_duplex'),
             'stopped': ('stopped', None)}
CASES = []; ISLANDS = []; DECAP = {}; DIG = {}; MAIN = None; FIT = None; TILE_SCALE = 1.0
TAU_TILE = 335e-12     # pt_decap_tile: 152 ps tie-NMOS (extracted) + ~175-195 ps pfet L = 6 channel that the model cannot see
TAU_ROW = 60e-12       # 7T fillcap / pt_decap50 (54.5 tt - 69.7 ss ps)
TAU_MIM = 5e-12        # no ESR in the PDK model: plate + via estimate (grid resistance is in the mesh)


def chip_arg(argv=None, default=None):
    """'chip=rf' on the command line, else $PDN_CHIP, else default."""
    for a in (argv if argv is not None else sys.argv[1:]):
        if a.startswith('chip='): return a.split('=', 1)[1]
    c = os.environ.get('PDN_CHIP', default)
    if c not in ('rf', 'wired'): sys.exit('usage: <script> chip=rf|wired [...]')
    return c


def _bonds(chip):
    sites = json.load(open(f'{M.PRJ}/analog/pads/generated/provider-sites.json'))['sites']
    rows = [l.split()[:4] for l in open(f'{M.PRJ}/integration/chips/{chip}/bond_map.txt') if l.strip() and not l.startswith('#')]
    W, H = 3932.0, 5122.0
    def t(site, side):
        x, y = sites[site]['bond_center_um']
        return {'south': x, 'east': W+y, 'north': W+H+(W-x), 'west': 2*W+H+(H-y)}[side]
    order = sorted(rows, key=lambda r: t(r[0], r[1]))
    ring = {r[0]: k+1 for k, r in enumerate(order)}
    out = []
    for site, side, net, inst in rows:
        if net not in ('VDD', 'VSS'): continue
        x, y = sites[site]['bond_center_um']
        out.append(dict(site=site, x=x, y=y, net=net, side=side, ring=ring[site], inst=inst,
                        cap=net == 'VDD' and inst.startswith(('pad_dvdd', 'pad_vdd'))))
    return out


def apply(chip=None):
    global CHIP, CASES, ISLANDS, DECAP, DIG, MAIN
    if chip is None and CHIP: return
    chip = chip or chip_arg()
    if CHIP == chip: return
    assert CHIP is None, 'one chip per process'
    CHIP = chip
    global FIT, TILE_SCALE
    asm = os.environ.get('PDN_ASSEMBLY')      # =1: the chip assembly's floorplan (scratch/integration/assembly-<chip>) instead of the die fit
    fit = json.load(open(f'{M.ROOT}/scratch/integration/assembly-{chip}/fit/fit-s.json' if asm else f'{DF}/run/{chip}/fit-s.json'))
    if asm:
        fp = json.load(open(f'{M.ROOT}/scratch/integration/assembly-{chip}/floorplan.json'))
        n_plan = sum(1 for k in fit['placed_rects'] if k.startswith('decap_tile'))+len(fp.get('decap_tiles_unplaced', []))
        fit['placed_rects'] = {k: dict(rect=v['rect']) for k, v in fp['blocks'].items()}
        n_have = sum(1 for k in fit['placed_rects'] if k.startswith('decap_tile'))
        TILE_SCALE = n_have/n_plan if n_plan else 1.0
    FIT = fit
    M.RECTS.clear()
    for k, v in fit['placed_rects'].items(): M.RECTS[k] = v['rect']
    for k, v in fit['fixed'].items(): M.RECTS[k] = v
    for k, v in fit['pads'].items(): M.RECTS[k] = v[0]
    M.DIG[:] = fit['fixed']['digital']
    M.CUSTOM['west'] = [(r[0][1], r[0][3]) for r in fit['pads'].values() if r[0][0] < 500]
    M.CUSTOM['east'] = [(r[0][1], r[0][3]) for r in fit['pads'].values() if r[0][2] > 3400]
    M.BONDS[:] = _bonds(chip)
    M.P['ring_custom'] = (1.0, 1.0, 1.0)    # verified on the v5 run2 GDS: provider rails are uncut through all custom sites
    ISLANDS = list(pb.CHIPS[chip]['islands']); CASES = list(pb.CHIP_CASES[chip])
    DIG = pb.dig_meas(chip)
    M.ISW.clear(); M.ISL_C.clear()
    for isl in ISLANDS:
        m, n = pb.ISLAND_SWITCH[chip][isl]
        M.ISW[isl] = pb.SWITCH_MASTER[m][1]/n; M.ISL_C[isl] = ISL_C[isl]
        if f'isw_{isl}' not in M.RECTS: raise SystemExit(f'no isw_{isl} in the {chip} packing')
    LD.MAP.clear()
    for r in pb.MEASURED:
        if r[1] is not None and r[1] not in ISLANDS or not set(pb.pd2_expand(r)) & set(CASES): continue
        t = TAP.get(r[0], r[0]); t = next((x for x in t if x in M.RECTS), t[0]) if isinstance(t, tuple) else t
        if t not in M.RECTS: raise SystemExit(f'{chip}: tap {t} of {r[0]} not in the packing')
        LD.MAP[r[0]] = (t, r[1])
    if 'lod' in ISLANDS: LD.MAP['lo_obs'] = ('lo_obs', 'lod')     # debug load on a functional rail (ISLAND_EXTRA_WORST_MA)
    C.EXTRA_TAPS[:] = [('pll_vreg2', 'pll'), ('por', None)]
    C.VICT.clear()
    if chip == 'rf':
        C.VICT.update({'core_bias': ('core_bias', None), 'por': ('por', None), 'adc_i': ('adc_i', 'conv'), 'refbuf': ('refbuf', 'conv'),
                       'qvco': ('qvco', 'lo'), 'pll_vreg2': ('pll_vreg2', 'pll'), 'lna': ('lna', 'rf_rx'), 'lo_mmd': ('lo_mmd', 'lod'),
                       'rfdriver': ('rfdriver', 'rf_tx')})
        C.PORTS[:] = ['dig', 'd2h0', 'd2h1', 'adc', 'rfd', 'lo']
    else:
        C.VICT.update({'core_bias': ('core_bias', None), 'por': ('por', None), 'pll_vreg2': ('pll_vreg2', 'pll'), 'slicer': ('slicer', 'wired_rx'),
                       'wiredtx': ('wtx_mux8', 'wired_tx'), 'wrx_cap': ('wrx_cap', 'wired_cap')})
        C.PORTS[:] = ['dig', 'd2h0', 'd2h1', 'wrx', 'wtx']
        w = {k: [pb.pd2_expand(r)['W'] for r in pb.MEASURED if r[0] == k][0] for k in ('wiredtx8', 'wtx_post', 'wtx_padtail')}
        LD.WTX_MA = (w['wiredtx8'][0], sum(v[0] for v in w.values()), sum(v[1] for v in w.values()))
    DECAP = dict(json.load(open(f'{DF}/decap.json'))[chip]['scenarios']['asbuilt'])
    DECAP['tiles_nF'] = round(DECAP['tiles_nF']*TILE_SCALE, 3)   # tiles the floorplan actually holds (1.0 for the die fit)


def strap_R(strap_mv=STRAP_MV):
    """Requirement limit: each island tap's switch->pin strap drops strap_mv at the worst in-window current of all budget
    rows on that tap (any one case). Keyed 'tap|island'."""
    tot = {}
    for c in CASES:
        s = {}
        for r in pb.MEASURED:
            if r[0] not in LD.MAP or not r[1]: continue
            v = pb.pd2_expand(r).get(c)
            if not v: continue
            k = '%s|%s' % LD.MAP[r[0]]; s[k] = s.get(k, 0.0)+v[1]*(pb.RFDRV_DIE_FRACTION if r[0] == 'rfdriver' else 1.0)
        for k, v in s.items(): tot[k] = max(tot.get(k, 0.0), v)
    if 'lod' in ISLANDS: tot['lo_obs|lod'] = pb.ISLAND_EXTRA_WORST_MA['lod']
    out = {k: strap_mv/v for k, v in tot.items() if v > 0}
    out['pll_vreg2|pll'] = out['pll_cdr|pll']
    return out


def strap_width_um(tap, isl, rs=0.070):
    """Metal5 strap width (um, maximum sheet resistance) that meets the strap budget over the packed switch-to-tap
    Manhattan distance."""
    if not isl: return None
    x, y = M.centre(tap); sx, sy = M.centre(f'isw_{isl}')
    return rs*(abs(x-sx)+abs(y-sy))/strap_R()[f'{tap}|{isl}']


def pset(sel, grid=None, strap_mv=STRAP_MV, **over):
    apply()
    g = dict(GRID); g.update(grid or {})
    p = M.pset(sel)
    p['grid_cov'] = g['cov_m5']; p['grid_cov_m4'] = g['cov_m4']; p['strap_R'] = strap_R(strap_mv)
    p.update(over)
    return p


def dc_loads(case, level):
    """level: pd2n = nominal (digital: chip-scaled nominal, host typical); pd2w = worst in-window analog, chip-scaled worst
    digital, host 8 pF; pd2u = pd2w with the digital macro at the unscaled 81.79 mA; pd2r = worst analog, digital at PWR-DIG."""
    apply()
    m, rdir = CASE_MODE[case]; k = 0 if level == 'pd2n' else 1
    out = []
    for r in pb.MEASURED:
        if r[0] not in LD.MAP: continue
        v = pb.pd2_expand(r).get(case)
        if v and v[k] > 0: out.append((r[0], LD.MAP[r[0]][0], r[1], v[k]))
    if level != 'pd2n' and case.endswith('a') and 'lod' in ISLANDS:     # lo_obs observing: worst only, autonomous-LO cases
        out.append(('lo_obs', 'lo_obs', 'lod', pb.ISLAND_EXTRA_WORST_MA['lod']))
    if case == 'stopped': return out, 2.0, 1.0, m, rdir
    rf = rdir is not None
    dig = {'pd2n': DIG['nominal'], 'pd2w': DIG['worst'], 'pd2u': DIG['worst_unscaled'], 'pd2r': DIG['req_rf' if rf else 'req_wired_usb']}[level]
    host = (pb.HOST_MEAS['nominal'] if level == 'pd2n' else pb.HOST_MEAS['worst'])*(pb.RF_HOSTIO_FACTOR if rf else 1.0)
    return out, dig, host, m, rdir


# ---- decap: the 5.4 nF plan of this chip, placed where its die-fit packing put each part ------------------------------
def _spread(rects, nF, tau, split=None):
    """nF over the given rectangles, weighted by area, one lump at each rectangle centre."""
    if nF <= 0 or not rects: return []
    a = [(r[2]-r[0])*(r[3]-r[1]) for r in rects]; A = sum(a); out = []
    for r, ai in zip(rects, a):
        c = nF*1e-9*ai/A; out.append(((r[0]+r[2])/2, (r[1]+r[3])/2, c, tau/c))
    return out


def lumps(where, nF, tau):
    """where: macro (every mesh node inside the macro outline) | sites (ring nodes inside the custom pad spans: MOS under the
    custom bond sites)."""
    if nF <= 0: return []
    if where == 'macro': nodes = [(i, j) for i in range(M.NX) for j in range(M.NY) if M.in_dig(i, j)]
    elif where == 'sites':
        nodes = []
        for i, e in ((0, 'west'), (M.NX-1, 'east')):
            for j in range(M.NY):
                y = M.CORE[1]+j*M.PY
                if any(s-M.PY/2 <= y <= t+M.PY/2 for s, t in M.CUSTOM[e]): nodes.append((i, j))
    c = nF*1e-9/len(nodes)
    return [(M.CORE[0]+i*M.PX, M.CORE[1]+j*M.PY, c, tau/c) for i, j in nodes]


def mim_rects():
    """Block outlines that carry the grid MIM plates: placed analog blocks, not the spirals, decap cells, switches, ATB leaves,
    pads or the macro (decap.py counts the Metal4/Metal5-free area of the same blocks)."""
    skip = ('decap_', 'isw_', 'atb', 'iso_', 'pd_', 'obs_pre4')
    return [r for k, r in M.RECTS.items() if k in FIT['placed_rects']
            and not k.startswith(skip) and k not in SPIRALS]


def plan(rows=None, sites=None, mim=None, bank=None, tiles=None, scale=1.0):
    """The chip's 5.4 nF plan (decap.json as built): row fill in the macro, MOS under the custom bond sites, grid MIM over
    the block outlines, the 1.5 nF macro-edge bank (decap_bank_* cells) and the stacked MOS + MIM tiles (decap_tile_* cells,
    where the packer put them). Bank and tiles: 60 % MOS (tau 335 ps) / 40 % MIM by capacitance. Each argument overrides
    that part's nF; scale multiplies every part."""
    apply()
    g = lambda v, k: (DECAP[k] if v is None else v)*scale
    bk = [r for k, r in M.RECTS.items() if k.startswith('decap_bank_')]
    tl = [r for k, r in M.RECTS.items() if k.startswith('decap_tile_')]
    b, t = g(bank, 'bank_nF'), g(tiles, 'tiles_nF')
    return (lumps('macro', g(rows, 'row_fill_nF'), TAU_ROW)+lumps('sites', g(sites, 'bond_site_nF'), TAU_TILE)
            +_spread(mim_rects(), g(mim, 'grid_mim_nF'), TAU_MIM)
            +_spread(bk, b*0.6, TAU_TILE)+_spread(bk, b*0.4, TAU_MIM)+_spread(tl, t*0.6, TAU_TILE)+_spread(tl, t*0.4, TAU_MIM))


def plan_nF():
    apply(); return round(sum(DECAP[k] for k in ('row_fill_nF', 'bond_site_nF', 'grid_mim_nF', 'bank_nF', 'tiles_nF')), 2)
