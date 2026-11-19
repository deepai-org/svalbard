"""Interlock bench for wtx_mux8 (session 14): schematic or extracted netlist, per-phase states, bank-current sense,
optional per-group supply split (schematic only), supply ramp with phases scaled to the supply.

    python3 ilk.py '{"tag":"x","c":"ssp","net":"ext:/path/mux.spice","phases":"11110000","stop_at":22e-9}'

phases: 8 chars per phase after stop_at: '0' / '1' static, 'm' mid level (mid=, default 1.35 V) with optional residual
  swing res_pp (V pp, sine at f_ring), 'r' keep running; stuck: dict {k: 'H' | 'L'} held from t = 0.
net: 'sch' (current wtx_mux8.netlist(), wiring-C stand-ins as m9) | 'ext:<file>' (extracted subckt wtx_mux8).
"""
import sys, json, math, re
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
S13 = HERE.parent.parent / 's13'
sys.path.insert(0, str(S13))
import m9  # noqa: E402  (sets up the s12 paths)
from m9 import CH, tools, S, B, B4, M8, CORN, mux9  # noqa: E402
RUNS = HERE / 'runs'
CORN = dict(CORN, ffcold=dict(corner='ff', temp=0, vdd=3.63, swing=3.27, pess=False),
            sshot=dict(corner='ss', temp=85, vdd=2.97, swing=2.5, pess=True))
GROUPS = [('I0', 'in_nand'), ('I0b', 'in_inv1'), ('I1', 'in_inv2'), ('TS', 'trim'), ('D', 'detector'), ('HP', 'bank'),
          ('I2', 'pre_end'), ('I3', 'pre_end'), ('NP', 'pre_nor'), ('NN', 'pre_nor'), ('TG', 'pre_tg'), ('G', 'logic')]


def sense_headers(txt):
    """0 V sources in series with every header source node (PMOS with a TOP2M / TOP2Q drain)."""
    seen, out, k = {}, [], 0
    for l in txt.splitlines():
        f = l.split()
        if f and f[0][0] in 'Xx' and len(f) > 5 and 'pfet' in f[5]:
            d, g, s_ = f[1], f[2], f[3]
            hit = [i for i in (1, 3) if re.match(r'(xmux\.)?TOP2[MQ]\b', f[i].split('.t')[0]) or f[i].split('.t')[0] in ('TOP2M', 'TOP2Q')]
            if len(hit) == 1:
                i = 4 - hit[0]
                bank = 'M' if 'TOP2M' in f[hit[0]] else 'Q'
                key = (f[i], bank)
                if key not in seen:
                    seen[key] = f'VHS{bank}{len(seen)}'
                f[i] = f[i] + f'__hs{bank}'
                l = ' '.join(f)
        out.append(l)
    srcs = [f'{v} {n} {n}__hs{b} 0' for (n, b), v in seen.items()]
    out = '\n'.join(out)
    i = out.rfind('.ends')
    return out[:i] + '\n'.join(srcs) + '\n' + out[i:], list(seen.values())


def _base(n):
    n = n.split('__')[-1] if n.startswith('xmux') else n
    return re.sub(r'(\.(t|n)\d+)+$', '', n)


def _grp(g, d):
    g, d = _base(g), _base(d)
    if re.match(r'PH\d$', g):
        return 'det_in' if re.match(r'X[EDHS]\d$', d) else 'in_nand'
    if g.endswith('.Y') or re.match(r'Y\d$', g):
        return 'in_inv1'
    if g.endswith('.Z') or re.match(r'Z\d$', g):
        return 'in_inv2'
    if re.match(r'(X[EDHS]\d|D[ANR]|DRB|DR0|DR2|RUNB|DM)', g) or re.match(r'(X[EDHS]\d|DA\d|DN\d|DRB|RUNB)', d):
        return 'detector'
    if g.endswith('.X') or re.match(r'X\d$', g) or 'XT' in g:
        return 'pre'
    return 'other'


def split_groups(txt):
    """per-group sense of the PMOS current from the supply (crowbar / static current of a group = its PMOS current),
    classified by gate and drain net (works on the schematic and on the extracted netlist).  Headers are excluded."""
    out, seen = [], {}
    for l in txt.splitlines():
        f = l.split()
        if f and f[0][0] in 'Xx' and len(f) > 5 and 'pfet' in f[5]:
            for i in (1, 3):
                if _base(f[i]).startswith('VDD') and not _base(f[4 - i]).startswith('TOP2'):
                    grp = _grp(f[2], f[4 - i])
                    key = (f[i], grp)
                    seen.setdefault(key, f'VG{len(seen)}_{grp}')
                    f[i] = f[i] + '__g' + grp
                    l = ' '.join(f)
                    break
        out.append(l)
    out = '\n'.join(out)
    i = out.rfind('.ends')
    return out[:i] + '\n'.join(f'{v} {n} {n}__g{g} 0' for (n, g), v in seen.items()) + '\n' + out[i:], list(seen.values())


def force_run_high(txt):
    """negative control: every device whose gate is RUNB (the detector's NAND output, which drives RUN and its copies)
    gets its gate tied to VSS -> RUN and every copy high whatever the detector sees."""
    out, n = [], 0
    for l in txt.splitlines():
        f = l.split()
        if f and f[0][0] in 'Xx' and len(f) > 5 and 'fet' in f[5] and f[2].split('.t')[0].split('.n')[0] == 'RUNB':
            f[2] = 'VSS'; n += 1; l = ' '.join(f)
        out.append(l)
    if n == 0:
        raise RuntimeError('no RUNB gate found')
    return '\n'.join(out) + '\n', n


def run(tag, c='ssp', net='sch', par=None, phases=None, stop_at=22e-9, mid=1.35, res_pp=0.0, stuck=None, f_ring=None, rate=None,
        nbits=None, tstop=6e-7, tstep=2e-11, ramp=None, groups=False, force=False, probes=(), ic_run=True, cload=0.45e-12, keep=False):
    cc = dict(CORN[c]); corner, temp, vdd, swing, pess = cc['corner'], cc['temp'], cc['vdd'], cc['swing'], cc['pess']
    res = {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    work = RUNS / tag; work.mkdir(parents=True, exist_ok=True)
    rate = rate or (8 * f_ring if f_ring else 3.125e9)
    ui = 1 / rate; tq = 8 * ui
    if net == 'sch':
        txt = M8.wire_c(mux9.netlist(par))
    else:
        txt = B.clean(Path(net.split(':', 1)[1]).read_text()).replace('/', '__')
    nforce = 0
    if force:
        txt, nforce = force_run_high(txt)
    gsrc = []
    if groups:
        txt, gsrc = split_groups(txt)
    if pess:
        txt = B4.pess_all(txt)
    txt, hs = sense_headers(txt)
    (work / 'mux.spice').write_text(txt)
    L = ['* ilk bench', CH.pad_header(corner, temp, res), '.include mux.spice',
         f'VDD VDD 0 {vdd}' if not ramp else f'VDD VDD 0 PWL(0 0 {ramp} {vdd})', 'VSS VSS 0 0']
    sc = f'*v(VDD)/{vdd}' if ramp else ''
    tr = 60e-12; kk = 2.197 / tr; t00 = 1e-9
    stuck = {int(k): v for k, v in (stuck or {}).items()}
    for k in range(8):
        t0_ = t00 + k * ui
        osc = f'{swing}*(0.5+0.5*tanh({kk * tq / (2 * math.pi):.6e}*sin(2*3.141592653589793*(time-{t0_:.6e})/{tq:.6e})))'
        if k in stuck:
            src = f'{swing if stuck[k] == "H" else 0.0}'
        elif phases is None or phases[k] == 'r':
            src = osc
        else:
            ch = phases[k]
            if ch == 'm':
                lv = f'({mid}+{res_pp / 2}*sin(2*3.141592653589793*(time-{t0_:.6e})/{tq:.6e}))' if res_pp else f'{mid}'
            else:
                lv = f'{0.0 if ch == "0" else swing}'
            src = lv if stop_at == 0 else f'({osc})*(0.5-0.5*tanh((time-{stop_at:.6e})/30p))+{lv}*(0.5+0.5*tanh((time-{stop_at:.6e})/30p))'
        L.append(f'BPH{k} PH{k}_s 0 V=({src}){sc}'); L += [f'RPH{k} PH{k}_s PH{k} 150', f'CPH{k} PH{k} 0 60f']
    nbits = nbits or max(16, int((tstop - t00) / ui) - 4)
    bits = S.prbs7_bits(nbits)
    for k in range(8):
        tv = [(0.0, 1)]
        for n in range(k, nbits, 8):
            if (phases is not None or stuck) and stop_at is not None and t00 + (n - 3.5) * ui > stop_at:
                break                       # the streams stop with the ring
            tv.append((t00 + (n - 3.5) * ui, 1 - bits[n]))
        L.append(S.pwl_bits(f'F{k}', f'F{k}_s', tv, vdd)); L.append(f'RF{k} F{k}_s F{k} 1000')
    if ramp:      # the PWL bit sources are absolute: scale every logic input by the supply through a B source
        L = [re.sub(r'^([VB]F\d) (F\d_s) 0 ', r'\1 \2_u 0 ', l) for l in L]
        L += [f'BFS{k} F{k}_s 0 V=v(F{k}_s_u)*v(VDD)/{vdd}' for k in range(8)]
    L += ['VOVP OVP 0 0', 'VOVN OVN 0 0']
    for k in range(8):
        for b in range(mux9.NTR):
            L.append(f'VTR{k}_{b} TR{k}_{b} 0 0')
    hi = 'VDD'
    L += [f'RENM ENM {hi} 1', f'RENP ENP {hi} 1', 'VPOL POL 0 0', f'REM EN_MAIN {hi} 1', f'REQ EN_POST {hi} 1', 'VEXT EXT 0 0',
          'CAVP AVG_P 0 2p', 'CAVN AVG_N 0 2p', 'CRUN RUN 0 20f']
    L.append('XMUX ' + ' '.join(mux9.PORTS[:-6]) + ' MAIN_P MAIN_N POST_N POST_P VDD VSS wtx_mux8')
    L += [f'CLP MAIN_P 0 {cload}', f'CLN MAIN_N 0 {cload}', f'CLPQ POST_P 0 {cload}', f'CLNQ POST_N 0 {cload}']
    if ic_run and not ramp:
        L += ['.ic ' + ' '.join(f'v(xmux.DN{j})={vdd} v(xmux.DA{j})={vdd}' for j in range(4))]
    pr = ['MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'RUN', 'PH0', 'VDD'] + list(probes)
    cur = ['VDD'] + [f'v.xmux.{h}' for h in hs] + [f'v.xmux.{g}' for g in gsrc]
    vecs = ' '.join(f'v({x})' for x in pr) + ' ' + ' '.join(f'i({x})' for x in cur)
    L += ['.options reltol=1e-3 method=gear rshunt=1e10', f'.tran {tstep} {tstop:.6e} 0 {tstep}', '.control', f'save {vecs}',
          'set wr_singlescale', 'run', f'wrdata wave.txt {vecs}', '.endc', '.end']
    (work / 'tb.sp').write_text('\n'.join(L) + '\n')
    _, log = tools.ngspice_host(work, 'tb.sp', timeout=30000)
    if not (work / 'wave.txt').exists():
        return dict(tag=tag, ok=False, reason=log[-800:])
    names = pr + ['I_' + x for x in cur]
    w = tools.read_wrdata(work / 'wave.txt', names); t = w['time']
    itot = -w['I_VDD'] * 1e3
    ibank = sum(w['I_v.xmux.' + h] for h in hs) * 1e3
    o = dict(tag=tag, c=c, net=net if net == 'sch' else Path(net.split(':', 1)[1]).name, force=force, nforce=nforce, phases=phases,
             stuck=stuck or None, mid=mid, res_pp=res_pp, stop_at=stop_at, ramp=ramp, vdd=vdd, rate=rate, n_hs=len(hs))
    def avg(a, b, v):
        m = (t >= a) & (t <= b); return round(float(v[m].mean()), 4) if m.any() else None
    tend = t[-1]
    o['i_tot_end_ma'] = avg(tend - 20e-9, tend, itot); o['i_bank_end_ma'] = avg(tend - 20e-9, tend, ibank)
    o['i_bank_max_after_stop_ma'] = round(float(ibank[t > (stop_at or 0) + 2e-9].max()), 3)
    o['i_bank_max_ma'] = round(float(ibank.max()), 3)
    if stop_at:
        o['i_bank_run_ma'] = avg(8e-9, stop_at - 1e-9, ibank)
        bad = np.nonzero((t > stop_at) & (ibank >= 0.1))[0]
        o['t_bank_below_0p1_ns'] = round(float(t[bad[-1]] - stop_at) * 1e9, 1) if len(bad) else 0.0
        if len(bad) and bad[-1] >= len(t) - 2:
            o['t_bank_below_0p1_ns'] = None
    o['run_end'] = round(float(w['RUN'][-1]), 3)
    o['run_min_v'] = round(float(w['RUN'][t > 10e-9].min()), 3)
    dn = S.crossings(t, w['RUN'], th=vdd / 2, rising=False)
    dn = dn[dn > (stop_at or 0)]
    o['t_run_low_ns'] = round(float(dn[0] - (stop_at or 0)) * 1e9, 1) if len(dn) else None
    o['gate_end'] = [round(float(w['MAIN_P'][-1]), 3), round(float(w['MAIN_N'][-1]), 3)]
    gs = {}
    for g in gsrc:
        gs[g.split('_', 1)[1]] = gs.get(g.split('_', 1)[1], 0) + avg(tend - 20e-9, tend, w['I_v.xmux.' + g] * 1e3)
    for g, v in sorted(gs.items()):
        o['grp_' + g + '_ma'] = round(v, 3)
    for p in probes:
        o['p_' + p] = [round(float(w[p][-1]), 3), round(float(w[p][t > tend - 20e-9].min()), 3), round(float(w[p][t > tend - 20e-9].max()), 3)]
    if phases is None and not stuck:        # running: gate-level eye
        edges = t00 + 8 * ui * np.arange(-1, nbits // 8 + 2); edges = edges[(edges > 0) & (edges < tend)]
        o['gate'] = CH.score(t, w['MAIN_P'] - w['MAIN_N'], edges, bits, nper=8)
        o['i_tot_ma'] = avg(10e-9, tend, itot)
    (work / 'result.json').write_text(json.dumps(o, default=str))
    if not keep:
        (work / 'wave.txt').unlink()
        (work / 'mux.spice').unlink()
    return o


if __name__ == '__main__':
    print(json.dumps(run(**json.loads(sys.argv[1])), default=str), flush=True)
