"""SP-03: dynamic 80 MS/s test of the radio DAC (dac_i / dac_q), separate from benches.py.

What the existing benches do NOT test: benches.dac_deck holds every code for TWO clock periods, so
'rate80M' (period 12.5 ns) is a 40 MS/s static-code test and 'nominal'/'sine' (period 25 ns) are 20 MS/s.
This bench updates the code on EVERY clock edge at 80 MHz:
  * coherent sine: N samples, `cycles` signal cycles (coprime with N), amplitude `dbfs` below full scale,
    two's-complement codes into CODE0..9 (the dac_logic convention used by benches.dac_deck);
  * the differential output v(OUTP)-v(OUTN) is resampled on a uniform grid of `os` points per update period
    over the N periods after the pipeline latency, and FFT'd (rectangular window, coherent):
      - SFDR / SNDR / THD in the first Nyquist zone (0-40 MHz) of the CONTINUOUS waveform (includes glitches,
        settling, ZOH droop is a known deterministic sinc and is reported, not removed);
      - same metrics on the per-period mid-point samples (the DAC's static/linearity contribution);
      - in-band (0-10 MHz, HE20 half-bandwidth 9.7 MHz) SNDR;
  * glitch / settling: a major-carry step (code -1 -> 0, offset-binary 511 -> 512) and a full-scale step,
    each held 4 periods: glitch impulse area (V*s) of v(t) - v_final over the transition period, peak
    excursion beyond the final value, and settling time to +/-0.5 LSB.
Load: 100 fF per leg (same as benches.dac_deck), ideal 10 uA IBIAS, low-swing 80 MHz DAC_CLOCK.
Usage: python3 dac_dynamic.py [--view sch|ext] [--corners tt,ss,ff] [--block dac_i]
Results: generated/<block>-dynamic.json (only with --publish), scratch/converters/<block>_dyn/."""
import argparse, json, math, re, shutil
import concurrent.futures as cf
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import benches as B   # noqa: E402
import convkit as ck  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
P = 12.5e-9                 # 80 MS/s update
T0 = B.DAC_T0               # EN settle (benches.dac_deck; 600 ns since the v4 bias decap)
LAT = 2                     # registered update: output follows the code after the 2nd rising edge
CORNERS = {'tt': ('typical', 27, 3.3), 'ss': ('ss', 32, 3.15), 'ff': ('ff', 22, 3.35)}


def sine_codes(n, cycles, dbfs):
    a = 511.0 * 10 ** (dbfs / 20)
    return [int(round(a * math.sin(2 * math.pi * cycles * k / n + 0.1))) for k in range(n)]


def deck(net, corner, temp, vdd, top, codes, tstep=20e-12):
    """One new code per period; code k is applied at T0 + k*P + P/2 (mid-period, between rising edges)."""
    n = len(codes)
    def bitpwl(bit):
        pts = [(0, 0.0)]
        for i, cd in enumerate(codes):
            v = 3.3 if ((cd & 0x3ff) >> bit) & 1 else 0.0
            ts = T0 + i * P + P / 2
            if v != pts[-1][1]:
                pts += [(ts, pts[-1][1]), (ts + 0.2e-9, v)]
        return B.pwl(pts)
    tstop = T0 + (n + LAT + 2) * P
    t = B.header(net, corner, temp, vdd)
    t += 'VDD VDD 0 {vdd}\nIB VDD IBIAS 10u\nD1 IBIAS VDD dclamp\n'
    ctext, cpins = B.dac_clock(P)
    t += ctext
    t += 'VEN EN 0 PWL(0 0 30n 0 30.2n {vdd})\nVHZ HOLD_ZERO 0 0\n'
    for b in range(10):
        t += f'VC{b} CODE{b} 0 {bitpwl(b)}\n'
    t += 'CLP OUTP 0 100f\nCLN OUTN 0 100f\n'
    t += f'X1 VDD 0 OUTP OUTN IBIAS {cpins} EN HOLD_ZERO ' + ' '.join(f'CODE{i}' for i in range(10)) + f' ATB_BIAS {top}\n'
    t += '.save v(OUTP) v(OUTN) i(VDD)\n'          # keep only what is analysed (ff ran out of vector memory)
    t += '.control\nset wr_singlescale\nset wr_vecnames\n'
    t += f'tran {tstep:.3g} {tstop:.4e} {T0 - 20e-9:.4e} {tstep:.3g}\n'
    t += f'meas tran idd avg i(VDD) from={T0:.4e} to={tstop:.4e}\n'
    t += 'wrdata dac.dat v(OUTP) v(OUTN)\n.endc\n.end\n'
    return t, tstop


def load(work):
    d = np.loadtxt(Path(work) / 'dac.dat', skiprows=1)
    return d[:, 0], d[:, 1] - d[:, 2], (d[:, 1] + d[:, 2]) / 2   # wr_singlescale: t, OUTP, OUTN


def edge_time(t, k):
    """Rising CLKP edge that registers code k into the output (k-th applied code)."""
    return T0 + (k + LAT) * P


def spectrum(x, n_per, nbin_sig, fs_grid, f_lim):
    """x: uniform samples over whole number of signal periods; returns metrics up to f_lim."""
    N = len(x)
    p = np.abs(np.fft.rfft(x - x.mean())) ** 2
    f = np.arange(len(p)) * fs_grid / N
    sig = p[nbin_sig]
    use = (f > 0) & (f <= f_lim)
    others = use.copy(); others[nbin_sig] = False
    spur_bin = int(np.argmax(np.where(others, p, 0)))
    sndr = 10 * np.log10(sig / max(p[others].sum(), 1e-30))
    # Harmonics fold about the 80 MS/s update rate (ZOH images / sampled aliases): bin of 1/P is kz.
    kz = int(round((1 / P) / (fs_grid / N)))
    harm = [min((h * nbin_sig) % kz, kz - (h * nbin_sig) % kz) for h in range(2, 8)]
    hp = [p[b] for b in harm if 0 < b < len(p) and f[b] <= f_lim and b != nbin_sig]
    thd = 10 * np.log10(max(sum(hp), 1e-30) / sig) if hp else None
    top = sorted(((float(f[b] / 1e6), round(float(10 * np.log10(p[b] / sig)), 1)) for b in np.argsort(np.where(others, p, 0))[-5:]), key=lambda z: z[1], reverse=True)
    return dict(amp_V=round(float(2 * math.sqrt(sig) / N), 4), sndr_db=round(float(sndr), 2), enob=round(float((sndr - 1.76) / 6.02), 2),
                sfdr_dbc=round(float(10 * np.log10(sig / max(p[spur_bin], 1e-30))), 2), sfdr_f_MHz=round(float(f[spur_bin] / 1e6), 3),
                thd_db=round(float(thd), 2) if thd is not None else None, top_spurs_MHz_dBc=top)


def sine_eval(work, n, cycles, osr=64):
    t, v, cm = load(work)
    ta = edge_time(t, 0)
    grid = ta + (np.arange(n * osr) + 0.5) * P / osr
    xc = np.interp(grid, t, v)
    mids = np.interp(ta + (np.arange(n) + 0.5) * P, t, v)
    fsig = cycles / (n * P)
    cont = spectrum(xc, osr, cycles, osr / P, 40e6)
    band = spectrum(xc, osr, cycles, osr / P, 10e6)
    mid = spectrum(mids, 1, cycles, 1 / P, 40e6)
    zoh = 20 * math.log10(abs(math.sin(math.pi * fsig * P) / (math.pi * fsig * P)))
    return dict(f_signal_MHz=round(fsig / 1e6, 4), continuous_0_40MHz=cont, continuous_0_10MHz=dict(sndr_db=band['sndr_db'], enob=band['enob']),
                midpoint_samples=mid, zoh_droop_db=round(zoh, 3), cm_V=round(float(np.mean(np.interp(grid, t, cm))), 4))


def step_eval(work, codes, k_step, lsb):
    """Transition registered at the edge for code index k_step."""
    t, v, _ = load(work)
    te = edge_time(t, k_step)
    v0 = float(np.interp(te - 0.2 * P, t, v))
    vf = float(np.mean(v[(t > te + 3.0 * P) & (t < te + 3.9 * P)]))
    m = (t >= te) & (t <= te + P)
    dev = v[m] - vf
    area = float(np.trapezoid(dev, t[m]))
    # 'glitch impulse': deviation area beyond an ideal step at the edge
    over = float(np.max((v[m] - vf) * np.sign(vf - v0))) if vf != v0 else float(np.max(np.abs(dev)))
    win = (t >= te) & (t < te + 3.9 * P)          # the code is held 4 periods; the next step starts at te + 4P
    bad = np.where(np.abs(v[win] - vf) > 0.5 * lsb)[0]
    ts = float(t[win][bad[-1]] - te) if len(bad) else 0.0
    return dict(v_before=round(v0, 5), v_final=round(vf, 5), step_V=round(vf - v0, 5), overshoot_V=round(over, 5),
                net_area_Vs=area, settle_0p5lsb_ns=round(ts * 1e9, 3), lsb_mV=round(lsb * 1e3, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--block', default='dac_i')
    ap.add_argument('--view', default='sch', choices=['sch', 'ext'])
    ap.add_argument('--corners', default='tt')
    ap.add_argument('--n', type=int, default=128)
    ap.add_argument('--cycles', default='13,29')
    ap.add_argument('--dbfs', type=float, default=-1.0)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--publish', action='store_true')
    a = ap.parse_args()
    src = REPO / f'scratch/converters/{a.block}/sim/{a.view}.spice'
    top = f'pt_{a.block}'
    base = REPO / f'scratch/converters/{a.block}_dyn/{a.view}'
    jobs = {}
    for cn in a.corners.split(','):
        corner = CORNERS[cn]
        for cyc in map(int, a.cycles.split(',')):
            jobs[f'sine_{cn}_c{cyc}'] = (corner, sine_codes(a.n, cyc, a.dbfs), ('sine', cyc))
        # steps: midscale major carry (-1 -> 0) and full scale (-512 -> 511), each held 4 periods
        jobs[f'steps_{cn}'] = (corner, [-512] * 4 + [-1] * 4 + [0] * 4 + [-512] * 4 + [511] * 4 + [-1] * 4, ('steps', None))
    def one(item):
        name, (corner, codes, kind) = item
        w = base / name; w.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, w / 'net.spice')
        text, _ = deck('net.spice', *corner, top, codes)
        if not ((w / 'dac.dat').exists() and (w / 'tb.spice').exists() and (w / 'tb.spice').read_text() == text):
            r = ck.ngspice(w, 'tb.spice', text, timeout=6 * 3600)
        idd = B.meas((w / 'tb.spice.log').read_text()).get('idd')
        try:
            if kind[0] == 'sine':
                res = sine_eval(w, a.n, kind[1])
            else:
                t, v, _ = load(w)
                vfs_lo = float(np.mean(v[(t > edge_time(t, 1) + 0.5 * P) & (t < edge_time(t, 3) + 0.9 * P)]))
                vfs_hi = float(np.mean(v[(t > edge_time(t, 17) + 0.5 * P) & (t < edge_time(t, 19) + 0.9 * P)]))
                lsb = (vfs_hi - vfs_lo) / 1023
                res = dict(fullscale_V=[round(vfs_lo, 4), round(vfs_hi, 4)],
                           major_carry_m1_to_0=step_eval(w, codes, 8, lsb),
                           fullscale_m512_to_511=step_eval(w, codes, 16, lsb))
        except Exception as e:
            res = dict(error=str(e)[-400:])
        res['supply_mA'] = round(-idd * 1e3, 3) if idd is not None else None
        res['corner'] = dict(zip(('mos', 'temp_c', 'vdd_v'), corner))
        return name, res
    with cf.ThreadPoolExecutor(a.workers) as ex:
        out = dict(ex.map(one, jobs.items()))
    doc = dict(block=a.block, view=a.view, update_rate_Hz=1 / P, n=a.n, dbfs=a.dbfs, load='100 fF per leg',
               method=__doc__.split('Usage')[0].strip(), results=out)
    (base / 'dynamic.json').write_text(json.dumps(doc, indent=1))
    if a.publish:
        (HERE / 'generated' / f'{a.block}-dynamic-{a.view}.json').write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
