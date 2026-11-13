"""M1 (+M4) chip-level PDN model: geometry, parameter sets and netlist builder.

Geometry source: scratch/chip-assembly-v6/run/floorplan-v6.json (block rects; unplaced blocks at their v6 seeds),
spec/package-channel.json (bond pad order, bond lengths, board nets), v5 pdn-shapes.json (core ring 2 x 25 um M3/M4,
necked to 3-22 um on the west/east edges by the pad families), gf180mcu_fd_io fill10 LEF (ring rails: DVDD 124 um,
DVSS 101.4 um on each of Metal3/4/5), tech LEF sheet resistance (Metal1-4 0.076/0.090/0.104, Metal5 0.050/0.060/0.070
ohm/sq min/nom/max).  v6 has NO top-level strap plan: the interior grid is a parameter (top-metal coverage per net).
"""
import json, math, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mna import Net
ROOT = '/home/ubuntu/svalbard'
PRJ = f'{ROOT}/projects/programmable_transceiver_platform'
FP = json.load(open(f'{ROOT}/scratch/chip-assembly-v6/run/floorplan-v6.json'))
PKG = json.load(open(f'{PRJ}/spec/package-channel.json'))
CORE = (452.0, 452.0, 3480.0, 4670.0)
NX, NY = 13, 18
PX = (CORE[2]-CORE[0])/(NX-1); PY = (CORE[3]-CORE[1])/(NY-1)
DIG = [1262.0, 3030.0, 2978.0, 4670.0]

# ---- parameter sets: every uncertain value has a low and a high end (MANDATE "bounded in both directions") ----------
P = {
 # name:            (lowZ / "opt",  nominal,  highZ / "pess")
 'bond_nH_per_mm':  (0.83, 0.92, 1.00),     # package-channel.json bond_nH_0p83 / bond_nH_1p0
 'bond_k1':         (0.20, 0.30, 0.40),     # mutual k of adjacent bonds (free-space partial-L gives 0.37 at 0.3 mm / 2.5 mm)
 'bond_R':          (0.09, 0.12, 0.15),     # ohm per bond (25 um Au, 2.0-2.9 mm: 0.10-0.14) + pad stub
 'gnd_bond_mm':     (2.0, 2.4, 2.9),        # GND bond lengths are not in package-channel.json (f_mm null): range of the supply bonds
 'Rs_m5':           (0.050, 0.060, 0.070),  # tech LEF
 'Rs_m34':          (0.076, 0.090, 0.104),
 'grid_cov':        (0.15, 0.08, 0.04),     # top-metal (Metal5) strap coverage per net in the analog core (ASSUMED: no v6 plan)
 'dig_cov':         (0.20, 0.12, 0.08),     # same inside the digital macro (its own PDN straps, Metal4+Metal5 equivalent)
 'Lsq_loop_nH':     (0.10, 0.20, 0.40),     # VDD/VSS loop inductance per mesh square (strap pair per ~250 um tile)
 'ring_custom':     (1.0, 0.33, 0.0),       # fraction of the provider ring rails that continues through custom pad families
 'ring_core_w':     (25.0, 16.0, 8.0),      # VDD core-ring width (um, M3||M4) along custom pad families (v5: 3-22 um pieces)
 'Ron_scale':       (0.8, 1.0, 1.25),       # island switch Ron scale (extracted full-RC value = 1.0)
 'isl_strap_w':     (60.0, 30.0, 20.0),     # island rail strap width (um, Metal5); v5 used 10-30 um bars
 'Cint_dig_nF':     (0.50, 0.30, 0.15),     # digital macro intrinsic (non-switching gates + n-well); A2 used 0.3-0.5 total
 'Cint_ring_nF':    (0.15, 0.08, 0.04),     # pad ring (ESD clamps, n-well, rail overlap), spread on the boundary
 'Cint_ana_scale':  (1.5, 1.0, 0.5),        # scale on the island decaps (island_support evidence: 150/200/250/250/100 pF)
 'cap0201_L_nH':    (1.2, 1.8, 2.6),        # finger -> 0201 on the back-side strip: F.Cu trace 2.0-2.9 mm, via 0.4, ESL 0.3
 'conn_L_nH':       (2.0, 3.0, 4.5),        # finger -> connector contact -> carrier plane/bulk (trace + via + 0.85-1.2 nH contact)
}
def pset(sel):
    """sel: 'opt' | 'nom' | 'pess' or dict of overrides {name: index or value}."""
    i = {'opt': 0, 'nom': 1, 'pess': 2}[sel] if isinstance(sel, str) else 1
    d = {k: v[i] for k, v in P.items()}
    if isinstance(sel, dict):
        for k, v in sel.items(): d[k] = P[k][v] if isinstance(v, int) else v
    return d

# ---- pads (ring order, package-channel.json bond_pad 1..74: south W->E 1-17, east S->N 18-37, north E->W 38-54, west N->S 55-74)
def pad_xy(n):
    if n <= 17: return (500+(n-1)*183.0, CORE[1])
    if n <= 37: return (CORE[2], 566+(n-18)*211.0)
    if n <= 54: return (3432-(n-38)*183.0, CORE[3])
    return (CORE[0], 4575-(n-55)*211.0)
SUP = sorted(((v['bond_pad'], k, v['net'], v['f_mm']) for k, v in PKG['supplies_grounds'].items()))
VDD_PADS = [(n, net, f) for n, k, net, f in SUP if net != 'GND']
VSS_PADS = [n for n, k, net, f in SUP if net == 'GND']
# custom pad family spans (floorplan-v6 fixed rects): the provider cells are replaced there
CUSTOM = {'west': [(r['rect'][1], r['rect'][3]) for r in FP['fixed'] if r['kind'] == 'pad' and r['rect'][0] < 500],
          'east': [(r['rect'][1], r['rect'][3]) for r in FP['fixed'] if r['kind'] == 'pad' and r['rect'][2] > 3400]}

def vn(i, j): return f'v_{i}_{j}'
def gn(i, j): return f'g_{i}_{j}'
def near(x, y):
    i = min(NX-1, max(0, round((x-CORE[0])/PX))); j = min(NY-1, max(0, round((y-CORE[1])/PY)))
    return int(i), int(j)
def in_dig(i, j):
    x = CORE[0]+i*PX; y = CORE[1]+j*PY
    return DIG[0]-1 <= x <= DIG[2]+1 and DIG[1]-1 <= y <= DIG[3]+1

# ---- block taps ------------------------------------------------------------------------------------------------------
SEED = dict(qvco=(1400, 2400), wrx_cap=(2050, 2700), wiredtx=(2900, 2800), cdr=(2900, 1900), slicer=(2700, 1500),
            refbuf=(2300, 2000), lo_lf=(1150, 3200), lo_ext=(1150, 3300), isw_conv=(1700, 600), isw_debug=(3250, 3600))
def centre(name):
    if name in FP['placed']:
        r = FP['placed'][name]['rect']; return ((r[0]+r[2])/2, (r[1]+r[3])/2)
    for r in FP['fixed']:
        if r['name'] == name: return ((r['rect'][0]+r['rect'][2])/2, (r['rect'][1]+r['rect'][3])/2)
    return SEED[name]
ISW = dict(wired=0.2484, rf=0.3007, pll=0.2877, conv=0.4807, debug=0.3878)   # ohm = extracted full-RC drop / design current
ISL_C = dict(wired=150e-12, rf=200e-12, pll=250e-12, conv=250e-12, debug=100e-12)   # island_support evidence island_decap_f


def build(p, decap=None, n_vdd_bonds=None, strip_caps=True, split=None, host_split=None):
    """Return (net, info). decap: list of (x, y, C, ESR) lumps placed VDD-VSS at the nearest mesh node (raw rail).
    n_vdd_bonds: keep only the first n supply bonds (negative control). split: dict island -> dedicated bond pad number
    (that pad's bond feeds the island directly instead of the ring)."""
    n = Net(); info = {}
    rs_grid = p['Rs_m5']/p['grid_cov']; rs_dig = p['Rs_m5']/p['dig_cov']; lsq = p['Lsq_loop_nH']*1e-9/2
    for i in range(NX):
        for j in range(NY):
            for (a, b) in (((i, j), (i+1, j)), ((i, j), (i, j+1))):
                if b[0] >= NX or b[1] >= NY: continue
                dig = in_dig(*a) and in_dig(*b)
                horiz = b[0] > a[0]
                sq = (PX/PY) if horiz else (PY/PX)
                r = (rs_dig if dig else rs_grid)*sq; l = lsq*sq
                # boundary edges also carry the ring
                edge = None
                if not horiz and a[0] == 0: edge = 'west'
                if not horiz and a[0] == NX-1: edge = 'east'
                if horiz and a[1] == 0: edge = 'south'
                if horiz and a[1] == NY-1: edge = 'north'
                for net_, nm in (('vdd', vn), ('vss', gn)):
                    n.add_rl(nm(*a), nm(*b), r, l)
                    if edge:
                        length = PX if horiz else PY
                        frac = 1.0
                        if edge in CUSTOM:
                            y0 = CORE[1]+a[1]*PY; y1 = y0+PY
                            cov = sum(max(0, min(y1, e)-max(y0, s)) for s, e in CUSTOM[edge])/PY
                            frac = 1-cov*(1-p['ring_custom'])
                        w_rail = (124.0+14.0) if net_ == 'vdd' else (101.4+14.0)
                        g_rail = frac*w_rail*(2/p['Rs_m34']+1/p['Rs_m5'])          # siemens*um
                        cw = p.get('core_ring_w', 25.0)
                        w_core = cw if (net_ == 'vss' or edge not in CUSTOM) else (cw*(1-cov)+min(cw, p['ring_core_w'])*cov)
                        g_core = w_core*2/p['Rs_m34']
                        n.add_rl(nm(*a), nm(*b), length/(g_rail+g_core), 0.15e-9*length/1000)
    # ring intrinsic capacitance on the boundary, digital intrinsic inside the macro
    bnd = [(i, j) for i in range(NX) for j in range(NY) if i in (0, NX-1) or j in (0, NY-1)]
    for (i, j) in bnd: n.add_rc(vn(i, j), gn(i, j), 2.0*len(bnd), p['Cint_ring_nF']*1e-9/len(bnd))
    dg = [(i, j) for i in range(NX) for j in range(NY) if in_dig(i, j)]
    for (i, j) in dg: n.add_rc(vn(i, j), gn(i, j), 1.0*len(dg), p['Cint_dig_nF']*1e-9/len(dg))   # ~1 ohm aggregate ESR (A2)
    info['dig_nodes'] = dg
    # decap lumps
    for (x, y, C, esr) in (decap or []):
        i, j = near(x, y); n.add_rc(vn(i, j), gn(i, j), esr, C)
    # islands: mesh -> Ron -> island rail node at the switch -> strap -> block
    info['isl'] = {}; split = split or {}
    for isl, ron in ISW.items():
        x, y = centre(f'isw_{isl}'); i, j = near(x, y)
        if isl not in (split or {}): n.add_rl(vn(i, j), f'isl_{isl}', ron*p['Ron_scale'], 0.0)
        n.add_rc(f'isl_{isl}', gn(i, j), 0.3, ISL_C[isl]*p['Cint_ana_scale'])
        info['isl'][isl] = (x, y)
    # bonds (one coupled group) and board
    pairs = []; R = []; L = []; pos = []
    vp = VDD_PADS if n_vdd_bonds is None else VDD_PADS[:n_vdd_bonds]
    for pad, net_, f in vp:
        x, y = pad_xy(pad); i, j = near(x, y)
        die = vn(i, j)
        for isl, sp in split.items():
            if sp == pad: die = f'isl_{isl}'
        if host_split and pad in host_split: die = 'hv'
        pairs.append((die, f'F_{pad}')); R.append(p['bond_R'])
        # die-side bond length: package-channel gives the finger trace f_mm, not the supply bond length; use the
        # neighbouring signal bonds (2.2-2.9 mm) via the same range as the ground bonds
        L.append(p['gnd_bond_mm']*p['bond_nH_per_mm']*1e-9); pos.append(pad)
        if strip_caps:
            n.add_rl(f'F_{pad}', f'C_{pad}', 0.03, p['cap0201_L_nH']*1e-9); n.add_rc(f'C_{pad}', 'gnd', 0.015, 1e-6)
        n.add_rl(f'F_{pad}', 'car', 0.055, p['conn_L_nH']*1e-9)
    for pad in VSS_PADS:
        x, y = pad_xy(pad); i, j = near(x, y)
        die = 'hg' if (host_split and pad in host_split) else gn(i, j)
        pairs.append((die, 'gnd')); R.append(p['bond_R']); L.append(p['gnd_bond_mm']*p['bond_nH_per_mm']*1e-9); pos.append(pad)
    m = len(pairs); Lm = np.zeros((m, m))
    edge_of = lambda q: 0 if q <= 17 else 1 if q <= 37 else 2 if q <= 54 else 3
    for a in range(m):
        for b in range(m):
            if a == b: Lm[a, b] = L[a]; continue
            d = abs(pos[a]-pos[b])
            if d <= 3 and edge_of(pos[a]) == edge_of(pos[b]) or (d <= 3 and {pos[a], pos[b]} & {17, 18, 37, 38, 54, 55}):
                Lm[a, b] = p['bond_k1']*d**-0.6*math.sqrt(L[a]*L[b])
    n.add_coupled(pairs, R, Lm)
    info['bond_pairs'] = pairs; info['bond_pos'] = pos; info['bond_R'] = R
    if host_split:   # separate host (D2H) rail: half of the ring intrinsic C, no on-die tie to the core rails
        n.add_rc('hv', 'hg', 2.0, p['Cint_ring_nF']*0.5e-9)
    # carrier: source (3.3 V -1 %) behind 20 mohm (B2a), bulk 10 uF (ESR 5 m, ESL 1 nH) + 100 nF (ESR 20 m, ESL 0.6 nH)
    n.add_rl('car', 'gnd', 0.020, 0.0)          # Norton source resistance (source current injected in the DC solve)
    n.add_rl('car', 'cb1', 0.005, 1e-9); n.add_rc('cb1', 'gnd', 1e-6, 10e-6)
    n.add_rl('car', 'cb2', 0.020, 0.6e-9); n.add_rc('cb2', 'gnd', 1e-6, 100e-9)
    return n, info

def tap(n, p, name, island=None, pos=None):
    """Create (once) the supply tap nodes of a block; returns (vdd_node, vss_node). Island blocks hang off the island rail
    through a Metal5 strap of width isl_strap_w over the Manhattan distance switch -> block."""
    x, y = pos or centre(name); i, j = near(x, y)
    if island is None: return vn(i, j), gn(i, j)
    nm = f't_{name}_{island}'
    if nm not in n.idx:
        sx, sy = centre(f'isw_{island}')
        d = abs(x-sx)+abs(y-sy)
        n.add_rl(f'isl_{island}', nm, max(1e-3, p['Rs_m5']*d/p['isl_strap_w']), 0.4e-12*d)
    return nm, gn(i, j)
