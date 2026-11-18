"""LNA closing evidence (session Q): the rows that decide GO / NO-GO for pt_lna, on the extracted layout in generated/.

  python3 lna_close.py currents | stab | stab_lf | band | chain | neg | write     (each stage writes scratch/rf_rx/close/<stage>.json;
                                                                  `write` assembles generated/lna-evidence.json)
Limits were fixed before the runs (scratch/rf-lna-q/NOTES.md) and are constants here.  At most 3 simulations at once.
Corners: tt / ss / ff / sf / fs x 22 / 32 C x 3.15 / 3.35 V (20).  Views: extpr (extracted + pad delta + Rg 150 ohm/10 um),
extpp (pessimistic NF end), extlo (low-loss end).  Extraction is capacitance-only (no wire resistance): see README open items."""
import sys, json, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import rfrx_flow as flow, tb, lna_match as LM, simlib as S

OUT = flow.SCRATCH / 'close'
GEN = flow.GENERATED
PROCS = ('typical', 'ss', 'ff', 'sf', 'fs')
CORNERS = [(p, t, v) for p in PROCS for t in (22, 32) for v in (3.15, 3.35)]
NOM, FF, SS = ('typical', 27, 3.3), ('ff', 32, 3.35), ('ss', 32, 3.15)
LIM = dict(idd_rx_ma=19.0, idd_lo_ma=11.8, re_diff_ohm=1.0, re_cm_ohm=1.0, s11_db=-10.0, lna_nf_db=6.0, derate_db=1.5, chain_nf_dsb_db=4.1)
TANK_CT = {('extpr', 'typical'): 9, ('extpr', 'ss'): 6, ('extpr', 'ff'): 9, ('extpr', 'sf'): 9, ('extpr', 'fs'): 9, ('extpp', 'ss'): 12,
           ('extpp', 'typical'): 12, ('extlo', 'ff'): 6, ('extlo', 'typical'): 6}


def par(fns, n=None):
    import os
    n = n or int(os.environ.get("JOBS", "3"))
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(lambda f: f(), fns))


def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.json').write_text(json.dumps(obj, indent=1, default=str))


def currents():
    def one(c, lob):
        tb.set_lobias(lob)
        try:
            u = tb.lna_ac(OUT / ('idd_lo' if lob else 'idd_rx'), 'ext', c, f=2.44e9, ct=9)
        finally:
            tb.set_lobias(False)
        return dict(corner=c, lobias=lob, idd_ma=u['idd_a'] * 1e3 if u.get('idd_a') else None)
    rows = par([(lambda c=c, lob=lob: one(c, lob)) for c in CORNERS for lob in (False, True)])
    off = [tb.lna_ac(OUT / 'idd_off', 'ext', c, 'off', f=2.44e9) for c in (NOM, ('ff', 85, 3.63))]
    for r in rows:
        r['pass'] = r['idd_ma'] is not None and r['idd_ma'] <= (LIM['idd_lo_ma'] if r['lobias'] else LIM['idd_rx_ma'])
    save('currents', dict(rows=rows, off_a=[o.get('idd_a') for o in off]))


def _stab(view, c, group, deg=None, lob=False, **kw):
    tb.set_lobias(lob)
    try:
        r = LM.stability(OUT / 'stab', view, c, deg=deg, **kw)
    except Exception as e:
        r = dict(error=repr(e))
    finally:
        tb.set_lobias(False)
    ok_d = (r.get('min_mu') or 0) > 1 and (r.get('min_k') or 0) > 1 and (r.get('min_re_zin_real_mixer_ohm') or -1) >= LIM['re_diff_ohm']
    ok_c = (r.get('min_re_zcm_real_mixer_ohm') or -1) >= LIM['re_cm_ohm']
    # common mode restricted to the range where the device has gain (information; the pass field uses the full 0.1-30 GHz minimum)
    return dict(group=group, view=view, corner=c, degeneration_model=deg or tb.LNA_DEG_VIEW.get(view, 'nom'), lobias=lob, case=kw,
                pass_differential=bool(ok_d), pass_common_mode=bool(ok_c), **r)


def stab():
    jobs = [('extpr', c, 'A corners', 'lowr', {}) for c in CORNERS]
    jobs += [(v, c, 'A model ends', dg, {}) for v in ('extlo', 'extpp') for c in (FF, ('ff', 22, 3.35), SS, NOM) for dg in (None, 'lowr')]
    jobs += [('extpr', FF, 'B states', 'lowr', st) for st in (dict(ct=0), dict(ct=15), dict(rt=True), dict(att=31), dict(att=63), dict(mode='bypass'))]
    jobs += [('extpr', FF, 'B passive reference (LNA disabled)', 'lowr', dict(mode='off'))]
    jobs += [('extpr', FF, 'S1 no credit', 'lowr', dict(lsup=l)) for l in (0.25e-9, 2e-9)]
    jobs += [('extpr', FF, 'S1 RF bond tolerance', 'lowr', dict(bond=b)) for b in (LM.BOND - LM.BOND_TOL, LM.BOND + LM.BOND_TOL)]
    jobs += [('extpr', FF, 'S2 real PDN', 'lowr', k) for k in (dict(cdie=5.4e-9, rdie=0.1, rsw=0.3, lsup=0.25e-9), dict(cdie=5.4e-9, rdie=0.03, rsw=0.2, lsup=0.5e-9),
                                                              dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=1e-9), dict(cdec=100e-12, rsw=0.25, cdie=5.4e-9, rdie=0.05, lsup=0.5e-9),
                                                              dict(cdec=500e-12, rsw=0.25, cdie=5.4e-9, rdie=0.05, lsup=0.5e-9))]
    jobs += [('extpr', FF, 'S3 undamped island decap, no die decap', 'lowr', k) for k in (dict(cdec=100e-12), dict(cdec=500e-12), dict(cdec=100e-12, lsup=2e-9), dict(cdec=500e-12, lsup=0.25e-9))]
    rows = par([(lambda j=j: _stab(j[0], j[1], j[2], deg=j[3], **j[4])) for j in jobs])
    rows.append(_stab('extpr', FF, 'B duplex bias', deg='lowr', lob=True))
    rows += _duplex_pdn()
    save('stab', rows)


def _duplex_pdn():
    """Review 4: duplex bias and the attenuator at its end with the real supply network."""
    pdn = (dict(cdie=5.4e-9, rdie=0.03, rsw=0.2, lsup=0.5e-9), dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=1e-9), dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=2e-9))
    return ([_stab('extpr', FF, 'B duplex bias, real PDN', deg='lowr', lob=True, **k) for k in pdn] +
            [_stab('extpr', FF, 'B attenuator 63, real PDN', deg='lowr', att=63, **pdn[1])])


def stab_extra():
    rows = [r for r in json.loads((OUT / 'stab.json').read_text()) if 'real PDN' not in r['group'] or r['group'].startswith('S2')]
    save('stab', rows + _duplex_pdn())


def stab_lf():
    """Review 4 finding 1: the 0.1-30 GHz sweep does not see the anti-resonance of the bond loop with the die decap (45-100 MHz).
    Same bench, 5 MHz - 1 GHz at 400 points per decade, real-PDN cases incl. low die decap, RX and duplex bias, tt / ss / ff."""
    pdn = [dict(cdie=5.4e-9, rdie=0.1, rsw=0.3, lsup=0.25e-9), dict(cdie=5.4e-9, rdie=0.03, rsw=0.2, lsup=0.5e-9), dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=1e-9),
           dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=2e-9), dict(cdie=3e-9, rdie=0.1, rsw=0.3, lsup=1e-9), dict(cdie=0.9e-9, rdie=0.03, rsw=0.2, lsup=1e-9, cdec=500e-12)]
    def one(c, lob, k):
        global OUT
        tb.set_lobias(lob)
        try:
            r = LM.stability(OUT / 'stab_lf', 'extpr', c, deg='lowr', f1=5e6, f2=1e9, ppd=400, **k)
        except Exception as e:
            r = dict(error=repr(e))
        finally:
            tb.set_lobias(False)
        return dict(corner=c, lobias=lob, case=k, pass_common_mode=bool((r.get('min_re_zcm_real_mixer_ohm') or -1) >= LIM['re_cm_ohm']),
                    pass_differential=bool((r.get('min_re_zin_real_mixer_ohm') or -1) >= LIM['re_diff_ohm']), **r)
    jobs = [(FF, False, k) for k in pdn] + [(FF, True, k) for k in pdn[1:4]] + [(NOM, False, pdn[3]), (SS, False, pdn[3])]
    save('stab_lf', par([(lambda j=j: one(*j)) for j in jobs]))


def band():
    def one(view, c, d_mm):
        ct = TANK_CT.get((view, c[0]), 9)
        w = OUT / 'band'
        u = tb.lna_ac(w, view, c, f=2.44e9, ct=ct); z = complex(u['zin_re_ohm'], u['zin_im_ohm'])
        m, s11_fit, loss_fit = LM.channel_fit(z, d_mm=d_mm); m['ct'] = ct
        b = tb.lna_band(w, view, c, m, ct=ct)
        ideal = tb.lna_ac(w, view, c, f=2.44e9, ct=ct, match=tb.board_match(z, f=2.44e9))
        own = tb.lna_ac(w, view, c, f=2.44e9, ct=ct, match=tb.board_match(z, f=2.44e9), noiseless_load=True)
        inb = [r for r in b['rows'] if 2.3999e9 <= r['f'] <= 2.48351e9]
        row = dict(view=view, corner=c, carrier_distance_mm=d_mm, ct=ct, zpad_ohm=[z.real, z.imag], carrier_parts=m['parts'],
                   s11_worst_db=max(r['s11_db'] for r in b['rows']), gain_db=[min(r['gain_db'] for r in inb), max(r['gain_db'] for r in inb)],
                   nf_db=[min(r['nf_db'] for r in inb), max(r['nf_db'] for r in inb)], gain_ideal_lossless_match_db=ideal['gain_db'],
                   nf_own_ideal_match_db=own['nf_db'], channel_and_match_loss_db=ideal['gain_db'] - max(r['gain_db'] for r in inb))
        der = LIM['derate_db'] if view == 'extpp' else 0.
        row['pass_s11'] = row['s11_worst_db'] <= LIM['s11_db']; row['pass_nf'] = row['nf_db'][1] + der <= LIM['lna_nf_db']
        return row
    jobs = [('extpr', (p, t, v), 2.) for p in PROCS for t, v in ((32, 3.15), (22, 3.35))]
    jobs += [('extpr', NOM, 2.), ('extpr', NOM, 10.), ('extpp', SS, 2.), ('extpp', SS, 10.), ('extpp', ('typical', 32, 3.15), 2.), ('extlo', ('ff', 22, 3.35), 2.)]
    save('band', par([(lambda j=j: one(*j)) for j in jobs]))


PKG_MODELS = ('A_min', 'A_nom', 'A_max', 'B_min', 'B_nom', 'B_max')     # pads owner's coupled bond model: site option x inductance bound


def bounce(model, corner=NOM, f=2.421875e9, decap=True, view='extpr'):
    """Die-VSS bounce -> LNA output through the package (ground / supply bond current couples magnetically into the RX wires),
    referred to the differential source EMF: two AC runs (EMF, then a current injected into die VSS).  50 ohm per leg at the
    board ends of the RX wires, pad 0.5 pF per leg, controls and bias referenced to die VSS, 50 ohm mixer model."""
    c, t_, vdd = corner; w = OUT / 'pkg'; w.mkdir(parents=True, exist_ok=True)
    nl = tb.netlist(w, 'lna', view)
    (w / 'lna-bond-model.spice').write_text(LM.PKG_MODEL.read_text())
    ctl = '\n'.join(f'V{n} {n} vss {vdd if n == "en" else 0}' for n in ('en', 'gain_lo', 'byp', 'island_off', 'se', 'rt', 'lobias', 'ct1', 'ct2', 'att0', 'att1', 'att2', 'att3', 'att4'))
    body = f""".include {nl}
.include lna-bond-model.spice
Xpkg bp bn rf_in_p rf_in_n vss vdq rfrx_bond_{model}
VDDX VDD vdq {vdd}
{'Cdie VDD vdm 5.4n' + chr(10) + 'Rdie vdm vss 0.1' if decap else ''}
Vibs vib vss 3.3
Ib vib ibias 10u
{ctl}
Vct0 ct0 vss {vdd}
Vct3 ct3 vss {vdd}
Vs s 0 DC 0 AC 1
Ep e_p 0 s 0 0.5
En e_n 0 s 0 -0.5
Rsp e_p bp 50
Rsn e_n bn 50
Cpp rf_in_p vss 0.5p
Cpn rf_in_n vss 0.5p
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Vm vm vss 1.65
Ibn 0 vss DC 0 AC 0
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD vss ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias scm_b vtk_b pt_lna
{tb.src_net(view, gnd='vss')}
.control
op
ac lin 1 {f} {f}
let gs=abs(v(rf_out_p)-v(rf_out_n))
print gs
alter Vs acmag=0
alter Ibn acmag=1
ac lin 1 {f} {f}
let gb=abs(v(rf_out_p)-v(rf_out_n))
let vb=abs(v(vss))
print gb vb
.endc
"""
    log, m = tb.run(w, f'bounce_{model}_{tb._tag(corner)}_{int(decap)}.cir', body, corner)
    import math
    r = m['gb'] / m['vb'] / m['gs']
    return dict(model=model, corner=corner, die_decap=decap, f_hz=f, gain_emf_to_out=m['gs'], out_per_volt_of_vss_bounce=m['gb'] / m['vb'],
                bounce_to_input_referred_db=20 * math.log10(r))


def pkg():
    """Coordinator request 2026-11-18: the LNA with the pads owner's coupled package model, both site options, three bounds."""
    def st(model, kw, lf):
        k = dict(kw, **(dict(f1=5e6, f2=1e9, ppd=400) if lf else {}))
        try:
            r = LM.stability(OUT / 'pkg', 'extpr', FF, deg='lowr', pkg=model, **k)
        except Exception as e:
            r = dict(error=repr(e))
        return dict(model=model, case=kw, sweep='5 MHz-1 GHz, 400/decade' if lf else '0.1-30 GHz, 40/decade', **r)
    jobs = [(m, kw, lf) for m in PKG_MODELS for kw, lf in ((dict(), False), (dict(cdie=3e-9, rdie=0.03, rsw=0.2), True), (dict(cdie=3e-9, rdie=0.03, rsw=0.2), False),
                                                           (dict(cdie=5.4e-9, rdie=0.1, rsw=0.3), True))]
    rows = par([(lambda j=j: st(*j)) for j in jobs])
    bn = [bounce(m, c, decap=d) for m in PKG_MODELS for c, d in ((NOM, True), (NOM, False))]
    save('pkg', dict(stability=rows, bounce=bn))


CHAIN_POINTS = [('extpr', NOM, 'ext_best_1v16'), ('extpr', SS, 'cml_1v05'), ('extpp', SS, 'floor_0v90')]   # LO as delivered: tb.LO_REAL (MW-20)


def chain_point(view, c, lo, d_mm=2.0):
    """One deterministic chain-NF point (tb.chain_det, ~30 min transient): real channel, per-chip carrier parts, real LO level."""
    ct = TANK_CT.get((view, c[0]), 9); w = OUT / 'chain' / f'{view}_{tb._tag(c)}_{lo}'
    u = tb.lna_ac(w, view, c, f=2.44e9, ct=ct); z = complex(u['zin_re_ohm'], u['zin_im_ohm'])
    m, _, _ = LM.channel_fit(z, d_mm=d_mm); m['ct'] = ct
    r = tb.chain_det(w, view, c, ct=ct, match=m, lo=tb.LO_REAL[lo] if lo != 'ideal' else None)
    return dict(view=view, corner=c, lo=lo, lo_level=tb.LO_REAL.get(lo), carrier_distance_mm=d_mm, ct=ct, carrier_parts=m['parts'],
                nf_dsb_db=r.get('nf_dsb_db'), nf_ssb_db=r.get('nf_ssb_db'), gain_sig_db=r.get('gain_sig_db'), f_parts=r.get('f_parts'))


def chain():
    save('chain', par([(lambda j=j: chain_point(*j)) for j in CHAIN_POINTS]))


def neg():
    """Negative controls: (1) common-mode bench on the LNA with the tail AC-shorted to VSS, the tank feed shorted to VDD and the
    CM network open (= the original failure mechanism) must FAIL; (2) the bench self-tests (hand-calculable + broken cases)."""
    src = tb.netlist(OUT / 'neg', 'lna', 'extpr')
    t = (OUT / 'neg' / src).read_text()
    i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
    t = t[:e] + 'Cnegt tail VSS 1u\nRnegf vtk VDD 1m\nRnegc ncm VSS 1e-3\n' + t[e:]      # ncm shorted: the CM network loses its resistor
    p = OUT / 'neg' / 'lna_neg.spice'; p.write_text(t)
    tb.SELFTEST_NETLIST['lna'] = p
    tb.LNA_DEG_VIEW['selftest'] = 'nom'
    r = LM.stability(OUT / 'neg', 'selftest', FF, deg='lowr')
    import bench_selftest
    st = bench_selftest.run(OUT / 'selftest')
    save('neg', dict(cm_bench_on_broken_lna=r, cm_bench_fails_as_required=bool((r.get('min_re_zcm_real_mixer_ohm') or 0) < 0),
                     bench_selftest=st))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None


def write():
    ld = lambda n: json.loads((OUT / f'{n}.json').read_text()) if (OUT / f'{n}.json').exists() else None
    cur, st, bd, ng, ch, rb, lf = ld('currents'), ld('stab'), ld('band'), ld('neg'), ld('chain'), ld('readback_lvs'), ld('stab_lf')
    lay = json.loads((GEN / 'lna-layout.json').read_text())
    rec = dict(block='lna', top_cell='pt_lna', state='candidate', limits=LIM,
               hashes={f: sha(p) for f, p in (('lna.spice', flow.HERE / 'lna.spice'), ('lna.gds', GEN / 'lna.gds'), ('lna.ext.spice', GEN / 'lna.ext.spice'),
                                              ('netlists.py', flow.HERE / 'netlists.py'), ('lna_ind.gds', GEN / 'lna_ind.gds'), ('lna_deg.gds', GEN / 'lna_deg.gds'))},
               layout=dict(area_um2=lay.get('area_um2'), bbox_um=lay.get('bbox_um'), magic_drc=lay.get('drc_count'), klayout_drc=(lay.get('klayout_drc') or {}).get('violations'),
                           lvs=(lay.get('lvs') or {}).get('final_result'), readback_lvs=rb),
               extraction='capacitance only (Magic ext2spice cthresh 0); wire and via resistance NOT extracted')
    tests = {}
    if cur:
        rx = [r['idd_ma'] for r in cur['rows'] if not r['lobias']]; lo = [r['idd_ma'] for r in cur['rows'] if r['lobias']]
        tests['supply_current'] = dict(target=f"RX <= {LIM['idd_rx_ma']} mA, lobias <= {LIM['idd_lo_ma']} mA at all 20 corners", rx_ma=[min(rx), max(rx)], lobias_ma=[min(lo), max(lo)],
                                       off_a=cur['off_a'], rows=cur['rows'], **{'pass': all(r['pass'] for r in cur['rows'])})
    if st:
        g = lambda k, rows: min((r.get(k) if r.get(k) is not None else -99) for r in rows)
        act = [r for r in st if 'passive' not in r['group']]
        s3 = [r for r in act if r['group'].startswith('S3')]; phys = [r for r in act if not r['group'].startswith('S3')]
        tests['stability'] = dict(
            target='every row: mu > 1, K > 1, min Re(Zin) >= 1.0 ohm (differential) and min Re(Zcm) >= 1.0 ohm (common mode), 0.1-30 GHz, real extracted mixers',
            rows=len(act), min_mu=g('min_mu', act), min_k=g('min_k', act), min_re_diff_ohm=g('min_re_zin_real_mixer_ohm', act),
            min_re_cm_ohm_physical_supply=g('min_re_zcm_real_mixer_ohm', phys), min_re_cm_ohm_undamped_island_decap=g('min_re_zcm_real_mixer_ohm', s3) if s3 else None,
            passive_reference=[r for r in st if 'passive' in r['group']],
            pass_differential=all(r['pass_differential'] for r in act), pass_common_mode=all(r['pass_common_mode'] for r in act),
            failing_rows_differential=sum(not r['pass_differential'] for r in act), failing_rows_common_mode=sum(not r['pass_common_mode'] for r in act),
            detail=st, **{'pass': all(r['pass_differential'] and r['pass_common_mode'] for r in act)})
    if st and (OUT / 'stab').exists():
        # information: minima below 8 GHz (where the stage has gain) from the saved curves; S3 = files with island decap and no die decap
        def lowmin(kind, pred):
            vals = []
            for f in (OUT / 'stab').glob(f'*_{kind}?_zr.txt'):
                if pred(f.name):
                    d = np.array(S.read_table(f)); vals.append(float(d[d[:, 0] <= 8e9, 1].min()))
            return min(vals) if vals else None
        s3 = lambda n: '_cd' in n and '_di' not in n
        act = lambda n: '_active' in n or '_bypass' in n
        tests['stability']['minima_0p1_to_8_ghz_ohm'] = dict(
            differential_active=lowmin('mx', lambda n: act(n)), common_mode_active_physical_supply=lowmin('cm', lambda n: act(n) and not s3(n)),
            common_mode_active_undamped_island_decap=lowmin('cm', lambda n: act(n) and s3(n)),
            differential_disabled=lowmin('mx', lambda n: '_off' in n), common_mode_disabled=lowmin('cm', lambda n: '_off' in n),
            note='information only: the pass fields use the 0.1-30 GHz minimum; above ~9 GHz the enabled and the disabled LNA read the same (passive network)')
    if lf:
        v = [r.get('min_re_zcm_real_mixer_ohm') for r in lf if r.get('min_re_zcm_real_mixer_ohm') is not None]
        tests['stability_5mhz_to_1ghz_real_pdn'] = dict(
            target='min Re(Zcm) >= 1.0 ohm and min Re(Zin) >= 1.0 ohm from 5 MHz (supply anti-resonance), real-PDN cases, RX and duplex bias',
            min_re_cm_ohm=min(v) if v else None, failing_rows=sum(not (r['pass_common_mode'] and r['pass_differential']) for r in lf), rows=lf,
            **{'pass': all(r['pass_common_mode'] and r['pass_differential'] for r in lf)})
    if bd:
        tests['band_on_real_channel'] = dict(
            target=f"S11 <= {LIM['s11_db']} dB over 2.395-2.4885 GHz; LNA NF incl. the real COB channel and lossy carrier parts <= {LIM['lna_nf_db']} dB (extpp: + {LIM['derate_db']} dB derate)",
            note='carrier parts fitted PER CHIP (per-board tuning); closure over part and bond tolerance with one fixed BOM is NOT shown',
            rows=bd, **{'pass': all(r['pass_s11'] and r['pass_nf'] for r in bd)})
    if ch:
        ok = lambda r: r.get('nf_dsb_db') is not None and r['nf_dsb_db'] <= LIM['chain_nf_dsb_db']
        tests['chain_nf'] = dict(target=f"on-chip chain NF <= {LIM['chain_nf_dsb_db']} dB DSB on the real channel, at tt, ss and the pessimistic end, with the LO as delivered",
                                 rows=ch, **{'pass': bool(ch) and all(ok(r) for r in ch)})
    pk, pc = ld('pkg'), ld('pad_c_tolerance')
    if pk:
        srows = [r for r in pk['stability'] if 'error' not in r]
        okd = all(r['min_mu'] > 1 and r['min_k'] > 1 and r['min_re_zin_real_mixer_ohm'] >= LIM['re_diff_ohm'] for r in srows)
        okc = all(r['min_re_zcm_real_mixer_ohm'] >= LIM['re_cm_ohm'] for r in srows)
        tests['package_model'] = dict(
            target='pads owner coupled bond model (lna-bond-model.spice), site options A / B x min / nom / max, ff 32 C 3.35 V: same stability limits; bounce figures are information',
            min_k=min(r['min_k'] for r in srows), min_re_diff_ohm=min(r['min_re_zin_real_mixer_ohm'] for r in srows),
            min_re_cm_ohm_0p1_30ghz=min(r['min_re_zcm_real_mixer_ohm'] for r in srows if r['sweep'].startswith('0.1')),
            min_re_cm_ohm_5mhz_1ghz=min(r['min_re_zcm_real_mixer_ohm'] for r in srows if r['sweep'].startswith('5 MHz')),
            pass_differential=okd, pass_common_mode=okc, errors=len(pk['stability']) - len(srows), stability_rows=pk['stability'],
            die_vss_bounce_to_differential_input_db=pk['bounce'], pad_capacitance_tolerance=pc, **{'pass': bool(okd and okc and len(srows) == len(pk['stability']))})
    if ng:
        tests['negative_controls'] = dict(ng, **{'pass': bool(ng['cm_bench_fails_as_required'] and (ng['bench_selftest'] or {}).get('all_ok'))})
    rec['tests'] = tests
    rec['all_pass'] = bool(tests) and all(t.get('pass') for t in tests.values())
    rec['not_covered'] = ['wire / via resistance (C-only extraction)', 'Monte Carlo / mismatch', 'IIP3 / IIP2', 'one fixed carrier BOM over tolerance',
                          'fallback external LNA through the bypass path', 'fill over the spirals, EM model of the spirals (analytic model only)']
    (GEN / 'lna-evidence.json').write_text(json.dumps(rec, indent=1, default=str))
    print('all_pass', rec['all_pass'], {k: v.get('pass') for k, v in tests.items()})


if __name__ == '__main__':
    {'currents': currents, 'stab': stab, 'stab_extra': stab_extra, 'stab_lf': stab_lf, 'band': band, 'chain': chain, 'pkg': pkg, 'neg': neg, 'write': write}[sys.argv[1]]()
