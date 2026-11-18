"""Session Q helpers: schematic LNA variants (netlists.py parameter overrides + text patch) dressed like a bench view
(pad_rf_pair delta, explicit Rg, optional +25 % device C, tank spiral variant), exposed as tb view 'selftest'."""
import sys, re
RX = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx'
sys.path.insert(0, RX)
import netlists as N, tb, simlib as S, rfrx_flow as flow, lna_match as LM, lna_spiral as LS
from pathlib import Path
Q = Path('/home/ubuntu/svalbard/scratch/rf-lna-q')
VIEW = {'extpr': (150., 'nom', False, 0.), 'extpp': (200., 'pess', True, tb.PAD_PESS_EXTRA_F), 'extlo': (60., 'lhi', False, tb.PAD_LO_EXTRA_F)}
TT = ('typical', 27, 3.3); FF = ('ff', 32, 3.35); SS = ('ss', 32, 3.15)

def variant(tag, mods=None, patch=None, like='extpr', ind=None, base=None):
    """base: path of an existing netlist (e.g. the extracted one) instead of a fresh netlists.lna()."""
    W = Q / 'w' / tag; W.mkdir(parents=True, exist_ok=True)
    mods = mods or {}
    if base is None:
        old = {k: getattr(N, k) for k in mods}
        for k, v in mods.items(): setattr(N, k, v)
        try: subs = N.lna()
        finally:
            for k, v in old.items(): setattr(N, k, v)
        p = W / 'lna_raw.spice'; N.emit(p, subs); t = p.read_text()
    else:
        t = Path(base).read_text()
    if patch: t = patch(t)
    rg, iv, cgs, dpad = VIEW[like]
    t = tb.with_rg(tb.with_pad_rf_pair(t, 'lna'), rg)
    if ind != 'none':
        t = tb.with_lna_ind(t, ind or iv)
    if cgs: t = tb.with_cgs_extra(t)
    if dpad:
        i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
        t = t[:e] + f'Cpadpp_p rf_in_p VSS {dpad:g}\nCpadpp_n rf_in_n VSS {dpad:g}\n' + t[e:]
    p = W / 'lna.spice'; p.write_text(t)
    tb.SELFTEST_NETLIST['lna'] = p
    tb.LNA_DEG_VIEW['selftest'] = tb.LNA_DEG_VIEW.get(like, 'nom')
    return W

def sub_in(t, old, new, count=None):
    n = t.count(old)
    assert n and (count is None or n == count), (old, n)
    return t.replace(old, new)

def fmt(r):
    return 'mu %.4f K %.2f Re_diff %.3f @ %.2f GHz | Re_cm %.3f @ %.2f GHz ok=%s' % (r['min_mu'], r['min_k'], r['min_re_zin_real_mixer_ohm'], r['f_min_re_zin_hz'] / 1e9, r['min_re_zcm_real_mixer_ohm'], r['f_min_re_zcm_hz'] / 1e9, LM.stability_ok(r))
