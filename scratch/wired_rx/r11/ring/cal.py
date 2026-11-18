"""RX ring phase calibration for the real-chain benches (r11).
Extracted pt_pll_ring (analog/timing/generated/pll_ring.ext.spice), open loop (r10ptrim/ringbench.py set-up: HOLD high, VCTRL forced
through 100 ohm, REF low), on the regulated supply VRING, each phase through 30 ohm / 60 fF into the extracted pt_ptrim DUT (code 0,
lumped real consumer loads on CKP).  VCTRL is searched until |f/f0 - 1| < 0.5 %; the last run's steady-state period of v(ph0..7)
(at the ptrim pins) is written as one-period tables scaled in time to exactly 1/f0 -> ph_<tag>.npz (for PWL replay), and the phase
statistics -> cal.json[tag].
  cal.py TAG DUT corner temp vdd vring band f0_MHz [v1,v2]
Run through ../../slot.sh."""
import sys, json, shutil
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10ptrim')
import bench, sweep, ringbench as rb
wf = bench.wf
H = Path(__file__).resolve().parent
import os
# sensitivity: extra lumped C (fF) on single phases, e.g. R11_PHX='0:50,1:30' (clockmux.WSI + prescale_hf.CK_IN on PH0, obs_pre4 on PH1)
PHX = {int(a.split(':')[0]): float(a.split(':')[1]) for a in os.environ.get('R11_PHX', '').split(',') if a}


def deck(work, dut, corner, temp, vdd, vring, band, vc, tend):
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    (work / 'ring.spice').write_text(rb.ring_text()); shutil.copy(dut, work / 'dut.spice')
    P = bench.ports(dut, 'pt_ptrim')
    L = ['* ring -> ptrim (cal)', wf.sim_header(corner, temp), '.include ring.spice', '.include dut.spice', f'VDD vdd 0 {vdd}', 'VMP vdd vddp 0'] + rb.ring_lines(vring, vc, band)
    m = dict(VDD_WIRE_SW='vddp', VSS='0', ptrim_en='vdd')
    for k in range(8):
        L += [f'RPH{k} phs{k} ph{k} 30', f'CPH{k} ph{k} 0 {60 + PHX.get(k, 0):g}f']
        m[f'PH{k}'] = f'ph{k}'; m[f'CKP{k}'] = f'o{k}'
        for b in range(5): m[f'T{k}_{b}'] = '0'
        L += [f'RR{k} o{k} p{k} 0.01', f'CL{k} p{k} 0 {bench.PIN[k] + (bench.WCK if k == 0 else 0) + 30:g}f']
    L.append('XDUT ' + ' '.join(m[p] for p in P) + ' pt_ptrim')
    return rb.run_deck(work, L, [f'v(ph{k})' for k in range(8)] + [f'v(p{k})' for k in range(8)] + ['i(VRGS)'], tend)


def main():
    """Settled calibration (fix 2026-11-18 06:10 after the ptrim sub-agent showed the ring period still drifting in a 30 ns
    run: 2182 -> 1503 ps at 30 ns -> 1458 ps at 58 ns).  Each run is TEND long; accepted only if the last six PH0 periods agree
    within 0.5 ps; the table is ONE cycle [e0[-3], e0[-2]) on its own period.
      cal.py TAG DUT corner temp vdd vring band f0_MHz vctrl_start slope_MHz_per_V"""
    tag, dut, corner, temp, vdd, vring, band, f0 = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3], int(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), int(sys.argv[7]), float(sys.argv[8]) * 1e6
    vc = float(sys.argv[9]); slope = float(sys.argv[10]) * 1e6
    TEND = float(os.environ.get('R11_TEND', 320e-9))    # the low band settles slower (480 MHz: 1 ps over six periods at 160 ns)
    pts = {}; best = None
    for it in range(5):
        work = H / 'sim' / tag
        try:
            d = deck(work, dut, corner, temp, vdd, vring, band, vc, TEND)
        except Exception as e:
            print(tag, 'vc', vc, 'FAILED', repr(e)[:300], flush=True); break
        t = d[d.dtype.names[0]]
        e0 = rb.edges(t, d['vph0'], vring / 2)
        if len(e0) < 12: print(tag, 'vc', vc, 'no oscillation', flush=True); break
        per = np.diff(e0)[-7:-1]; T = float(per[-1]); drift = float(np.ptp(per))
        pts[vc] = 1 / T
        print(tag, f'vc {vc:.4f} f {1e-6 / T:.2f} MHz, last periods ptp {drift * 1e12:.2f} ps', flush=True)
        if abs(1 / T / f0 - 1) < 0.005:
            best = (vc, d, T, drift); break
        if len(pts) >= 2:
            xs = sorted(pts, key=lambda v: abs(pts[v] - f0))[:2]; slope = (pts[xs[1]] - pts[xs[0]]) / (xs[1] - xs[0])
        vc = float(min(max(vc + (f0 - 1 / T) / slope, 0.6), vring - 0.05))
    D = json.loads((H / 'cal.json').read_text()) if (H / 'cal.json').exists() else {}
    if best is None:
        D[tag] = dict(ok=False, corner=corner, temp=temp, vdd=vdd, vring=vring, band=band, f0=f0, pts={str(k): v for k, v in pts.items()})
        (H / 'cal.json').write_text(json.dumps(D, indent=1)); print(tag, 'NO FREQUENCY MATCH', pts); return
    vc, d, T, drift = best
    t = d[d.dtype.names[0]]
    e0 = rb.edges(t, d['vph0'], vring / 2)
    ta = e0[-3]; T = float(e0[-2] - e0[-3]); n = 400; tg = ta + np.arange(n) / n * T
    tab = {f'ph{k}': np.interp(tg, t, d[f'vph{k}']) for k in range(8)}
    tab.update({f'ckp{k}': np.interp(tg, t, d[f'vp{k}']) for k in range(8)})
    wrap = max(abs(float(np.interp(ta + T, t, d[f'vph{k}']) - tab[f'ph{k}'][0])) for k in range(8))
    np.savez_compressed(H / f'ph_{tag}.npz', n=n, T_meas=T, f0=f0, vring=vring, **tab)
    t0 = e0[-8] - 1e-12
    st, _ = rb.phase_stats(t, d, vring, t0)
    r = []
    for k in range(8):
        e = rb.edges(t, d[f'vph{k}'], vring / 2); e = e[e >= ta - 1e-13]; r.append(float((e[0] - ta) % T))
    slot = [(r[(k + 1) % 8] - r[k]) % T - T / 8 for k in range(8)]
    pos = [((r[k] - k * T / 8 + T / 2) % T) - T / 2 for k in range(8)]
    dl = []
    for k in range(8):
        ri = rb.edges(t, d[f'vph{k}'], vring / 2); ri = ri[ri > t0]; ro = rb.edges(t, d[f'vp{k}'], vdd / 2)
        dl.append(float(np.mean([ro[ro > x][0] - x for x in ri[:-2] if len(ro[ro > x])])))
    sel = t > t0
    D[tag] = dict(ok=bool(drift < 0.5e-12 and wrap < 0.05), settled_last6_period_ptp_ps=round(drift * 1e12, 3), wrap_mismatch_V=round(wrap, 4), tend_ns=TEND * 1e9,
                  dut=str(dut), dut_sha256=bench.sha(dut), ring_sha256=bench.sha(rb.RING), corner=corner, temp=temp, vdd=vdd, vring=vring, band=band, f0=f0, vctrl=vc,
                  f_meas=1 / T, pts={str(k): v for k, v in pts.items()}, ring_out=st, slot_err_ps=[round(x * 1e12, 1) for x in slot],
                  pos_err_ps=[round(x * 1e12, 1) for x in pos], ckp_delay_code0_ps=[round(x * 1e12, 1) for x in dl],
                  phx_fF={str(k): v for k, v in PHX.items()}, i_ring_mA=round(abs(float(np.mean(d[d.dtype.names[-1]][sel]))) * 1e3, 3))
    (H / 'cal.json').write_text(json.dumps(D, indent=1))
    print(tag, 'OK' if D[tag]['ok'] else 'NOT SETTLED', 'vc', round(vc, 4), 'f', round(1e-6 / T, 2), 'drift ps', D[tag]['settled_last6_period_ptp_ps'], 'wrap V', D[tag]['wrap_mismatch_V'],
          'slot_err_ps', D[tag]['slot_err_ps'], 'pos_err_ps', D[tag]['pos_err_ps'], 'duty', [p['duty'] for p in st['ph']], flush=True)
    for f in (H / 'sim' / tag).glob('out.txt'): f.unlink()


if __name__ == '__main__':
    main()
