"""Ring duty / phase-spacing bench (timing r12).  Extracted pt_pll_ring (or a patched copy), open loop: HOLD high, VCTRL
forced on ATB_VCTRL through 100 ohm, REF low; ring block on its regulated supply VRING; each PHk through 30 ohm into a
lumped 117 fF (the 114-119 fF real load per phase: wired TX block, ptrim, samplers).  VCTRL is searched until f is within
0.5 % of f0; settled run (last six periods within 1 ps).
  rb.py TAG NETLIST corner temp vring band f0_MHz vc0 slope_MHz_per_V  -> res/<TAG>.json
Measured at VRING/2 on the PH pins: duty per phase, slot error (spacing of consecutive rising edges minus T/8), position
error (rising edge vs k*T/8 after PH0, mean-removed).
PASS LIMITS (declared before any run, 2026-11-19): duty 0.45..0.55 on every phase; |position error| <= 10 ps and
|slot error| <= 10 ps at every corner and at 625 and 810 MHz."""
import sys, json, re, shutil, os, subprocess
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx')
import wrx_flow as wf
H = Path(__file__).resolve().parent
RP = ('REF EN N4 N8 HOLD IBIAS PH0 PH1 PH2 PH3 PH4 PH5 PH6 PH7 LOCK FBCK REFO ATB_VCTRL N5 N10 KP0 KP1 KP2 FU0 FU1 FU2 FU3 '
      'FD0 FD1 FD2 FD3 BAND VDD VSS').split()
RPC = 'REF EN N4 N8 HOLD IBIAS PH0 PH1 PH2 PH3 PH4 PH5 PH6 PH7 LOCK FBCK REFO ATB_VCTRL BAND VDD VSS'.split()
CLOAD = float(os.environ.get('RB_CLOAD', 117))


def edges(t, v, th, rising=True):
    s = v > th; i = np.where(s[1:] != s[:-1])[0]; i = i[s[i + 1] == rising]
    return t[i] + (th - v[i]) * (t[i + 1] - t[i]) / (v[i + 1] - v[i])


def run(work, net, corner, temp, vring, band, vc, tend):
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    shutil.copy(net, work / 'ring.spice')
    core = '.subckt pt_pll_ring_core ' in Path(net).read_text()
    rp = RPC if core else RP
    m = {p: '0' for p in rp}
    m.update(EN='en', HOLD='vdd', IBIAS='ib', LOCK='lock', FBCK='fbck', REFO='refo', ATB_VCTRL='vc', BAND='vdd' if band else '0', VDD='vdd')
    for k in range(8): m[f'PH{k}'] = f'phs{k}'
    L = ['* ring r12', wf.sim_header(corner, temp), '.include ring.spice', f'VS vdd 0 {vring}', f'VC vc0 0 {vc}', 'RC vc0 vc 100',
         'IB vdd ib 10u', f'VE en 0 PWL(0 0 0.5n 0 0.6n {vring})', 'XR ' + ' '.join(m[p] for p in rp) + (' pt_pll_ring_core' if core else ' pt_pll_ring'),
         'C1 lock 0 10f', 'C2 fbck 0 10f', 'C3 refo 0 10f']
    for k in range(8): L += [f'RP{k} phs{k} ph{k} 30', f'CP{k} ph{k} 0 {CLOAD:g}f']
    saves = [f'v(ph{k})' for k in range(8)] + ['i(VS)']
    ctl = [f'tran 4p {tend:g} {tend - 40e-9:g}', 'set wr_singlescale', 'set wr_vecnames', 'option numdgt=7', f'wrdata out.txt {" ".join(saves)}']
    (work / 'tb.cir').write_text('\n'.join(L + ['.option method=gear', '.control', *ctl, '.endc', '.end', '']))
    log = wf.ngspice(work, 'tb.cir', timeout=7200)
    if not (work / 'out.txt').exists(): raise RuntimeError(log[-1500:])
    return np.genfromtxt(work / 'out.txt', names=True)


def stats(d, vring):
    t = d[d.dtype.names[0]]; th = vring / 2
    e0 = edges(t, d['vph0'], th)
    per = np.diff(e0)[-7:-1]; T = float(np.mean(per)); drift = float(np.ptp(per))
    ta = e0[-4]
    duty, r = [], []
    for k in range(8):
        v = d[f'vph{k}']; re_ = edges(t, v, th); fe = edges(t, v, th, False)
        re_ = re_[re_ >= ta - T / 2 - 1e-13]; fe = fe[fe > re_[0]]
        duty.append(float((fe[0] - re_[0]) / T)); r.append(float((re_[0] - ta) % T))
    slot = [((r[(k + 1) % 8] - r[k]) % T - T / 8) * 1e12 for k in range(8)]
    pos = np.array([((r[k] - k * T / 8 + T / 2) % T) - T / 2 for k in range(8)]); pos = (pos - pos.mean()) * 1e12
    return dict(f_mhz=1e-6 / T, T_ps=T * 1e12, drift_ps=drift * 1e12, duty=[round(x, 4) for x in duty],
                slot_ps=[round(x, 1) for x in slot], pos_ps=[round(float(x), 1) for x in pos])


def main():
    tag, net, corner, temp, vring, band, f0 = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3], int(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]), float(sys.argv[7]) * 1e6
    vc, slope = float(sys.argv[8]), float(sys.argv[9]) * 1e6
    tend = float(os.environ.get('RB_TEND', 200e-9))
    pts, best = {}, None
    for it in range(6):
        work = H / 'sim' / tag
        try:
            d = run(work, net, corner, temp, vring, band, vc, tend)
            s = stats(d, vring)
        except Exception as e:
            print(tag, 'vc', vc, 'FAILED', repr(e)[:300], flush=True); break
        f = s['f_mhz'] * 1e6; pts[vc] = f
        print(tag, f"vc {vc:.4f} f {s['f_mhz']:.1f} drift {s['drift_ps']:.2f} ps", flush=True)
        if abs(f / f0 - 1) < 0.005:
            best = s; break
        if len(pts) >= 2:
            xs = sorted(pts, key=lambda v: abs(pts[v] - f0))[:2]; slope = (pts[xs[1]] - pts[xs[0]]) / (xs[1] - xs[0])
        vc = float(min(max(vc + (f0 - f) / slope, 0.5), vring - 0.02))
    (H / 'res').mkdir(exist_ok=True)
    out = dict(tag=tag, net=str(net), corner=corner, temp=temp, vring=vring, band=band, f0_mhz=f0 / 1e6, vctrl=vc, cload_fF=CLOAD,
               ok=best is not None, pts={str(k): v for k, v in pts.items()}, **(best or {}))
    if best:
        out['pass'] = (all(0.45 <= x <= 0.55 for x in best['duty']) and max(abs(x) for x in best['pos_ps']) <= 10
                       and max(abs(x) for x in best['slot_ps']) <= 10 and best['drift_ps'] < 1.0)
    (H / 'res' / f'{tag}.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out.get(k) for k in ('tag', 'ok', 'pass', 'f_mhz', 'duty', 'slot_ps', 'pos_ps')}), flush=True)
    shutil.rmtree(H / 'sim' / tag, ignore_errors=True)


if __name__ == '__main__':
    main()
