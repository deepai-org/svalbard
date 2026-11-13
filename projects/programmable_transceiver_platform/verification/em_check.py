"""PD42 EM screen at 85 C junction (MANDATE EM/IR sign-off) for attached_tx_buffer and tx_steering_buffer.
Every extracted MOS finger gets a 0 V drain sense source; per-finger mean |I| and RMS come from the
operating benches (buffer: published readiness deck, held enable, MAIN on with data toggling;
steering: 2 pF at 400 MHz). M1 S/D column current = 2 x max finger current of its array (interior
column shared by two fingers; conservative: full finger current, no credit for the strap bar collecting
part of it). Limits: DRM 14.2 at 85 C, M1 2.09 mA/um (DC/average), via 0.58 mA/cut, contact 0.58 mA/cut.
Usage: em_check.py <tbuf|steer> <phys.spice> <layout.json> <outdir> [corner ...]   corner = proc:temp:vdd"""
import sys, json, re, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s
from concurrent.futures import ThreadPoolExecutor
kind, phys, lay, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]); out.mkdir(parents=True, exist_ok=True)
corners = [tuple(c.split(':')) for c in sys.argv[5:]] or [('ff', '85', '3.35'), ('typical', '85', '3.3'), ('ss', '85', '3.15')]
LIM_M1 = 2.09
def instrument(txt):
    lines, devs, inside = [], [], False
    for l in txt.splitlines():
        if l.startswith('.subckt'): inside = True
        elif l.startswith('.ends'): inside = False
        f = l.split()
        if inside and f and f[0].startswith('X') and len(f) > 5 and re.match(r'[np]fet_0[36]v[03]', f[5]):
            k = len(devs); w = float(re.search(r' w=([\d.]+)u', l).group(1)); L = float(re.search(r' l=([\d.]+)u', l).group(1))
            devs.append(dict(name=f[0], d=f[1], g=f[2], s=f[3], b=f[4], model=f[5], w=w, l=L))
            lines.append(f'VEM{k} {f[1]} em{k} 0'); f[1] = f'em{k}'; l = ' '.join(f)
        lines.append(l)
    return '\n'.join(lines), devs
def subckt(txt):
    a = txt.index('.subckt'); b = txt.index('.ends', a); return txt[a:txt.index('\n', b) + 1]
newsub, devs = instrument(subckt(phys.read_text()))
IRNETS = ('VDD', 'VSS', 'OUT', 'TOP', 'BOTTOM', 'LOCAL_OUT', 'BUFFER_COMPLEMENT_WELL')
IRNODES = sorted({q for x in devs for q in (x['d'], x['s']) if '.' in q and q.split('.')[0] in IRNETS})
top = re.search(r'^\.subckt (\S+) (.*)$', newsub, re.M); cell = top.group(1)
def deck_tbuf(p, t, v):
    G = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/termination-buffer-candidate/source-headroom/reference-reset')
    base = (G / 'connected.spice').read_text().splitlines()
    a = next(i for i, l in enumerate(base) if l.startswith('.subckt buffer_compensated_flat'))
    b = next(i for i in range(a, len(base)) if base[i].startswith('.ends'))
    lines = base[:a] + newsub.splitlines() + base[b + 1:]
    ON = lambda t0: f'PWL(0n 0 {t0}n 0 {t0+0.02}n {v} 3000n {v})'
    o = []
    for l in lines:
        f = l.split(' ', 1)[0]
        if f == 'VDD': l = f'VDD VDD 0 PWL(0n 0 10n {v} 3000n {v})'
        elif f == 'VPULL': l = f'VPULL PULL 0 {v}'
        elif f == 'VTX_RESET': l = 'VTX_RESET TX_RESET 0 PWL(0n 0 1n 0 1.02n 3.3 20n 3.3 20.02n 0 3000n 0)'
        elif f == 'VTX_QUALIFIED': l = 'VTX_QUALIFIED TX_QUALIFIED 0 ' + ON(22)
        elif f == 'VBUF_REQUEST': l = 'VBUF_REQUEST BUF_REQUEST VSS ' + ON(78)
        elif f == 'VTERM_ENABLE': l = 'VTERM_ENABLE REQ_TERM_ENABLE 0 ' + ON(78)
        elif f == 'VEN_MAIN': l = 'VEN_MAIN REQ_EN_MAIN 0 PWL(0n 0 78n 0 78.02n 1 3000n 1)'
        elif f in ('VEN_POST', 'VEN_DETECT', 'VEN_TMDS'): l = f'{f} ' + l.split()[1] + ' 0 0'
        elif f == 'VTRAFFIC_READY': l = 'VTRAFFIC_READY TRAFFIC_READY 0 0'
        elif l.startswith('tran '): l = 'tran 20p 700n'
        elif l.startswith('wrdata '): l = 'wrdata OUT v(TERM_VCM) ' + ' '.join(f'i(v.xbuf.vem{k})' for k in range(len(devs))) + ((' v(VDD) v(VSS) v(TERM_VCM) ' + ' '.join(f'v(xbuf.{q})' for q in IRNODES)) if IRNODES else '')
        o.append(l)
    return '\n'.join(o) + '\n', 300e-9
# Use case (PD42): 3.24 Gb/s (fastest wired rate) at transition density 0.5 = 810 MHz square; load = the 8 selector
# gates the buffer drives in tx_protected_pad (nfet_03v3 20/0.28, extracted txpad) + 0.5 pF assumed assembly route.
USE = ''.join(f'XG{k} 0 OUT 0 0 nfet_03v3 w=20u l=0.28u\n' for k in range(8)) + 'CR OUT 0 0.5p\nVIN IN 0 PULSE(0 {v} 1n 50p 50p 567p 1234.6p)\n'
def deck_steer(p, t, v):
    S = s.SCRATCH
    ports = top.group(2).split(); conn = {'VDD': 'VDD', 'VSS': '0', 'IN': 'IN', 'OUT': 'OUT'}
    d = (f'* steer em\n.include {S}/transceiver-pad-pdk/ngspice/design.ngspice\n.lib {S}/transceiver-pad-pdk/ngspice/sm141064.ngspice typical\n'
         f'.lib {S}/transceiver-pad-pdk/ngspice/sm141064.ngspice res_typical\n.lib {S}/transceiver-pad-pdk/ngspice/sm141064.ngspice diode_typical\n'
         f'.lib {S}/transceiver-pad-pdk/ngspice/sm141064.ngspice mimcap_typical\n.temp 27\n' + newsub +
         f'\nVDD VDD 0 {v}\n' + (USE.replace('{v}', str(v)) if kind == 'steer_use' else f'VIN IN 0 PULSE(0 {v} 1n 50p 50p 1.2n 2.5n)\nCL OUT 0 2p\n') + 'XS ' + ' '.join(conn[q] for q in ports) + f' {cell}\n')
    d += '.control\nset wr_singlescale\nset wr_vecnames\ntran 1p 22n\nwrdata OUT v(OUT) ' + ' '.join(f'i(v.xs.vem{k})' for k in range(len(devs))) + '\nquit\n.endc\n.end\n'
    return d, 2e-9
def job(c):
    p, t, v = c; name = f'{kind}_{p}_{t}_{v}'
    d, t0 = (deck_tbuf if kind == 'tbuf' else deck_steer)(p, t, v)
    d = s.corner(d, p, int(t)).replace('wrdata OUT', f'wrdata {out}/{name}.dat')
    x = s.run(out, name, d, timeout_s=20000)
    tt = x[:, 0]; m = tt >= (tt[-1] - t0); nd = len(devs); cur = x[:, 2:2 + nd]; vv = x[:, 2 + nd:]
    dt = np.gradient(tt[m]); T = dt.sum()
    mean = np.abs((cur[m] * dt[:, None]).sum(0) / T); mabs = (np.abs(cur[m]) * dt[:, None]).sum(0) / T
    rms = np.sqrt((cur[m] ** 2 * dt[:, None]).sum(0) / T); peak = np.abs(cur[m]).max(0)
    ir = {}
    if kind == 'tbuf' and IRNODES:
        ref = {'VDD': vv[:, 0], 'VSS': vv[:, 1], 'OUT': vv[:, 2]}
        avg = lambda y: float((y[m] * dt).sum() / T)
        for net in IRNETS:
            cols = [3 + i for i, q in enumerate(IRNODES) if q.split('.')[0] == net]
            if not cols: continue
            vals = [avg(vv[:, c]) for c in cols]
            ir[net] = dict(terminals=len(cols), spread_mV=round((max(vals) - min(vals)) * 1e3, 2),
                           max_drop_from_port_mV=round(max(abs(q - avg(ref[net])) for q in vals) * 1e3, 2) if net in ref else None)
    return name, dict(ir=ir, mean=mean.tolist(), mean_abs=mabs.tolist(), rms=rms.tolist(), peak=peak.tolist(), v_out_end=float(x[-1, 1]))
with ThreadPoolExecutor(int(__import__('os').environ.get('EM_JOBS', '2'))) as ex:
    res = dict(ex.map(job, corners))
units = json.loads(lay.read_text())['units']
def key(model, w, l, d, g, sn, b):
    n = lambda q: q.split('.')[0]   # extresist terminal nodes NET.tK
    return (model, round(w, 3), round(l, 3), n(g), n(b), frozenset((n(d), n(sn))))
report = dict(scope=__doc__, limits=dict(metal1_ma_per_um_85c=LIM_M1, via_cut_ma_85c=.58, source='DRM 14.2 (strap_capacity.py)'), corners={})
for name, r in res.items():
    rows = []
    for u in units:
        if len(u['nodes']) != 4 or not u['model'].startswith(('nfet', 'pfet')): continue
        d, g, sn, b = u['nodes']; kk = key(u['model'], u['w_um'], u['l_um'], d, g, sn, b)
        idx = [k for k, x in enumerate(devs) if key(x['model'], x['w'], x['l'], x['d'], x['g'], x['s'], x['b']) == kk]
        if not idx: raise SystemExit(f'no extracted devices for unit {u}')
        imax = max(r['mean_abs'][k] for k in idx) * 1e3; irms = max(r['rms'][k] for k in idx) * 1e3; ipk = max(r['peak'][k] for k in idx) * 1e3
        wcol = u['m1_column_um'] or 0.23        # singles: PCell 0.23 um M1 strip
        col = (2 if u['nf'] > 1 else 1) * imax
        frac = u.get('m1_max_fraction') or (.62 if u['nf'] > 1 else 1.0)   # PD40 non-power bars: S bar at .62h -> <= .62
        pin_mA = u['nf'] * imax                     # all fingers of the array through one D (or S) pin
        pin_frac = None if u['power'] else round(pin_mA / .58, 3)   # single-cut via stack per pin (0.58 mA/cut, 85 C)
        rows.append(dict(power_strapped=u['power'], pin_mA=round(pin_mA, 4), pin_single_cut_fraction=pin_frac, m1_max_fraction=frac, column_dist_ma_per_um=round(frac * col / wcol, 3), fraction_of_85c_limit_distributed=round(frac * col / wcol / LIM_M1, 3), unit=u['unit'], model=u['model'], nf=u['nf'], nodes=u['nodes'], m1_column_um=wcol, finger_mean_abs_mA=round(imax, 4), finger_rms_mA=round(irms, 4), finger_peak_mA=round(ipk, 3),
                         column_mA=round(col, 4), column_ma_per_um=round(col / wcol, 3), fraction_of_85c_limit=round(col / wcol / LIM_M1, 3),
                         column_rms_ma_per_um=round((2 if u['nf'] > 1 else 1) * irms / wcol, 3)))
    worst = max(rows, key=lambda q: q['fraction_of_85c_limit'])
    worst_d = max(rows, key=lambda q: q['fraction_of_85c_limit_distributed'])
    worst_pin = max(rows, key=lambda q: q['pin_single_cut_fraction'] or 0)
    # M5 trunks: port nets carry the sum of their devices' currents, internal nets at most half of it (source = sink)
    lay_j = json.loads(lay.read_text()); tw = lay_j.get('trunk_widths_um', {})
    ports = ('VDD', 'VSS', 'OUT', 'REF', 'BIAS', 'ENABLE', 'IN')
    trunk = {}
    for net, wdt in tw.items():
        tot = sum(r['mean_abs'][k] for k, x in enumerate(devs) if net in (x['d'].split('.')[0], x['s'].split('.')[0])) * 1e3
        i_tr = tot if net in ports else tot / 2
        trunk[net] = dict(width_um=wdt, current_mA=round(i_tr, 3), ma_per_um=round(i_tr / wdt, 3), fraction_of_85c_limit=round(i_tr / wdt / 4.5, 3))
    # PD46 review: strap segments (trunk -> array gap included), every via level, COMP contacts.
    # I_bar = pin current (nf x worst finger mean|I|) / bars of that pin x 1.2 (bar imbalance allowance);
    # STRAP_LAYERS metal layers share it evenly (3 = M2+M3+M4 with via2/via3 along the whole strap; 1 = M4-only old layout).
    import os as _os
    SL = int(_os.environ.get('STRAP_LAYERS', '3')); cut = lambda a: max(1, int((a - .26) // .52) + 1)
    lj = json.loads(lay.read_text()); straps = lj.get('power_straps', []); tw_ = lj.get('trunk_widths_um', {})
    urow = {q['unit']: q for q in rows}
    nb = {}
    for st in straps: nb[(st['unit'], st['net'])] = nb.get((st['unit'], st['net']), 0) + 1
    srows = []
    for st in straps:
        q = urow.get(st['unit'])
        if q is None: continue
        x0, y0, x1, y1 = st['strap_um']; h = y1 - y0; L = x1 - x0
        sib = [s_['strap_um'][3] - s_['strap_um'][1] for s_ in straps if (s_['unit'], s_['net']) == (st['unit'], st['net'])]
        # Imbalance rule (coordinator decision 2026-11-12, reviews r2/r3): no allowance for a single bar; 1.2x for several bars
        # (equal height is not enough: bars on one trunk see unequal trunk paths, r3 measured 1.09-1.13x). Sign-off stays pessimistic: 85 C and ff, outside the 22-32 C operating window.
        kimb = 1.0 if len(sib) == 1 else 1.2   # r3: bars sharing a trunk get unequal trunk paths -> only a single bar is exempt
        ib = q['nf'] * q['finger_mean_abs_mA'] / nb[(st['unit'], st['net'])] * kimb
        v4 = cut(tw_.get(st['net'], 8.) - .6) * cut(h - .6); v23 = cut(L - .6) * cut(h - .6)
        ncol = q['nf'] // 2 + 1; v1 = cut(h - .4)
        col = (2 if q['nf'] > 1 else 1) * q['finger_mean_abs_mA']
        ncont = cut({u_['unit']: u_['w_um'] for u_ in units}[st['unit']] - .3)
        if SL > 1:   # PD46 review r2: via4 feeds from M4 only -> per-bar ladder for the peak M4 share and via crowding
            import em_strap_ladder as _sl
            m4s, v4k, v23pk = _sl.worst(x0, tw_.get(st['net'], 8.), x1, h, ib)
        else: m4s, v4k, v23pk = 1., 1., 0.
        srows.append(dict(unit=st['unit'], net=st['net'], bar_h_um=round(h, 2), length_um=round(L, 2), bar_mA=round(ib, 3), imbalance=kimb, layers=SL,
                          m4_peak_share=round(m4s, 3), via4_crowding=round(v4k, 2),
                          metal_frac=round(ib * m4s / h / LIM_M1, 3), via4_frac=round(ib / v4 / .58 * v4k, 3),
                          via23_frac=round(v23pk / .58, 3),
                          via1_frac=round(col / v1 / .58, 3), contact_frac=round(col / ncont / .58, 3)))
    sw = {k: max(srows, key=lambda r_: r_[k]) for k in ('metal_frac', 'via4_frac', 'via23_frac', 'via1_frac', 'contact_frac')} if srows else {}
    print(name, 'STRAP', {k: (v[k], v['unit'], v['net']) for k, v in sw.items()}, flush=True)
    report['corners'][name] = dict(strap_rows=srows, strap_worst={k: v[k] for k, v in sw.items()}, ir_mean_window=r.get('ir'), worst_pin_cut_fraction=worst_pin['pin_single_cut_fraction'], worst_pin_unit=worst_pin['unit'], worst_fraction_distributed=worst_d['fraction_of_85c_limit_distributed'], worst_unit_distributed=worst_d['unit'], m5_trunks=trunk, worst_fraction=worst['fraction_of_85c_limit'], worst_unit=worst['unit'], rows=rows, v_out_end=r['v_out_end'],
                                   total_mean_abs_mA_by_unit={str(q['unit']): round(q['finger_mean_abs_mA'] * q['nf'], 3) for q in rows})
    print(name, 'distributed worst', worst_d['fraction_of_85c_limit_distributed'], 'unit', worst_d['unit'], 'pin', worst_pin['pin_single_cut_fraction'], worst_pin['unit'], 'trunk worst', max((v['fraction_of_85c_limit'], k) for k, v in trunk.items()) if trunk else None, 'IR', r.get('ir'))
    print(name, 'worst', worst['fraction_of_85c_limit'], 'unit', worst['unit'], worst['model'], worst['nodes'], worst['column_ma_per_um'], 'mA/um', flush=True)
(out / f'em-{kind}.json').write_text(json.dumps(report, indent=1))
