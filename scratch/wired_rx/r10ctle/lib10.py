"""r10ctle shared bench pieces (host ngspice; EVERY caller must be started through scratch/wired_rx/slot.sh).
Netlists: 'pub' = analog/wired_rx/generated/*.ext.spice, 'sch' = analog/wired_rx/*.spice, 'stg' = staged extraction
(r10ctle/stage/gen).  bound: nom | pess (r7slicer/pess.py) | opt (C x0.85, junction x0.75)."""
import os, re, subprocess, sys, json, hashlib
from pathlib import Path
H = Path(__file__).resolve().parent
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx')
G = W / 'generated'
VAR = os.environ.get('R10_VAR', '')        # '' = the staged r4; 'f2' = doubled-follower what-if build (stage_f2/gen)
STG = H / ('stage' + ('_' + VAR if VAR else '')) / 'gen'
NET = H / 'net'; NET.mkdir(exist_ok=True)
RUN = H / 'run'; RUN.mkdir(exist_ok=True)
PDK = __import__('os').environ.get('R11_PDK', '/home/ubuntu/svalbard/scratch/digital-libchar/pdk/libs.tech/ngspice')   # = analog image /foss/pdks/gf180mcuD (md5 match); frozen-pdk copy was deleted
PESS = '/home/ubuntu/svalbard/scratch/wired_rx/r7slicer/pess.py'
# corner key -> (lib corner, temp, vdd, bound)
CORN = {'tt': ('typical', 27, 3.30, 'nom'), 'ss315': ('ss', 32, 3.15, 'nom'), 'ss330': ('ss', 32, 3.30, 'nom'),
        'ss340': ('ss', 32, 3.40, 'nom'), 'ss350': ('ss', 32, 3.50, 'nom'), 'ff': ('ff', 22, 3.35, 'nom'),
        'ssp315': ('ss', 32, 3.15, 'pess'), 'ssp330': ('ss', 32, 3.30, 'pess'), 'ssp340': ('ss', 32, 3.40, 'pess'),
        'ssp350': ('ss', 32, 3.50, 'pess'), 'ffo': ('ff', 22, 3.35, 'opt'), 'ff350': ('ff', 22, 3.50, 'nom')}
MAIN = ('tt', 'ss315', 'ss350', 'ff', 'ssp315', 'ssp350')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cscale(src, dst, k, jk):
    out = []
    for l in Path(src).read_text().splitlines():
        t = l.split()
        if t and t[0][0] in 'Cc' and len(t) >= 4:
            m = re.match(r'([\d.eE+-]+)(.*)', t[3]); t[3] = f'{float(m.group(1)) * k:.6g}{m.group(2)}'; l = ' '.join(t)
        elif t and t[0][0] in 'Xx':
            l = ' '.join(re.sub(r'^(ad|as|pd|ps)=([\d.eE+-]+)([a-z]*)$', lambda m: f'{m.group(1)}={float(m.group(2)) * jk:.6g}{m.group(3)}', x) for x in t)
        out.append(l)
    Path(dst).write_text('\n'.join(out) + '\n')


def src_path(block, kind):
    if kind == 'pub': return G / f'{block}.ext.spice'
    if kind == 'sch': return W / f'{block}.spice'
    if kind == 'stg': return STG / f'{block}.ext.spice'
    return Path(kind)                                   # explicit file


def net(block, kind, bound='nom'):
    """Path of the netlist variant; pess/opt copies are cached under net/ keyed by the source sha."""
    src = src_path(block, kind)
    if bound == 'nom': return src
    dst = NET / f'{block}_{sha(src)[:10]}_{bound}.spice'
    if not dst.exists():
        if bound == 'pess':
            subprocess.run([sys.executable, PESS, str(src), str(dst)], check=True, capture_output=True)
        else:
            cscale(src, dst, 0.85, 0.75)
    return dst


def ports(path, name):
    txt = Path(path).read_text().replace('\n+', ' ')
    m = re.search(rf'^\.subckt {name} (.*)$', txt, re.M | re.I)
    return m.group(1).split()


def inst(xname, path, name, mapping, default=None):
    out = []
    for p in ports(path, name):
        if p in mapping: out.append(mapping[p])
        elif default is not None: out.append(default(p) if callable(default) else default)
        else: raise KeyError(f'{name}: port {p} unmapped')
    return f'{xname} ' + ' '.join(out) + f' {name}'


def hdr(ck, title='r10'):
    c, temp, vdd, bound = CORN[ck]
    return [f'* {title} {ck}', f'.include {PDK}/design.ngspice', f'.lib {PDK}/sm141064.ngspice {c}',
            f'.lib {PDK}/sm141064.ngspice res_{c}', f'.lib {PDK}/sm141064.ngspice diode_{c}',
            f'.lib {PDK}/sm141064.ngspice mimcap_{c}',
            f'.option temp={temp} gmin=1e-12 reltol=1e-3', f'VDD vdd 0 {vdd}']


def ctle_inst(kind, bound, code, en=True, byp=False, lfz=0, inp='inp', inn='inn', outp='slp', outn='sln', x='XC', name='pt_ctle'):
    p = net('ctle', kind, bound)
    m = dict(VDD_WIRE_SW='vdd', VSS='0', IBIAS='ib', ctle_en='vdd' if en else '0', wire_ctle_bypass='vdd' if byp else '0',
             RX_P=inp, RX_N=inn, CTLE_P=outp, CTLE_N=outn, atb_ctle_pbias='pb', atb_ctle_src='src')
    for k in range(3):
        m[f'ctle_peak{k}'] = 'vdd' if (code >> k) & 1 else '0'
        m[f'lf_zero{k}'] = 'vdd' if (lfz >> k) & 1 else '0'
    return [f'.include {p}', 'RIB vdd ib 260k', inst(x, p, name, m)]


WELL = H / 'stage' / 'well.json'      # written by the layout step: follower p-well area/perimeter per side


def well_lines(bound, outp='slp', outn='sln'):
    """Isolated p-well / DNWELL junction of each follower (Magic does not extract it): diode_pw2dw to the rail.
    Before the layout exists: 30 x 12 um well assumed.  pess x1.25, opt x0.75 on the area and perimeter."""
    a, pj = (360e-12, 84e-6)
    if WELL.exists():
        w = json.loads(WELL.read_text()); a, pj = w['area_m2'], w['perim_m']
    if VAR == 'f2': a, pj = 2 * a, 2 * pj        # two islands per side
    k = dict(nom=1.0, pess=1.25, opt=0.75)[bound]
    return [f'DWP {outp} vdd diode_pw2dw area={a * k:.4g} pj={pj * k:.4g}', f'DWN {outn} vdd diode_pw2dw area={a * k:.4g} pj={pj * k:.4g}']


SLICER_KIND = ['pub']      # what-if hook: path of an alternative slicer netlist


def slicer_noslwire():
    """Published slicer extraction without the wiring C on SL_P/N (what-if: SL re-route; callers add the new wiring C)."""
    p = NET / 'slicer_noslwire.spice'
    if not p.exists():
        p.write_text('\n'.join(l for l in (G / 'slicer.ext.spice').read_text().splitlines()
                               if not (l[:1] in 'Cc' and len(l.split()) >= 4 and {'SL_P', 'SL_N'} & set(l.split()[1:3]))) + '\n')
    return str(p)


def slicer_inst(bound, slp='slp', sln='sln', clocks=None, en='vdd', kind=None, x='XS', pre='', include=True):
    kind = kind or SLICER_KIND[0]
    """clocks None: static (CKP0-3 high, CKP4-7 low) as in r9chain; else dict CKPk -> node."""
    p = net('slicer', kind, bound)
    m = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en=en, SL_P=slp, SL_N=sln)
    for k in range(8):
        m[f'CKP{k}'] = (clocks or {}).get(f'CKP{k}', 'vdd' if k < 4 else '0')
    for q in ('VTAP', 'VTAN', 'VTBP', 'VTBN'): m[q] = 'vt08'
    outs = {'QCK': f'{pre}qck', **{f'{a}{j}': f'{pre}{a.lower()}{j}' for a in 'DE' for j in range(4)}}
    m.update(outs)
    return ([f'.include {p}', 'VVT vt08 0 0.8'] if include else []) + [inst(x, p, 'pt_slicer', m, default='0')]


def rxsel_inst(kind, bound, slp='slp', sln='sln', urx=('urxp', 'urxn'), en=True, direct=False, term=True):
    p = net('rxselect', kind, bound)
    m = dict(VDD_WIRE_SW='vdd', VSS='0', rxselect_en='vdd' if en else '0', rxselect_direct='vdd' if direct else '0',
             RX_P=urx[0], RX_N=urx[1], SL_P=slp, SL_N=sln)
    return [f'.include {p}', inst('XR', p, 'pt_rxselect', m)] + ([f'RU1 {urx[0]} 0 50', f'RU2 {urx[1]} 0 50'] if term else [])


def wmon_inst(bound, rxp='urxp', rxn='urxn', cp='slp', cn='sln'):     # RX taps sit on the USB pair (PINS.md); CTLE taps on SL
    p = net('wmon_sel', 'pub', bound)
    m = dict(VDD_WIRE_SW='vdd', VSS='0', wmon_en='0', wmon_sel0='0', wmon_sel1='0', RX_P=rxp, RX_N=rxn, CTLE_P=cp, CTLE_N=cn, WMON_IN='wm')
    return [f'.include {p}', inst('XM', p, 'pt_wmon_sel', m)]


def load_lines(ck, rxsel_kind='stg', slicer=True, clocks=None, route_f=30.0, extra_sl_f=0.0, direct=False):
    """Everything that hangs on SL in the r4 topology (follower output = SL): slicer, rxselect r2 (off gate), wmon_sel
    (off), top route C (bounded with the netlists: x1.15 / x0.85)."""
    bound = CORN[ck][3]
    k = dict(nom=1.0, pess=1.15, opt=0.85)[bound]
    L = []
    if slicer: L += slicer_inst(bound, clocks=clocks)
    L += rxsel_inst(rxsel_kind, bound, direct=direct, term=not direct) + wmon_inst(bound)
    c = (route_f + extra_sl_f) * k
    L += [f'CSP slp 0 {c:.4g}f', f'CSN sln 0 {c:.4g}f']
    return L


def run(tag, lines, timeout=7200):
    (RUN / f'{tag}.cir').write_text('\n'.join(lines) + '\n')
    r = subprocess.run(['ngspice', '-b', f'{tag}.cir'], cwd=RUN, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, OMP_NUM_THREADS='1'))
    log = r.stdout + r.stderr; (RUN / f'{tag}.log').write_text(log)
    return log


def meas(log, keys):
    out = {}
    for k in keys:
        m = re.search(rf'^{re.escape(k)}\s*=\s*([-+0-9.eE]+)', log, re.M)
        if m: out[k] = float(m.group(1))
    return out


def _vn(name):
    return name.replace('.json', f'_{VAR}.json') if VAR else name


def store(name, key, val):
    p = H / _vn(name); d = json.loads(p.read_text()) if p.exists() else {}
    d[key] = val; p.write_text(json.dumps(d, indent=1))


def stored(name):
    p = H / _vn(name)
    return json.loads(p.read_text()) if p.exists() else {}
