#!/usr/bin/env python3
"""PKG-W1 qualification bench: TX -> user AC-coupling caps at the placement point -> carrier 50 ohm line ->
TT01 COB (pkg_channel.py, per-pin WIRE_RX_P/N geometry) -> die pad C -> on-die termination -> pt_ctle -> slicer
input load.  Placements P1..P4 = 2/10/30/50 mm of carrier line (spec/package-channel.md section 6), bond
+/-0.3 mm, pad C 2.35 pF (today) / 1.6 pF (S7 target).

Metric: eye at the CTLE output (= slicer input) for PRBS7 at 2.5 Gb/s: for every sampling phase (40 per UI) the
inner eye height min(v | 1) - max(v | 0) over the window after start-up; reported: best-phase height and the
width (fraction of the UI with height >= the slicer requirement, 2 x 20 mV = 40 mV: slicer offset after trim
<= 2 mV-step residual + sensitivity/noise margin).  Also the open-loop eye without CTLE (code-independent
reference) is reported at the termination.

usage: pkg_qual.py [--net ctle.spice] [--codes 0 3 5 7] [--places P1 P4] [--cpad 2.35] [--corner ss ...]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture  # noqa: E402  (prbs, sims_pwl)
import pkg_channel as pc  # noqa: E402
import sims  # noqa: E402
import wrx_flow as f  # noqa: E402

SCRATCH = HERE.parents[3] / 'scratch' / 'wired_rx' / 'pkg_qual'
ENV = dict(tt=('typical', 27, 3.3), ss=('ss', 32, 3.15), ff=('ff', 22, 3.35))
EYE_REQ_V = 0.040
ASSESS_ONLY = False


def deck(sub, netfile, code, place, dbond=0.0, cpad=2.35, rterm=50.0, vcm=1.2, rate=2.5e9, vtx=0.4, nbits=200,
         corner='typical', temp=27, vdd=3.3, ctle_on=True, dc_cm=None, acc=False):
    """dc_cm: DC-coupled user (no board AC caps), TX common mode dc_cm, on-die 2 x rterm differential termination
    (DIFF_ENABLE bridge, no CM current).  acc: proposed on-die AC coupling between the pad and the CTLE (10 pF MIM per
    leg, 20 kohm bias to 1.0 V on the CTLE side, 0.2 pF bottom-plate parasitic on the CTLE side)."""
    ui = 1 / rate
    bits = capture.prbs(nbits + 8)
    tr = 0.3 * ui                                    # TX 20-80 ~ 0.3 UI (moderate TX edge)
    pts = [(0, -vtx)]
    for m, b in enumerate(bits):
        t = 1e-9 + m * ui
        v = vtx if b else -vtx                       # open-circuit +/-vtx -> +/-vtx/2 per leg into 50 ohm
        pts += [(t, pts[-1][1]), (t + tr, v)]
    pwl_p = capture.sims_pwl([(t, v / 2) for t, v in pts])
    pwl_n = capture.sims_pwl([(t, -v / 2) for t, v in pts])
    L = [pc.subckt('cobp', 'WIRE_RX_P', pc.PLACES[place], dbond), pc.subckt('cobn', 'WIRE_RX_N', pc.PLACES[place], dbond),
         f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VCM vcm 0 {vcm}',
         f'VTP tpi {"tcm" if dc_cm is not None else 0} {pwl_p}', f'VTN tni {"tcm" if dc_cm is not None else 0} {pwl_n}',
         'RTP tpi tp 50', 'RTN tni tn 50']
    if dc_cm is None:
        L += ['CACP tp bp 100n', 'CACN tn bn 100n', 'RBP bp 0 1G', 'RBN bn 0 1G',
              f'RTMP pdp vcm {rterm}', f'RTMN pdn vcm {rterm}']
    else:
        L += [f'VTCM tcm 0 {dc_cm}', 'RJP tp bp 0.001', 'RJN tn bn 0.001', f'RTMD pdp pdn {2 * rterm}']
    L += ['XCP pdp bp cobp', 'XCN pdn bn cobn', f'CPP pdp 0 {cpad}p', f'CPN pdn 0 {cpad}p']
    if acc:
        L += ['VACB accb 0 1.0', 'CCP pdp rxp 10p', 'CCN pdn rxn 10p', 'RAP rxp accb 20k', 'RAN rxn accb 20k',
              'CBP rxp 0 0.2p', 'CBN rxn 0 0.2p']
    else:
        L += ['RSHP pdp rxp 0.001', 'RSHN pdn rxn 0.001']
    L += [
         f'VEN en 0 {vdd if ctle_on else 0}', 'VBY byp 0 0',
         f'VP0 p0 0 {(code & 1) * vdd}', f'VP1 p1 0 {((code >> 1) & 1) * vdd}', f'VP2 p2 0 {((code >> 2) & 1) * vdd}',
         'CLP outp 0 150f', 'CLN outn 0 150f']
    m = dict(VDD_WIRE_SW='vdd', VSS='0', IBIAS='ib', ctle_en='en', wire_ctle_bypass='byp', ctle_peak0='p0',
             ctle_peak1='p1', ctle_peak2='p2', RX_P='rxp', RX_N='rxn', CTLE_P='outp', CTLE_N='outn',
             atb_ctle_pbias='pb', atb_ctle_src='src', lf_zero0='0', lf_zero1='0', lf_zero2='0')   # r3: LF zero bank off
    m = {k: v for k, v in m.items() if k in sub.ports}
    L.append(sims.inst(sub, m))
    t_end = 1e-9 + nbits * ui
    ctl = '\n'.join([f'tran 2p {t_end:.4g} 0 5p', 'set wr_singlescale', 'wrdata tran.txt v(outp) v(outn) v(rxp) v(rxn)'])
    # (with acc the DC operating point has the coupling caps open: pad side at the TX CM, CTLE side at 1.0 V)
    text = '\n'.join([f'* pkg_qual {place} code {code}', sims.sim_header(corner, temp), f'.include {netfile}',
                      '\n'.join(L), '.control', ctl, '.endc', '.end', ''])
    return text, bits, ui


def eye(t, v, bits, ui, t_skip=12):
    """inner eye of v(t) for the bit stream: heights min(v | 1) - max(v | 0) on a continuous delay grid (0..12 UI in
    1/40 UI steps, i.e. any latency); eye_mV = the best height, width_ui = the longest contiguous delay range whose
    height is >= EYE_REQ_V (so an eye that straddles a UI boundary is not cut)"""
    grid = np.arange(0, 12, 1 / 40)
    heights = []
    for s in grid:
        ones, zeros = [], []
        for m in range(t_skip, len(bits) - 14):
            ts = 1e-9 + (m + s) * ui
            if ts > t[-1]:
                break
            x = float(np.interp(ts, t, v))
            (ones if bits[m] else zeros).append(x)
        heights.append(min(ones) - max(zeros) if ones and zeros else -9)
    h = np.array(heights)
    best, run_, k_best = 0, 0, int(np.argmax(h))
    for ok in h >= EYE_REQ_V:
        run_ = run_ + 1 if ok else 0
        best = max(best, run_)
    return dict(eye_mV=round(1e3 * float(h.max()), 1), width_ui=round(best / 40, 3), delay_ui=round(float(grid[k_best]), 3))


def run(sub, netfile, tag, **kw):
    work = SCRATCH / tag
    work.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(netfile, work / 'dut.spice')
    text, bits, ui = deck(sub, 'dut.spice', **kw)
    (work / 'tb.cir').write_text(text)
    log = (work / 'tb.cir.log').read_text() if ASSESS_ONLY else f.ngspice(work, 'tb.cir', timeout=3600)
    try:
        d = np.loadtxt(work / 'tran.txt')
        t = d[:, 0]
        # wr_singlescale: time, v(outp), v(outn), v(rxp), v(rxn)
        r = dict(ctle=eye(t, d[:, 1] - d[:, 2], bits, ui), pad=eye(t, d[:, 3] - d[:, 4], bits, ui),
                 ctle_out_cm_v=round(float(np.mean(d[:, 1] + d[:, 2]) / 2), 3), ctle_in_cm_v=round(float(np.mean(d[:, 3] + d[:, 4]) / 2), 3))
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-400:])
    r.update(tag=tag, **{k: v for k, v in kw.items()})
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    print(tag, r.get('ctle'), 'pad', r.get('pad'), r.get('error', ''), flush=True)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--net', default=str(HERE / 'ctle.spice'))
    ap.add_argument('--codes', type=int, nargs='*', default=[0, 2, 4, 6, 7])
    ap.add_argument('--places', nargs='*', default=['P1', 'P2', 'P3', 'P4'])
    ap.add_argument('--bonds', type=float, nargs='*', default=[0.0])
    ap.add_argument('--cpad', type=float, nargs='*', default=[2.35])
    ap.add_argument('--rterm', type=float, nargs='*', default=[50.0])
    ap.add_argument('--env', nargs='*', default=['tt'])
    ap.add_argument('--vtx', type=float, default=0.4)
    ap.add_argument('--out', default='results.json')
    ap.add_argument('--dc-cm', type=float, nargs='*', default=[None])
    ap.add_argument('--acc', action='store_true')
    ap.add_argument('--assess-only', action='store_true', help='re-judge stored runs (no simulation)')
    a = ap.parse_args()
    global ASSESS_ONLY
    ASSESS_ONLY = a.assess_only
    sub = f.parse_spice(Path(a.net))
    sub = sub.get('pt_ctle') if isinstance(sub, dict) else sub
    tagn = 'ext' if 'ext' in Path(a.net).name else 'sch'
    store = SCRATCH / a.out
    SCRATCH.mkdir(parents=True, exist_ok=True)
    res = json.loads(store.read_text()) if store.exists() else {}
    for env in a.env:
        corner, temp, vdd = ENV[env]
        for cp in a.cpad:
            for rt in a.rterm:
                for pl in a.places:
                    for db in a.bonds:
                        for code in a.codes:
                            for dcm in a.dc_cm:
                                tag = f'{tagn}_{env}_{pl}_b{db:+.1f}_c{cp}_r{rt:g}_code{code}_v{a.vtx:g}' + \
                                    ('' if dcm is None else f'_dc{dcm:g}') + ('_acc' if a.acc else '')
                                res[tag] = run(sub, Path(a.net), tag, code=code, place=pl, dbond=db, cpad=cp, rterm=rt,
                                               corner=corner, temp=temp, vdd=vdd, vtx=a.vtx, dc_cm=dcm, acc=a.acc)
                                store.write_text(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
