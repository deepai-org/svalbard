"""Cell-level LDE synchroniser bench (resume 10).  wc_cnt alone (subckt carved from a top extraction, or a schematic),
CK = ideal 625/810 MHz clock with 100 ps edges, LDE = one-period pulse (30 ps edges, as the top bench) repeated every
5 T + STEP, so its phase against CK slides through a whole period.  Per LDE pulse: number of INJ pulses (must be 1) and the
CK cycle in which INJ rises.  Known answer: r7c full top = single at lde 0.5 ns, double at 0.6 ns after CKP0 (CK at the
cell is ~x ns after CKP0, so the double window must exist and be narrow); a deliberately broken case (LDE width 2 T on the
r7c cell) must report doubles everywhere.
usage: cntcell.py VARIANT corner f [width_in_T] [step_ps]"""
import sys, re
import numpy as np
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import sims, wrx_flow as wf
H = Path(__file__).resolve().parent
SRC = dict(r7f=Path('/home/ubuntu/svalbard/scratch/wired_rx/r12/cap/r7f/gen/wrx_cap.ext.spice'))
CORN = dict(typical=(27, 3.3), ss=(32, 3.15), ff=(22, 3.35), ss35=(32, 3.5), sf=(27, 3.3), fs=(27, 3.3))
def cell(var):
    if var.startswith('sch'):
        import capture as c
        _row, ports, net = c.cnt(); name = 'wc_cnt'
        return c.subckt(name, ports, net), ports
    if var.endswith('pess'):
        import subprocess
        base = var[:-4]; dst = H / f'{base}_pess.spice'
        subprocess.run(['python3', str('/home/ubuntu/svalbard/scratch/wired_rx/r7slicer/pess.py'), str(SRC[base]), str(dst)], check=True, stdout=subprocess.DEVNULL)
        sp = dst.read_text()
    else:
        sp = SRC[var].read_text()
    k = sp.index('.subckt wc_cnt '); e = sp.index('.ends', k)
    txt = sp[k:e] + '.ends\n'
    ports = re.search(r'\.subckt wc_cnt (.*?)\n(?!\+)', txt, re.S).group(1).replace('\n+', ' ').split()
    return txt, ports
def run(var, corner, f, width=1.0, step=20e-12):
    temp, vdd = CORN[corner]; T = 1 / f; n = int(T / step) + 2; per = 5 * T + step; t0 = 3e-9
    txt, ports = cell(var)
    w = H / 'cnt' / f'{var}_{corner}_{int(f/1e6)}_{width}'; w.mkdir(parents=True, exist_ok=True)
    (w / 'cell.spice').write_text(txt)
    lde = [(0, 0.)]
    for i in range(n):
        a = t0 + i * per
        lde += [(a, 0.), (a + 30e-12, vdd), (a + width * T, vdd), (a + width * T + 30e-12, 0.)]
    conn = {p: f'nc{i}' for i, p in enumerate(ports)}; conn.update(CK='ck', ENB='0', LDE='lde', INJ='inj', VDD='vdd', VSS='0')
    pwl = 'PWL(' + ' '.join(f'{a:.6e} {b:.3f}' for a, b in lde) + ')'
    tb = [f'* cnt {var} {corner}', sims.sim_header(corner.replace('ss35', 'ss'), temp), '.include cell.spice', f'VDD vdd 0 {vdd}',
          f'VCK ck0 0 PULSE(0 {vdd} 1e-9 100p 100p {T/2-100e-12:.6e} {T:.6e})', 'RCK ck0 ck 100', 'CCK ck 0 20f',
          f'VLDE lde 0 {pwl}', 'X1 ' + ' '.join(conn[p] for p in ports) + ' wc_cnt', 'CINJ inj 0 60f',
          '.control', f'tran 5p {t0 + n * per:.5e}', 'set wr_singlescale', 'wrdata out.txt v(ck) v(lde) v(inj)', '.endc', '.end']
    (w / 'tb.cir').write_text('\n'.join(tb)); wf.ngspice(w, 'tb.cir', timeout=1800)
    d = np.loadtxt(w / 'out.txt'); t = d[:, 0]
    def rises(x):
        v = x > vdd / 2; i = np.where(v[1:] & ~v[:-1])[0] + 1
        return t[i] - (x[i] - vdd / 2) / (x[i] - x[i - 1]) * (t[i] - t[i - 1])
    ck, ld, inj = rises(d[:, 1]), rises(d[:, 2]), rises(d[:, 3])
    injf = rises(vdd - d[:, 3])
    rows = []
    for i, a in enumerate(ld):
        nxt = ld[i + 1] if i + 1 < len(ld) else a + per
        mine = inj[(inj > a) & (inj < nxt)]
        ph = a - ck[ck <= a].max()                      # LDE rise after the last CK rise at the cell pin
        lat = [int(round((x - ck[ck <= a].max()) / T)) for x in mine]
        # INJ high for k CK cycles seeds slot 0 k times: count cycles, not rises (first bench version counted rises
        # and failed its own broken-case control)
        k = sum(int(round((injf[injf > x].min() - x) / T)) for x in mine)
        rows.append((ph, k, lat))
    bad = [(round(p * 1e12), k, l) for p, k, l in rows if k != 1]
    lats = sorted(set(l[0] for p, k, l in rows if k == 1))
    # boundary where the capture cycle changes (the inherent ambiguity point)
    one = sorted((p, l[0]) for p, k, l in rows if k == 1)
    chg = [(round(one[i][0] * 1e12), round(one[i + 1][0] * 1e12)) for i in range(len(one) - 1) if one[i][1] != one[i + 1][1]]
    print(f'{var} {corner} {vdd} V f={f/1e6:.0f} width {width} T: pulses {len(rows)}, not-single {len(bad)} {bad[:12]}, latencies {lats}, cycle change between LDE phases (ps after CK at the cell) {chg}', flush=True)
if __name__ == '__main__':
    a = sys.argv
    run(a[1], a[2], float(a[3]), float(a[4]) if len(a) > 4 else 1.0, float(a[5]) * 1e-12 if len(a) > 5 else 20e-12)
