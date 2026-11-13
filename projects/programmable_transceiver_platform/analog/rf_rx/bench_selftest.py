"""Fork P: hand-calculable self-tests of the LNA benches (coordinator rule: prove benches small first).

Each case swaps pt_lna for a hand-built netlist with a known answer (tb view 'selftest'), runs the real bench
function and compares with the analytic value; each 'broken' case must FAIL its check.
  T1 NF (tb.lna_ac / tb.lna_band noise):  matched 100 ohm termination + noiseless buffer -> NF = 3.01 dB.
  T2 NF of a matched resistive 6.02 dB pi pad (300/75/300 ohm diff) + matched 100 ohm termination + noiseless
     buffer: Friis F = L + (2-1)*L = 2L -> 9.03 dB.
  T3 S11 (tb.lna_band with a board ladder vs lna_match.s11_db analytic) on a series R-C 'LNA' (R 4 ohm diff,
     C 1 pF diff): every band point within 0.05 dB.
  T4 harmonic-folding input (tb.lna_ac at 3 fLO): buffer with a known 200 ohm noise resistor in series with one output leg
     -> LNA-only output noise extracted by the chain_det formula equals 4kT*200 within 1 %.
  B1 broken: T1 with an extra noiseless-claimed 50 ohm series resistor per leg (really noisy) -> must not read 3.01.
  T3b same with the lossy trimmer ladder (part Q, trimmer ESL / terminal C).
  B2 broken: T3 compared with the wrong bond (lb 1.0 vs 1.5 nH) -> must exceed the 0.05 dB tolerance.
  T6 noiseless LNA reads NF 0 dB with the noiseless-load method chain_det uses; B4: the old noisy-load method
     must read > 0 (it double-counted the mixer-model noise).
  T5 stability screen (lna_match.rein_sweep): series R-C with R = 4 ohm diff behind the 0.25 pF diff pad
     allowance -> min Re(Zin) = analytic R*(C/(C+Cp))^2 = 2.56 ohm; B3 broken: R = -10 ohm -> must report negative.
"""
import json, math
from pathlib import Path
import tb, lna_match as LM, rfrx_flow as flow
NOM = ('typical', 27, 3.3)
PORTS = 'rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD VSS ct3 att0 att1 att2 att3 att4 src_p src_n tank_p tank_n'
KT = 4 * 1.380649e-23 * 300.15


def _sub(body):
    return f'.subckt pt_lna {PORTS}\n{body}\n.ends\n'


def _buf(src_p='rf_in_p', src_n='rf_in_n', gain=1.0):
    # noiseless differential buffer driving the 50 ohm/leg mixer model (outputs referenced to VCM 1.65 V via the bench)
    return (f'Eop rf_out_p mid VCVS {src_p} {src_n} {gain / 2}\nEon mid rf_out_n VCVS {src_p} {src_n} {gain / 2}\n'
            'Emid mid 0 VCVS VDD 0 0.5\nRq1 rf_outq_p rf_outq_n 1e9\n').replace('VCVS ', '')


def _case(work, name, body):
    p = Path(work) / f'{name}.spice'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_sub(body))
    tb.SELFTEST_NETLIST['lna'] = p
    return Path(work) / name


def run(work):
    work = Path(work); out = {}
    # T1 / B1
    w = _case(work, 't1', 'Rt rf_in_p rf_in_n 100\n' + _buf())
    r = tb.lna_ac(w, 'selftest', NOM)
    out['T1_nf_matched_termination'] = dict(expected_db=3.01, got_db=r['nf_db'], ok=abs(r['nf_db'] - 3.01) < 0.05)
    w = _case(work, 'b1', 'Rs1 rf_in_p a 50\nRs2 rf_in_n b 50\nRt a b 100\n' + _buf('a', 'b'))
    r = tb.lna_ac(w, 'selftest', NOM)
    out['B1_broken_series_resistors'] = dict(expected_db=3.01, got_db=r['nf_db'], must_fail=True,
                                             check_fails=not abs(r['nf_db'] - 3.01) < 0.05)
    # T2: 100 ohm differential matched 6.02 dB pi pad (R shunt 300.3 ohm diff each side, series 74.9 ohm diff)
    w = _case(work, 't2', 'Rsh1 rf_in_p rf_in_n 300\nRse1 rf_in_p a 37.5\nRse2 rf_in_n b 37.5\nRsh2 a b 300\nRt a b 100\n' + _buf('a', 'b'))
    r = tb.lna_ac(w, 'selftest', NOM, f=1e7)   # 10 MHz: the bench's 0.5 pF/leg pad allowance is negligible (it detunes a resistive pad at 2.4 GHz)
    out['T2_nf_6dB_pad_plus_termination'] = dict(expected_db=9.03, got_db=r['nf_db'], ok=abs(r['nf_db'] - 9.03) < 0.1)
    # T3 / B2: series R-C load, ladder network
    net = {'order': 'ladder', 'net': [['sL', 3.0e-9], ['pC', 4.0e-12], ['sL', 2.0e-9], ['pC', 2.0e-12]], 'lb': 1.5e-9, 'ct': 7}
    w = _case(work, 't3', 'Rl rf_in_p x 4\nCl x rf_in_n 1p\n' + _buf())
    rb = tb.lna_band(w, 'selftest', NOM, net)
    import numpy as np
    fz = 2.390e9 + 0.5e6 * np.arange(208)          # the REQUESTED grid (review lna2: not the returned one)
    assert len(rb['rows']) == len(fz)
    pad = 1 / (1 / (4 + 1 / (1j * 2 * np.pi * fz * 1e-12)) + 1j * 2 * np.pi * fz * 0.25e-12)   # 0.5 pF/leg bench pad = 0.25 pF diff
    ana = LM.s11_db([(t, v) for t, v in net['net']], fz, pad)
    err = [abs(a - x['s11_db']) for a, x in zip(ana, rb['rows'])]
    out['T3_s11_ladder_vs_analytic'] = dict(max_err_db=float(max(err)), ok=bool(max(err) < 0.05))
    ana_b = LM.s11_db([(t, v - 0.5e-9 if i == 0 else v) for i, (t, v) in enumerate(net['net'])], fz, pad)
    err_b = [abs(a - x['s11_db']) for a, x in zip(ana_b, rb['rows'])]
    # T3b: lossy trimmer ladder (tb._ladder_net lossy) vs lna_match._apply_lossy
    netl = {'order': 'ladder', 'lossy': True, 'lb': 1.5e-9,
            'net': [['sL', 2.2e-9], ['pT', 3.0e-12], ['sL', 2.0e-9], ['pT', 1.5e-12], ['sL', 1.8e-9], ['pT', 1.2e-12]]}
    rl = tb.lna_band(w, 'selftest', NOM, netl)
    anal = LM._s11(LM._apply_lossy(pad, fz, [(t, v) for t, v in netl['net']], 1.5e-9))
    errl = [abs(a - x['s11_db']) for a, x in zip(anal, rl['rows'])]
    out['T3b_s11_lossy_trimmer_ladder_vs_analytic'] = dict(max_err_db=float(max(errl)), ok=bool(max(errl) < 0.05))
    out['B2_broken_bond_value'] = dict(max_err_db=float(max(err_b)), must_fail=True, check_fails=bool(not max(err_b) < 0.05))
    # T4: LNA-only output noise extraction at 3 fLO (formula used by tb.chain_det)
    w = _case(work, 't4', 'Rt rf_in_p rf_in_n 1e6\nEop a mid rf_in_p rf_in_n 0.5\nRn a rf_out_p 200\nEon mid rf_out_n rf_in_p rf_in_n 0.5\n'
                         'Emid mid 0 VDD 0 0.5\nRq1 rf_outq_p rf_outq_n 1e9\n')
    f3 = 7.2e9
    kt = 4 * 1.380649e-23 * 300.15 * 100
    k1 = 4 * 1.380649e-23 * 300.15
    # rf_out_n is an ideal source; Rn (200) in series with the p leg into the 50 ohm leg: divider 50/250.
    # noiseless load (as tb.chain_det uses it): only Rn -> 4kT*200*(50/250)^2.  Bench (noisy) load: Rmp adds 4kT*50*(200/250)^2.
    for lbl, nl_, expv in (('T4_lna_only_output_noise_noiseless_load', True, k1 * 200 * 0.04),
                           ('T4b_output_noise_with_bench_load', False, k1 * (200 * 0.04 + 50 * 0.64))):
        r = tb.lna_ac(w, 'selftest', NOM, f=f3, noiseless_load=nl_)
        n_out = (10 ** (r['nf_db'] / 10) - 1) * 10 ** (r['gain_db'] / 10) * kt
        out[lbl] = dict(expected_v2_hz=expv, got_v2_hz=n_out, ok=abs(n_out / expv - 1) < 0.02)
    # T5 / B3: stability screen (lna_match.rein_sweep) on a series R-C (R 4 ohm diff) and on a -10 ohm one
    w = _case(work, 't5', 'Rl rf_in_p x 4\nCl x rf_in_n 1p\n' + _buf())
    r = LM.rein_sweep(w, 'selftest', NOM, 7)
    fz = np.logspace(8, math.log10(12e9), 400)
    exp5 = float(np.min(np.real(1 / (1 / (4 + 1 / (1j * 2 * np.pi * fz * 1e-12)) + 1j * 2 * np.pi * fz * 0.25e-12))))
    out['T5_rein_series_rc'] = dict(expected_ohm=exp5, got_ohm=r['min_re_zin_ohm'], ok=r['min_re_zin_ohm'] is not None and abs(r['min_re_zin_ohm'] - exp5) < 0.05)
    w = _case(work, 'b3', 'Rl rf_in_p x -10\nCl x rf_in_n 1p\n' + _buf())
    r = LM.rein_sweep(w, 'selftest', NOM, 7)
    out['B3_broken_negative_resistance'] = dict(got_ohm=r['min_re_zin_ohm'], must_fail=True, check_fails=not (r['min_re_zin_ohm'] or 0) > 0)
    # T6 / B4: chain_det LNA term (review: the 50 ohm/leg mixer MODEL's noise must not be counted as LNA noise).
    # A noiseless LNA (VCCS input conductance 1/100 S, VCCS gm into the outputs) must read NF 0 dB with the noiseless
    # load chain_det now uses; with the noisy bench load (the old method) it must read > 0.5 dB.
    w = _case(work, 't6', 'Gin rf_in_p rf_in_n rf_in_p rf_in_n 0.01\n'
                         'Gop rf_out_p mid rf_in_p rf_in_n -0.02\nGon rf_out_n mid rf_in_p rf_in_n 0.02\n'
                         'Emid mid 0 VDD 0 0.5\nRq1 rf_outq_p rf_outq_n 1e9\n')
    r = tb.lna_ac(w, 'selftest', NOM, noiseless_load=True)
    out['T6_chain_det_lna_term_noiseless_lna'] = dict(expected_db=0.0, got_db=r['nf_db'], ok=abs(r['nf_db']) < 0.05)
    r = tb.lna_ac(w, 'selftest', NOM)
    out['B4_broken_old_method_counts_load_noise'] = dict(got_db=r['nf_db'], must_fail=True, check_fails=not abs(r['nf_db']) < 0.05)
    out['all_ok'] = all(v.get('ok', v.get('check_fails')) for v in out.values() if isinstance(v, dict))
    return out


if __name__ == '__main__':
    r = run(flow.SCRATCH / 'char' / 'lna_selftest')
    print(json.dumps(r, indent=1, default=float))
