"""r12/ctle bench driver for pt_ctle r5 (EVERY call through ../../slot.sh, one job per call; OMP_NUM_THREADS=1).

Wraps r11/chain/rc11.py -> r10ctle/ch10.py / lib10.py without writing into those directories:
  lib10.STG -> v/<var>/ (ctle.ext.spice of the variant + staged rxselect r2 R+C netlist of r11/rc_ctle), results res/<var>/.
Corner key '<mos>@<poly>': mos in tt ss315 ss350 ff sf fs ssp315 (rc11 / lib10 keys), poly t | s | f = res_typical /
res_ss (+20 % ppolyf_u_1k) / res_ff (-20 %).  IBIAS = ideal current source R5_IBIAS (default 10 uA) from the rail.
The CTLE's own supply current is measured with a 0 V source in its VDD pin (VMC).

  r5lib.py ac   <var> <ck> [codes=0,1,..]   chain AC per code + op values -> res/<var>/ac.json ; PDA picks -> pick.json
  r5lib.py pick <var> <ck>                  PDA eye (T3; 2.5 / 3.125 / 3.24 Gb/s) from cached AC -> pick.json (no ngspice)
  r5lib.py loop <var> <ck>                  replica-loop gain (voltage injection at the tail-bias NMOS gate) -> loop.json
  r5lib.py tran <var> <ck> <rate> <stim> [neg=sl3p]   rc11.tran(clock='ideal') -> res/<var>/tran.json
"""
import sys, os, json, re, shutil, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r11/chain')
import rc11
from rc11 import L, ch10
RXSEL = Path('/home/ubuntu/svalbard/scratch/wired_rx/r11/rc_ctle/rxselect.rc.ext.spice')   # staged rxselect r2, R+C
OWNER_CHAIN = Path('/home/ubuntu/svalbard/scratch/wired_rx/r11/chain')
IBIAS = float(os.environ.get('R5_IBIAS', '10e-6'))
POLY = dict(t='typical', s='ss', f='ff')
MOS = dict(tt='tt', ss315='ss315', ss350='ss350', ff='ff', sf='sf', fs='fs', ssp315='ssp315', ssp350='ssp350')
RATES = (2.5, 3.125, 3.24)


def split(ck):
    m, p = ck.split('@')
    return m, p


def setup(var):
    stg = HERE / 'v' / var
    assert (stg / 'ctle.ext.spice').exists(), stg
    if not (stg / 'rxselect.ext.spice').exists():
        shutil.copy(RXSEL, stg / 'rxselect.ext.spice')
    res = HERE / 'res' / var; res.mkdir(parents=True, exist_ok=True)
    L.STG = stg
    ch10.ACD = res / 'ac'; ch10.ACD.mkdir(exist_ok=True)
    L.H = res; rc11.H = res; L.RUN = res / 'run'; L.RUN.mkdir(exist_ok=True)
    L.NET = HERE / 'net'; L.NET.mkdir(exist_ok=True)
    w = stg / 'well.json'
    L.WELL = w if w.exists() else Path('/home/ubuntu/svalbard/scratch/wired_rx/r10ctle/stage/well.json')
    if not (res / 'aperture.json').exists(): shutil.copy(OWNER_CHAIN / 'aperture.json', res / 'aperture.json')
    for ck in list(L.CORN):
        pass
    return res


# termination trim code per combination: 100 ohm differential at 20 MHz on the a6 R-aware pad model (tcode.py -> tcode.json)
TC = json.loads((HERE / 'tcode.json').read_text()) if (HERE / 'tcode.json').exists() else {}
# ---- corners: register '<mos>@<poly>' keys in lib10.CORN, poly corner emitted by hdr
for mk in MOS:
    for pk in POLY:
        L.CORN[f'{mk}@{pk}'] = L.CORN[mk]
        rc11.TCODE[f'{mk}@{pk}'] = TC.get(f'{mk}@{pk}', {}).get('code', rc11.TCODE[mk])
        rc11.RINGTAG[f'{mk}@{pk}'] = rc11.RINGTAG[mk]
_hdr0 = L.hdr


def _hdr(ck, title='r12'):
    out = _hdr0(ck, title)
    if '@' in ck:
        pk = split(ck)[1]
        out = [f'.lib {L.PDK}/sm141064.ngspice res_{POLY[pk]}' if l.startswith('.lib') and ' res_' in l else l for l in out]
    return out


L.hdr = _hdr


def _ctle_inst(kind, bound, code, en=True, byp=False, lfz=0, inp='inp', inn='inn', outp='slp', outn='sln', x='XC', name='pt_ctle'):
    p = L.net('ctle', kind, bound)
    m = dict(VDD_WIRE_SW='vddc', VSS='0', IBIAS='ib', ctle_en='vdd' if en else '0', wire_ctle_bypass='vdd' if byp else '0',
             RX_P=inp, RX_N=inn, CTLE_P=outp, CTLE_N=outn, atb_ctle_pbias='pb', atb_ctle_src='src')
    for k in range(3):
        m[f'ctle_peak{k}'] = 'vdd' if (code >> k) & 1 else '0'
        m[f'lf_zero{k}'] = 'vdd' if (lfz >> k) & 1 else '0'
    return [f'.include {p}', 'VMC vdd vddc 0', f'IIB vdd ib {IBIAS:g}', L.inst(x, p, name, m)]


L.ctle_inst = _ctle_inst


def jstore(res, name, key, val):
    p = res / name; d = json.loads(p.read_text()) if p.exists() else {}
    d[key] = val; p.write_text(json.dumps(d, indent=1))


def clean(res):
    for f in (res / 'run').glob('*'):
        if f.suffix in ('.txt', '.cir', '.raw') or f.stat().st_size > 200_000: f.unlink()


OPN = ['slp', 'sln', 'inp', 'inn', 'pb', 'xc.slr', 'xc.cp', 'xc.cn', 'xc.cpr', 'xc.vref', 'xc.vgr', 'xc.sp', 'xc.spr', 'src', 'xc.fbias', 'xc.na', 'xc.nb']


def ac(var, ck, codes=range(8)):
    res = setup(var); ch10.PADR[0] = 0.0; ch10.TCODE = rc11.TCODE[ck]
    n = int(round(ch10.FMAX / ch10.DF)); rows = {}
    for code in codes:
        tag = f'{ck}_c{code}'
        out = ch10.ACD / f'{tag}.npz'
        if out.exists(): continue
        b = L.hdr(ck, f'r12 chain ac {var} code{code}') + ['VTP tpi 0 DC 0 AC 1', 'VTN tni 0 DC 0 AC -1'] + ch10.chain(ck, code)
        b += ['.control', 'op', 'print i(VMC)', 'print i(VDD)'] + [f'print v({x})' for x in OPN] + \
             [f'ac lin {n} {ch10.DF} {ch10.FMAX}', 'set wr_singlescale', f'wrdata chac_{tag}.txt v(slp)-v(sln) v(inp)-v(inn) v(xc.cp)-v(xc.cn)', '.endc', '.end']
        t0 = time.time(); log = L.run(f'chac_{tag}', b, timeout=3600)
        f_ = L.RUN / f'chac_{tag}.txt'
        if not f_.exists():
            jstore(res, 'ac.json', tag, dict(error=log[-600:])); print(tag, 'ERROR', log[-300:], flush=True); continue
        d = np.loadtxt(f_)
        r = dict(f=d[:, 0], h=d[:, 1] + 1j * d[:, 2], hin=d[:, 3] + 1j * d[:, 4], hcore=d[:, 5] + 1j * d[:, 6])
        opv = {}
        for k_ in ['i(vmc)', 'i(vdd)'] + [f'v({x})' for x in OPN]:
            m = re.search(rf'^{re.escape(k_)} = ([-+0-9.eE]+)', log, re.M | re.I)
            opv[k_] = float(m.group(1)) if m else None
        r['cm'] = (opv['v(slp)'] + opv['v(sln)']) / 2; r['cmi'] = (opv['v(inp)'] + opv['v(inn)']) / 2; r['i(vdd)'] = opv['i(vdd)']
        np.savez(out, **r); f_.unlink()
        g = lambda fq: round(float(20 * np.log10(np.interp(fq, r['f'], abs(r['h'])))), 3)
        gc = lambda fq: round(float(20 * np.log10(np.interp(fq, r['f'], abs(r['hcore'])))), 3)
        gi = lambda fq: round(float(20 * np.log10(np.interp(fq, r['f'], abs(r['hin'])))), 3)
        row = dict(core_g20M=gc(20e6), core_g1g25=gc(1.25e9), in_g20M=gi(20e6), in_g1g25=gi(1.25e9), g20M=g(20e6), g625=g(625e6), g1g25=g(1.25e9), g1g62=g(1.62e9), gpk=round(float(20 * np.log10(abs(r['h']).max())), 3),
                   fpk_MHz=round(float(r['f'][abs(r['h']).argmax()] / 1e6)), sl_cm=round(r['cm'], 4), sl_off_mV=round(1e3 * (opv['v(slp)'] - opv['v(sln)']), 2),
                   in_cm=round(r['cmi'], 4), idd_ctle_mA=round(-1e3 * opv['i(vmc)'], 3), op={k_: (None if v is None else round(v, 5)) for k_, v in opv.items()},
                   seconds=round(time.time() - t0))
        jstore(res, 'ac.json', tag, row)
        print(var, tag, {k_: row[k_] for k_ in ('g20M', 'g1g25', 'g1g62', 'gpk', 'sl_cm', 'sl_off_mV', 'idd_ctle_mA', 'seconds')},
              'slr', row['op']['v(xc.slr)'], 'cp', row['op']['v(xc.cp)'], 'pb', row['op']['v(pb)'], flush=True)
    clean(res)


def pick(var, ck, stim='T3', codes=range(8)):
    res = setup(var); ch10.TCODE = rc11.TCODE[ck]
    have = [c for c in codes if (ch10.ACD / f'{ck}_c{c}.npz').exists()]
    rows = {}
    for rate in RATES:
        best, allc = ch10.pick(ck, rate * 1e9, stim, codes=have, banks=1)
        rows[f'{rate:g}G_{stim}'] = dict(code=best['code'], eye_mVppd=float(best['eye_mVppd']), width_ui=best['width_ui_ge60'],
                                         all={str(x['code']): [float(x['eye_mVppd']), x['width_ui_ge60']] for x in allc})
    rows['codes'] = have; rows['netlists'] = ch10.evidence(); rows['term_code'] = ch10.TCODE
    jstore(res, 'pick.json', ck, rows)
    print(var, ck, {k: (v['code'], v['eye_mVppd'], v['width_ui']) for k, v in rows.items() if 'G_' in k}, flush=True)


def loop_netlist(var):
    """Copy of the variant's CTLE with a series AC source between the replica-side diode `na` and the gate of the tail-bias
    NMOS (drain atb_ctle_pbias, gate na, nfet 5/1): Middlebrook voltage injection (gate side is capacitive, diode side low-Z)."""
    src = L.STG / 'ctle.ext.spice'; dst = L.STG / 'ctle_loop.spice'
    lines = src.read_text().replace('\n+', ' ').splitlines(); out = []; hit = 0
    for l in lines:
        t = l.split()
        if t and t[0][0] in 'Xx' and 'nfet_03v3' in t and not hit:
            pos = [x for x in t[1:] if '=' not in x]
            par = {x.split('=')[0]: x.split('=')[1] for x in t if '=' in x}
            d_, g_ = pos[0], pos[1]
            if d_.split('.')[0].startswith('atb_ctle_pbias') and g_.split('.')[0] == 'na' and par.get('l') in ('1u', '1e-06', '1.0u') and par.get('w') in ('5u', '5e-06', '5.0u'):
                t[2] = 'na_inj'; l = ' '.join(t) + f'\nVINJ na_inj {g_} DC 0 AC 1'; hit += 1
        out.append(l)
    assert hit == 1, hit
    dst.write_text('\n'.join(out) + '\n')
    return dst


def loop(var, ck):
    res = setup(var); ch10.PADR[0] = 0.0; ch10.TCODE = rc11.TCODE[ck]
    lp = loop_netlist(var)
    bound = L.CORN[ck][3]
    b = L.hdr(ck, f'r12 loop {var}') + ['VTP tpi 0 DC 0', 'VTN tni 0 DC 0'] + ch10.chain(ck, 0)
    b = [l.replace(str(L.net('ctle', 'stg', bound)), str(L.net('ctle', str(lp), bound))) for l in b]
    tag = f'loop_{ck}'
    b += ['.control', 'op', 'print v(xc.slr) v(slp) v(sln)', 'ac dec 40 1e3 3e9', 'set wr_singlescale',
          f'wrdata {tag}.txt v(xc.na_inj) v(xc.na)', '.endc', '.end']
    log = L.run(tag, b, timeout=3600)
    f_ = L.RUN / f'{tag}.txt'
    if not f_.exists():
        jstore(res, 'loop.json', ck, dict(error=log[-600:])); print(ck, 'ERROR', log[-300:]); return
    d = np.loadtxt(f_); f = d[:, 0]; vy = d[:, 1] + 1j * d[:, 2]; vx = d[:, 3] + 1j * d[:, 4]
    T = -vx / vy
    mag = 20 * np.log10(abs(T)); ph = np.degrees(np.unwrap(np.angle(T)))
    i0 = np.where((mag[:-1] > 0) & (mag[1:] <= 0))[0]
    if len(i0):
        k = i0[0]; fu = float(np.interp(0, [mag[k + 1], mag[k]], [f[k + 1], f[k]])); pu = float(np.interp(fu, f, ph))
        pm = 180.0 + pu                     # T = -vx/vy has ~0 deg at DC for negative feedback
    else:
        fu, pm = None, None
    j = np.where((ph[:-1] > -180) & (ph[1:] <= -180))[0]
    gm_ = float(-np.interp(f[j[0]], f, mag)) if len(j) else None
    row = dict(dc_gain_dB=round(float(mag[0]), 2), f_unity_Hz=fu, phase_margin_deg=None if pm is None else round(pm, 1), gain_margin_dB=gm_,
               phase_at_dc_deg=round(float(ph[0]), 1))
    jstore(res, 'loop.json', ck, row); f_.unlink(); print(var, ck, row, flush=True)
    clean(res)


def tran(var, ck, rate, stim, neg=None):
    res = setup(var)
    r = rc11.tran(ck, rate, stim, clock='ideal', neg=neg)
    clean(res)
    return r


if __name__ == '__main__':
    a = sys.argv[1:]
    kw = dict(x.split('=', 1) for x in a if '=' in x); pos = [x for x in a if '=' not in x]
    codes = [int(x) for x in kw['codes'].split(',')] if 'codes' in kw else range(8)
    if pos[0] == 'ac': ac(pos[1], pos[2], codes)
    elif pos[0] == 'pick': pick(pos[1], pos[2], codes=codes)
    elif pos[0] == 'loop': loop(pos[1], pos[2])
    elif pos[0] == 'tran': tran(pos[1], pos[2], float(pos[3]), pos[4], neg=kw.get('neg'))


def opdump(var, ck, code=0):
    """chain operating point, every CTLE-internal node voltage -> res/<var>/op_<ck>.json (EM audit input)"""
    res = setup(var); ch10.PADR[0] = 0.0; ch10.TCODE = rc11.TCODE[ck]
    b = L.hdr(ck, f'r12 op {var}') + ['VTP tpi 0 DC 0', 'VTN tni 0 DC 0'] + ch10.chain(ck, code) + ['.control', 'op', 'print all', '.endc', '.end']
    log = L.run(f'op_{ck}', b, timeout=1800)
    v = {m.group(1).lower(): float(m.group(2)) for m in re.finditer(r'^(\S+) = ([-+0-9.eE]+)\s*$', log, re.M)}
    v = {k: x for k, x in v.items() if k.startswith('xc.')}
    (res / f'op_{ck}.json').write_text(json.dumps(v)); print(var, ck, 'nodes', len(v), flush=True); clean(res)


if __name__ == '__main__' and sys.argv[1] == 'op':
    opdump(sys.argv[2], sys.argv[3])
