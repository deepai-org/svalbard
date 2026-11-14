"""Real phase source for wired-TX benches: extracted pt_pll_ring_core (TX ring, timing/generated/pll_ring_core.ext.spice)
run open loop (VCTRL forced on ATB_VCTRL, REF low) on the regulated ring supply (pt_pll_vreg output, ~0.9 x rail).

    python3 sim_ringsrc.py cal  <corner> <temp> <vring> <band> <vctrl,...> [pess]   # frequency / phase spacing table
"""
import sys, json, re
from pathlib import Path
import numpy as np
WTX = Path(__file__).resolve().parent
sys.path.insert(0, str(WTX))
import tools, sim_wiredtx as S
RING = WTX.parent / 'timing/generated/pll_ring_core.ext.spice'
RPORTS = 'REF EN N4 N8 HOLD IBIAS PH0 PH1 PH2 PH3 PH4 PH5 PH6 PH7 LOCK FBCK REFO ATB_VCTRL BAND VDD VSS'.split()


def ring_text(pess=False, opt=False):
    t = RING.read_text()
    assert S.ports_of(t, 'pt_pll_ring_core') == RPORTS, S.ports_of(t, 'pt_pll_ring_core')
    if pess:
        t = S.pessimize(t)
    elif opt:
        t = S.scale_c(t, 0.85)
    t = t.replace('/', '__')
    names = re.findall(r'^\.subckt\s+(\S+)', t, re.M | re.I)
    pat = r'(?<!\S)(' + '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r')(?!\S)'
    return re.sub(pat, lambda m: 'rg_' + m.group(), t)     # private namespace (the DUT carries cells of the same name)


def ring_lines(vring, vctrl, band, out=None, pfx='RG'):
    """instance lines: ring on its own supply VRING (ideal source = regulator output), phases on nodes out[k]."""
    out = out or [f'RPH{k}' for k in range(8)]
    L = [f'V{pfx}S {pfx}_VDD 0 {vring}', f'V{pfx}C {pfx}_VC0 0 {vctrl}', f'R{pfx}C {pfx}_VC0 {pfx}_VC 100',
         f'I{pfx}B {pfx}_VDD {pfx}_IB 10u',
         f'V{pfx}E {pfx}_EN 0 PWL(0 0 0.5n 0 0.6n {vring})',
         f'X{pfx} 0 {pfx}_EN 0 0 0 {pfx}_IB ' + ' '.join(out) + f' {pfx}_LOCK {pfx}_FBCK {pfx}_REFO {pfx}_VC '
         f'{"%s_VDD" % pfx if band else "0"} {pfx}_VDD 0 rg_pt_pll_ring_core']
    return L


def edges(t, v, th, rising=True):
    s = v > th; i = np.where(s[1:] != s[:-1])[0]; i = i[s[i + 1] == rising]
    return t[i] + (th - v[i]) * (t[i + 1] - t[i]) / (v[i + 1] - v[i])


def measure(w, vring, t0):
    t = w['time']; r = {}
    e0 = edges(t, w['RPH0'], vring / 2); e0 = e0[e0 > t0]
    if len(e0) < 4:
        return dict(osc=False)
    T = float(np.mean(np.diff(e0))); r.update(osc=True, f_mhz=round(1e-6 / T, 2), jit_ps=round(float(np.ptp(np.diff(e0))) * 1e12, 2))
    ph, duty, hi, lo = [], [], [], []
    for k in range(8):
        v = w[f'RPH{k}']; ek = edges(t, v, vring / 2); ek = ek[ek > e0[0] - 1e-13]
        fk = edges(t, v, vring / 2, False); fk = fk[fk > ek[0]]
        n = min(len(ek), len(e0)) - 1
        d = np.mean((ek[:n] - e0[:n]) % T) / T * 360
        ph.append(round(float(d), 2)); duty.append(round(float(np.mean((fk[:n] - ek[:n]) % T) / T), 4))
        sel = t > t0; hi.append(round(float(v[sel].max()), 3)); lo.append(round(float(v[sel].min()), 3))
    r.update(phase_deg=ph, duty=duty, vhi=hi, vlo=lo)
    order = np.argsort(ph); r['order'] = [int(x) for x in order]
    sp = np.diff(np.sort(ph + [360.0])); r['slot_err_ps'] = [round(float((x - 45) / 360 * T * 1e12), 1) for x in sp]
    return r


def cal(corner, temp, vring, band, vctrls, pess=False, work=None, load_f=60e-15):
    out = {}
    for vc in vctrls:
        wk = Path(work or tools.SCRATCH / 'realring' / 'ringcal') / f'{corner}_{vring}_{band}_{vc}{"_p" if pess else ""}'; wk.mkdir(parents=True, exist_ok=True)
        (wk / 'ring.spice').write_text(ring_text(pess))
        L = ['* ring cal', tools.model_header(corner, temp), '.include ring.spice'] + ring_lines(vring, vc, band)
        L += [f'CL{k} RPH{k} 0 {load_f}' for k in range(8)]
        vecs = ' '.join(f'v(RPH{k})' for k in range(8)) + ' i(VRGS)'
        L += ['.options reltol=1e-3 method=gear', '.tran 5p 40n 0 5p', '.control', f'save {vecs}', 'set wr_singlescale', 'run',
              f'wrdata wave.txt {vecs}', '.endc', '.end']
        (wk / 'tb.sp').write_text('\n'.join(L) + '\n')
        tools.ngspice(wk, 'tb.sp')
        w = tools.read_wrdata(wk / 'wave.txt', [f'RPH{k}' for k in range(8)] + ['I'])
        m = measure(w, vring, 20e-9); m['i_ma'] = round(float(-np.mean(w['I'][w['time'] > 20e-9]) * 1e3), 2)
        out[vc] = m; print(vc, json.dumps(m), flush=True)
    return out


if __name__ == '__main__':
    if sys.argv[1] == 'cal':
        corner, temp, vring, band = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
        vcs = [float(x) for x in sys.argv[6].split(',')]
        r = cal(corner, temp, vring, band, vcs, pess=len(sys.argv) > 7 and sys.argv[7] == 'pess')
        Path(f'ringcal_{corner}_{vring}_{band}{"_p" if len(sys.argv) > 7 else ""}.json').write_text(json.dumps(r, indent=1))
