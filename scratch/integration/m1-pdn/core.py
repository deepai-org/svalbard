"""Shared machinery for the M1 runs: full netlist with taps, ports, transfer impedances, DC and decap plans."""
import numpy as np, json
import model as M, loads as LD
VICT = {'core_bias': ('core_bias', None), 'por': ('por', None), 'adc_i': ('adc_i', 'conv'), 'refbuf': ('refbuf', 'conv'),
        'qvco': ('qvco', 'pll'), 'pll_vreg2': ('pll_vreg2', 'pll'), 'lna': ('lna', 'rf'), 'slicer': ('slicer', 'wired')}
PORTS = ['dig', 'd2h0', 'd2h1', 'wrx', 'wtx', 'adc', 'rfd', 'lo']
TAU_MOS = 42.0*3.63e-12      # s: pt_decap_tile ESR x C at 100 MHz (analog/decap/generated/sim-results.json)
FILL_DENS = 0.541e-15        # F/um2 measured library fillcap (verification/digital_hardening/decap check-summary.json)

def decap_plan(kind, total_nF=0.0, tau_mim=5e-12, dig_fill_nF=0.45, frac=0.30):
    """Returns the decap lump list. kind: none | uniform (MOS tiles spread over the analog core) | digital (MOS in/at the
    macro) | ap49 (MIM over block outlines, weighted by outline area, + digital fillcap) | mim_uniform."""
    d = []
    ana = [(i, j) for i in range(M.NX) for j in range(M.NY) if not M.in_dig(i, j)]
    dig = [(i, j) for i in range(M.NX) for j in range(M.NY) if M.in_dig(i, j)]
    xy = lambda ij: (M.CORE[0]+ij[0]*M.PX, M.CORE[1]+ij[1]*M.PY)
    if kind in ('uniform', 'mim_uniform') and total_nF > 0:
        c = total_nF*1e-9/len(ana); tau = TAU_MOS if kind == 'uniform' else tau_mim
        d += [(*xy(a), c, tau/c) for a in ana]
    if kind == 'digital' and total_nF > 0:
        c = total_nF*1e-9/len(dig); d += [(*xy(a), c, TAU_MOS/c) for a in dig]
    if kind == 'ap49':
        excl = ('qvco', 'lc_load_rsv', 'adc_i', 'adc_q', 'bbfilter_i', 'bbfilter_q')
        blk = {k: v for k, v in M.FP['placed'].items() if k not in excl and not k.startswith('leaf')}
        area = {k: v['w']*v['h'] for k, v in blk.items()}; tot = sum(area.values())
        cm = 5.7e-9*frac/0.999   # 2.86 mm2 x 2 fF/um2 = 5.7 nF at 100 %; AP4-9 counts >= 30 % usable
        for k, a in area.items():
            c = cm*a/tot; r = blk[k]['rect']; d.append(((r[0]+r[2])/2, (r[1]+r[3])/2, c, tau_mim/c))
        c = dig_fill_nF*1e-9/len(dig); d += [(*xy(a), c, TAU_MOS/c) for a in dig]
    return d

def full(p, decap=None, x_feed=0.0, **kw):
    """Build the netlist, create every tap, return (net, info, ports, victims). ports[name] = RHS column for 1 A drawn."""
    n, info = M.build(p, decap=decap, **kw)
    hs = kw.get('host_split')
    taps = {}
    for b, (t, isl) in LD.MAP.items():
        taps[(t, isl)] = M.tap(n, p, t if isl else t, isl) if isl else M.tap(n, p, t, None)
        taps.setdefault(t, taps[(t, isl)])
    for t, isl in (('wrx_cap', 'wired'), ('lo_ext', 'pll'), ('polyphase', 'pll'), ('qvco', 'pll'), ('pll_vreg2', 'pll'), ('por', None)):
        taps[t] = M.tap(n, p, t, isl); taps[(t, isl)] = taps[t]
    info['taps'] = taps
    dg = info['dig_nodes']; N = len(n.names)
    def col(entries):
        x = np.zeros(N, complex)
        for nm, v in entries:
            k = n.idx[nm]
            if k >= 0: x[k] += v
        return x
    def load(t, a=1.0): return [(taps[t][0], -a), (taps[t][1], a)]
    south = [(i, 0) for i in range(M.NX)]
    hv = (lambda ij: 'hv') if hs else (lambda ij: M.vn(*ij)); hg = (lambda ij: 'hg') if hs else (lambda ij: M.gn(*ij))
    ports = {
        'dig': col([(M.vn(*a), -1/len(dg)) for a in dg]+[(M.gn(*a), 1/len(dg)) for a in dg]),
        # D2H: rising edges draw from VDD (70 % leaves through the signal bonds to the board load, 30 % charges the pad
        # capacitance to VSS); falling edges half a period later return the 70 % into VSS. even n: +1.0, odd n: 0.3-0.7.
        'd2h0': col([(hv(a), -1/len(south)) for a in south]+[(hg(a), 1.0/len(south)) for a in south]),
        'd2h1': col([(hv(a), -1/len(south)) for a in south]+[(hg(a), -0.4/len(south)) for a in south]),
        'wrx': col(load('wrx_cap')), 'wtx': col(load('wiredtx')),
        'adc': col(load('adc_i', 0.5)+load('adc_q', 0.5)),
        # rfdriver: fraction x_feed of the current arrives from the board through the RF_TX pad chokes (not through the
        # die VDD) and returns through die VSS; the rest is drawn from the rf island.
        'rfd': col([(taps['rfdriver'][0], -(1-x_feed)), (taps['rfdriver'][1], 1.0)]),
        'lo': col(load('lo_mmd')),
    }
    vict = {k: taps[t] for k, (t, isl) in VICT.items()}
    info['south'] = south; info['hv'] = hv; info['hg'] = hg
    return n, info, ports, vict

def transfer(n, info, ports, vict, freqs):
    """Zd[f, victim, port] = differential rail (vdd tap - vss tap) per amp; Zg = vss tap vs board ground per amp.
    Extra victim 'dig' = mean over the macro nodes."""
    names = list(vict)+['dig', 'host']; R = np.stack([ports[k] for k in PORTS], axis=1)
    Zd = np.zeros((len(freqs), len(names), len(PORTS)), complex); Zg = np.zeros_like(Zd)
    dg = info['dig_nodes']
    for a, f in enumerate(freqs):
        V = n.solve(2*np.pi*f, R)
        for b, k in enumerate(names):
            if k == 'dig':
                vv = np.mean([V[n.idx[M.vn(*q)]] for q in dg], axis=0); vg = np.mean([V[n.idx[M.gn(*q)]] for q in dg], axis=0)
            elif k == 'host':   # D2H driver rail at the south pad row (or the split host rail)
                so = info['south']
                vv = np.mean([V[n.idx[info['hv'](q)]] for q in so], axis=0); vg = np.mean([V[n.idx[info['hg'](q)]] for q in so], axis=0)
            else:
                vv = V[n.idx[vict[k][0]]]; vg = V[n.idx[vict[k][1]]]
            Zd[a, b] = vv-vg; Zg[a, b] = vg
    return names, Zd, Zg

def dc(n, info, case, level, vsrc=3.267, x_feed=0.0):
    """Static solve. Returns per-tap rail voltage, bond currents, totals."""
    out, idig, ihost, m, rdir = LD.dc_loads(case, level)
    e = [('car', vsrc/0.020)]; dg = info['dig_nodes']; taps = info['taps']
    for a in dg: e += [(M.vn(*a), -idig*1e-3/len(dg)), (M.gn(*a), idig*1e-3/len(dg))]
    for a in info['south']: e += [(info['hv'](a), -ihost*1e-3/len(info['south'])), (info['hg'](a), ihost*1e-3/len(info['south']))]
    for b, t, isl, ma in out:
        xf = x_feed if b == 'rfdriver' else 0.0
        e += [(taps[(t, isl)][0], -ma*1e-3*(1-xf)), (taps[(t, isl)][1], ma*1e-3)]
    V = n.solve(0.0, n.inj(e)).real
    res = {}
    for b, t, isl, ma in out:
        tp = taps[(t, isl)]
        res[b] = dict(tap=t, island=isl, mA=ma, rail=float(V[n.idx[tp[0]]]-V[n.idx[tp[1]]]),
                      vss_mV=float(V[n.idx[tp[1]]]*1e3), vdd_drop_mV=float((vsrc-V[n.idx[tp[0]]])*1e3))
        if isl:
            sx, sy = M.centre(f'isw_{isl}'); i, j = M.near(sx, sy)
            res[b].update(pre_switch_mV=float((vsrc-V[n.idx[M.vn(i, j)]])*1e3),
                          switch_mV=float((V[n.idx[M.vn(i, j)]]-V[n.idx[f'isl_{isl}']])*1e3),
                          strap_mV=float((V[n.idx[f'isl_{isl}']]-V[n.idx[tp[0]]])*1e3))
    res['digital'] = dict(tap='digital', island=None, mA=idig,
                          rail=float(min(V[n.idx[M.vn(*a)]]-V[n.idx[M.gn(*a)]] for a in dg)), vss_mV=float(max(V[n.idx[M.gn(*a)]] for a in dg)*1e3))
    for k, (t, isl) in VICT.items():
        if k not in res and (t in taps):
            res['tap:'+k] = dict(tap=t, island=isl, mA=0, rail=float(V[n.idx[taps[t][0]]]-V[n.idx[taps[t][1]]]), vss_mV=float(V[n.idx[taps[t][1]]]*1e3))
    # bond currents
    ib = {}
    for (a, b), r, pos in zip(info['bond_pairs'], info['bond_R'], info['bond_pos']):
        Va = V[n.idx[a]] if n.idx[a] >= 0 else 0.0; Vb = V[n.idx[b]] if n.idx[b] >= 0 else 0.0
        ib[pos] = float(abs(Vb-Va)/r*1e3)    # mA magnitude per bond
    ring = [float(V[n.idx[M.vn(i, j)]]-V[n.idx[M.gn(i, j)]]) for i in range(M.NX) for j in range(M.NY) if i in (0, M.NX-1) or j in (0, M.NY-1)]
    return dict(blocks=res, bond_mA=ib, ring_rail_min=min(ring), ring_rail_max=max(ring), total_mA=sum(x[3] for x in out)+idig+ihost, mode=m)
