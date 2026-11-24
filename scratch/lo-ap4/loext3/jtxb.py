"""Joint bench for the pt_lo_ext revision (copy of ../mw20/joint.py, same deck and method: extracted rxmix_i / rxmix_q,
RF source and loads as rf_rx/tb.py rxmix_tran, IF 5 MHz, window 300-700 ns, LO 2.4 GHz), extended by: explicit supply,
tank common mode, external modes, mode 0.  ONE ngspice at a time (sequential).
usage: joint3.py <tag> <lo_ext netlist (.ext.spice, or - for sq)> case...
  case = kind:corner:vdd[:k=v...]   corner tt (27 C) | ss (32 C) | ff (22 C)
  kind: sq (ideal 0/VDD square on the mixer LO pins) | int (lo_mode 2) | cml (lo_mode 3) | pas (lo_mode 1) | off (lo_mode 0)
  keys: amp (tank V per side, 0.58) cm (tank CM V, 1.7) vpp (external source Vpp per leg, open circuit behind 50 ohm, 2.0)
        vb (force ATB_VB)
Mixer netlists: snapshot snap3/ of analog/rf_rx/generated at first use (md5 recorded in every result)."""
import sys, json, math, re, shutil, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
T = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T); sys.path.insert(0, T + '/lcvco')
import timing_flow as tf
import run_timing as rt
import run_loop as rl
RX = Path(T).parent / 'rf_rx' / 'generated'
HERE = Path(__file__).resolve().parent
tag, loext = sys.argv[1], Path(sys.argv[2]).resolve()
TEMP = dict(tt=27, ss=32, ff=22)
import os
FLO, FIF, AMP = 2.4e9, 5e6, 0.01
T0, T1 = 300e-9, 700e-9   # whole IF periods, in band (REVIEW-mw20 B2)
SNAP = HERE / 'snap3'      # snapshot of the rf_rx mixers (snap: 18:47 tree with hib pin; snap2: 22:58 tree)
SNAP.mkdir(exist_ok=True)
for b in ('rxmix_i', 'rxmix_q'):          # snapshot of the rf_rx working tree (its owner is editing): sha recorded
    if not (SNAP / f'{b}.ext.spice').exists():
        shutil.copy(RX / f'{b}.ext.spice', SNAP / f'{b}.ext.spice')
md5 = lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest()
_ports = (SNAP / 'rxmix_i.ext.spice').read_text().replace('\n+', ' ').split('.subckt pt_rxmix_i ')[1].split('\n')[0].split()
HIB = ' en' if 'hib' in _ports else ''       # older mixer netlists have a hib pin (RX state = high)
assert len(_ports) == (20 if HIB else 19), _ports

def tone(t, v, f):
    re_ = im = 0.0
    w = 2 * math.pi * f
    for i in range(len(t) - 1):
        dt = t[i + 1] - t[i]
        re_ += .5 * dt * (v[i] * math.cos(w * t[i]) + v[i + 1] * math.cos(w * t[i + 1]))
        im += .5 * dt * (v[i] * math.sin(w * t[i]) + v[i + 1] * math.sin(w * t[i + 1]))
    return 2 * math.hypot(re_, im) / (t[-1] - t[0])

def one(case):
    f = case.split(':')
    kind, corner, v = f[0], f[1], float(f[2])
    kw = dict(amp=0.58, cm=1.7, vpp=2.0, vb=None, line=0.0, buf=1)
    kw.update({kv.split('=')[0]: float(kv.split('=')[1]) for kv in f[3:]})
    a, vb, temp = kw['amp'], kw['vb'], TEMP[corner]
    name = case.replace(':', '_').replace('=', '')
    wd = HERE / 'jruns' / tag / name
    if (wd / 'result.json').exists():
        return json.loads((wd / 'result.json').read_text())
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    inc = ''
    for b in ('rxmix_i', 'rxmix_q'):
        (wd / f'{b}.spice').write_text(tf.uniquify_subckts((SNAP / f'{b}.ext.spice').read_text(), b, keep=(f'pt_{b}',)))
        inc += f'.include {b}.spice\n'
    per = 1 / FLO
    if kind == 'sq':
        lo = ''.join(f'V{n} {n} 0 PULSE({lo_} {hi} {d} 20p 20p {per / 2 - 20e-12} {per})\n'
                     for n, lo_, hi, d in (('loip', 0, v, 0), ('loin', v, 0, 0), ('loqp', 0, v, per / 4), ('loqn', v, 0, per / 4)))
    elif kind == 'sine':
        vb = vb if vb is not None else 0.739 * v
        lo = ''.join(f'V{n} {n} 0 SIN({vb} {s * a} {FLO} 0 0 {ph})\n' for n, s, ph in (('loip', 1, 0), ('loin', -1, 0), ('loqp', 1, -90), ('loqn', -1, -90)))
    else:
        t = rt.rg_wrap_locml(loext.read_text())
        (wd / 'lo_ext.spice').write_text(tf.uniquify_subckts(t, 'loext', keep=('pt_lo_ext', 'ct_locml', 'ct_locml_core')))
        inc += '.include lo_ext.spice\n'
        q = 0.25 / FLO
        legs = (('ip', 1, 0), ('in', -1, 0), ('qp', 1, q), ('qn', -1, q))
        if kind == 'int':
            lo = ''.join(f'VLI{n} loi{n} 0 sin({kw["cm"]} {s * a} {FLO} 0 0 {-ph * FLO * 360})\nRP{n} pad{n} 0 50\n' for n, s, ph in legs)
        else:       # external source as run_timing.tb_lo_ext: 50 ohm, 100 pF board coupling, 1 pF pad; QVCO off (tank nodes 0 V)
            av = kw['vpp'] / 2
            lo = ''.join(f'VS{n} s{n} 0 sin(0 {s * av} {FLO} 0 0 {-ph * FLO * 360})\nRS{n} s{n} b{n} 50\nCB{n} b{n} pad{n} 100p\nCP{n} pad{n} 0 1p\n'
                         f'VLI{n} loi{n} 0 0\n' for n, s, ph in legs)
        # TX-mixer LO route (2026-11-23): shielded Metal4 line, `line` mm, 10 RC sections per leg, 90 ohm/mm (1 um M4,
        # 0.09 ohm/sq) and 180 fF/mm to the shields; TX gate load at the far end (the RX mixers stay at the lo_ext node)
        L_ = kw['line']
        for n in ('ip', 'in', 'qp', 'qn'):
            if L_ > 0:
                prev = f'lo{n}'
                for k in range(10):
                    nxt = f't{n}' if k == 9 else f't{n}_{k}'
                    lo += f'RL{n}{k} {prev} {nxt} {90 * L_ / 10:.4g}\nCL{n}{k} {nxt} 0 {180e-15 * L_ / 10:.4g}\n'
                    prev = nxt
            else:
                lo += f'RL{n} lo{n} t{n} 1m\n'
            lo += f'XTX{n} txd o{n} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCW{n} o{n} 0 22f\n'
        if kw.get('buf', 1):
            lo += 'XTB tip tin tqp tqn oip oin oqp oqn vdd 0 pt_lo_txbuf\n'
            if kw.get('ext'):   # published extracted cell (generated/lo_txbuf.ext.spice) instead of the schematic
                (wd / 'lo_txbuf.spice').write_text(tf.uniquify_subckts(Path(os.environ.get('TXBUF_EXT', str(Path(T, 'generated', 'lo_txbuf.ext.spice')))).read_text(), 'lo_txbuf', keep=('pt_lo_txbuf',)))   # p_* names collide with lo_ext / rxmix primitives
            else:
                for f_ in ('lo_txbuf.spice', 'timing_cells.spice'):
                    (wd / f_).write_text(Path(T, f_).read_text())
            inc += '.include lo_txbuf.spice\n'
        else:
            lo += ''.join(f'RB{n} t{n} o{n} 1m\n' for n in ('ip', 'in', 'qp', 'qn'))
        lo += 'EDI zdi 0 oip oin 1\nEDQ zdq 0 oqp oqn 1\nEDL zdl 0 tip tin 1\nEDR zdr 0 loip loin 1\n'
        ext, inn, cs = dict(int=(0, v, 0), cml=(v, v, v), pas=(v, 0, 0), off=(0, 0, 0))[kind]
        lo += f'VTXD txd 0 2.5\nVTXS txs 0 1.0\nVEXT ext 0 {ext}\nVINT int 0 {inn}\nVCS cmlsel 0 {cs}\n'
        lo += 'X1 padip padin padqp padqn loiip loiin loiqp loiqn ext int cmlsel loip loin loqp loqn vb vdd 0 pt_lo_ext\n'
        if vb is not None:      # force the LO common-mode target through ATB_VB (the cell exposes it for this)
            lo += f'VVBF vb 0 {vb}\n'
    mix = ''
    for m, (lp, ln) in dict(i=('loip', 'loin'), q=('loqp', 'loqn')).items():
        mix += (f'Rsp{m} sp rp{m} 300\nRsn{m} sn rn{m} 300\nCcp{m} rp{m} rf_p{m} 4p\nCcn{m} rn{m} rf_n{m} 4p\n'
                f'Ib{m} vib ibias{m} 10u\n'
                f'XM{m} rf_p{m} rf_n{m} {lp} {ln} bb_p{m} bb_n{m} ibias{m} en 0 0 0 0 0 0 0 atb_vcm{m} atb_vbp{m}{HIB} vdd 0 pt_rxmix_{m}\n'
                f'Cbp{m} bb_p{m} 0 1p\nCbn{m} bb_n{m} 0 1p\n')
    deck = rl.header(corner, temp).replace('reltol=1e-3', 'reltol=1e-4') + inc + f"""VDD vdd 0 {v}
Vibs vib 0 3.3
Ven en 0 {v}
Vs s 0 DC 0 SIN(0 {AMP} {FLO + FIF})
Ep sp 0 s 0 0.5
En sn 0 s 0 -0.5
{lo}{mix}.save v(bb_pi) v(bb_ni) v(bb_pq) v(bb_nq) v(loip) v(loin) v(loqp) v(loqn) i(VDD) v(vb) v(zdi) v(zdq) v(zdl) v(zdr) v(oip) v(oqp)
.measure tran opp pp v(zdi) from={T0} to={T1}
.measure tran omax max v(oip) from={T0} to={T1}
.measure tran omin min v(oip) from={T0} to={T1}
.measure tran oqmax max v(oqp) from={T0} to={T1}
.measure tran oqmin min v(oqp) from={T0} to={T1}
.measure tran linepp pp v(zdl) from={T0} to={T1}
.measure tran rxpp pp v(zdr) from={T0} to={T1}
.measure tran ti1 when v(zdi)=0 rise=1 td={T0}
.measure tran ti2 when v(zdi)=0 rise=11 td={T0}
.measure tran tif when v(zdi)=0 fall=1 td={T0}
.measure tran tq1 when v(zdq)=0 rise=1 td={T0}
.tran 5p {T1} {T0 - 2e-9} 5p
.control
run
linearize v(bb_pi) v(bb_ni) v(bb_pq) v(bb_nq) v(loip) v(loin) v(loqp) v(loqn) i(VDD)
wrdata out.dat v(bb_pi)-v(bb_ni) v(bb_pq)-v(bb_nq) v(loip) v(loin) v(loqp) v(loqn) i(VDD)
.endc
.end
"""
    m = tf.ngspice(wd, 'j', deck, timeout=6 * 3600)
    r = dict(case=case, tag=tag, kind=kind, corner=corner, temp_c=temp, vdd=v, tank_amp_v=a if kind == 'int' else None, tank_cm_v=kw['cm'] if kind == 'int' else None,
             ext_vpp=kw['vpp'] if kind in ('cml', 'pas', 'off') else None, vb_forced=vb, errors=m['_errors'][:3],
             if_hz=FIF, window_s=[T0, T1], mixer_snapshot=SNAP.name,
             md5=dict(lo_ext=md5(loext) if kind != 'sq' else None, rxmix_i=md5(SNAP / 'rxmix_i.ext.spice'), rxmix_q=md5(SNAP / 'rxmix_q.ext.spice')))
    try:
        rows = [[float(x) for x in l.split()] for l in (wd / 'out.dat').read_text().splitlines() if l.strip()]
        rows = [x for x in rows if T0 <= x[0] <= T1]
        t = [x[0] for x in rows]
        col = lambda k: [x[2 * k + 1] for x in rows]
        ai, aq = tone(t, col(0), FIF), tone(t, col(1), FIF)
        lop, lon = col(2), col(3)
        vs = v / 2
        last = [i for i, x in enumerate(t) if x >= T1 - 4e-9]
        r.update(if_amp_i_v=ai, if_amp_q_v=aq, gain_i_db=20 * math.log10(ai / AMP), gain_q_db=20 * math.log10(aq / AMP),
                 lo_max_v=max(lop[i] for i in last), lo_min_v=min(lop[i] for i in last), lo_avg_v=sum(lop[i] for i in last) / len(last),
                 vgs_on_v=max(lop[i] for i in last) - vs, vgs_off_v=min(lop[i] for i in last) - vs,
                 duty_above_avg=sum(1 for i in last if lop[i] > sum(lop[j] for j in last) / len(last)) / len(last))
        import cmath
        nl = int(round(24 / FLO / 5e-12))           # 24 LO periods = 10 ns on the 5 ps grid
        seg = rows[-nl:]
        fz = lambda k: 2 * sum(x[2 * k + 1] * cmath.exp(-2j * math.pi * FLO * x[0]) for x in seg) / nl
        fi, fq = fz(2) - fz(3), fz(4) - fz(5)
        col_ = lambda k: [x[2 * k + 1] for x in seg]
        r.update(lo_vpp_ip=max(col_(2)) - min(col_(2)), lo_vpp_in=max(col_(3)) - min(col_(3)), lo_vpp_qp=max(col_(4)) - min(col_(4)),
                 lo_vpp_qn=max(col_(5)) - min(col_(5)), lo_fund_i_diff_v=abs(fi), lo_fund_q_diff_v=abs(fq),
                 q_minus_i_deg=(math.degrees(cmath.phase(fq / fi)) + 180) % 360 - 180 if abs(fi) > 1e-6 else None,
                 i_vdd_total_ma=-1e3 * sum(col_(6)) / len(seg))
        hw = len(rows) // 2
        r['gain_i_half_db'] = [20 * math.log10(tone([x[0] for x in h_], [x[1] for x in h_], FIF) / AMP) for h_ in (rows[:hw + 1], rows[hw:])]
    except Exception as e:
        r['error'] = repr(e)
    per = (m['ti2'] - m['ti1']) / 10 if m.get('ti2') and m.get('ti1') else None
    r.update(out_i_max_v=m.get('omax'), out_i_min_v=m.get('omin'), out_q_max_v=m.get('oqmax'), out_q_min_v=m.get('oqmin'), out_diff_pp_v=m.get('opp'),
             line_diff_pp_v=m.get('linepp'), rx_lo_diff_pp_v=m.get('rxpp'), f_out_hz=(1 / per if per else None),
             duty_i=(((m['tif'] - m['ti1']) % per) / per if per and m.get('tif') else None),
             q_minus_i_deg=((((m['tq1'] - m['ti1']) / per) * 360 + 180) % 360 - 180 if per and m.get('tq1') else None),
             line_mm=kw['line'], buf=kw.get('buf', 1))
    (wd / 'result.json').write_text(json.dumps(r, indent=1))
    return r

for c_ in sys.argv[3:]:
    r = one(c_)
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ('md5', 'tag')}), flush=True)
