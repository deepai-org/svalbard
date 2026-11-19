#!/usr/bin/env python3
"""Benches of the pad_txpad candidate (patterns: ../../txr/tb.py, ../../hsfix/rbench.py). ngspice 47 of the pads sim image.
  tb2.py ka                         known answer: published C-only pad, DC termination at tt 27 C 3.3 V must read 91.58 ohm (txr)
  tb2.py term <model> <tag> [quick|off]   differential / per-leg DC resistance vs TERM_TRIM code 0..15, +-10 mV about TERM_VCM 1.65 V,
                                    23 corners (quick: 5); off = TERM_ENABLE and all trim bits 0 (negative control: must be > 10 kohm)
Output bench/<tag>-<part>.json; raw files deleted."""
import sys, json, re
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s, stress_safe_family_sims as f
HERE = Path(__file__).resolve().parent
VCM, DV = 1.65, 0.01
CORNERS = [(p, t, v) for p in ('typical', 'ss', 'ff', 'sf', 'fs') for t in (22, 32) for v in (3.15, 3.35)] + [('ss', 22, 3.5), ('ss', 32, 3.5), ('typical', 27, 3.3)]
QUICK = [('typical', 27, 3.3), ('ss', 32, 3.15), ('ff', 22, 3.35), ('sf', 32, 3.15), ('fs', 22, 3.35)]
HIGH = ('CASCODE', 'DETECT_PBIAS', 'DVDD_P', 'DVDD_N')


def header(pr, t):
    sec = dict(typical=('typical', 'res_typical', 'diode_typical', 'mimcap_typical'), ss=('ss', 'res_ss', 'diode_ss', 'mimcap_ss'), ff=('ff', 'res_ff', 'diode_ff', 'mimcap_ff'),
               sf=('sf', 'res_typical', 'diode_typical', 'mimcap_typical'), fs=('fs', 'res_typical', 'diode_typical', 'mimcap_typical'))[pr]
    return f'.include {f.PDK}/design.ngspice\n' + ''.join(f'.lib {f.PDK}/sm141064.ngspice {x}\n' for x in sec) + f'.temp {t}\n'


def load(model):
    text = re.sub(r'\n\+\s*', ' ', Path(model).read_text())
    text = '\n'.join(l for l in text.splitlines() if not l.startswith('.lib '))
    text = re.sub(r'#(?=[\s=)]|$)', '_h', text, flags=re.M)
    m = re.search(r'(?m)^\.subckt (\S+) (.*)$', text)
    return text + '\n', m.group(1), m.group(2).split()


def controls(ports, vdd, over):
    d = f'VDD VDD 0 {vdd}\n'
    for p in ports:
        if p in ('PAD_P', 'PAD_N', 'VDD') or p in over: continue
        if p in ('VSS', 'DVSS_P', 'DVSS_N'): d += f'V{p} {p} 0 0\n'
        elif p == 'TERM_VCM': d += f'VTERM_VCM TERM_VCM 0 {VCM}\n'
        elif p == 'ATB_ESD_RAIL': d += 'RATB ATB_ESD_RAIL 0 10meg\n'
        else: d += f'V{p} {p} ' + ('VDD 0' if p in HIGH else '0 0') + '\n'
    return d + ''.join(over.values())


def term_deck(text, cell, ports, pr, t, vdd, off, trim):
    over = {}
    if 'TERM_ENABLE' in ports: over['TERM_ENABLE'] = 'VTERM_ENABLE TERM_ENABLE ' + ('0 0' if off else 'VDD 0') + '\n'
    if trim:
        for k in range(4):
            over[f'TERM_TRIM{k}'] = f'BT{k} TERM_TRIM{k} 0 V = ' + ('0' if off else f'{vdd} * (floor((v(code) + 0.5) / {1 << k}) - 2 * floor((v(code) + 0.5) / {2 << k}))') + '\n'
    inst = lambda n, pp, pn: f'X{n} ' + ' '.join({'PAD_P': pp, 'PAD_N': pn}.get(p, p) for p in ports) + f' {cell}\n'
    d = header(pr, t) + text + controls(ports, vdd, over) + 'Vcode code 0 0\nRcode code 0 1k\n'
    d += f'VPA PA 0 {VCM + DV}\nVNA NA 0 {VCM - DV}\nVPB PB 0 {VCM - DV}\nVNB NB 0 {VCM + DV}\n' + inst('A', 'PA', 'NA') + inst('B', 'PB', 'NB')
    return d


def term(model, tag, mode, loader=load):
    text, cell, ports = loader(model)
    trim = 'TERM_TRIM0' in ports; off = mode == 'off'
    W = HERE / 'bench' / tag; out = dict(model=str(model), model_sha256=s.sha(Path(model)), vcm=VCM, off=off, corners={})
    for pr, t, vdd in (QUICK if mode in ('quick', 'off') else CORNERS):
        name = f'term_{pr}_{t}_{vdd}'
        d = term_deck(text, cell, ports, pr, t, vdd, off, trim) + s.control(W, name, 'dc Vcode 0 15 1' if trim else 'dc Vcode 0 0.5 1', 'i(VPA) i(VNA) i(VPB) i(VNB)')
        x = np.atleast_2d(s.run(W, name, d, timeout_s=3000))
        rows = []
        for r in x:
            ipa, ina, ipb, inb = (-r[k] for k in (1, 2, 3, 4))
            rp = 2 * DV / (ipa - ipb); rn = 2 * DV / (inb - ina); rd = 4 * DV / (((ipa - ina) - (ipb - inb)) / 2)
            rows.append([round(rd, 3), round(rp, 3), round(rn, 3)])
        out['corners'][f'{pr}_{t}_{vdd}'] = rows
        print(pr, t, vdd, ' '.join(f'{r[0]:.1f}' for r in rows), flush=True)
        for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
    (HERE / 'bench' / f'{tag}-term{"-off" if off else ""}.json').write_text(json.dumps(out, indent=1))
    return out


# ----------------------------------------------------------------------------------------------------------------- ESD
IO = '/home/ubuntu/svalbard/scratch/transceiver-pad-pdk/gf180mcu_fd_io.spice'   # read on the host, pasted into the deck
RING = dict(r_site=0.025, r_ring=0.5)      # ohm: site landing -> ring node at the pad; ring node -> the lumped clamp set (each rail)
MOSM = ('nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0')


def clamp_cells():
    """Provider dvdd / dvss / cor cells (RC clamps) as ../../clamp/gen.py prepares them."""
    io = re.sub(r'\n\+\s*', ' ', open(IO).read())
    def refinger(mm):
        mult, w, l, nf = float(mm.group(1)), float(mm.group(2)), mm.group(3), float(mm.group(4)); k = nf
        while w / k > 50e-6: k *= 2
        return f'm={mult*k:g} w={w/k:g} l={l} nf=1'
    out = ''
    for c in ('dvdd', 'dvss', 'cor'):
        b = re.search(r'^\.SUBCKT gf180mcu_fd_io__%s .*?^\.ENDS' % c, io, re.M | re.S).group(0)
        b = re.sub(r'm=(\S+) w=(\S+) l=(\S+) nf=(\S+)', refinger, b)
        b = re.sub(r' (as|ad|ps|pd|nrd|nrs|sa|sb|sd)=\S+', '', b)
        # MOS capacitors (behavioural C(v) in the PDK: with a rail that is not voltage-driven ngspice stops at the first timepoints)
        # -> linear capacitors of the model's high-bias value (cvar1 + cvar2 = 2.177 fF/um2), rail decaps AND trigger capacitors
        # (trigger RC then 360 kohm x 4.35 pF = 1.57 us, inside the 1.14-2.09 us of CLAMP.md).
        def lin(mm):
            a, bn, mult, cl, cw = mm.group(2), mm.group(3), float(mm.group(4)), float(mm.group(5)), float(mm.group(6))
            return f'C{mm.group(1)} {a} {bn} {mult * cl * cw * 2.177e-3:.4g}'
        b = re.sub(r'(?m)^X(\S+) (\S+) (\S+) cap_nmos_06v0 m=(\S+) c_length=(\S+) c_width=(\S+)', lin, b)
        out += b + '\n'
    return out


def esd_deck(text, cell, ports, case, src, clamps=True):
    """Unpowered die. Ring: RD (DVDD at the pad), RS (DVSS at the pad), clamp nodes CD / CS behind r_ring.
    case: vss = zap PAD_P against the ring ground (CS = 0); vdd = against the ring supply (CD = 0); pp = PAD_P against PAD_N."""
    d = f'.include {f.PDK}/design.ngspice\n' + ''.join(f'.lib {f.PDK}/sm141064.ngspice {x}\n' for x in ('typical', 'res_typical', 'diode_typical', 'mimcap_typical', 'moscap_typical')) + '.temp 27\n'
    d += '.option method=gear reltol=1e-3 rshunt=1e12 cshunt=1e-17\n' + text + (clamp_cells() if clamps else '')
    m = {'DVSS_P': 'SP', 'DVSS_N': 'SN', 'DVDD_P': 'DP', 'DVDD_N': 'DN', 'VSS': 'RS', 'PAD_P': 'PAD_P', 'PAD_N': 'PAD_N'}
    d += 'Xpad ' + ' '.join(m.get(p, 'c_' + p) for p in ports) + f' {cell}\n'
    for p in ports:
        if p not in m: d += f'Rc_{p} c_{p} RS 100\n'                  # every core-side pin (controls, VDD, TERM_VCM) held at the pad ground
    r = RING
    d += f'Rsp SP RS {r["r_site"]}\nRsn SN RS {r["r_site"]}\nRdp DP RD {r["r_site"]}\nRdn DN RD {r["r_site"]}\nRrs RS CS {r["r_ring"]}\nRrd RD CD {r["r_ring"]}\n'
    import os
    if float(os.environ.get('TB2_CDIE', '0')) > 0: d += f"Cdie CD CS {float(os.environ['TB2_CDIE']):g}\n"      # die capacitance on the ring (rail-to-rail)
    if clamps:
        d += ''.join(f'Xdvdd{k} CD CS CS gf180mcu_fd_io__dvdd\n' for k in range(8)) + ''.join(f'Xdvss{k} CD CS CD gf180mcu_fd_io__dvss\n' for k in range(10))
        d += ''.join(f'Xcor{k} CD CS CD CS gf180mcu_fd_io__cor\n' for k in range(4))
    ref = dict(vss='CS', vdd='CD', pp='PAD_N')[case]
    d += f'Vref {ref} 0 0\nRfl1 CS 0 1g\nRfl2 CD 0 1g\nRfl3 PAD_N 0 1g\n'
    d += f'IINJECT 0 PAD_P {src}\n'
    return d


def mos_nodes(text, cell, ports):
    """(name, model, d, g, s, b) of every MOS of the pad subckt with ngspice vector names."""
    body = text[text.index('.subckt ' + cell):]; body = body[:body.index('.ends')]
    m = {'DVSS_P': 'SP', 'DVSS_N': 'SN', 'DVDD_P': 'DP', 'DVDD_N': 'DN', 'VSS': 'RS', 'PAD_P': 'PAD_P', 'PAD_N': 'PAD_N'}
    def vec(n): return (m.get(n, 'c_' + n) if n in ports else 'xpad.' + n).lower()
    out = []
    for l in body.splitlines():
        w = l.split()
        if w and w[0][0] == 'X' and len(w) > 5 and w[5] in MOSM: out.append((w[0], w[5]) + tuple(vec(n) for n in w[1:5]))
    return out


def run_dock(W, name, deck, timeout_s=5000):
    """Same deck in the pinned iic-osic-tools ngspice (../../dock.sh, ngbehavior=hsa), used for decks with the provider clamp cells
    (their behavioural MOS capacitors stop the patched ngspice 47 at the initial timepoint)."""
    import subprocess
    W.mkdir(parents=True, exist_ok=True); rel = '/work/' + str(W.relative_to(HERE.parents[1]))
    deck = deck.replace(str(f.PDK), '/foss/pdks/gf180mcuD/libs.tech/ngspice').replace(str(W), rel)
    (W / f'{name}.spice').write_text(deck); (W / f'{name}.dat').unlink(missing_ok=True)
    subprocess.run([str(HERE.parents[1] / 'dock.sh'), f'cd {rel} && ngspice -b {name}.spice > {name}.log 2>&1'], capture_output=True, text=True, timeout=timeout_s)
    return np.loadtxt(W / f'{name}.dat', skiprows=1)


def esd(model, tag, cases, clamps=True, sim='dock'):
    """cases: list of 'hbm:<kV>:<vss|vdd|pp>:<pos|neg>' or 'cdm:<A>:<vss|vdd|pp>:<pos|neg>'."""
    text, cell, ports = load(model)
    W = HERE / 'bench' / tag; mos = mos_nodes(text, cell, ports)
    nodes = sorted({n for d in mos for n in d[2:]} | {'pad_p', 'pad_n', 'rs', 'rd', 'cs', 'cd', 'sp', 'dp'})
    fn = HERE / 'bench' / f'{tag}-esd.json'; out = json.loads(fn.read_text()) if fn.exists() else dict(model=str(model), model_sha256=s.sha(Path(model)), ring=RING, clamps=clamps, simulator=sim, c_die_F=float(__import__('os').environ.get('TB2_CDIE', '0')), runs={})
    for c in cases:
        kind, lvl, ref, pol = c.split(':'); sg = 1 if pol == 'pos' else -1
        if kind == 'hbm': ipk = float(lvl) / 1.5; src = f'EXP(0 {sg * ipk:.4f} 5n 2n 15n 150n)'; tran = 'tran .1n 400n uic'
        else: ipk = float(lvl); src = f'PULSE(0 {sg * ipk} 2n 0.2n 0.5n 1n 1)'; tran = 'tran .01n 12n uic'
        name = c.replace(':', '_')
        d = esd_deck(text, cell, ports, ref, src, clamps) + s.control(W, name, tran, ' '.join(f'v({n})' for n in nodes))
        x = np.atleast_2d((run_dock if sim == 'dock' else s.run)(W, name, d, timeout_s=5000)); col = {n: x[:, 1 + i] for i, n in enumerate(nodes)}
        refn = dict(vss='cs', vdd='cd', pp='pad_n')[ref]
        tend = 399e-9 if kind == 'hbm' else 11.9e-9
        res = dict(ipk=ipk, complete=bool(np.isfinite(x).all() and x[-1, 0] >= tend), t_end=float(x[-1, 0]),
                   pad_vs_ref_peak=float(np.max(np.abs(col['pad_p'] - col[refn]))), pad_vs_local_vss_peak=float(np.max(np.abs(col['pad_p'] - col['rs']))),
                   pad_vs_local_vdd_peak=float(np.max(np.abs(col['pad_p'] - col['rd']))), rail_dvdd_minus_dvss_peak=float(np.max(np.abs(col['rd'] - col['rs']))))
        worst = {}
        for nm, mdl, dd, g, ss_, b in mos:
            lim = 5.0 if '03v3' in mdl else 8.0; dc = 3.63 if '03v3' in mdl else 6.0
            vg = max(float(np.max(np.abs(col[g] - col[k]))) for k in (dd, ss_, b)); vds = float(np.max(np.abs(col[dd] - col[ss_])))
            w = worst.setdefault(mdl, dict(limit=lim, dc_screen=dc, gate_max=0., gate_dev='', ds_max=0., ds_dev='', over_transient=0, over_dc=0, n=0))
            w['n'] += 1; v = max(vg, vds)
            if vg > w['gate_max']: w['gate_max'], w['gate_dev'] = round(vg, 3), nm
            if vds > w['ds_max']: w['ds_max'], w['ds_dev'] = round(vds, 3), nm
            w['over_transient'] += v > lim; w['over_dc'] += v > dc
        res['mos'] = worst; out['runs'][c] = res
        print(c, 'COMPLETE' if res['complete'] else 'INCOMPLETE', 'pad-ref %.2f pad-vss %.2f pad-vdd %.2f rail %.2f' % (res['pad_vs_ref_peak'], res['pad_vs_local_vss_peak'], res['pad_vs_local_vdd_peak'], res['rail_dvdd_minus_dvss_peak']),
              ' | '.join(f"{k}: g {v['gate_max']} ds {v['ds_max']} over {v['over_transient']}/{v['over_dc']}" for k, v in worst.items()), flush=True)
        fn.write_text(json.dumps(out, indent=1))
        for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
    return out


# ------------------------------------------------------------------------------------------------- AC, driver DC, idle
def ac(model, tag, code=6, pr='typical', temp=27, vdd=3.3, extra='', loader=load):
    """Per-leg pad capacitance (termination off, driver off) and differential die impedance / return loss vs 100 ohm (termination on, `code`)."""
    text, cell, ports = loader(model); W = HERE / 'bench' / tag; out = dict(model=str(model), model_sha256=s.sha(Path(model)), code=code, corner=[pr, temp, vdd], extra=extra)
    for part in ('cap', 'rl'):
        over = {'TERM_ENABLE': 'VTERM_ENABLE TERM_ENABLE ' + ('VDD 0' if part == 'rl' else '0 0') + '\n'}
        for k in range(4): over[f'TERM_TRIM{k}'] = f'VT{k} TERM_TRIM{k} ' + ('VDD 0' if part == 'rl' and code >> k & 1 else '0 0') + '\n'
        d = header(pr, temp) + text + controls(ports, vdd, over) + 'Xpad ' + ' '.join(ports) + f' {cell}\n' + extra
        d += f'VACP PAD_P 0 DC {VCM} AC ' + ('0.5' if part == 'rl' else '1') + f'\nVACN PAD_N 0 DC {VCM} AC ' + ('-0.5' if part == 'rl' else '0') + '\n'
        name = f'ac_{part}'; d += s.control(W, name, 'ac dec 10 1e8 3.16e9', 'i(VACP) i(VACN)')
        x = np.atleast_2d(s.run(W, name, d, timeout_s=3000)); fr = x[:, 0]; ip = -(x[:, 1] + 1j * x[:, 2]); inn = -(x[:, 3] + 1j * x[:, 4])
        pick = lambda v, f0: v[int(np.argmin(np.abs(fr - f0)))]
        if part == 'cap':
            out['c_leg_pF'] = {f'{f0/1e9:g}GHz': round(float(pick(ip.imag / (2 * np.pi * fr), f0)) * 1e12, 4) for f0 in (1e8, 1e9, 2.5e9)}
            out['c_mutual_pF_100MHz'] = round(float(pick(-inn.imag / (2 * np.pi * fr), 1e8)) * 1e12, 4)
        else:
            z = 1.0 / ((ip - inn) / 2); g = (z - 100) / (z + 100); rl = -20 * np.log10(np.abs(g))
            out['zdiff_real_100MHz'] = round(float(pick(z.real, 1e8)), 3)
            out['return_loss_dB'] = {f'{f0/1e9:g}GHz': round(float(pick(rl, f0)), 2) for f0 in (1e8, 5e8, 1.25e9, 1.6e9, 2.5e9)}
            out['return_loss_min_dB_0.1_1.25GHz'] = round(float(rl[fr <= 1.26e9].min()), 2); out['return_loss_min_dB_1.25_2.5GHz'] = round(float(rl[(fr >= 1.25e9) & (fr <= 2.55e9)].min()), 2)
        for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
    print(tag, json.dumps(out)[:900]); (HERE / 'bench' / f'{tag}-ac.json').write_text(json.dumps(out, indent=1)); return out


def gatec(model, tag, loader=load, pr='typical', temp=27, vdd=3.3, code=6):
    """Small-signal capacitance at each steering-switch gate pin (MAIN/POST/TMDS _P/_N: all unit gates + wiring of that pin), 100 MHz,
    gate DC 0 V (switch off) and VDD (switch on); termination on (code `code` if trimmed), bias pins 0, pads held by the termination."""
    text, cell, ports = loader(model); W = HERE / 'bench' / tag; out = dict(model=str(model), model_sha256=s.sha(Path(model)), corner=[pr, temp, vdd], code=code, c_pF={})
    for pin in ('MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'TMDS_P', 'TMDS_N'):
        for lvl in (0, vdd):
            over = {'TERM_ENABLE': 'VTERM_ENABLE TERM_ENABLE VDD 0\n', pin: f'VG {pin} 0 DC {lvl} AC 1\n'}
            for k in range(4): over[f'TERM_TRIM{k}'] = f'VT{k} TERM_TRIM{k} ' + ('VDD 0' if code >> k & 1 else '0 0') + '\n'
            d = header(pr, temp) + text + controls(ports, vdd, over) + 'Xpad ' + ' '.join(ports) + f' {cell}\nRPP PAD_P TERM_VCM 1g\nRPN PAD_N TERM_VCM 1g\n'
            name = f'g_{pin}_{lvl:g}'; d += s.control(W, name, 'ac lin 1 1e8 1e8', 'i(VG)')
            x = np.atleast_2d(s.run(W, name, d, timeout_s=3000)); ig = -(x[0, 1] + 1j * x[0, 2])
            out['c_pF'][f'{pin}@{lvl:g}V'] = round(float(ig.imag / (2 * np.pi * 1e8)) * 1e12, 4)
            for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
    print(tag, json.dumps(out['c_pF']), flush=True); (HERE / 'bench' / f'{tag}-gatec.json').write_text(json.dumps(out, indent=1)); return out


def drive(model, tag, mode, i_ma, pr='typical', temp=27, vdd=3.3, code=6):
    """DC with the MAIN branch on. mode out: MAIN_P = VDD, MAIN_N = 0, termination off, 50 ohm to VDD at each bond pad (all current through the
    bond pad). mode idle: MAIN_P = MAIN_N = POST_P = POST_N = VDD (electrical idle of the mux, WT34 (3)), termination on at `code`, POST tail = MAIN / 3.
    Tail bias: diode-connected 2 x 20/1 reference fed i/16 (the wired TX DAC ratio)."""
    text, cell, ports = load(model); W = HERE / 'bench' / tag; idle = mode == 'idle'
    over = {'TERM_ENABLE': 'VTERM_ENABLE TERM_ENABLE ' + ('VDD 0' if idle else '0 0') + '\n', 'MAIN_BIAS': f'IREF VDD MAIN_BIAS {i_ma * 1e-3 / 16}\nXREFA MAIN_BIAS MAIN_BIAS 0 0 nfet_03v3 w=20u l=1u\nXREFB MAIN_BIAS MAIN_BIAS 0 0 nfet_03v3 w=20u l=1u\n',
            'MAIN_P': 'VMAIN_P MAIN_P VDD 0\n', 'MAIN_N': 'VMAIN_N MAIN_N ' + ('VDD 0' if idle else '0 0') + '\n'}
    for k in range(4): over[f'TERM_TRIM{k}'] = f'VT{k} TERM_TRIM{k} ' + ('VDD 0' if idle and code >> k & 1 else '0 0') + '\n'
    if idle:
        over.update({'POST_P': 'VPOST_P POST_P VDD 0\n', 'POST_N': 'VPOST_N POST_N VDD 0\n',
                     'POST_BIAS': f'IREFP VDD POST_BIAS {i_ma * 1e-3 / 48}\nXREFC POST_BIAS POST_BIAS 0 0 nfet_03v3 w=20u l=1u\nXREFD POST_BIAS POST_BIAS 0 0 nfet_03v3 w=20u l=1u\n'})
    d = header(pr, temp) + text + controls(ports, vdd, over) + 'Xpad ' + ' '.join(ports) + f' {cell}\nVdum dum 0 0\nRdum dum 0 1k\n'
    d += 'VLP LP VDD 0\nVLN LN VDD 0\n' + ('RLP LP PAD_P 1e9\nRLN LN PAD_N 1e9\n' if idle else 'RLP LP PAD_P 50\nRLN LN PAD_N 50\n')
    mos = [(a, b) + tuple(v if v.startswith('xpad.') else v[2:] for v in c) for a, b, *c in mos_nodes(text, cell, ports)]
    fix = {'rs': '0', 'sp': '0', 'sn': '0', 'dp': 'vdd', 'dn': 'vdd'}
    mos = [(a, b) + tuple(fix.get(v, v) for v in c) for a, b, *c in mos]
    nm = Path(str(model) + '.nodes.json'); nmap = json.loads(nm.read_text()) if nm.exists() else {}
    want = sorted({v for dv in mos for v in dv[2:] if v not in ('0',)} | {'pad_p', 'pad_n'} | {'xpad.' + v.lower() for v in nmap.values() if '__' in v})
    name = f'{mode}_{i_ma:g}'; d += s.control(W, name, 'dc Vdum 0 0.5 1', ' '.join(f'v({n})' for n in want) + ' i(VLP) i(VLN) i(VTERM_VCM)')
    x = np.atleast_2d(s.run(W, name, d, timeout_s=3000))[0]; col = {n: float(x[1 + i]) for i, n in enumerate(want)}; col['0'] = 0.
    ilp, iln, ivcm = (-float(v) for v in x[1 + len(want):1 + len(want) + 3])
    out = dict(model=str(model), mode=mode, i_set_mA=i_ma, corner=[pr, temp, vdd], pad_p=col['pad_p'], pad_n=col['pad_n'], pad_diff_mV=round((col['pad_p'] - col['pad_n']) * 1e3, 3),
               i_load_p_mA=round(ilp * 1e3, 4), i_load_n_mA=round(iln * 1e3, 4), i_term_vcm_mA=round(ivcm * 1e3, 4))
    worst = {}
    for nmn, mdl, dd, g, ss_, b in mos:
        v = max(abs(col[g] - col[k]) for k in (dd, ss_, b)); v = max(v, abs(col[dd] - col[ss_]))
        w = worst.setdefault(mdl, dict(dc_screen=3.63 if '03v3' in mdl else 6.0, max_v=0., dev='', over=0))
        if v > w['max_v']: w['max_v'], w['dev'] = round(v, 4), nmn
        w['over'] += v > w['dc_screen']
    out['mos_dc'] = worst
    if nmap and not idle:
        g = lambda net, pre: [col['xpad.' + v.lower()] for k, v in nmap.items() if k.startswith(net + '|' + pre) and '__' in v]
        mean = lambda v: float(np.mean(v)) if v else float('nan')
        vd = mean(g('PAD_P', 'nmos:SUM_')); ds = [mean(g(f'SUM_P_D_{u}', 'nmos:PAD_P')) - mean(g(f'SUM_P_D_{u}', f'nmos:MAIN_TAIL_{u}')) for u in range(8)]
        dt = [mean(g(f'MAIN_TAIL_{u}', f'nmos:SUM_P_D_{u}')) - mean(g(f'MAIN_TAIL_{u}', 'nmos:VSS')) for u in range(8)]; vs = mean(g('VSS', 'nmos:MAIN_TAIL_'))
        out['metal_drop_mV'] = dict(bond_to_cascode_drains=round((col['pad_p'] - vd) * 1e3, 3), sum_mean=round(mean(ds) * 1e3, 3), tail_mean=round(mean(dt) * 1e3, 3), vss_rise=round(vs * 1e3, 3))
        out['metal_drop_mV']['total'] = round(sum(out['metal_drop_mV'].values()), 3)
    print(tag, mode, i_ma, json.dumps({k: v for k, v in out.items() if k != 'model'})[:700], flush=True)
    fn = HERE / 'bench' / f'{tag}-{mode}.json'; o = json.loads(fn.read_text()) if fn.exists() else {}
    o[f'{i_ma:g}mA_{pr}_{temp}_{vdd}'] = out; fn.write_text(json.dumps(o, indent=1))
    for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
    return out


def pub_loader(model):
    f.DRAWN_SHUNT = True; f.FAMILIES['txpad'] = dict(model=Path(model), lifecycle=None)
    return f.model_text('txpad')


if __name__ == '__main__':
    part = sys.argv[1]
    (HERE / 'bench').mkdir(exist_ok=True)
    if part == 'ka':
        pub = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/stress-safe-families/wired-transmit/physical.spice'
        o = term(pub, 'ka-pubc', 'quick', loader=pub_loader); r = o['corners']['typical_27_3.3'][0][0]
        print('KNOWN ANSWER tt', r, 'expected 91.58 (txr 91.577)', 'PASS' if abs(r - 91.58) < 0.05 else 'FAIL')
        o = term(pub, 'ka-pubc', 'off', loader=pub_loader); r = o['corners']['typical_27_3.3'][0][0]
        print('NEGATIVE CONTROL (TERM_ENABLE 0) tt', r, 'PASS' if abs(r) > 1e4 else 'FAIL')
    elif part == 'esd':
        esd(Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4:])
    elif part == 'esdnc':   # negative control: no ring clamps -> the positive zap must blow through every limit
        esd(Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4:], clamps=False)
    elif part == 'esdnc47':  # the same clamp-less deck in the pads' patched ngspice 47 (simulator cross-check)
        esd(Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4:], clamps=False, sim='pad47')
    elif part == 'esdka':   # known answer: 10 ohm PAD_P-VSS dummy cell, HBM 1 kV vs ring VSS -> 0.6667 A x 0.99326 (5 tau) x (10 + 0.5) = 6.953 V
        ka = HERE / 'bench' / 'esdka_cell.spice'
        ka.write_text('.subckt kacell PAD_P PAD_N VSS DVSS_P DVSS_N DVDD_P DVDD_N\nRK PAD_P VSS 10\nR1 PAD_N VSS 1meg\nR2 DVSS_P VSS 1meg\nR3 DVSS_N VSS 1meg\nR4 DVDD_P VSS 1meg\nR5 DVDD_N VSS 1meg\n.ends kacell\n')
        o = esd(ka, sys.argv[2], ['hbm:1:vss:pos']); r = o['runs']['hbm:1:vss:pos']['pad_vs_ref_peak']
        print('ESD KNOWN ANSWER pad-ref', r, 'expected about 6.95 V', 'PASS' if abs(r - 6.95) < 0.15 else 'FAIL')
    elif part == 'gatec':
        gatec(Path(sys.argv[2]).resolve(), sys.argv[3])
    elif part == 'gatecpub':
        gatec(Path(sys.argv[2]).resolve(), sys.argv[3], loader=pub_loader)
    elif part == 'acpub':
        ac(Path(sys.argv[2]).resolve(), sys.argv[3], loader=pub_loader)
    elif part == 'ac':
        ac(Path(sys.argv[2]).resolve(), sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    elif part in ('out', 'idle'):
        a = sys.argv[5:]
        drive(Path(sys.argv[2]).resolve(), sys.argv[3], part, float(sys.argv[4]), *( [a[0], int(a[1]), float(a[2])] if len(a) >= 3 else []), **(dict(code=int(a[3])) if len(a) > 3 else {}))
    elif part == 'term':
        term(Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else 'full')
