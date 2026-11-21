"""r12 ptrim real-ring trim solve + verification for one calibration tag (r10ptrim/rr2.py method, self-contained here).
usage: rr12.py NAME CALTAG DUT corner temp vdd [scale=1.0] [codes=0,4,...,31] [full=0]
  CALTAG: cal/ph_<CALTAG>.npz (cal12.py: r12 ring -> ptrim, one settled own-period table at the ptrim pins, replayed as PWL)
  scale : lumped consumer load factor (1.15 with the pessimistic ptrim netlist = the r10 slow-pessimistic bound)
  full=1: deck A at all 32 codes (4 decks of 8 copies) instead of the 9-point curve
Deck A: copies with every channel at one code -> CKPk rising position vs code (VDD/2, against the k*T/8 grid).
Solve : codes minimising the peak-to-peak of the eight positions (piecewise-linear interpolation of the measured curve).
Deck B: one copy WITH the solved codes -> measured residual (G2), duty, levels, current.
-> res/<NAME>.json.  Each deck is one ngspice run; the caller wraps the whole script in slot.sh (serial inside)."""
import sys, json, re, shutil, time
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10ptrim')
import bench, savefix
H = Path(__file__).resolve().parent
name, cal, dut, corner, temp, vdd = sys.argv[1:7]
o = dict(scale='1.0', full='0', codes='0,4,8,12,16,20,24,28,31'); o.update(dict(a.split('=', 1) for a in sys.argv[7:]))
temp, vdd, scale = int(temp), float(vdd), float(o['scale'])
dut = str(Path(dut).resolve())
npz = H / 'cal' / f'ph_{cal}.npz'; C = json.loads((H / 'cal' / f'{cal}.json').read_text())[cal]
d = np.load(npz); f = float(d['f0']); T = 1 / f; Tp = T * 1e12; n = int(d['n'])
CODES = list(range(32)) if o['full'] == '1' else [int(x) for x in o['codes'].split(',')]


def deck(tag, codesets):
    work = H / 'sim' / tag
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True); shutil.copy(dut, work / Path(dut).name)
    copies = [dict(codes=c, load='lump', route=(0.0, 30.0), scale=scale) for c in codesets]
    text, meta = bench.deck(dut, corner, temp, vdd, f, copies, ncyc=8)
    lines = text.splitlines(); k = 0
    for i, l in enumerate(lines):
        m = re.match(r'VPH(\d) ', l)
        if m:
            j = int(m.group(1)); v = d[f'ph{j}']
            lines[i] = f'VPH{j} phs{j} 0 PWL(' + ' '.join(f'{q * T / n:.6e} {v[q % n]:.5f}' for q in range(n + 1)) + ') r=0'; k += 1
    assert k == 8
    (work / 'tb.cir').write_text('\n'.join(lines) + '\n')
    t0 = time.time(); log = bench.wf.ngspice(work, 'tb.cir', timeout=7200)
    if not (work / 'out.txt').exists():
        print(name, 'ERROR', log[-800:]); sys.exit(1)
    res = bench.analyse(work, meta, vdd, copies)
    shutil.rmtree(work)
    ref = res['copies'][0][0]['dr_ps']
    pos = [[None if c['dr_ps'] is None else ((c['dr_ps'] - ref + Tp / 2) % Tp) - Tp / 2 for c in ch] for ch in res['copies']]
    fpos = [[None if c['df_ps'] is None else ((c['df_ps'] - ref + Tp / 2) % Tp) - Tp / 2 for c in ch] for ch in res['copies']]
    return res, pos, fpos, round(time.time() - t0, 1)


un = lambda x: (np.array(x, float) + Tp / 2) % Tp - Tp / 2
A, PA, rawA = [], [], []
sims = []
for i in range(0, len(CODES), 9 if o['full'] != '1' else 8):
    part = CODES[i:i + (9 if o['full'] != '1' else 8)]
    res, pos, fpos, s = deck(f'{name}_a{i}', [[c] * 8 for c in part]); sims.append(s)
    if i:          # re-reference later decks to this deck's own channel 0 at its first code via the shared code: not shared ->
        pass       # positions are re-referenced below through channel-0 delay (dr_ps, same source timing in every deck)
    for j, c in enumerate(part):
        rawA.append((c, res['copies'][j], res['idd_mA'][j]))
# absolute rise delays (same PWL source timing in every deck) -> positions relative to channel 0 at code CODES[0]
ref = rawA[0][1][0]['dr_ps']
PA = np.array([[((ch[k]['dr_ps'] - ref + Tp / 2) % Tp) - Tp / 2 for k in range(8)] for _, ch, _ in rawA]).T     # [channel, code]
PA = np.array([np.unwrap(row, period=Tp) for row in PA])
P = np.array([np.interp(np.arange(32), CODES, PA[k]) for k in range(8)])
steps = np.diff(PA, axis=1) / np.diff(CODES)
best = None
for tau in np.arange(P.min(), P.max() + 0.05, 0.05):
    c = np.abs(P - tau).argmin(axis=1); v = P[np.arange(8), c]; pp = float(v.max() - v.min())
    if best is None or pp < best[0] - 1e-9: best = (pp, [int(x) for x in c])
codes = best[1]
resB, posB, fposB, sB = deck(f'{name}_b', [codes]); sims.append(sB)
pb = un(posB[0]); fb = un(fposB[0])
need_meas = float(np.ptp(PA[:, 0])); rng = PA[:, -1] - PA[:, 0]
need = need_meas + 4.0 + 10.0
allc = [c for _, ch, _ in rawA for c in ch] + list(resB['copies'][0])
S = dict(name=name, cal=cal, cal_ok=bool(C.get('ok')), cal_drift_ps=C.get('settled_last6_period_ptp_ps'), ring_pos_err_ps=C.get('pos_err_ps'),
         ring_duty=[p['duty'] for p in C['ring_out']['ph']], dut=dut, dut_sha256=bench.sha(dut), source_sha256=bench.sha(npz), corner=corner, temp=temp, vdd=vdd,
         scale=scale, f_hz=f, T_ps=round(Tp, 2), code_points=CODES, pos_vs_code_ps=[[round(float(x), 2) for x in PA[k]] for k in range(8)],
         code0_pos_ps=[round(float(x), 2) for x in PA[:, 0]], need_meas_ps=round(need_meas, 2), need_ps=round(need, 2),
         range_ps=[round(float(x), 2) for x in rng], range_min_ps=round(float(rng.min()), 2), ratio=round(float(rng.min()) / need, 3),
         G1=bool(rng.min() >= 1.25 * need), monotonic=bool(steps.min() > 0), step_ps_min_max=[round(float(steps.min()), 3), round(float(steps.max()), 3)],
         max_step_deg=round(float(steps.max()) * 360 / Tp, 3) if o['full'] == '1' else None,
         best_codes=codes, predicted_pp_ps=round(best[0], 2),
         verify=dict(pos_ps=[round(float(x - pb.mean()), 2) for x in pb], pp_ps=round(float(np.ptp(pb)), 2), pp_deg=round(float(np.ptp(pb)) / Tp * 360, 3),
                     fall_pp_ps=round(float(np.ptp(fb)), 2), duty=[c['duty'] for c in resB['copies'][0]], idd_mA=resB['idd_mA'][0]),
         idd_code0_mA=rawA[0][2], idd_code31_mA=rawA[-1][2], duty_code0=[c['duty'] for c in rawA[0][1]], duty_code31=[c['duty'] for c in rawA[-1][1]],
         lo_max_V=max(c['lo'] for c in allc), hi_min_V=min(c['hi'] for c in allc),
         edge_max_ps=max(max(c['tr_ps'] or 9e9, c['tf_ps'] or 9e9) for c in allc), sim_s=sims)
S['G2'] = bool(S['verify']['pp_deg'] <= 3.0)
S['C1'] = bool(S['lo_max_V'] <= 0.1 * vdd and S['hi_min_V'] >= 0.9 * vdd)
(H / 'res').mkdir(exist_ok=True); (H / 'res' / f'{name}.json').write_text(json.dumps(S, indent=1))
print(name, 'need', S['need_meas_ps'], '+14 =', S['need_ps'], 'range_min', S['range_min_ps'], 'ratio', S['ratio'], 'G1', S['G1'], 'codes', codes,
      'pp', S['verify']['pp_ps'], 'ps', S['verify']['pp_deg'], 'deg G2', S['G2'], 'mono', S['monotonic'], 'idd', S['verify']['idd_mA'], S['idd_code0_mA'], S['idd_code31_mA'], flush=True)
