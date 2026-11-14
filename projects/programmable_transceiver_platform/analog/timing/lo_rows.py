"""Row plans of the LO / observation blocks laid out with layout_engine (LO/timing owner).

`plan(block, name)` returns the keyword arguments for `timing_flow.build_layout(block, **kw)`.
Plans:
  'r4'  : the row plans the published cells had before area pass 4 (kept for old/new comparisons)
  'ap4' : area pass 4 (AP4-5, 2026-11-13) repack, STAGED ONLY until listed in PUBLISHED below.  Same netlists.  Two levers only:
          (1) groups of similar device height share a row, so the outline is no longer set by the widest row
              while the others are half empty (lo_mmd: rows of 110-200 um next to 379 um CMOS rows);
          (2) Metal4 tracks run over the devices (`over_cell`) in rows without MIM capacitors (transistor and
              ppolyf PCells use Metal1 only; escapes are Metal2/3), instead of in a channel above the row.
          Functional groups stay contiguous inside a row, so a net local to a group keeps its track span.
"""


def _chunk(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def _check(rows, names):
    flat = [n for r in rows for n in r if not n.startswith('GAP:')]
    assert sorted(flat) == sorted(names), sorted(set(names) ^ set(flat))[:8]
    return rows


# Tank ports LP/LN of pt_lo_mmd and pt_lo_mmd_qdum: one trunk pair (1 um wide, 4.8 um apart), placed the same way in
# both cells.  The engine keeps the columns next to each wide trunk free over its span, but the columns between the
# two trunks can still take a short trunk of another net (review 2026-11-13: one does, a different net in each cell;
# extracted coupling of LP/LN to switching CMOS nets <= 0.1 fF).
TANK_PAIR = dict(trunk_groups=[['LP', 'LN']], net_width={'LP': 1.0, 'LN': 1.0})


# ------------------------------------------------------------------ lo_mmd
def _mmd_groups(devs):
    names = [d.name for d in devs]
    g = lambda *pre: [n for n in names if n.startswith(pre)]
    G = dict(pm=g('PM_'), ccp=g('CCP', 'RCP'), ccn=g('CCN', 'RCN'), pre=g('K0') + g('PS_'), a1=g('C0_A1_'),
             c0=g('F1') + g('C0_A2_') + g('C0_C2_') + g('F2'), c1=g('C0_C1_'),
             b_a1=g('C1_A1_'), b_a2=g('C1_A2_', 'C1_B2_'), b_b1=g('C1_B1_'), b_c1=g('C1_C1_'),
             b_c2=g('C1_C2_'), b_g2=g('C1_G2_'), b_g1=g('C1_G1_'), k2=g('S1', 'S2', 'K2'))
    used = {n for r in G.values() for n in r}
    cm = [n for n in g('C2_', 'C3_', 'C4_', 'E4', 'O1', 'O2') if n not in used]
    used |= set(cm)
    G['bias'] = [n for n in names if n not in used]
    G['cmos'] = cm
    return names, G


def mmd_rows_r4(devs):
    names, G = _mmd_groups(devs)
    R = [G['ccp'] + G['pm'] + G['ccn'], G['pre'], G['a1'], G['c0'], G['c1'], G['b_a1'], G['b_a2'], G['b_b1'], G['b_c1'],
         G['b_c2'] + G['b_g2'], G['b_g1'], G['k2'], G['bias']]
    return _check(R + _chunk(G['cmos'], 60), names)


def mmd_rows_ap4(devs, n_first=26, n_chunk=60):
    """Bottom to top: CMOS rows; the two 19 um groups + the last CMOS devices; two rows of 35 um groups; the 67 um
    row (cell A slave latches / followers, prescaler slave + followers, cell B C/G slaves); top row (MIM row, channel
    above): bias, the AC-coupling network RCP CCP CCN RCN, prescaler master.
    The tank ports LP/LN leave at the top edge on adjacent trunks, so their wiring is a few um long and equal
    (r4: caps in the bottom row of a 955 um cell on either side of the master, 0.9 mm trunks 113 um apart,
    201 / 126 fF of wiring on the I tank against 22 / 30 fF in pt_lo_mmd_qdum).  pt_lo_mmd_qdum ap4 uses the same
    cap order (qdum_rows_ap4)."""
    names, G = _mmd_groups(devs)
    cm = G['cmos']
    k = len(cm) - n_first
    R = _chunk(cm[:k], n_chunk)
    R += [cm[k:] + G['b_c1'] + G['b_a1'],
          G['b_a2'] + G['b_g1'] + G['k2'],
          G['a1'] + G['c1'] + G['b_b1'],
          G['c0'] + G['pre'] + G['b_c2'] + G['b_g2'],
          G['bias'] + [G['ccp'][1], G['ccp'][0], G['ccn'][0], G['ccn'][1]] + G['pm']]
    return _check(R, names)


def _mmd_ap4():
    import netlist
    from pathlib import Path
    _, devs = netlist.load(Path(__file__).resolve().parent / 'lo_mmd.spice', 'pt_lo_mmd')
    n = len(mmd_rows_ap4(devs))
    return dict(rows=mmd_rows_ap4, max_row_width=220, over_cell=set(range(n - 1)), **TANK_PAIR)


# ------------------------------------------------------------------ lo_mmd_qdum / lo_obs (QVCO corner slot, <= 108 um wide)
def qdum_rows_ap4(devs):
    """Same order as pt_lo_mmd ap4: followers + bias at the bottom, prescaler slave, prescaler master, and the
    AC-coupling caps in the top row (tank ports LP/LN at the top edge, short and matched)."""
    names = [d.name for d in devs]
    g = lambda *pre: [n for n in names if n.startswith(pre)]
    caps = g('RCP') + g('CCP') + g('CCN') + g('RCN')
    k0 = g('K0')
    used = set(caps + k0 + g('PM_') + g('PS_'))
    bias = [n for n in names if n not in used]
    return _check([bias + k0, g('PS_'), g('PM_'), caps], names)


def obs_rows_ap4(devs):
    """Bottom to top: output driver + TSPC dividers, CML-to-CMOS, slave, master + bias (LP/LN ports at the top edge)."""
    names = [d.name for d in devs]
    g = lambda *pre: [n for n in names if n.startswith(pre)]
    out = g('D1', 'D2', 'O1_', 'O2_', 'O3_')
    c2c = g('CT_', 'CX', 'CY', 'CP1', 'CP2', 'C1_', 'C2_')
    sl = g('ST_', 'SA', 'SH', 'S1', 'S2', 'S3', 'S4', 'SR')
    ms = g('MT_', 'MA', 'MH', 'M1', 'M2', 'M3', 'M4', 'MR')
    used = set(out + c2c + sl + ms)
    bias = [n for n in names if n not in used]
    return _check([out, c2c, sl + bias[:3], bias[3:] + ms], names)


# ------------------------------------------------------------------ lo_ext
def _ext_groups(devs):
    names = [d.name for d in devs]
    g = lambda *pre: [n for n in names if n.startswith(pre)]
    bias = [n for n in names if not n.startswith(('IP_', 'IN_', 'QP_', 'QN_', 'DI_', 'DQ_', 'PI_', 'PQ_'))]

    def cml_bias(p):
        return [n for n in g(p + '_') if not n.startswith((p + '_T_', p + '_CORE', p + '_RP', p + '_RN', p + '_S1', p + '_S2',
                                                           p + '_DM', p + '_E1', p + '_E2'))]

    def lo_row(a, b, p):
        A = g(a + '_TN', a + '_TP') + [a + '_RB', a + '_CL']
        B = g(b + '_TN', b + '_TP') + [b + '_RB', b + '_CL']
        dm = g(p + '_DM')
        pa, pb = g(p + '_E1'), g(p + '_E2')
        return A + [p + '_RP', p + '_S1'] + dm[:1] + pa + [p + '_CORE'] + pb + dm[1:] + [p + '_S2', p + '_RN'] + B[::-1]

    pad = lambda a: g(a + '_SW') + g(a + '_RG') + [a + '_CG', a + '_RP'] + g(a + '_CC') + [a + '_CA', a + '_RL', a + '_KP', a + '_KN']
    return names, g, bias, cml_bias, lo_row, pad


def ext_rows_r4(devs):
    """Published r4h plan (scratch/lo/r4_area/lay_ext.py): LO rows on top, I/Q rows identical."""
    names, g, bias, cml_bias, lo_row, pad = _ext_groups(devs)
    R = [bias, g('DI_T_') + g('DQ_T_'), cml_bias('DI'), cml_bias('DQ'), pad('IP'), pad('IN'), pad('QP'), pad('QN'),
         lo_row('IP', 'IN', 'DI'), lo_row('QP', 'QN', 'DQ')]
    return _check(R, names)


def ext_rows_ap4(devs):
    """Same row order as r4h (pad rows and LO rows untouched, I and Q rows still identical).  The separate row of
    CML tail devices (24 x 10/1, DC only) is folded onto the ends of the four pad rows (6 each: I tails on the I pad
    rows, Q tails on the Q pad rows), which were 77 um shorter than the LO rows."""
    names, g, bias, cml_bias, lo_row, pad = _ext_groups(devs)
    ti, tq = g('DI_T_'), g('DQ_T_')
    h = len(ti) // 2
    R = [bias, cml_bias('DI'), cml_bias('DQ'), pad('IP') + ti[:h], pad('IN') + ti[h:], pad('QP') + tq[:h], pad('QN') + tq[h:],
         lo_row('IP', 'IN', 'DI'), lo_row('QP', 'QN', 'DQ')]
    return _check(R, names)


def _no_mim_rows(block, rows_fn):
    """Row indices without MIM capacitors (Metal4/5 plates): the rows that may carry their tracks over the devices."""
    import netlist
    from pathlib import Path
    _, devs = netlist.load(Path(__file__).resolve().parent / f'{block}.spice', f'pt_{block}')
    by = {d.name: d for d in devs}
    return {i for i, r in enumerate(rows_fn(devs)) if not any(by[n].model.startswith('cap_mim') for n in r)}


def _clk_obs16_ap4():
    # netlist order (mux tree, divider chain, output driver), narrower rows: the channel height is set by the number
    # of nets in a row (one Metal4 track each), so 130 um rows need ~2/3 of the tracks of 196 um rows; tracks over
    # the devices (no MIM in this cell)
    return dict(max_row_width=130, over_cell=True)


PLANS = {
    ('lo_ext', 'r4'): lambda: dict(rows=ext_rows_r4),
    ('lo_ext', 'ap4'): lambda: dict(rows=ext_rows_ap4, over_cell=_no_mim_rows('lo_ext', ext_rows_ap4)),
    ('lo_mmd_qdum', 'r4'): lambda: dict(max_row_width=220),
    ('lo_mmd_qdum', 'ap4'): lambda: dict(rows=qdum_rows_ap4, over_cell={0, 1, 2}, **TANK_PAIR),
    ('lo_obs', 'r4'): lambda: dict(max_row_width=200),
    ('lo_obs', 'ap4'): lambda: dict(rows=obs_rows_ap4, over_cell=True, net_space={'LP': 1.0, 'LN': 1.0}),
    ('clk_obs16', 'r4'): lambda: dict(max_row_width=200),
    ('clk_obs16', 'ap4'): _clk_obs16_ap4,

    ('lo_mmd', 'r4'): lambda: dict(rows=mmd_rows_r4, max_row_width=220),
    ('lo_mmd', 'ap4'): _mmd_ap4,
}


# Plan each block is PUBLISHED with.  A block moves to 'ap4' here only when its ap4 layout has passed the extracted
# benches and the independent review and generated/ has been republished (2026-11-13: none yet; every ap4 layout is
# staged only, see scratch/lo-ap4/NOTES.md).  Standard flows (run_timing.py, `lo_rows.py <block>`) use this plan.
PUBLISHED = {}


def plan(block, name=None):
    return PLANS[(block, name or PUBLISHED.get(block, 'r4'))]()


if __name__ == '__main__':
    # python3 lo_rows.py <block> [plan] [--publish]: build the layout with its row plan.  Staged in
    # scratch/timing/<block>/stage; generated/ is written only with --publish and only if DRC, LVS and the
    # KLayout precheck are clean (extracted benches are the caller's job before publishing).
    import json
    import sys
    import timing_flow as tf
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    blk, name = args[0], (args[1] if len(args) > 1 else PUBLISHED.get(args[0], 'r4'))
    lay = tf.build_layout(blk, publish='clean' if '--publish' in sys.argv else 'never', **plan(blk, name))
    print(json.dumps(dict(block=blk, plan=name, size_um=lay['layout']['size_um'], area_um2=lay['layout']['area_um2'],
                          drc=lay['drc_errors'], lvs_unique=lay['lvs'].get('unique_match'), klayout=lay['klayout'],
                          clean=lay['layout_clean'], published=lay['published'], stage=lay['stage']), default=str))
