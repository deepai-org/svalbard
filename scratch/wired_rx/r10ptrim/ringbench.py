"""MW-31 bench: pt_ptrim driven by the EXTRACTED CDR ring (analog/timing/generated/pll_ring.ext.spice, pt_pll_ring r9v, the
netlist scratch/wired_rx/r7cdr/cl13.py uses), open loop (HOLD high, VCTRL forced on ATB_VCTRL through 100 ohm, REF low,
FU/FD/KP low), ring on its own (regulated) supply VRING, each phase through a 30 ohm / 60 fF route into ptrim; ptrim on
VDD with the lumped real loads.
  ringbench.py cal  TAG corner temp vring band vctrl[,vctrl..]                 ring alone (60 fF + 45 fF per phase): f, duty, levels
  ringbench.py run  TAG DUT corner temp vdd vring band vctrl codes [route=lo]    ring -> ptrim (one deck per code)
Result -> ring.json[TAG]."""
import sys, os, json, re, shutil
from pathlib import Path
import numpy as np
import bench, sweep
wf = bench.wf
H = Path(__file__).resolve().parent
RING = Path(os.environ['R11_RING']) if os.environ.get('R11_RING') else bench.W.parent / 'timing/generated/pll_ring.ext.spice'
RP = 'REF EN N4 N8 HOLD IBIAS PH0 PH1 PH2 PH3 PH4 PH5 PH6 PH7 LOCK FBCK REFO ATB_VCTRL N5 N10 KP0 KP1 KP2 FU0 FU1 FU2 FU3 FD0 FD1 FD2 FD3 BAND VDD VSS'.split()


def ring_text():
    t = RING.read_text()
    assert bench.ports(RING, 'pt_pll_ring') == RP, bench.ports(RING, 'pt_pll_ring')
    t = t.replace('/', '__')
    names = re.findall(r'^\.subckt\s+(\S+)', t, re.M | re.I)
    pat = r'(?<!\S)(' + '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r')(?!\S)'
    return re.sub(pat, lambda m: 'rg_' + m.group(), t)


def ring_lines(vring, vctrl, band):
    m = {p: '0' for p in RP}
    m.update(EN='rg_en', HOLD='rg_vdd', IBIAS='rg_ib', LOCK='rg_lock', FBCK='rg_fbck', REFO='rg_refo', ATB_VCTRL='rg_vc', BAND='rg_vdd' if band else '0', VDD='rg_vdd')
    for k in range(8): m[f'PH{k}'] = f'phs{k}'
    return [f'VRGS rg_vdd 0 {vring}', f'VRGC rg_vc0 0 {vctrl}', 'RRGC rg_vc0 rg_vc 100', 'IRGB rg_vdd rg_ib 10u',
            f'VRGE rg_en 0 PWL(0 0 0.5n 0 0.6n {vring})', 'XRG ' + ' '.join(m[p] for p in RP) + ' rg_pt_pll_ring',
            'CRG1 rg_lock 0 10f', 'CRG2 rg_fbck 0 10f', 'CRG3 rg_refo 0 10f']


def edges(t, v, th, rising=True):
    s = v > th; i = np.where(s[1:] != s[:-1])[0]; i = i[s[i + 1] == rising]
    return t[i] + (th - v[i]) * (t[i + 1] - t[i]) / (v[i + 1] - v[i])


def run_deck(work, L, saves, tend):
    ctl = [f'tran 4p {tend:g}', 'set wr_singlescale', 'set wr_vecnames', 'option numdgt=7', f'wrdata out.txt {" ".join(saves)}']
    (work / 'tb.cir').write_text('\n'.join(L + ['.option method=gear', '.control', *ctl, '.endc', '.end', '']))
    log = wf.ngspice(work, 'tb.cir', timeout=7200)
    if not (work / 'out.txt').exists(): raise RuntimeError(log[-1500:])
    d = np.genfromtxt(work / 'out.txt', names=True)
    return d


def phase_stats(t, d, vring, t0):
    e0 = edges(t, d['vph0'], vring / 2); e0 = e0[e0 > t0]
    T = float(np.mean(np.diff(e0)))
    out = dict(f_mhz=round(1e-6 / T, 2), T_ps=round(T * 1e12, 2), ph=[])
    for k in range(8):
        v = d[f'vph{k}']; r = edges(t, v, vring / 2); r = r[r > e0[0] - 1e-13]; fl = edges(t, v, vring / 2, False); fl = fl[fl > r[0]]
        n = min(len(r), len(fl), len(e0)) - 1; sel = t > t0
        r2 = edges(t, v, 0.2 * vring); r8 = edges(t, v, 0.8 * vring); r2 = r2[r2 > t0]; r8 = r8[r8 > r2[0]]
        out['ph'].append(dict(deg=round(float(np.mean((r[:n] - e0[:n]) % T) / T * 360), 2), duty=round(float(np.mean(fl[:n] - r[:n]) / T), 4),
                              hi=round(float(v[sel].max()), 3), lo=round(float(v[sel].min()), 3), tr_ps=round(float(r8[0] - r2[0]) * 1e12, 1)))
    return out, T


def main():
    mode, tag = sys.argv[1], sys.argv[2]
    store = H / 'ring.json'
    if mode == 'cal':
        corner, temp, vring, band = sys.argv[3], int(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
        for vc in [float(x) for x in sys.argv[7].split(',')]:
            work = H / 'sim' / tag / f'vc{vc}'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
            (work / 'ring.spice').write_text(ring_text())
            L = ['* ring cal', wf.sim_header(corner, temp), '.include ring.spice'] + ring_lines(vring, vc, band)
            for k in range(8): L += [f'RPH{k} phs{k} ph{k} 30', f'CPH{k} ph{k} 0 105f']
            d = run_deck(work, L, [f'v(ph{k})' for k in range(8)] + ['i(VRGS)'], 30e-9)
            st, T = phase_stats(d[d.dtype.names[0]], d, vring, 18e-9)
            D = json.loads(store.read_text()) if store.exists() else {}
            D.setdefault(tag, {})[str(vc)] = dict(corner=corner, temp=temp, vring=vring, band=band, **st); store.write_text(json.dumps(D, indent=1))
            print(tag, vc, st['f_mhz'], 'duty', [p['duty'] for p in st['ph']], 'hi', min(p['hi'] for p in st['ph']), 'tr', max(p['tr_ps'] for p in st['ph']), flush=True)
            (work / 'out.txt').unlink()
        return
    dut, corner, temp, vdd, vring, band, vc, codes = sys.argv[3], sys.argv[4], int(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7]), int(sys.argv[8]), float(sys.argv[9]), sys.argv[10]
    o = dict(route='lo'); o.update(dict(a.split('=', 1) for a in sys.argv[11:]))
    P = bench.ports(dut, 'pt_ptrim'); rr, rc = sweep.ROUTE[o['route']]
    for code in [int(c) for c in codes.split(',')]:
        work = H / 'sim' / tag / f'c{code}'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
        (work / 'ring.spice').write_text(ring_text()); shutil.copy(dut, work / 'dut.spice')
        L = ['* ring -> ptrim', wf.sim_header(corner, temp), '.include ring.spice', '.include dut.spice', f'VDD vdd 0 {vdd}', 'VMP vdd vddp 0'] + ring_lines(vring, vc, band)
        m = dict(VDD_WIRE_SW='vddp', VSS='0', ptrim_en='vdd')
        for k in range(8):
            L += [f'RPH{k} phs{k} ph{k} 30', f'CPH{k} ph{k} 0 60f']
            m[f'PH{k}'] = f'ph{k}'; m[f'CKP{k}'] = f'o{k}'
            for b in range(5): m[f'T{k}_{b}'] = 'vdd' if (code >> b) & 1 else '0'
            pin = bench.PIN[k] + (bench.WCK if k == 0 else 0)
            if rr > 0: L += [f'CRA{k} o{k} 0 {rc / 2:g}f', f'RR{k} o{k} p{k} {rr:g}', f'CL{k} p{k} 0 {pin + rc / 2:g}f']
            else: L += [f'RR{k} o{k} p{k} 0.01', f'CL{k} p{k} 0 {pin + rc:g}f']
        L.append('XDUT ' + ' '.join(m[p] for p in P) + ' pt_ptrim')
        d = run_deck(work, L, [f'v(ph{k})' for k in range(8)] + [f'v(p{k})' for k in range(8)] + ['i(VMP)'], 30e-9)
        t = d[d.dtype.names[0]]; st, T = phase_stats(t, d, vring, 18e-9)
        sel = t > 18e-9; chans = []
        for k in range(8):
            vi, vo = d[f'vph{k}'], d[f'vp{k}']
            ri = edges(t, vi, vring / 2); ri = ri[ri > 18e-9]; ro = edges(t, vo, vdd / 2); fo = edges(t, vo, vdd / 2, False)
            dl = []
            for x in ri[:-2]:
                y = ro[ro > x]
                if len(y): dl.append(y[0] - x)
            ro2 = ro[ro > 18e-9]; du = []
            for x in ro2[:-1]:
                y = fo[fo > x]
                if len(y): du.append((y[0] - x) / T)
            chans.append(dict(delay_ps=round(float(np.mean(dl)) * 1e12, 2) if dl else None, delay_pp_ps=round(float(np.ptp(dl)) * 1e12, 2) if dl else None,
                              duty=round(float(np.mean(du)), 4) if du else None, hi=round(float(vo[sel].max()), 3), lo=round(float(vo[sel].min()), 3)))
        idd = abs(float(np.trapezoid(d[d.dtype.names[-1]][sel], t[sel]) / (t[sel][-1] - t[sel][0]))) * 1e3
        res = dict(dut=str(dut), dut_sha256=bench.sha(dut), ring=str(RING), ring_sha256=bench.sha(RING), corner=corner, temp=temp, vdd=vdd, vring=vring, band=band, vctrl=vc,
                   code=code, ring_out=st, channels=chans, idd_mA=round(idd, 3))
        D = json.loads(store.read_text()) if store.exists() else {}
        D.setdefault(tag, {})[str(code)] = res; store.write_text(json.dumps(D, indent=1))
        print(tag, 'code', code, 'f', st['f_mhz'], 'in duty', [p['duty'] for p in st['ph']], 'in hi', min(p['hi'] for p in st['ph']), 'in tr', max(p['tr_ps'] for p in st['ph']),
              'delay', [c['delay_ps'] for c in chans], 'out duty', [c['duty'] for c in chans], 'lvl', max(c['lo'] for c in chans), min(c['hi'] for c in chans), 'idd', res['idd_mA'], flush=True)
        (work / 'out.txt').unlink()


if __name__ == '__main__':
    main()
