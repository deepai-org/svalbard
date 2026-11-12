"""Benches for the FD baseband filter (fork S): corner trim search (CNV-01 / Wi-Fi alias rejection),
GX-1 wide range, RC-17 high-gain bandwidth / DC operating point / power-up latch, fine DCOC DAC.
All functions take the tb.netlist view ('sch', 'ext') and return plain dicts with pass/fail fields."""
from pathlib import Path
import netlists as N
import bbf_fd as F
import tb
import rfrx_flow as flow


def _nl(work, block, view):
    """view: 'sch' / 'ext' (tb.netlist) or a Path to any netlist defining pt_<block> (bench validation, staged
    layouts)."""
    if isinstance(view, Path):
        return tb.S.prepare(Path(work), view, view.name)
    return tb.netlist(work, block, view)


def _vt(view):
    return view.stem if isinstance(view, Path) else view


def _cv(corner):
    """(MOS corner, T, VDD) of a standard 3-tuple corner or a 6-tuple skew corner (see SKEW)."""
    return (corner[1], corner[3], corner[4]) if len(corner) == 6 else tuple(corner)


def _ctag(corner):
    return corner[0] if len(corner) == 6 else tb._tag(corner)


def _run(work, name, body, corner):
    """tb.S.run with resume: an identical deck whose log already exists is not re-simulated.  The deck carries
    the sha256 of every included netlist, so a relayout / re-extraction never reuses an old log (review fix)."""
    import hashlib, re as _re
    tags = []
    for inc in _re.findall(r'^\.include\s+(\S+)', body, _re.M):
        pth = Path(work) / inc
        if pth.exists():
            tags.append(f'* netlist {inc} sha256 {hashlib.sha256(pth.read_bytes()).hexdigest()}')
    body = '\n'.join(tags) + '\n' + body
    hdr = skew_header(*corner[1:]) if len(corner) == 6 else flow.sim_header(corner[0], corner[1])
    deck_ = f'* {name}\n' + hdr + body + '\n.end\n'
    f, lg = Path(work) / name, Path(work) / (name + '.log')
    if f.exists() and lg.exists() and f.read_text() == deck_:
        log = lg.read_text()
        m = flow.parse_meas(log)
        if m:
            return log, m
    f.write_text(deck_)
    log = flow.ngspice(Path(work), name, timeout=7200)
    return log, flow.parse_meas(log)


def op_method(log):
    """How ngspice reached the DC operating point (from its notes): 'newton', 'gmin', 'source' or 'optran'
    (the pseudo-transient fallback, which is not a DC solution of the circuit and fails the op rows)."""
    if 'Transient op started' in log:
        return 'optran'
    if 'source stepping' in log.lower() or 'Starting source stepping' in log:
        return 'source'
    if 'gmin stepping' in log.lower():
        return 'gmin'
    return 'newton'


CTRL = ['en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1', *F.BW, *F.GN,
        'gainc0', 'gainc1', *F.QT, 'island_off', *F.FC, *F.DCF, 'dcf_sign']
PINS = ' '.join(F.PORTS).replace(' VSS', ' 0')
# CNV-01 (scratch/rf-cnv): Wi-Fi 20 MHz at 40 MS/s, alternate channel aliases from 31.25 MHz
FC_TARGET, FC_TOL = 10.5e6, 0.5e6
F_PASS, PASS_DROOP_DB = 8.75e6, 3.0
F_ALIAS, ALIAS_REJ_DB = 31.25e6, 38.0
# GX-1: widest range 20..30 MHz, peaking <= 1 dB, droop <= 3 dB at 19.1 MHz
WIDE_LO, WIDE_HI, F_WIDE, PEAK_MAX = 20e6, 30e6, 19.1e6, 1.0


def on_for(db=0, m=0, qt=F.QT_RESET, extra=()):
    """PGA code db, cap code m (0..127: bw = m >> 3, fc_fine = m & 7), Q-trim code qt (0..15)."""
    k, c0, c1 = N.GAIN_TABLE[db]
    on = {'en', *[f'gain{j}' for j in range(6) if k >> j & 1]}
    if c0:
        on.add('gainc0')
    if c1:
        on.add('gainc1')
    on |= {f'bw{j}' for j in range(4) if (m >> 3) >> j & 1}
    on |= {f'fc_fine{j}' for j in range(3) if m >> j & 1}
    on |= {f'qt{j}' for j in range(4) if qt >> j & 1}
    return on | set(extra)


def deck(nl, vdd, on, block, cm=1.65, src='rx', supply=None, ctl_ramp=False):
    a, b = ('rx_in', 'tx_in') if src == 'rx' else ('tx_in', 'rx_in')
    ctl = '\n'.join((f'V{c} {c} 0 PWL(0 0 2u {vdd})' if (ctl_ramp and c in on) else
                     f'V{c} {c} 0 {vdd if c in on else 0}') for c in CTRL)
    cmr = f'PWL(0 0 2u {cm})' if ctl_ramp else cm
    return f""".include {nl}
VDD VDD 0 {supply or vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Vcmr cmr 0 {cmr}
Vap {a}_p cmr DC 0 AC 0.5
Van {a}_n cmr DC 0 AC -0.5
Vbp {b}_p cmr 0
Vbn {b}_n cmr 0
{ctl}
X1 {PINS} pt_{block}
Cl1 out_rx_p 0 1p
Cl2 out_rx_n 0 1p
Cl3 out_tx_p 0 1p
Cl4 out_tx_n 0 1p
Cl5 obs_p 0 1p
Cl6 obs_n 0 1p
"""


def ac(work, view, corner, block='bbfilter_i', on=None, tag='a', cm=1.65):
    c, t, vdd = _cv(corner)
    nl = _nl(work, block, view)
    on = on_for() if on is None else on
    body = deck(nl, vdd, on, block, cm) + f"""
.control
op
let idd=-i(VDD)
let ocm=(v(out_rx_p)+v(out_rx_n))/2-{cm}
print idd ocm
ac dec 50 100k 300Meg
let g=db(v(out_rx_p)-v(out_rx_n))
meas ac g_dc find g at=100k
meas ac g_max max g
meas ac f3db when g=(g_dc-3) fall=1
meas ac g_pass find g at={F_PASS}
meas ac g_alias find g at={F_ALIAS}
meas ac g_wide find g at={F_WIDE}
.endc
"""
    log, m = _run(work, f'{block}_fd{tag}_{_vt(view)}_{_ctag(corner)}.cir', body, corner)
    r = dict(idd_a=m.get('idd'), out_cm_minus_in_v=m.get('ocm'), dc_gain_db=m.get('g_dc'), f3db_hz=m.get('f3db'))
    if m.get('g_dc') is not None:
        g = m['g_dc']
        r.update(peaking_db=m['g_max'] - g, rel_pass_db=m['g_pass'] - g, rel_alias_db=m['g_alias'] - g,
                 rel_wide_db=m['g_wide'] - g)
    return r


def _search(work, view, corner, block, qt, lo_ok, f_target, mmax=31):
    """Smallest |f3 - f_target| over cap code m in 0..mmax (f3 falls with m) at 0 dB; few sims."""
    seen = {}

    def f3(m):
        if m not in seen:
            seen[m] = ac(work, view, corner, block, on_for(0, m, qt), tag=f'm{m}q{qt}')
        return seen[m].get('f3db_hz') or 0.

    a_, b_ = 0, mmax
    fa, fb = f3(a_), f3(b_)
    if fa < f_target:
        return a_, seen
    if fb > f_target:
        return b_, seen
    while b_ - a_ > 1:              # bisection on the monotonic f3(m)
        mid = (a_ + b_) // 2
        if f3(mid) >= f_target:
            a_ = mid
        else:
            b_ = mid
    best = min((a_, b_), key=lambda m: abs(f3(m) - f_target))
    return best, seen


def trim_cnv01(work, view, corner, block='bbfilter_i', qts=None, gains=(0, 21, 42)):
    """CNV-01: per-corner (cap code, Q code) giving f3 = 10.5 +- 0.5 MHz, droop <= 3 dB at 8.75 MHz,
    >= 38 dB at 31.25 MHz, peaking <= 1 dB, at every listed PGA code with the same trim."""
    qts = qts or [F.QT_RESET, F.QT_RESET + 1, F.QT_RESET - 1, F.QT_RESET + 2, F.QT_RESET - 2, F.QT_RESET + 3]
    tried = []
    for qt in qts:
        m, _ = _search(work, view, corner, block, qt, None, FC_TARGET)
        rows = {g: ac(work, view, corner, block, on_for(g, m, qt), tag=f'cnv_g{g}m{m}q{qt}') for g in gains}
        # trim reference: f3 = 10.5 +- 0.5 MHz at 0 dB; the CNV-01 shape (droop at 8.75 MHz, alias rejection
        # at 31.25 MHz, peaking) must then hold at every PGA code with the same codes (f3 is reported per code)
        r0 = rows[gains[0]]
        ok = bool(r0.get('f3db_hz') and abs(r0['f3db_hz'] - FC_TARGET) <= FC_TOL) and all(
            r.get('f3db_hz') and r['rel_pass_db'] >= -PASS_DROOP_DB and r['rel_alias_db'] <= -ALIAS_REJ_DB
            and r['peaking_db'] <= PEAK_MAX for r in rows.values())
        rec = dict(cap_code=m, qt=qt, rows=rows, pass_=ok)
        tried.append(rec)
        if ok:
            break
    best = next((r for r in tried if r['pass_']), tried[0])
    return dict(best, tried=[(r['cap_code'], r['qt'], r['pass_']) for r in tried], state='pass' if best['pass_'] else 'fail')


def _wide_ok(r):
    return bool(r.get('f3db_hz') and WIDE_LO <= r['f3db_hz'] <= WIDE_HI and r['peaking_db'] <= PEAK_MAX
                and r['rel_wide_db'] >= -PASS_DROOP_DB)


def trim_wide(work, view, corner, block='bbfilter_i', qts=(14, 13, 15, 12, 11, 10), gains=(21, 42)):
    """GX-1: per-corner cap code (0..7) and Q code at 0 dB with f3 in 20..30 MHz, peaking <= 1 dB, droop <= 3 dB
    at 19.1 MHz; then, with the same cap code, a Q code per coarse PGA state (21 dB: gainc0, 42 dB: gainc0+1)
    meeting the same limits (the stage-1 loop and A1 noise gain change with the coarse steps; digital keeps a
    3-entry Q-code table per mode)."""
    tried, base = [], None
    for qt in qts:
        m, _ = _search(work, view, corner, block, qt, None, 25e6, mmax=7)
        r = ac(work, view, corner, block, on_for(0, m, qt), tag=f'wide_g0m{m}q{qt}')
        tried.append((m, qt, _wide_ok(r)))
        if _wide_ok(r):
            base = (m, qt, r)
            break
    if base is None:
        return dict(state='fail', tried=tried)
    m, q0, r0 = base
    rows = {0: dict(r0, qt=q0)}
    ok = True
    for g in gains:
        hit = None
        for dq in (-3, -2, -4, -1, -5, 0, -6, 1, -7):
            q = q0 + dq
            if not 0 <= q <= 15 or q < VALIDATOR_QT_MIN.get(m, 0):
                continue
            r = ac(work, view, corner, block, on_for(g, m, q), tag=f'wide_g{g}m{m}q{q}')
            if _wide_ok(r):
                hit = dict(r, qt=q)
                break
        rows[g] = hit or dict(r, qt=q, failed=True)
        ok = ok and hit is not None
    return dict(cap_code=m, qt_by_pga_db={g: v['qt'] for g, v in rows.items()}, rows=rows, tried=tried,
                state='pass' if ok else 'fail')


def op_dc(work, view, corner, block='bbfilter_i', on=None, cm=1.75, starts=True, min_nodes=10):
    """DC operating point, fork B (review item 2).  ngspice's DC homotopies (gmin / source stepping) do not converge
    on this 5-OTA, 10-loop netlist and it falls back to the pseudo-transient ('Transient op'), which is not by itself
    a DC solution.  So: (1) seed run (any method) -> every node voltage; (2) Newton re-solve from a .nodeset of that
    seed: must converge WITHOUT any homotopy or fallback (method 'newton') and land within 10 mV of the seed on every
    driven signal node -> a true DC equilibrium.
    (3) latch search: transients (uic) from 4 extreme initial states (every stage output and OTA first-stage node at
    CM 0.3 / 3.0 V and +-1 V differential) must settle to the SAME equilibrium (+-10 mV CM/DM, < 10 mV pp at
    18-20 us).  A Newton re-solve that needs any homotopy/fallback, or a second equilibrium, FAILS."""
    import re as _re
    c, t, vdd = _cv(corner)
    nl = _nl(work, block, view)
    on = on_for(42, 8) if on is None else on
    base = deck(nl, vdd, on, block, cm) + '.option itl1=500 gminsteps=20 srcsteps=20\n'

    def solve(tag, nodeset=''):
        body = base + nodeset + f"""
.control
op
let ocm=(v(out_rx_p)+v(out_rx_n))/2-{cm}
let odm=v(out_rx_p)-v(out_rx_n)
print ocm odm
print all
.endc
"""
        log, m = _run(work, f'{block}_fdop3{tag}_{_vt(view)}_{_ctag(corner)}.cir', body, corner)
        v = {k.lower(): float(x) for k, x in _re.findall(r'^\s*v\(([^)]+)\)\s*=\s*([-+0-9.eE]+)', log, _re.M)}
        if not v:
            v = {k.lower(): float(x) for k, x in _re.findall(r'^\s*([a-z0-9_.#/]+)\s*=\s*([-+0-9.eE]+)', log, _re.M | _re.I)
                 if '.' in k or '/' in k or k.startswith(('x', 'net'))}
        return op_method(log), m, v
    meth0, m0, v0 = solve('seed')
    if m0.get('ocm') is None or not v0:
        return dict(converged=False, method=meth0, state='fail')
    ns = '.nodeset ' + ' '.join(f'v({k})={x:.6g}' for k, x in v0.items() if '#' not in k) + '\n'
    meth1, m1, v1 = solve('newton', ns)
    # compare on the driven signal-path nodes only: bank capacitor nodes behind OFF switches, the series-MIM mid
    # nodes and the isolated out_tx/obs nodes have no DC conductance (their DC value is set by leakage, and the
    # pseudo-transient leaves them at arbitrary values, e.g. 7.5 V), so they are excluded and listed
    SIG = _re.compile(r'(^|[./])((s1|bp1|lp1|bp2|co|out_rx|inj|lp|bp)_[pn]|xa|xb|outp|outn|ocm|cmfb|cdump|tail|ctl|mp|mn|'
                      r'v1_[pn]|v2_[pn]|atb_vcm|atb_vbp)$')
    cmp_ = [k for k in v0 if SIG.search(k) and k in v1]
    dmax = max((abs(v1[k] - v0[k]) for k in cmp_), default=9.)
    rows = [dict(start='seed', method=meth0, ocm=m0.get('ocm'), odm=m0.get('odm')),
            dict(start='nodeset(seed) Newton re-solve', method=meth1, ocm=m1.get('ocm'), odm=m1.get('odm'),
                 n_nodes_compared=len(cmp_), max_node_dev_v=dmax)]
    # the seed (pseudo-transient end point) is only approximate (<= ~2 mV off); the proof is that plain Newton converges
    # from it with no homotopy, so the seed tolerance is 10 mV
    ok = meth1 == 'newton' and dmax < 1e-2 and len(cmp_) >= min_nodes
    if starts:     # latch search: transients from extreme initial conditions (uic), settled state at 18-20 us
        st = [k for k in v0 if _re.search(r'(^|[./])((s1|bp1|lp1|bp2|co)_[pn]|xa|xb|outp|outn)$', k)]
        for tag, f in (('cmlo', lambda k: 0.3), ('cmhi', lambda k: 3.0),
                       ('dmp', lambda k: 1.65 + (1. if k.endswith(('_p', 'xa', 'outp')) else -1.)),
                       ('dmn', lambda k: 1.65 - (1. if k.endswith(('_p', 'xa', 'outp')) else -1.))):
            body = base + '.ic ' + ' '.join(f'v({k})={f(k):.3g}' for k in st) + f"""
.control
tran 5n 20u uic
let ocm=(v(out_rx_p)+v(out_rx_n))/2-{cm}
let odm=v(out_rx_p)-v(out_rx_n)
meas tran ocmf avg ocm from=18u to=20u
meas tran odmf avg odm from=18u to=20u
meas tran odpp pp odm from=18u to=20u
.endc
"""
            _, mm = _run(work, f'{block}_fdop3ic{tag}_{_vt(view)}_{_ctag(corner)}.cir', body, corner)
            good = (mm.get('ocmf') is not None and abs(mm['ocmf'] - (m1.get('ocm') or 0)) < 0.01
                    and abs(mm['odmf'] - (m1.get('odm') or 0)) < 0.01 and mm.get('odpp', 1) < 0.01)
            rows.append(dict(start=f'tran uic from {tag}', n_nodes=len(st), ocm=mm.get('ocmf'), odm=mm.get('odmf'),
                             odm_pp=mm.get('odpp'), same_equilibrium=good))
            ok = ok and good
    ok = ok and abs(m1.get('ocm') or 1) < 0.05
    return dict(converged=m1.get('ocm') is not None, method=meth1, out_cm_minus_in_v=m1.get('ocm'), out_diff_v=m1.get('odm'),
                starts=rows, state='pass' if ok else 'fail')


def powerup(work, view, corner, block='bbfilter_i', on=None, cm=1.75):
    """Supply, controls and input CM ramp 0 -> final in 2 us; at 18-20 us the output CM must be the input
    CM (+-50 mV) and the differential output its DC value (|diff| < 0.1 V, no oscillation)."""
    c, t, vdd = corner
    nl = tb.netlist(work, block, view)
    on = on_for(42, 8) if on is None else on        # reset cap code 8 / Q code 6, top PGA code
    body = deck(nl, vdd, on, block, cm, supply=f'PWL(0 0 2u {vdd})', ctl_ramp=True) + f"""
.tran 20n 20u uic
.control
run
let ocm=(v(out_rx_p)+v(out_rx_n))/2-{cm}
let odm=v(out_rx_p)-v(out_rx_n)
meas tran ocm_end avg ocm from=18u to=20u
meas tran odm_end avg odm from=18u to=20u
meas tran odm_pp pp odm from=18u to=20u
.endc
"""
    log, m = _run(work, f'{block}_fdpu_{view}_{tb._tag(corner)}.cir', body, corner)
    ok = (m.get('ocm_end') is not None and abs(m['ocm_end']) < 0.05 and abs(m['odm_end']) < 0.1
          and m['odm_pp'] < 0.01)
    return dict(out_cm_minus_in_v=m.get('ocm_end'), out_diff_v=m.get('odm_end'), out_diff_pp_v=m.get('odm_pp'),
                state='pass' if ok else 'fail')


def dcoc(work, view, corner, block='bbfilter_i', codes=(0, 1, 2, 3, 4, 64, 127, 128, 129, 254, 255)):
    """Fine DCOC: stage-1 differential output vs code, both signs, PGA 0 dB; read through the observe mux
    (obs_sel = 10: after the PGA stage, TG into 1 pF; DC-exact) so the same bench runs on sch and ext."""
    c, t, vdd = corner
    nl = tb.netlist(work, block, view)
    body = deck(nl, vdd, on_for(0, 8, extra=('obs_sel1',)), block) + '\n.control\n'
    for sg in (0, 1):
        for code in codes:
            for k in range(F.DCF_BITS):
                body += f'alter vdcf{k} dc={vdd if (code >> k) & 1 else 0}\n'
            body += f'alter vdcf_sign dc={vdd if sg else 0}\nop\n'
            body += f'let s1_{sg}_{code}=v(obs_p)-v(obs_n)\nprint s1_{sg}_{code}\n'
    body += '.endc\n'
    log, m = tb.S.run(work, f'{block}_fddcoc_{view}_{tb._tag(corner)}.cir', body, corner=c, temp=t)
    s = {(sg, code): m.get(f's1_{sg}_{code}') for sg in (0, 1) for code in codes}
    if any(v is None for v in s.values()):
        return dict(state='fail', error='missing op points')
    z = s[(0, 0)]
    lsb = abs(s[(0, 255)] - z) / 255
    dnl = []
    for sg in (0, 1):
        seq = [abs(s[(sg, c_)] - z) for c_ in codes]
        dnl += [((seq[i + 1] - seq[i]) / (codes[i + 1] - codes[i])) / lsb - 1 for i in range(len(codes) - 1)]
    mono = min(dnl) > -1
    return dict(lsb_mv=lsb * 1e3, full_scale_mv=[(s[(0, 255)] - z) * 1e3, (s[(1, 255)] - z) * 1e3],
                dnl_lsb_min=min(dnl), dnl_lsb_max=max(dnl), monotonic=mono,
                points_mv={f'{sg}:{c_}': (v - z) * 1e3 for (sg, c_), v in s.items()},
                state='pass' if mono and lsb * 1e3 < 1.0 and abs(s[(0, 255)] - z) > 0.08 else 'fail')


# ---------------------------------------------------------------- noise (review item 4)
# Chain noise reference at the filter input (generated/rf_rx_chain.json, fork P/R deterministic chain, tt):
# LNA + mixer gain RF EMF (100 ohm diff source) -> I baseband = 35.7 dB at 5 MHz IF; DSB source noise
# (both sidebands) at the filter input = sqrt(2) * sqrt(4 k T 100) * G.
# last plausible chain reference seen by fork B (generated/rf_rx_chain.json, 2026-11-12 00:xx: fork P LNA + published
# mixers, deterministic DSB bench); used only when the run-time file fails the plausibility check below
CHAIN_PINNED = dict(gain_db=35.34, gain_db_by={'tt': 35.34, 'ss': 31.49}, nf_dsb_db={'tt': 4.2197, 'ss': 5.9363},
                    source='pinned (rf_rx_chain.json as read 2026-11-12 ~00:30 UTC)')


def chain_ref():
    """LNA + mixer/TIA reference read at run time from generated/rf_rx_chain.json (fork B: the TIA/LNA are being
    changed concurrently, so no hard-coded copy).  Gain: the lower of the I/Q extracted conversion gains (ext_m; lower
    gain = larger filter penalty, pessimistic); ss: minus the tt->ss drop of the deterministic bench's 4 MHz signal
    gain.  NF: the deterministic DSB chain NF without the filter, tt and ss.  Plausibility: I/Q gains within 3 dB,
    matched-LNA gain > 0 dB, DSB NF < 10 dB; otherwise the pinned reference is used and the reason recorded."""
    import json
    try:
        d = json.loads((Path(__file__).parent / 'generated' / 'rf_rx_chain.json').read_text())
        gi, gq = d['ext_m']['gain_i_db'], d['ext_m']['gain_q_db']
        dt, ds = d['det_lna_matched_extpr'], d['det_lna_matched_extpr_ss_32_3.15']
        bad = [w for w, c in (('I/Q gain differ > 3 dB', abs(gi - gq) > 3), ('LNA gain <= 0 dB', dt['lna_matched']['gain_db'] <= 0),
                              ('DSB NF >= 10 dB', dt['nf_dsb_db'] >= 10)) if c]
    except Exception as e:
        bad = [f'unreadable: {e!r}'[:120]]
    if bad:
        return dict(CHAIN_PINNED, valid_runtime=False, reason='; '.join(bad))
    g = min(gi, gq)
    dss = dt['gain_sig_db']['4.0MHz'] - ds['gain_sig_db']['4.0MHz']
    return dict(gain_db=round(g, 2), gain_db_by={'tt': round(g, 2), 'ss': round(g - dss, 2)},
                nf_dsb_db={'tt': dt['nf_dsb_db'], 'ss': ds['nf_dsb_db']}, valid_runtime=True,
                source='generated/rf_rx_chain.json at run time')


CHAIN_GAIN_DB = chain_ref()['gain_db']
KT4 = 4 * 1.380649e-23 * 300.15


def chain_source_noise_v(gain_db=None):
    return (2 * KT4 * 100.) ** .5 * 10 ** ((CHAIN_GAIN_DB if gain_db is None else gain_db) / 20)


def noise(work, view, corner, block='bbfilter_i', db=0, m=8, qt=F.QT_RESET, f_lo=1e5, f_hi=10e6):
    """Differential output noise and input-referred noise (rx_in diff), PGA code db, cap code m, Q code qt.
    Input-referred density at 1 / 5 MHz, rms over f_lo..f_hi (output and input-referred), and the chain NF
    penalty dF = (v_in / v_src_chain)^2 against the DSB source noise at the filter input."""
    import numpy as np
    c, t, vdd = _cv(corner)
    nl = _nl(work, block, view)
    d = deck(nl, vdd, on_for(db, m, qt), block).replace('Van rx_in_n cmr DC 0 AC -0.5', "Ean rx_in_n cmr rx_in_p cmr -1").replace(
        'Vap rx_in_p cmr DC 0 AC 0.5', 'Vap rx_in_p cmr DC 0 AC 1')
    name = f'{block}_fdnz_g{db}m{m}q{qt}_{_vt(view)}_{_ctag(corner)}.cir'
    body = d + f"""
.control
noise v(out_rx_p,out_rx_n) Vap dec 20 {f_lo:g} {f_hi:g}
setplot noise1
wrdata {name}.onz onoise_spectrum inoise_spectrum
.endc
"""
    log, m_ = _run(work, name, body, corner)
    try:
        a = np.loadtxt(Path(work) / f'{name}.onz')
    except Exception as e:
        return dict(state='fail', error=repr(e)[:200])
    f, on, inz = a[:, 0], a[:, 1], a[:, 3] * 2     # inoise refers to Vap; v_in,diff = 2 Vap -> x2
    trap = getattr(np, 'trapezoid', None) or np.trapz
    vo = float(trap(on ** 2, f) ** .5); vi_rms = float(trap(inz ** 2, f) ** .5)
    at = lambda fx: float(np.interp(np.log(fx), np.log(f), inz))
    src = chain_source_noise_v(chain_ref()['gain_db_by']['ss' if c == 'ss' else 'tt'])
    dF = (at(5e6) / src) ** 2
    return dict(pga_db=db, cap_code=m, qt=qt, out_rms_v=vo, in_rms_v=vi_rms, in_nv_rthz_1mhz=at(1e6) * 1e9,
                in_nv_rthz_5mhz=at(5e6) * 1e9, chain_src_nv_rthz=src * 1e9, delta_f_at_5mhz=dF,
                note='chain NF with this filter: F_total = F_chain + delta_f (F linear)')


# ---------------------------------------------------------------- CNV-01 per-PGA cutoff table (review item 3)
def trim_cnv01_pga(work, view, corner, block='bbfilter_i', qts=None, pgas=None, offsets=(0, -1, 1, -2, 2)):
    """CNV-01 with a per-PGA-code cap-code table.  The stage-1 loop (noise gain 1 + k/4) and the +12 dB biquad
    steps lower the cutoff by up to ~8 % from PGA 0 to 42 dB (review: 9.41-9.58 MHz at 42 dB with a single
    trim), more than the +-4.8 % window, so the per-part calibration stores one cap code per PGA code
    (base code at 0 dB + a small offset; digital: FS-1 cutoff table).  Every PGA code must then give
    f3 = 10.5 +- 0.5 MHz, <= 3 dB droop at 8.75 MHz, >= 38 dB at 31.25 MHz, <= 1 dB peaking."""
    pgas = sorted(N.GAIN_TABLE) if pgas is None else pgas
    base = trim_cnv01(work, view, corner, block, qts=qts, gains=(0,))
    m0, qt = base['cap_code'], base['qt']

    def ok(r):
        return bool(r.get('f3db_hz') and abs(r['f3db_hz'] - FC_TARGET) <= FC_TOL and r['rel_pass_db'] >= -PASS_DROOP_DB
                    and r['rel_alias_db'] <= -ALIAS_REJ_DB and r['peaking_db'] <= PEAK_MAX)
    table, qtab, rows, good = {}, {}, {}, True
    for g in pgas:
        # fork B: closest-to-target code (largest margin), not the first passing one.  f3 falls with m, so from
        # offset 0 step toward the target (-1 if f3 is low, +1 if high) until f3 crosses 10.5 MHz, then keep the
        # closer of the last two that pass (2-3 AC runs per PGA code).
        cand = {}

        def at(off):
            m = m0 + off
            if off not in cand and 0 <= m <= 127:
                cand[off] = ac(work, view, corner, block, on_for(g, m, qt), tag=f'cnvp_g{g}m{m}q{qt}')
            return cand.get(off, {}).get('f3db_hz')
        f0 = at(0)
        if f0:
            step = -1 if f0 < FC_TARGET else 1
            off = 0
            while abs(off) < max(abs(o) for o in offsets):
                fo = at(off + step)
                if not fo:
                    break
                off += step
                if (fo - FC_TARGET) * (f0 - FC_TARGET) <= 0:
                    break
        good_ = [(abs(r['f3db_hz'] - FC_TARGET), o, r) for o, r in cand.items() if r.get('f3db_hz') and ok(r)]
        any_ = [(abs(r['f3db_hz'] - FC_TARGET), o, r) for o, r in cand.items() if r.get('f3db_hz')]
        best = (min(good_, key=lambda x: x[0]) if good_ else min(any_, key=lambda x: x[0]) if any_ else None)
        best = best and (best[1], best[2], qt)
        if best is not None and (not ok(best[1]) or abs(best[1]['f3db_hz'] - FC_TARGET) > 0.3e6):
            # fork B: Q-code vernier (used when no cap code passes or the best is > 0.3 MHz off).  At ss one fine cap
            # LSB is ~10 % of f3 (window 9.5 %); qt +-1 moves f3 by ~3 %
            # (peaking / droop / alias still checked).  The per-PGA calibration entry is then {cap code, qt}.
            near = sorted(cand, key=lambda o: abs((cand[o].get('f3db_hz') or 0) - FC_TARGET))[:2]
            vern = []
            for o in near:
                for dq in (-1, 1, -2, 2):
                    q2 = qt + dq
                    if 0 <= q2 <= 15 and q2 >= VALIDATOR_QT_MIN.get(m0 + o, 0):
                        r2 = ac(work, view, corner, block, on_for(g, m0 + o, q2), tag=f'cnvp_g{g}m{m0 + o}q{q2}')
                        if r2.get('f3db_hz') and ok(r2):
                            vern.append((abs(r2['f3db_hz'] - FC_TARGET), o, r2, q2))
            if ok(best[1]):
                vern.append((abs(best[1]['f3db_hz'] - FC_TARGET), best[0], best[1], qt))
            if vern:
                _, o, r2, q2 = min(vern, key=lambda x: x[0])
                best = (o, r2, q2)
        if best is None:
            good = False; continue
        table[g] = best[0]; qtab[g] = best[2]
        rows[g] = dict(best[1], cap_code=m0 + best[0], qt=best[2], pass_=ok(best[1]))
        good = good and ok(best[1])
    return dict(cap_code_pga0=m0, qt=qt, offset_by_pga_db=table, qt_by_pga_db=qtab, rows=rows, base_tried=base.get('tried'),
                state='pass' if good else 'fail')


# ---------------------------------------------------------------- stability at skewed corners (review item 1)
PDK = flow.ANALOG_PDK + '/libs.tech/ngspice/sm141064.ngspice'
# (tag, MOS corner, poly-R/MIM corner, T, VDD, poly sheet override): MOS and R/MIM vary independently;
# the R override is the design-assumptions.md pessimistic poly spread (+-25 % around 1 kohm/sq).
SKEW = [('ssMOS_ffRC_22', 'ss', 'ff', 22, 3.15, 750), ('ssMOS_ffRC_32', 'ss', 'ff', 32, 3.15, 750),
        ('ffMOS_ffRC_22', 'ff', 'ff', 22, 3.35, 750), ('ffMOS_ssRC_22', 'ff', 'ss', 22, 3.35, 1250),
        ('ss_32', 'ss', 'ss', 32, 3.15, None), ('tt_27', 'typical', 'typical', 27, 3.3, None),
        ('ff_22', 'ff', 'ff', 22, 3.35, None)]


def skew_header(mos, rc, temp, rpoly=None):
    h = (f'.include {flow.ANALOG_PDK}/libs.tech/ngspice/design.ngspice\n.lib {PDK} {mos}\n.lib {PDK} res_{rc}\n'
         f'.lib {PDK} mimcap_{rc}\n.lib {PDK} diode_{rc}\n')
    if rpoly:
        h += f'.param rsh_ppolyf_u_1k={rpoly}\n'
    return h + f'.option temp={temp} gmin=1e-12 reltol=1e-3\n'


STAGES = ['s1', 'bp1', 'lp1', 'bp2', 'co']


def kick(work, view, skew, on, block='bbfilter_i', lim=50e-6):
    """10 ns 20 mV differential kick at 1 us, then a +100 mV input-CM step at 2.5 us (held).  Every stage's DM
    and CM (s1, bp1, lp1, bp2, co) is written out; per signal the quadratic-detrended residual pp in
    3.5-4.5 us and 5-6 us.  Stable: every residual at 5-6 us < 50 uV or decaying >= 2x.  0.25 ns max step."""
    import numpy as np, hashlib
    tag, mos, rc, temp, vdd, rp = skew
    nl = _nl(work, block, view)
    import re as _re
    src = Path(work) / nl
    txt = src.read_text()
    i = txt.index(f'.subckt pt_{block} '); e = txt.index('.ends', i)
    top = txt[i:e].replace('\n+', ' ')

    def net(n, h):      # extracted top nets may carry a cell prefix (e.g. XX6/s1_p): take the one present
        c = sorted(set(_re.findall(rf'(?<=\s)(\S*/)?{n}_{h}(?=\s)', top)))
        return (c[0] if c else '') + f'{n}_{h}'
    probes = ''.join(f'Ekp{n}{h} kp_{n}_{h} 0 {net(n, h)} 0 1\n' for n in STAGES for h in 'pn')
    pn = f'{block}_kprobe_{_vt(view)}.spice'
    (Path(work) / pn).write_text(txt[:e] + probes + txt[e:])
    d = deck(pn, vdd, on, block, 1.65)
    d = d.replace('Vap rx_in_p cmr DC 0 AC 0.5', 'Vap rx_in_p cmr PULSE(0 0.01 1u 0.2n 0.2n 10n 1)')
    d = d.replace('Van rx_in_n cmr DC 0 AC -0.5', 'Van rx_in_n cmr PULSE(0 -0.01 1u 0.2n 0.2n 10n 1)')
    d = d.replace('Vcmr cmr 0 1.65', 'Vcmr cmr 0 PULSE(1.65 1.75 2.5u 1n 1n 10 20)')
    lets = []
    for n in STAGES:
        lets += [f'let d_{n}=v(x1.kp_{n}_p)-v(x1.kp_{n}_n)', f'let c_{n}=(v(x1.kp_{n}_p)+v(x1.kp_{n}_n))/2']
    vecs = ' '.join(f'{k}_{n}' for n in STAGES for k in ('d', 'c'))
    code = ''.join(sorted(on))
    name = f'{block}_kick_{_vt(view)}_{tag}_{hashlib.sha1(code.encode()).hexdigest()[:8]}.cir'
    body = d + f"\n.tran 0.1n 6u 0 0.25n\n.control\nrun\n" + '\n'.join(lets) + f'\nwrdata {name}.dat {vecs}\n.endc\n'
    sha = hashlib.sha256((Path(work) / pn).read_bytes()).hexdigest()
    deck_ = f'* {name}\n* netlist sha256 {sha}\n' + skew_header(mos, rc, temp, rp) + body + '\n.end\n'
    f_ = Path(work) / name
    dat = Path(work) / f'{name}.dat'
    if not (f_.exists() and dat.exists() and f_.read_text() == deck_):
        f_.write_text(deck_)
        flow.ngspice(Path(work), name, timeout=7200)
    try:
        a = np.loadtxt(dat)
    except Exception as ex:
        return dict(state='fail', error=repr(ex)[:200])
    t = a[:, 0]; worst = (0., None, None); ok = True
    for j, nm in enumerate(f'{k}_{n}' for n in STAGES for k in ('d', 'c')):
        y = a[:, 2 * j + 1]; res = []
        for lo, hi in ((3.5e-6, 4.5e-6), (5e-6, 6e-6)):
            tu = np.arange(lo, hi, 0.1e-9); yu = np.interp(tu, t, y)
            p = np.polyfit(tu * 1e6, yu, 2); r = yu - np.polyval(p, tu * 1e6)
            F_ = np.abs(np.fft.rfft(r)); fr = np.fft.rfftfreq(len(r), 0.1e-9)
            res.append((float(r.max() - r.min()), float(fr[np.argmax(F_[1:]) + 1])))
        if res[1][0] > lim and res[1][0] > 0.5 * res[0][0]:
            ok = False
        if res[1][0] > worst[0]:
            worst = (res[1][0], nm, res[1][1])
    return dict(corner=tag, worst_residual_pp_v=worst[0], worst_signal=worst[1], worst_f_hz=worst[2],
                state='pass' if ok else 'fail')


# the validator-allowed boundary: lowest cap code (highest integrator frequency, lowest OTA feedback factor),
# highest Q at that code (cap code <= 1 requires qt >= 6: FS-1 rule), every coarse PGA state; the
# high-feedback-factor end (cap code 127, lowest PGA code) for the OTA local loops.
VALIDATOR_QT_MIN = {0: 6, 1: 6}
KICK_SET = [(0, 0, 6), (21, 0, 6), (42, 0, 6), (0, 0, 0), (42, 0, 0), (0, 2, 0), (42, 2, 0), (-6, 127, 0), (42, 127, 15)]


# ---------------------------------------------------------------- bench validation (coordinator: prove benches small first)
def _fake(kind, fc=10.5e6):
    """Hand-calculable stand-ins with the pt_bbfilter port list.  'bw5': ideal 5th-order Butterworth (RC pole +
    two unity-gain Sallen-Key with ideal VCVS), f3 = fc.  'unstable': the same with the Q-1.618 section replaced
    by a Sallen-Key of gain 3.2 (Q = 1/(3 - K) < 0, RHP pair) limited by tanh.  'rnet': each output = its input
    through 10k with 10k to an ideal 1.65 V (diff gain 0.5, input-referred noise 2 sqrt(2 * 4kT * 5k))."""
    import math
    ports = ' '.join(F.PORTS)
    L = [f'.subckt pt_bbfval {ports}'] + [f'Rdc{i} {n} 0 1e9' for i, n in enumerate(F.PORTS) if n != 'VSS']
    if kind == 'latch':     # bistable: xa follows 1.65 + 1.2 tanh(6 (xa - 1.65)) through 1k/1p -> 0.45 / 1.65 / 2.85 V
        L += ['Rl xa xd 1k', 'Cl xa 0 1p', 'Bl xd 0 v=1.65+1.2*tanh(6*(v(xa)-1.65))', 'Bop out_rx_p 0 v=v(xa)',
              'Bon out_rx_n 0 v=3.3-v(xa)', 'Rxb xb 0 1k']
    elif kind == 'rnet':
        L += ['Vcmx cmx 0 1.65', 'R1 rx_in_p out_rx_p 10k', 'R2 out_rx_p cmx 10k', 'R3 rx_in_n out_rx_n 10k', 'R4 out_rx_n cmx 10k']
    else:
        w0 = 2 * math.pi * fc; R = 1e3
        L += ["B0 u 0 v=v(rx_in_p)-v(rx_in_n)", f'R0 u s1 {R}', f'C0 s1 0 {1 / (w0 * R):.6e}', 'Ebuf s1b 0 s1 0 1']
        prev = 's1b'
        for k, (q, nm) in enumerate(((0.618034, 'lp1'), (1.618034, 'co'))):
            a, b = f'a{k}', f'b{k}'
            if kind == 'unstable' and nm == 'co':
                c = 1 / (w0 * R)
                L += [f'Ra{k} {prev} {a} {R}', f'Rb{k} {a} {b} {R}', f'C1{k} {a} {nm} {c:.6e}', f'C2{k} {b} 0 {c:.6e}',
                      f'Bu{k} {nm} 0 v=tanh(3.2*v({b}))']
            else:
                L += [f'Ra{k} {prev} {a} {R}', f'Rb{k} {a} {b} {R}', f'C1{k} {a} {nm} {2 * q / (w0 * R):.6e}',
                      f'C2{k} {b} 0 {1 / (2 * q * w0 * R):.6e}', f'Es{k} {nm} 0 {b} 0 1']
            prev = nm
        L += ['E9 bp1 0 lp1 0 1', 'E8 bp2 0 co 0 1']
        for n in ('s1', 'bp1', 'lp1', 'bp2', 'co'):
            L += [f'B{n}p {n}_p 0 v=1.65+v({n})/2', f'B{n}n {n}_n 0 v=1.65-v({n})/2']
        L += ['Bop out_rx_p 0 v=1.65+v(co)/2', 'Bon out_rx_n 0 v=1.65-v(co)/2']
    L += ['.ends', '']
    return '\n'.join(L)


def validate(work):
    """Run every bbfilter bench on hand-calculable circuits and a deliberately broken one; each check states the
    analytic expectation and passes only within tolerance (recorded in the evidence)."""
    import math
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    out = {}
    for k in ('bw5', 'unstable', 'rnet', 'latch'):
        (work / f'val_{k}.spice').write_text(_fake(k))
    nom = ('typical', 27, 3.3)
    # 1. AC bench: ideal Butterworth 10.5 MHz
    r = ac(work, work / 'val_bw5.spice', nom, 'bbfval', on=set(), tag='val')
    e_pass = -10 * math.log10(1 + (F_PASS / 10.5e6) ** 10); e_alias = -10 * math.log10(1 + (F_ALIAS / 10.5e6) ** 10)
    ok = (r.get('f3db_hz') and abs(r['f3db_hz'] / 10.5e6 - 1) < 0.01 and abs(r['rel_pass_db'] - e_pass) < 0.05
          and abs(r['rel_alias_db'] - e_alias) < 0.3 and abs(r['peaking_db']) < 0.05)
    out['ac_ideal_butterworth'] = dict(expect=dict(f3db_hz=10.5e6, rel_pass_db=e_pass, rel_alias_db=e_alias, peaking_db=0.),
                                       got={k: r.get(k) for k in ('f3db_hz', 'rel_pass_db', 'rel_alias_db', 'peaking_db')},
                                       state='pass' if ok else 'fail')
    # 2. noise bench: resistor network, 4kTR
    kt4 = 4 * 1.380649e-23 * 300.15
    e_in = 2 * math.sqrt(2 * kt4 * 5e3)
    r = noise(work, work / 'val_rnet.spice', nom, 'bbfval', 0, 0, 0)
    ok = r.get('in_nv_rthz_5mhz') and abs(r['in_nv_rthz_5mhz'] * 1e-9 / e_in - 1) < 0.03
    out['noise_resistor_network'] = dict(expect_in_nv_rthz=e_in * 1e9, got_in_nv_rthz=r.get('in_nv_rthz_5mhz'),
                                         state='pass' if ok else 'fail')
    # 3. op method detector: forced pseudo-transient must be flagged, a plain Newton op must not
    res = {}
    # broken case: a node with no DC path (two series capacitors) makes the DC matrix singular, so Newton and
    # the DC homotopies fail and ngspice falls back to the pseudo-transient op (what the old 'plain Newton' row
    # silently accepted)
    for tag, opt in (('forced_optran', 'Cfa flt 0 1p\nCfb flt out_rx_p 1p\n'), ('plain', '')):
        body = deck(_nl(work, 'bbfval', work / 'val_bw5.spice'), 3.3, set(), 'bbfval') + opt + '.control\nop\nprint v(out_rx_p)\n.endc\n'
        log, _ = _run(work, f'val_op_{tag}.cir', body, nom)
        res[tag] = op_method(log)
    out['op_fallback_detector'] = dict(expect=dict(forced_optran='optran', plain='newton'), got=res,
                                       state='pass' if res == dict(forced_optran='optran', plain='newton') else 'fail')
    # 3b. op_dc (Newton re-solve + latch search): ideal Butterworth passes, the bistable stand-in must FAIL
    og = op_dc(work, work / 'val_bw5.spice', nom, 'bbfval', on=set(), cm=1.65, min_nodes=1)
    ol = op_dc(work, work / 'val_latch.spice', nom, 'bbfval', on=set(), cm=1.65, min_nodes=1)
    out['op_latch_detector'] = dict(expect=dict(butterworth='pass', bistable='fail'),
                                    got=dict(butterworth=og.get('state'), bistable=ol.get('state'), bistable_starts=ol.get('starts')),
                                    state='pass' if (og.get('state'), ol.get('state')) == ('pass', 'fail') else 'fail')
    # 4. oscillation detector: the stable Butterworth must pass, the RHP-pole biquad must be flagged
    ks = kick(work, work / 'val_bw5.spice', SKEW[5], set(), 'bbfval')
    ku = kick(work, work / 'val_unstable.spice', SKEW[5], set(), 'bbfval')
    out['oscillation_detector'] = dict(expect=dict(stable='pass', unstable='fail'), got=dict(stable=ks.get('state'), unstable=ku.get('state'),
                                       unstable_worst_pp_v=ku.get('worst_residual_pp_v'), unstable_f_hz=ku.get('worst_f_hz')),
                                       state='pass' if (ks.get('state'), ku.get('state')) == ('pass', 'fail') else 'fail')
    out['state'] = 'pass' if all(v['state'] == 'pass' for v in out.values() if isinstance(v, dict)) else 'fail'
    return out
