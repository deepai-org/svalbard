#!/usr/bin/env python3
"""esd3.py (ring/, copy of ../hs/sec/esd2.py 2026-11-20): + --far D,S far-group cell counts (default 7,9 as esd2; the real ring has 5,7) + --ringv RND,RNS,RFD,RFS = per-rail ring ohms (DVDD near, DVSS near, DVDD far, DVSS far)
from the provider-ring extraction (ring/REPORT.md); outputs under ring/esd, ring/esdrun.  Everything else unchanged.
esd2.py (sec/, copy of ../esd.py, 2026-11-19): + --rxgate: receiver input gate on RX_P/N (nfet_06v0 16/0.7 x6, gate = RX, D/S/B = local VSS,
as the CTLE input pair size of analog/wired_rx/netlists.py) and the read-out RX - local VSS / RX - core VDD (6 V oxide 8.0 V, 3.3 V 5.0 V);
+ --pwl: no change.  Original docstring:
esd.py: HBM-like and CDM-speed-surrogate zaps on a pad_hspad model WITH a model of the provider ring (compact-model
diagnostic, not a qualification).  One ngspice run at a time.

    esd.py <model.spice> <tag> [--ring typ|high] [--cases all|P+VSS,N-VDD,P+N,...] [--kv 2,1] [--cdm 1,2,3] [--toy R] [--strip-site]

Pad model: hs_protected_pad wrapper (ports incl. DVDD) as written by hs_pad_compose.py / make_rmodel_a.py; a model without a
DVDD port (published / f6) gets no ring connection on the pad side but the ring is still there for the VDD cases.
Ring model (ASSUMPTION, stated in STATUS.md): the 8 `dvdd` + 10 `dvss` provider cells of the retained ring
(scratch/transceiver-pad-pdk/gf180mcu_fd_io.spice, instanced as scratch/pads-core/clamp/gen.py does; corner cells left out),
  near group = 1 dvss + 1 dvdd cell behind RN per rail from the pad site   (dvss_pads[1] is 0.1 mm, dvdd_pads[0] 0.2-0.5 mm away),
  far group  = the other 16 cells behind a further RF per rail              (next cells 1.2-1.7 mm away, the rest farther),
  RN / RF = 0.10 / 0.30 ohm typ, 0.125 / 0.375 ohm high metal.  No die decoupling, no board: bare unpowered die.
Cases <pad><sign><ref>: P+VSS = PAD_P zapped positive against the ring VSS pads (grounded at the near dvss cell), ...VDD = against
the supply pads (near dvdd cell grounded, VSS ring floating), P+N = PAD_P positive against PAD_N grounded (both rings floating).
Core VDD pin of the pad = ring supply (1 ohm to the far node); control pins held at the local VSS; RX pins 50 fF to local VSS.
Waveforms: HBM EXP(0 kV/1.5k 5n 2n 15n 150n), tran 0.1 n / 300 n (the evidence before used 600 n; peaks are in the first 30 n);
CDM surrogate PULSE(0 I 5n 0.2n 0.5n 1n), tran 10 p / 40 n.  Typical devices, 27 C.
Reported per run: bond-pad peak |V| against the grounded reference; worst MOS gate terminal voltage (|Vgs|, |Vgd|, |Vgb|) with
counts over the DC screen (6.0 / 3.63 V) and over the transient limit (8.0 / 5.0 V); worst diode reverse voltage; worst MIM voltage;
ring DVDD-DVSS peak at the site.  --toy R: the pad model is replaced by a resistor R from PAD_P to VSS (known answer).
--strip-site: the pad-site diodes are removed from the model (negative control: must fail)."""
import sys, re, json, hashlib, argparse
import numpy as np
from pathlib import Path
PADS = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads'
sys.path.insert(0, PADS)
import stress_safe_family_sims as f, stress_safe_clamp as s
from loading_audit import anchor_floating_conductors
HERE = Path(__file__).resolve().parent
MOS = {'nfet_03v3': (3.63, 5.0), 'pfet_03v3': (3.63, 5.0), 'nfet_06v0': (6.0, 8.0), 'pfet_06v0': (6.0, 8.0)}
RING = {'typ': (.10, .30), 'high': (.125, .375)}
CDIE = None
RXGATE = False
RINGV = None
SITECAP = None   # (C, R per rail): ring decap at the site landing (PC-45)
FAR = (7, 9)
ALL = [f'{p}{sg}{r}' for r in ('VSS', 'VDD') for p in 'PN' for sg in '+-'] + ['P+N', 'P-N']


def ring_text():
    io = re.sub(r'\n\+\s*', ' ', open('/home/ubuntu/svalbard/scratch/transceiver-pad-pdk/gf180mcu_fd_io.spice').read())
    def refinger(mm):
        mult, w, l, nf = float(mm.group(1)), float(mm.group(2)), mm.group(3), float(mm.group(4)); k = nf
        while w / k > 50e-6: k *= 2
        return f'm={mult * k:g} w={w / k:g} l={l} nf=1'
    out = []
    for c in ('dvdd', 'dvss'):
        b = re.search(r'^\.SUBCKT gf180mcu_fd_io__%s .*?^\.ENDS' % c, io, re.M | re.S).group(0)
        b = re.sub(r'm=(\S+) w=(\S+) l=(\S+) nf=(\S+)', refinger, b)
        b = re.sub(r' (as|ad|ps|pd|nrd|nrs|sa|sb|sd)=\S+', '', b)
        # the DVDD-DVSS MOS decoupling capacitor of each cell (X21, 4 x 15 x 15 um) is left out: the behavioural capacitor does not start
        # in this simulator build on a floating rail; without it the rail has LESS charge storage (pessimistic). The timer capacitor stays.
        n0 = b.count('\n'); b = '\n'.join(l for l in b.splitlines() if not re.match(r'X\d+ DVDD DVSS cap_nmos_06v0 ', l)); assert n0 - b.count('\n') == 1, c
        out.append(b)
    return '\n'.join(out) + '\n'


def load_model(path, strip_site=False, strip_sec=False):
    text = re.sub(r'\n\+\s*', ' ', Path(path).read_text())
    text = '\n'.join(l for l in text.splitlines() if not l.startswith('.lib '))
    text = re.sub(r'#(?=[\s=)]|$)', '_h', text, flags=re.M)
    if strip_site:
        keep = [l for l in text.splitlines() if not (l.startswith('D') and ('DVDD' in l.split()[2] or l.split()[1].startswith('VSS__a') or (l.split()[1] == 'VSS' and 'nd2ps' in l and '__dn' in l.split()[2])))]
        nrm = len(text.splitlines()) - len(keep); text = '\n'.join(keep)
        if nrm == 0: raise SystemExit('no site diode found to strip')
        print('stripped site diodes:', nrm)
    if strip_sec:     # negative control of the local secondary clamp: its diodes (cathode node DVDD__s*) removed
        keep = [l for l in text.splitlines() if not (l.startswith('D') and l.split()[2].startswith('DVDD__s'))]
        nrm = len(text.splitlines()) - len(keep); text = '\n'.join(keep)
        if nrm == 0: raise SystemExit('no secondary diode found to strip')
        print('stripped secondary diodes:', nrm)
    body, _ = anchor_floating_conductors(text + '\n', 1e12)
    lines = body.splitlines()
    wrap = next(l for l in lines if l.startswith('.subckt ') and 'ESD_RAIL' not in l.split()[2:])
    inner = next(l for l in lines if l.startswith('.subckt ') and 'ESD_RAIL' in l.split()[2:])
    return body, wrap.split()[1], wrap.split()[2:], inner


def devices(body, inner):
    """MOS / diode / MIM of the inner subckt: (name, model, [nodes])"""
    out, inside = [], False
    for l in body.splitlines():
        if l == inner: inside = True; continue
        if inside and l.startswith('.ends'): break
        if not inside: continue
        t = l.split()
        if not t: continue
        words = [w for w in t[1:] if '=' not in w]
        if t[0][0] == 'X' and len(words) >= 5 and words[4] in MOS: out.append((t[0], words[4], words[:4]))
        elif t[0][0] == 'D': out.append((t[0], words[2], words[:2]))
        elif t[0][0] == 'X' and words[-1].startswith('cap_mim'): out.append((t[0], words[-1], words[:2]))
    return out


def deck(body, cell, ports, inner, case, wave, analysis, ring, toy=None):
    rnd, rns, rfd, rfs = RINGV if RINGV else (RING[ring] * 2)[0:1] + (RING[ring] * 2)[0:1] + RING[ring][1:2] * 2
    m = re.fullmatch(r'([PN])([+-])(VSS|VDD|N)', case); leg, sign, ref = m.groups(); other = 'N' if leg == 'P' else 'P'
    # options as in scratch/pads-core/clamp/gen.py (the provider clamp's MOS capacitor does not start without them)
    d = f.header() + f'.lib {f.PDK}/sm141064.ngspice moscap_typical\n.option method=gear rshunt=1e12 cshunt=1e-17\n' + ring_text()
    d += f'RDN DVDDS DVDDN {rnd}\nRSN VSSS VSSN {rns}\nRDF DVDDN DVDDF {rfd}\nRSF VSSN VSSF {rfs}\n'
    d += 'Xn1 DVDDN VSSN VSSN gf180mcu_fd_io__dvdd\nXn2 DVDDN VSSN DVDDN gf180mcu_fd_io__dvss\n'
    d += ''.join(f'Xfd{i} DVDDF VSSF VSSF gf180mcu_fd_io__dvdd\n' for i in range(FAR[0])) + ''.join(f'Xfs{i} DVDDF VSSF DVDDF gf180mcu_fd_io__dvss\n' for i in range(FAR[1]))
    d += 'RLK1 VSSN 0 1g\nRLK2 DVDDN 0 1g\nRLK3 PAD_P 0 1g\nRLK4 PAD_N 0 1g\n'
    # 1 uA into the supply ring from t = 0: with the ring at exactly 0 V the provider clamp's behavioural MOS capacitor does not start
    # (ngspice 46 and 47: 'timestep too small' at the first point); a driven rail does.  1 uA x 300 ns = 0.3 pC: no effect on the result.
    d += 'IKICK VSSF DVDDF PWL(0 0 10p 1u)\n'
    if SITECAP: d += f'CSITE DVDDSC VSSSC {SITECAP[0]}\nRSITED DVDDS DVDDSC {SITECAP[1]}\nRSITES VSSS VSSSC {SITECAP[1]}\n'
    if CDIE: d += f'CDIE DVDDF DIEX {CDIE}\nRDIE DIEX VSSF 0.5\n'      # --cdie: die supply capacitance behind 0.5 ohm (as scratch/pads-core/clamp/gen.py: 1n)
    gnd = {'VSS': 'VSSN', 'VDD': 'DVDDN', 'N': f'PAD_{other}'}[ref]
    d += f'VGND {gnd} 0 0\n'
    if ref != 'N': d += f'RFLT PAD_{other} VSSS 1meg\nCFLT PAD_{other} VSSS 1p\n'
    if toy is not None:
        d += f'RTOY PAD_P VSSS {toy}\n'; top = {}
    else:
        d += body + '\n'
        top = {}
        for p in ports:
            if p in ('PAD_P', 'PAD_N'): top[p] = p
            elif p == 'VSS': top[p] = 'VSSS'
            elif p == 'DVDD': top[p] = 'DVDDS'
            elif p == 'VDD': top[p] = 'VDDC'; d += 'RVC VDDC DVDDF 1\n'
            elif p in ('RX_P', 'RX_N'):
                top[p] = p; d += f'RCORE_{p} {p} VSSS 1g\nCCORE_{p} {p} VSSS 50f\n'
                if RXGATE: d += f'XRXG_{p} VSSS {p} VSSS VSSS nfet_06v0 w=16u l=0.7u m=6\n'
            elif p == 'ATB_ESD_RAIL': top[p] = 'ATB'; d += 'RATB ATB VSSS 10meg\nCATB ATB VSSS 10p\n'
            else: top[p] = p; d += f'V{p} {p} VSSS 0\n'
        d += 'Xpad ' + ' '.join(top[p] for p in ports) + f' {cell}\n'
    a, b = ('0', f'PAD_{leg}') if sign == '+' else (f'PAD_{leg}', '0')
    d += f'IINJECT {a} {b} {wave}\n'
    # vectors
    vec = ['v(PAD_P)', 'v(PAD_N)', 'v(VSSS)', 'v(DVDDS)', 'v(VSSN)', 'v(DVDDN)'] + (['v(RX_P)', 'v(RX_N)', 'v(VDDC)'] if toy is None else [])
    nodemap = {}
    if toy is None:
        iports = inner.split()[2:]
        wl = next(l for l in body.splitlines() if l.startswith('X') and l.split()[-1] == inner.split()[1]).split()
        xinst = wl[0].lower(); wmap = dict(zip(iports, wl[1:-1]))       # inner port -> wrapper node
        for _, _, nodes in devices(body, inner):
            for n in nodes:
                if n in nodemap or n == '0': continue
                if n in wmap:
                    w = wmap[n]; nodemap[n] = f'v({top[w]})' if w in top else f'v(xpad.{w.lower()})'
                else: nodemap[n] = f'v(xpad.{xinst}.{n.lower()})'
        vec += sorted(set(nodemap.values()) - set(vec))
    d += s.control(HERE / 'esdrun', 'NAME', analysis, ' '.join(vec))
    return d, vec, nodemap


def analyse(x, vec, nodemap, devs, case):
    col = {v.lower(): i + 1 for i, v in enumerate(vec)}; g = lambda v: x[:, col[v.lower()]]
    m = re.fullmatch(r'([PN])([+-])(VSS|VDD|N)', case); leg = m[1]
    r = dict(pad_peak_abs_v=float(np.abs(g(f'v(PAD_{leg})')).max()), pad_p_range_v=[float(g('v(PAD_P)').min()), float(g('v(PAD_P)').max())],
             pad_n_range_v=[float(g('v(PAD_N)').min()), float(g('v(PAD_N)').max())],
             pad_minus_local_vss_abs_v=float(max(np.abs(g('v(PAD_P)') - g('v(VSSS)')).max(), np.abs(g('v(PAD_N)') - g('v(VSSS)')).max())),
             ring_dvdd_minus_dvss_site_v=[float((g('v(DVDDS)') - g('v(VSSS)')).min()), float((g('v(DVDDS)') - g('v(VSSS)')).max())])
    if 'v(rx_p)' in col:
        r.update(rx_minus_vss_abs_v=float(max(np.abs(g('v(RX_P)') - g('v(VSSS)')).max(), np.abs(g('v(RX_N)') - g('v(VSSS)')).max())),
                 rx_minus_vdd_abs_v=float(max(np.abs(g('v(RX_P)') - g('v(VDDC)')).max(), np.abs(g('v(RX_N)') - g('v(VDDC)')).max())))
    node = lambda n: np.zeros(len(x)) if n == '0' else g(nodemap[n])
    worst = {}; over_screen = over_limit = nmos = 0; wd = (0., ''); wm = (0., ''); wnp = (0., 0., '')
    for name, model, nodes in devs:
        if model in MOS:
            nmos += 1; D, G, S, B = (node(n) for n in nodes)
            v = float(max(np.abs(G - S).max(), np.abs(G - D).max(), np.abs(G - B).max()))
            over_screen += v > MOS[model][0]; over_limit += v > MOS[model][1]
            k = v / MOS[model][1]
            if k > worst.get('k', 0): worst = dict(k=k, device=name, model=model, gate_v=round(v, 3), nodes=nodes)
        elif model.startswith('diode'):
            v = float((node(nodes[1]) - node(nodes[0])).max())           # cathode - anode
            if v > wd[0]: wd = (v, f'{name} {model} {nodes[0]} {nodes[1]}')
            if not any(re.match(r'PAD_[PN]__(dn|up)$', q) for q in nodes):
                kb = v / (11.0 if 'nd2ps' in model else 10.5 if 'pd2nw' in model else 10.0)
                if kb > wnp[0]: wnp = (kb, v, f'{name} {model} {nodes[0]} {nodes[1]}')
        else:
            v = float(np.abs(node(nodes[0]) - node(nodes[1])).max())
            if v > wm[0]: wm = (v, f'{name} {nodes[0]} {nodes[1]}')
    worst.pop('k', None)
    r.update(mos=nmos, mos_over_dc_screen=int(over_screen), mos_over_transient_limit=int(over_limit), worst_mos=worst,
             worst_diode_reverse_v=round(wd[0], 3), worst_diode=wd[1], worst_mim_v=round(wm[0], 3), worst_mim=wm[1], worst_nonprimary_diode_rev_v=round(wnp[1], 3), worst_nonprimary_diode=wnp[2], worst_nonprimary_frac_bv=round(wnp[0], 3))
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument('model'); p.add_argument('tag'); p.add_argument('--ring', default='typ'); p.add_argument('--cases', default='all')
    p.add_argument('--kv', default='2,1'); p.add_argument('--cdm', default='1,2,3'); p.add_argument('--toy', type=float); p.add_argument('--strip-site', action='store_true'); p.add_argument('--strip-sec', action='store_true'); p.add_argument('--cdie'); p.add_argument('--rxgate', action='store_true'); p.add_argument('--ringv'); p.add_argument('--far', default='7,9')
    a = p.parse_args()
    global CDIE, RXGATE, RINGV, FAR; FAR = tuple(map(int, a.far.split(','))); CDIE = a.cdie; RXGATE = a.rxgate; RINGV = tuple(map(float, a.ringv.split(','))) if a.ringv else None
    cases = ALL if a.cases == 'all' else a.cases.split(',')
    W = HERE / 'esdrun'; W.mkdir(exist_ok=True); (HERE / 'esd').mkdir(exist_ok=True)
    if a.toy is None:
        body, cell, ports, inner = load_model(a.model, a.strip_site, a.strip_sec); devs = devices(body, inner)
    else: body = cell = ports = inner = None; devs = []
    stim = [(f'hbm{kv:g}kV', f'EXP(0 {kv / 1.5:.4f} 5n 2n 15n 150n)', 'tran .1n 300n uic', 299e-9, kv / 1.5) for kv in map(float, filter(None, a.kv.split(',')))]
    stim += [(f'cdm{i:g}A', f'PULSE(0 {i} 5n 0.2n 0.5n 1n 1)', 'tran .01n 40n uic', 39e-9, i) for i in map(float, filter(None, a.cdm.split(',')))]
    out = HERE / 'esd' / f'{a.tag}.json'
    res = json.loads(out.read_text())['results'] if out.exists() else []
    done = {(r['case'], r['stimulus']) for r in res if r.get('complete')}
    for sname, wave, analysis, stop, ipk in stim:
        for case in cases:
            if (case, sname) in done: continue
            name = f'{a.tag}_{sname}_{case}'.replace('+', 'p').replace('-', 'm')
            d, vec, nodemap = deck(body, cell, ports, inner, case, wave, analysis, a.ring, a.toy)
            d = d.replace(f'{W}/NAME.dat', f'{W}/{name}.dat')
            try:
                x = s.run(W, name, d, timeout_s=3600)
            except Exception as e:
                res.append(dict(case=case, stimulus=sname, complete=False, error=str(e)[:200])); print(a.tag, sname, case, 'FAILED', str(e)[:100], flush=True); continue
            ok = bool(np.isfinite(x).all() and x[-1, 0] >= stop)
            r = dict(case=case, stimulus=sname, ipk_a=ipk, ring=a.ring, complete=ok, deck_sha256=hashlib.sha256(d.encode()).hexdigest())
            if ok: r.update(analyse(x, vec, nodemap, devs, case))
            res = [q for q in res if (q['case'], q['stimulus']) != (case, sname)] + [r]
            (W / f'{name}.dat').unlink(missing_ok=True)
            w = r.get('worst_mos') or {}
            print(a.tag, sname, case, 'ok' if ok else 'INCOMPLETE', 'pad %.3f V' % r.get('pad_peak_abs_v', float('nan')), 'worst gate', w.get('gate_v'), w.get('model'),
                  'screen', r.get('mos_over_dc_screen'), 'limit', r.get('mos_over_transient_limit'), 'diode rev', r.get('worst_diode_reverse_v'), 'ring', r.get('ring_dvdd_minus_dvss_site_v'), 'rx-vss', r.get('rx_minus_vss_abs_v'), 'rx-vdd', r.get('rx_minus_vdd_abs_v'), flush=True)
            out.write_text(json.dumps(dict(tag=a.tag, model=str(Path(a.model).resolve()), model_sha256=s.sha(a.model) if a.toy is None else None, ring=a.ring,
                                           ring_ohm=dict(zip(('dvdd_near', 'dvss_near', 'dvdd_far', 'dvss_far'), RINGV)) if RINGV else dict(zip(('near', 'far'), RING[a.ring])), far_cells=FAR, cdie=a.cdie, rxgate=a.rxgate, toy_ohm=a.toy, strip_site=a.strip_site, strip_sec=a.strip_sec, results=res), indent=1) + '\n')


if __name__ == '__main__':
    main()
