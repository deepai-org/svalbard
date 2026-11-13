"""PD2 configuration of the M1 PDN model: reconciled currents (spec/budgets/power_budget.py MEASURED), the re-partitioned
islands and their switch masters, the v7 grid REQUIREMENT (spec/power-delivery.md section 3) and the v7 placement intent.
apply() mutates the model modules in place (islands, taps, positions); the M1 regression scripts e0-e6 never call it.
The interior grid, the switch-to-ring feed and the island straps are set to their REQUIREMENT limits, so a pass here means
"a floorplan that meets the requirement passes", not "v7 passes": v7 has no layout yet."""
import sys
import model as M, core as C, loads as LD
pb = LD.pb
X_FEED = 1.0-pb.RFDRV_DIE_FRACTION          # share of the rfdriver current that enters through the RF_TX pads
STRAP_MV = 15.0                              # requirement: switch VISL bar -> any block supply pin, at the block's worst current
GRID = dict(cov_m5=0.15, cov_m4=0.15)        # requirement: per-net coverage, Metal5 vertical / Metal4 horizontal
# Island switch positions: against the core ring, beside a supply pad (requirement G4). um, die coordinates.
ISW_POS = dict(wired_cap=(3330, 640), wired_rx=(3330, 1150), wired_tx=(3330, 2300), rf_rx=(600, 1050), rf_tx=(600, 3950), lod=(600, 640),
               lo=(600, 2680), pll=(3330, 4100), conv=(1700, 600), debug=(3250, 3600))
ISL_C = dict(wired_cap=100e-12, wired_rx=60e-12, wired_tx=50e-12, rf_rx=120e-12, rf_tx=80e-12, lod=150e-12, lo=100e-12, pll=150e-12,
             conv=250e-12, debug=100e-12)
# Block tap positions (v7 intent: each block near its switch and its pads).
POS = dict(lna=(950, 1420), rxmix_i=(1100, 1600), rxmix_q=(1100, 1350), bbfilter_i=(1500, 1900), bbfilter_q=(1500, 1300),
           txsum=(1000, 4265), rfdriver=(750, 4100), adc_i=(1836, 2014), adc_q=(2122, 1044), dac_i=(1102, 3639),
           dac_q=(893, 2902), refbuf=(2300, 2000), qvco=(1100, 2550), lo_pfdcp=(1300, 2300), lo_vreg=(700, 2680),
           lo_mmd=(900, 800), lo_mmd_qdum=(1100, 700), lo_ext=(1000, 1100), lo_obs=(1000, 950), qvco_pre=(1100, 2400),
           pll_cdr=(3242, 4104), pll_tx=(3247, 3788), pll_misc=(3242, 4104), pll_vreg2=(3242, 4104), clockmux=(2822, 2376),
           wordclk=(2900, 3200), prescale=(2759, 2976),
           ctle=(2900, 1050), ctle_follower=(2900, 1050), slicer=(3050, 1250), detect=(3150, 1350), termination=(3100, 1000),
           rxlevel=(2800, 1100), rxselect=(3000, 1300), vthdac=(3000, 1200), wrx_cap=(3050, 850), ptrim=(3150, 950),
           wiredtx=(3050, 2550), usbhs=(3187, 2048),
           core_bias=(947, 659), aosc=(3162, 3428), pad_usb=(3187, 2048), pad_ref=(482, 2410), por=(637, 2140))
RAW_TAP = dict(bias='core_bias', aosc='aosc', usbfs='pad_usb', rx_ref_in='pad_ref')
CASE_MODE = {'W': ('wired', None), 'U': ('usb', None), 'T': ('wired', None), 'RXe': ('rf_rx', 'rf_rx'), 'RXa': ('rf_rx', 'rf_rx'),
             'TXe': ('rf_tx', 'rf_tx'), 'TXa': ('rf_tx', 'rf_tx'), 'DXe': ('rf_rx', 'rf_duplex'), 'DXa': ('rf_rx', 'rf_duplex'),
             'stopped': ('stopped', None)}
CASES = list(CASE_MODE)
_applied = False

def apply():
    global _applied
    if _applied: return
    _applied = True
    M.ISW.clear(); M.ISL_C.clear()
    for isl, master in pb.ISLAND_SWITCH.items():
        M.ISW[isl] = pb.SWITCH_MASTER[master][1]; M.ISL_C[isl] = ISL_C[isl]
        M.FP['placed'].pop(f'isw_{isl}', None); M.SEED[f'isw_{isl}'] = ISW_POS[isl]
    for k, xy in POS.items():
        M.FP['placed'].pop(k, None); M.SEED[k] = xy
    M.FP['fixed'] = [r for r in M.FP['fixed'] if r['name'] not in POS]      # CUSTOM spans were taken at import
    LD.MAP.clear()
    for r in pb.MEASURED:
        LD.MAP[r[0]] = (RAW_TAP.get(r[0], r[0]), r[1])
    LD.MAP['lo_obs'] = ('lo_obs', 'lod')          # debug load on a functional rail (power_budget.ISLAND_EXTRA_WORST_MA)
    C.EXTRA_TAPS[:] = [('pll_vreg2', 'pll'), ('por', None)]
    C.VICT.clear()
    C.VICT.update({'core_bias': ('core_bias', None), 'por': ('por', None), 'adc_i': ('adc_i', 'conv'), 'refbuf': ('refbuf', 'conv'),
                   'qvco': ('qvco', 'lo'), 'pll_vreg2': ('pll_vreg2', 'pll'), 'lna': ('lna', 'rf_rx'), 'slicer': ('slicer', 'wired_rx'),
                   'lo_mmd': ('lo_mmd', 'lod'), 'wiredtx': ('wiredtx', 'wired_tx'), 'rfdriver': ('rfdriver', 'rf_tx')})
    M.P['ring_custom'] = (1.0, 1.0, 1.0)    # verified on the v5 run2 GDS: provider rails are uncut through all custom sites

def strap_R(strap_mv=STRAP_MV):
    """Requirement limit: each island block's switch->pin strap drops strap_mv at that block's worst in-envelope current."""
    out = {}
    for r in pb.MEASURED:
        if not r[1]: continue
        i = max(v[1] for v in pb.pd2_expand(r).values())*(pb.RFDRV_DIE_FRACTION if r[0] == 'rfdriver' else 1.0)
        out[r[0]] = strap_mv/i
    out['pll_vreg2'] = out['pll_cdr']; out['lo_obs'] = strap_mv/pb.ISLAND_EXTRA_WORST_MA['lod']
    return out

def strap_width_um(name, rs=0.070):
    """Metal5 strap width (um, at the maximum sheet resistance) that meets the strap budget over the modelled
    switch-to-block Manhattan distance. Reported by e7 so the placement intent and G5 / G6 can be compared."""
    isl = LD.MAP[name][1]
    if not isl: return None
    x, y = M.centre(RAW_TAP.get(name, name)); sx, sy = M.centre(f'isw_{isl}')
    return rs*(abs(x-sx)+abs(y-sy))/strap_R()[name]

def pset(sel, grid=None, strap_mv=STRAP_MV, **over):
    apply()
    g = dict(GRID); g.update(grid or {})
    p = M.pset(sel)
    p['grid_cov'] = g['cov_m5']; p['grid_cov_m4'] = g['cov_m4']; p['strap_R'] = strap_R(strap_mv)
    p.update(over)
    return p

def dc_loads(case, level):
    """level: pd2n = nominal (digital 72.09 newest routed vectorless, host typical), pd2w = worst in-envelope analog,
    digital 81.79, host 8 pF; pd2r = worst analog with digital at the PWR-DIG requirement."""
    apply()
    m, rdir = CASE_MODE[case]; k = 0 if level == 'pd2n' else 1
    out = []
    for r in pb.MEASURED:
        v = pb.pd2_expand(r).get(case)
        if v and v[k] > 0: out.append((r[0], RAW_TAP.get(r[0], r[0]), r[1], v[k]))
    if level == 'pd2w' and case.endswith('a') and case != 'stopped':     # lo_obs observing: worst only, autonomous-LO cases
        out.append(('lo_obs', 'lo_obs', 'lod', pb.ISLAND_EXTRA_WORST_MA['lod']))
    if case == 'stopped': return out, 2.0, 1.0, m, rdir
    rf = rdir is not None
    dig = {'pd2n': pb.DIG_MEAS['nominal'], 'pd2w': pb.DIG_MEAS['worst'], 'pd2r': pb.DIG_MEAS['req_rf' if rf else 'req_wired_usb']}[level]
    host = (pb.HOST_MEAS['nominal'] if level == 'pd2n' else pb.HOST_MEAS['worst'])*(pb.RF_HOSTIO_FACTOR if rf else 1.0)
    return out, dig, host, m, rdir

# ---- decap lumps for the plans of spec/power-delivery.md section 4 -------------------------------------------------
TAU_TILE = 335e-12     # pt_decap_tile: 152 ps tie-NMOS (extracted) + ~175-195 ps pfet L = 6 channel that the model cannot see
TAU_ROW = 60e-12       # 7T fillcap / pt_decap50 (54.5 tt - 69.7 ss ps)
TAU_MIM = 5e-12        # no ESR in the PDK model: plate + via estimate (grid resistance is in the mesh)
def lumps(where, nF, tau):
    """where: macro | band (analog nodes within one mesh tile of the macro) | spread (all analog nodes) |
    sites (west/east boundary nodes inside the custom pad spans: MOS under the custom bond sites) | south."""
    if nF <= 0: return []
    dig = [(i, j) for i in range(M.NX) for j in range(M.NY) if M.in_dig(i, j)]
    ana = [(i, j) for i in range(M.NX) for j in range(M.NY) if not M.in_dig(i, j)]
    if where == 'macro': nodes = dig
    elif where == 'band': nodes = [a for a in ana if any(abs(a[0]-d[0]) <= 1 and abs(a[1]-d[1]) <= 1 for d in dig)]
    elif where == 'spread': nodes = ana
    elif where == 'south': nodes = [(i, 0) for i in range(M.NX)]
    elif where == 'sites':
        nodes = []
        for i, e in ((0, 'west'), (M.NX-1, 'east')):
            for j in range(M.NY):
                y = M.CORE[1]+j*M.PY
                if any(s-M.PY/2 <= y <= t+M.PY/2 for s, t in M.CUSTOM[e]): nodes.append((i, j))
    c = nF*1e-9/len(nodes)
    return [(M.CORE[0]+i*M.PX, M.CORE[1]+j*M.PY, c, tau/c) for i, j in nodes]

# ---- the decap plan of spec/power-delivery.md section 4 --------------------------------------------------------------
PLAN = dict(rows_nF=0.45, sites_nF=0.45, mim_nF=3.0, tiles_nF=1.5)
def plan(rows=None, sites=None, mim=None, tiles=None):
    """rows: pt_decap50 fill in the macro's free sites; sites: MOS tiles under the custom bond sites (ring);
    mim: MIM between the Metal5 / Metal4 grid straps over the analog blocks (spread); tiles: stacked pt_decap_tile + MIM
    bank against the macro edge (half MOS, half MIM by capacitance)."""
    g = lambda v, k: PLAN[k] if v is None else v
    t = g(tiles, 'tiles_nF')
    return (lumps('macro', g(rows, 'rows_nF'), TAU_ROW)+lumps('sites', g(sites, 'sites_nF'), TAU_TILE)
            +lumps('spread', g(mim, 'mim_nF'), TAU_MIM)+lumps('band', t*0.6, TAU_TILE)+lumps('band', t*0.4, TAU_MIM))
