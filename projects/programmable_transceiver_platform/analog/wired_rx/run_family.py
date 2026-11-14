"""Regenerate the wired-receive family: schematics, layouts, DRC, LVS, extracted
simulations (nominal + operating-envelope corners), safety cases, RTL check and
per-block evidence records.

    python3 run_family.py                 # everything
    python3 run_family.py --blocks ctle   # subset
    python3 run_family.py --no-corners    # skip the 12-point corner sweep
"""
import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import netlists
import sims
import wrx_flow as f

CEILING = dict(termination=200000, rxlevel=50000, rxselect=80000, ctle=200000, slicer=360000, detect=180000,
               cdr=300000, wmon_sel=None, ptrim=60000)   # cdr: lead reallocated 300k for the speed pass
CORNERS = [(c, t, v) for c in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
NOMINAL = ('typical', 27, 3.3)
# one StrongARM sampler per device row keeps its sensitive nets row-local
COLUMNS = dict(slicer=40, detect=30, cdr=20, vthdac=16)
# r7 (vthdac): Metal4/escapes over the devices, and every port treated as quiet (A/B codes and VT lines are static or
# quasi-static, so no 4 um gaps between their trunks): 80.9k -> 23.9k um^2
LAYOUT_OPTS = dict(vthdac=dict(over_dev=True, quiet=lambda p: True))
# AP4-1 (cdr r13 repack, 2026-11-13): tracks and Metal5 trunks over the devices, rows filled to 260 um (COLUMNS['cdr']
# is then unused): 137.2k (r11, 20 columns) -> 82.9k um^2
LAYOUT_OPTS['cdr'] = dict(over_dev=True, trunks_over=True, row_width=260.)


# r10 (CTLE r4, 2026-11-14): the AP4-1 repack (22 columns, tracks and trunks over the devices) and the output-follower
# fix as ONE layout, with the AP4 review findings addressed: rows holding the matched input pair or the isolated-well
# followers carry no foreign metal (matched=), sp / atb_ctle_src / cp / cn get empty neighbour slots (spaced=), DC
# current paths are sized for the 85 C EM limits (currents=), antenna diodes that find no site get one (ant_retry=).
def _ctle_matched(d):
    return d.iso or (d.model.startswith('pfet') and d.nodes[1] in ('RX_P', 'RX_N'))


def _ctle_currents(d):
    """mA, + = the net feeds the terminal (nominal tt values; wrx_flow applies 1.3x)."""
    n = d.nodes
    if d.model.startswith('pfet') and n[1] == 'atb_ctle_pbias' and n[0] != 'atb_ctle_pbias':
        return {0: -0.0625, 2: 0.0625}                 # tail / follower-reference fingers
    if d.model.startswith('pfet') and n[1] in ('RX_P', 'RX_N'):
        return {0: -2.5 / 6, 2: 2.5 / 6}               # input pair finger
    if d.model.startswith('ppolyf') and n[0] in ('cp', 'cn'):
        return {0: 2.5 / netlists.CTLE_RL_M, 1: -2.5 / netlists.CTLE_RL_M}     # load strip
    if d.model.startswith('nfet') and n[0] in ('cp_rl', 'cn_rl'):
        return {0: 2.5 / netlists.CTLE_RL_M, 2: -2.5 / netlists.CTLE_RL_M}     # load switch finger
    if d.iso:
        return {0: 3.0, 2: -3.0}                       # follower (spread over wrx_flow.ISO_ESC escapes per terminal)
    if d.model.startswith('nfet') and n[1] == 'fbias':
        return {0: 0.31, 2: -0.31}                     # follower sink finger / mirror diode
    return {}


LAYOUT_OPTS['ctle'] = dict(over_dev=True, trunks_over=True, row_width=204., matched=_ctle_matched, currents=_ctle_currents,
                           spaced=('sp', 'atb_ctle_src', 'atb_ctle_pbias', 'cp', 'cn', 'CTLE_P', 'CTLE_N'), ant_retry=3,
                           track_before={'sp': 'atb_ctle_pbias'},
                           trunk_match=(('RX_P', 'RX_N'), ('sp', 'atb_ctle_src'), ('CTLE_P', 'CTLE_N'), ('cp_rl', 'cn_rl')))


def layout_block_slicer():
    """pt_slicer r2: compact cells + macro assembly (slicer_compact.py), same report keys as layout_block."""
    import slicer_compact as sc
    cells = {n: sc.build_cell(n) for n in sc.CELLS}
    top = sc.build_top()
    sub = f.parse_spice(f.HERE / 'slicer.spice')
    rep = dict(block='slicer', subckt=sub.name, devices=len(sub.devices), nets=len(sub.nets),
               drc_errors=top['drc_errors'] + sum(c['drc_errors'] for c in cells.values()), drc_details='',
               lvs_unique_match=bool(top['lvs']['unique_match'] and all(c['lvs']['unique_match'] for c in cells.values())),
               lvs_final=top['lvs']['summary'].strip(), size_um=top['layout']['size_um'], area_um2=top['layout']['area_um2'],
               area_ceiling_um2=CEILING['slicer'], gds_export=top['gds_export'],
               revision='r7 compact (slicer_compact.py: 4 x ws_sa + 4 x ws_sae + ws_ctl + 4 x ws_aux, layout_engine macro assembly)',
               cells={n: dict(drc_errors=c['drc_errors'], lvs_unique=c['lvs']['unique_match'], size_um=c['size_um'],
                              devices=c['devices']) for n, c in cells.items()},
               extraction='flat (ext2spice hierarchy off, cthresh 0, C only)')
    (f.GENERATED / 'slicer-layout.json').write_text(json.dumps(rep, indent=1, default=str) + '\n')
    return rep


def layout_block(block):
    if block == 'slicer':
        return layout_block_slicer()
    sub = f.parse_spice(f.HERE / f'{block}.spice')
    work = f.SCRATCH / 'layout' / block
    lay = f.generate_layout(sub, work, columns=COLUMNS.get(block), **LAYOUT_OPTS.get(block, {}))
    if lay.get('antenna_unplaced'):      # AP4 review: an unplaced antenna diode used to pass silently
        raise RuntimeError(f'{block}: antenna diode(s) without a legal site: {lay["antenna_unplaced"]}')
    ref = f.lvs_reference(f.HERE / f'{block}.spice', sub.name, lay.get('antenna_diodes'), work / 'lvs_reference.spice')
    lv = f.lvs(work, f'{sub.name}.lvs.spice', sub.name, ref, sub.name)
    f.GENERATED.mkdir(exist_ok=True)
    # Publishable GDS: re-export the saved flat cell with the analog image's Magic 8.3.678
    # (the canary's 8.3.623 drops HRES 62/0 on ppolyf_u_1k) and run KLayout GF180 DRC on it.
    exp = work / 'export'
    if exp.exists():
        shutil.rmtree(exp)
    exp.mkdir()
    shutil.copy(work / f'{sub.name}.mag', exp / f'{sub.name}.mag')
    gds_export = f.export_gds(exp, sub.name, sum(d.model.startswith('ppolyf') for d in sub.devices))
    shutil.copy(exp / f'{sub.name}.gds', f.GENERATED / f'{block}.gds')
    from gds_uniquify import publish_checked   # analog/ (on sys.path via wrx_flow)
    precheck = publish_checked(f.GENERATED / f'{block}.gds', block, sub.name)   # unique names + KLayout precheck
    for ext in ('mag', 'ext.spice'):
        shutil.copy(work / f'{sub.name}.{ext}', f.GENERATED / f'{block}.{ext}')
    shutil.copy(work / 'lvs.txt', f.SCRATCH / 'layout' / f'{block}-lvs.txt')
    drc_lines = (work / 'drc-details.txt').read_text().strip()
    rep = dict(block=block, subckt=sub.name, devices=len(sub.devices), nets=len(sub.nets),
               drc_errors=lay['drc_count'], drc_details=drc_lines[:2000] if lay['drc_count'] else '',
               lvs_unique_match=lv['unique_match'], lvs_final=lv['final_result'],
               size_um=lay['size_um'], area_um2=lay['area_um2'], area_ceiling_um2=CEILING.get(block),
               gds_export=gds_export, klayout_precheck=precheck,
               grid=dict(columns=lay['columns'], rows=lay['rows'], pitch_um=lay['pitch_um']))
    (f.GENERATED / f'{block}-layout.json').write_text(json.dumps(rep, indent=1) + '\n')
    return rep


def sim_block(block, netkind, corner, temp, vdd):
    sub = f.parse_spice(f.HERE / f'{block}.spice')
    net = f.HERE / f'{block}.spice' if netkind == 'sch' else f.GENERATED / f'{block}.ext.spice'
    if netkind == 'ext':
        sub = f.parse_spice(net)  # port order of the extraction
    tag = f'{netkind}_{corner}_{temp}_{vdd}'
    benches = sims.BENCHES[block]
    if block == 'slicer':
        rates = tuple(4 * fr for fr in sims.RING_PLAN)
        dl = f.slicer_delays(sub, net, rates, tag, corner, temp, vdd)
        benches = [lambda s, n, **k: sims.tb_slicer_plan(s, n, delays=dl, **k),
                   lambda s, n, **k: sims.tb_slicer(s, n, rates=(), usb=False, **k)]   # offset / trim ramps
    return f.run_cases(block, sub, net, benches, tag, corner=corner, temp=temp, vdd=vdd)


MAXRATE = dict(slicer=(3.6e9, 4e9))   # above the ring plan (3.24 Gb/s quarter): margin, non-gating


def maxrate_block(block, corner, temp, vdd):
    """Non-gating rate sweep at one corner: slicer line rates, CDR PI half-rate clock frequencies."""
    net = f.GENERATED / f'{block}.ext.spice'
    sub = f.parse_spice(net)
    tag = f'maxrate_{corner}_{temp}_{vdd}'
    if block == 'slicer':
        dl = f.slicer_delays(sub, net, MAXRATE['slicer'], tag, corner, temp, vdd)
        fn = lambda s, n, **k: sims.tb_slicer(s, n, rates=MAXRATE['slicer'], offsets=False, usb=False, delays=dl, **k)
    else:
        fn = lambda s, n, **k: [c for fck in MAXRATE['cdr'] for c in sims.tb_cdr(s, n, fck=fck, codes=range(0, 32, 4), **k)]
    r = f.run_cases(block, sub, net, [fn], tag, corner=corner, temp=temp, vdd=vdd)
    for m in r.values():
        m['gating'] = False
    return r


EXPLORE = dict(  # non-gating: above the nominal verified rate, incl. the 5 Gb/s stretch goal
    slicer=[('slicer_5g', lambda sub, n, **k: sims.tb_slicer(
        sub, n, rates=(4e9, 5e9), offsets=False, usb=False,
        delays=f.slicer_delays(sub, f.GENERATED / 'slicer.ext.spice', (4e9, 5e9), 'explore_delay'), **k))],
    detect=[('thresholds', sims.tb_detect_thresholds)])


def explore_block(block):
    net = f.GENERATED / f'{block}.ext.spice'
    sub = f.parse_spice(net)
    out = {}
    for tag, fn in EXPLORE.get(block, []):
        r = f.run_cases(block, sub, net, [fn], 'explore_' + tag)
        for m in r.values():
            m['gating'] = False
        out.update(r)
    return out


LOADING = dict(  # (label, probe port, static controls high)
    ctle=[('rx_p_ctle_on', 'RX_P', {'ctle_en'}), ('rx_p_all_off', 'RX_P', set()),
          ('ctle_p_ctle_on_bypass_off', 'CTLE_P', {'ctle_en'})],
    wmon_sel=[('rx_p_wmon_off', 'RX_P', set()), ('ctle_p_wmon_off', 'CTLE_P', set())],
    rxselect=[('ctle_p_rxselect_direct', 'CTLE_P', {'rxselect_en', 'rxselect_direct'})],
    detect=[('rx_p_detect_off', 'RX_P', set()), ('tx_p_detect_off', 'TX_P', set())])


def loading_block(block):
    net = f.GENERATED / f'{block}.ext.spice'
    sub = f.parse_spice(net)
    out = {}
    for label, probe, high in LOADING.get(block, []):
        text, analyse = sims.tb_loading(sub, 'dut.spice', block, None, probe, {p: 1 for p in high})
        work = f.SCRATCH / 'sim' / block / 'loading' / label
        work.mkdir(parents=True, exist_ok=True)
        shutil.copy(net, work / 'dut.spice')
        (work / 'tb.cir').write_text(text)
        out[label] = analyse(f.ngspice(work, 'tb.cir'), None).get('cap_fF')
    return out


def safe_block(block):
    sub = f.parse_spice(f.GENERATED / f'{block}.ext.spice')
    out = {}
    for case, text, analyse in sims.tb_safe(sub, 'dut.spice', block):
        work = f.SCRATCH / 'sim' / block / 'safe' / case
        work.mkdir(parents=True, exist_ok=True)
        shutil.copy(f.GENERATED / f'{block}.ext.spice', work / 'dut.spice')
        (work / 'tb.cir').write_text(text)
        log = f.ngspice(work, 'tb.cir')
        try:
            out[case] = analyse(log, None)
        except Exception as exc:
            out[case] = dict(passed=False, error=repr(exc)[:300])
            out[case]['pass'] = False
    return out


CLOSED = [  # extracted runs with timing's pll_ring.ext (tt/27C/3.3V): name, kind, gating, kwargs
    # frequency acquisition to 625 MHz, hand-over (REF gate + IB_PLL clamp at an FBCK falling edge),
    # then BB pump steps (no slicer).  Measures the hand-over step the FLL must remove.
    ('acq_625m', 'acq', True, dict(T=4.6e-6, thold=1.6e-6, vc0=1.15, up=(3.4e-6, 3.5e-6), dn=(3.9e-6, 4.0e-6))),
    # bang-bang phase loop after the FLL (emulated): freq_hold=1 from t=0 (REF gated, PLL pump bias
    # clamped), VCTRL pre-charged to vc0 until tpre.  Step 1 (no data/PD) measures the free-running
    # ring frequency f1 in this state; step 2 runs with line rate = bpc * f1 * (1 + 500 ppm), i.e. as
    # if the FLL had left a +500 ppm residual, and the slicer + PD stand-in close the phase loop.
    ('track_quarter', 'track', True, dict(rate=2.5e9, bpc=4, track_only=True, vc0=1.158, T=3.4e-6, thold=1.0e-6,
                                          tpre=1.0e-6, settle=1.0e-6, fll_residual_ppm=500)),
    ('track_half', 'track', True, dict(rate=1.25e9, bpc=2, track_only=True, vc0=1.158, T=3.4e-6, thold=1.0e-6,
                                       tpre=1.0e-6, settle=1.0e-6, fll_residual_ppm=500)),
    # full dual loop WITHOUT the FLL step (PFD lock, hand-over, BB loop directly): non-gating record
    ('dual_quarter_2g5_no_fll', 'closed', False, dict(rate=2.5e9, bpc=4, T=4.4e-6, thold=1.6e-6, tpre=0.2e-6,
                                                      vc0=1.15, settle=1.2e-6)),
    ('dual_half_1g25_no_fll', 'closed', False, dict(rate=1.25e9, bpc=2, T=4.4e-6, thold=1.6e-6, tpre=0.2e-6,
                                                    vc0=1.15, settle=1.2e-6))]
CLOSED_STORE = f.SCRATCH / 'cdr-closed.json'

# AC-3 (2026-11-10): pt_cdr r-ac3 + pll_ring (HOLD from t=0) + slicer r2, all extracted, tt/27C/3.3V.
# Line rates are set relative to the measured free-running ring f1 at vc0 (the FLL result stand-in):
# the loop must pull in the static offset with the integral path alone (no hand-over).  name, gating, kwargs
AC3 = [('ac3_q_p600', True, dict(bpc=4, ppm=600)),
       ('ac3_q_m5600', True, dict(bpc=4, ppm=-5600)),
       ('ac3_h_p600', True, dict(bpc=2, ppm=600)),
       ('ac3_h_m5600', True, dict(bpc=2, ppm=-5600)),
       # SSC slope: -400 ppm/us ramp (> the 330 ppm/us of a 33 kHz 0..-5000 ppm triangle) from release
       ('ac3_q_ramp', True, dict(bpc=4, ppm=0, ppm_per_us=-400, T=5.0e-6)),
       # sinusoidal jitter points (jitter tolerance), +600 ppm static offset
       ('ac3_q_sj03_2m', False, dict(bpc=4, ppm=600, sj_ui=0.3, sj_hz=2e6, T=5.0e-6)),
       ('ac3_q_sj01_10m', False, dict(bpc=4, ppm=600, sj_ui=0.1, sj_hz=10e6))]
AC3_STORE = f.SCRATCH / 'cdr-ac3.json'


def ac3_free(vc0=1.16, rate=2.5e9, bpc=4, tpre=0.8e-6):
    """Free-running RX ring with HOLD_PLL=1 from t=0 and VCTRL released from vc0 at tpre (no votes)."""
    work = f.SCRATCH / 'ac3' / f'free_bpc{bpc}'
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(f.PROJECT / 'analog/timing/generated/pll_ring.ext.spice', work / 'pll.spice')
    shutil.copy(f.GENERATED / 'cdr.ext.spice', work / 'cdr.spice')
    shutil.copy(f.GENERATED / 'slicer.ext.spice', work / 'sl.spice')
    psub = sims.subckt_ports(work / 'pll.spice', 'pt_pll_ring')
    body, ctl, an = sims.tb_cdr_ac3(psub, f.parse_spice(work / 'sl.spice'), f.parse_spice(work / 'cdr.spice'),
                                    rate=rate, bpc=bpc, T=tpre + 0.8e-6, tpre=tpre, vc0=vc0, bb=False,
                                    vz_node=vz_node(work / 'pll.spice'), settle=0.2e-6)
    (work / 'tb.cir').write_text('\n'.join([f'* ac3 free', sims.sim_header('typical', 27), '.include pll.spice',
                                            '.include sl.spice', '.include cdr.spice', body, '.control', ctl, '.endc', '.end']))
    log = f.ngspice(work, 'tb.cir', timeout=10 * 3600)
    r = an(log, work / 'tran.txt')
    r['pll_ring_ext_sha256'] = f.sha256(work / 'pll.spice')
    r['cdr_ext_sha256'] = f.sha256(work / 'cdr.spice')
    return r, work


def ac3_one(name, kw, f1, src):
    kw = dict(kw)
    bpc = kw.pop('bpc')
    work = f.SCRATCH / 'ac3' / name
    work.mkdir(parents=True, exist_ok=True)
    for n in ('pll.spice', 'cdr.spice', 'sl.spice'):
        shutil.copy(src / n, work / n)
    psub = sims.subckt_ports(work / 'pll.spice', 'pt_pll_ring')
    rate = bpc * f1     # ppm/ramp/SJ are applied relative to the free-running ring
    body, ctl, an = sims.tb_cdr_ac3(psub, f.parse_spice(work / 'sl.spice'), f.parse_spice(work / 'cdr.spice'),
                                    rate=rate, bpc=bpc, vz_node=vz_node(work / 'pll.spice'), **kw)
    (work / 'tb.cir').write_text('\n'.join([f'* {name}', sims.sim_header('typical', 27), '.include pll.spice',
                                            '.include sl.spice', '.include cdr.spice', body, '.control', ctl, '.endc', '.end']))
    log = f.ngspice(work, 'tb.cir', timeout=10 * 3600)
    try:
        r = an(log, work / 'tran.txt')
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-500:], **{'pass': False})
    r.update(kwargs=kw, free_running_ring_hz=f1, pll_ring_ext_sha256=f.sha256(work / 'pll.spice'),
             cdr_ext_sha256=f.sha256(work / 'cdr.spice'), slicer_ext_sha256=f.sha256(work / 'sl.spice'))
    return r


def run_ac3(only=None, jobs=1):
    """Free-running reference first (one per rate mode), then the AC-3 cases; results in AC3_STORE."""
    res = json.loads(AC3_STORE.read_text()) if AC3_STORE.exists() else {}
    free = {}
    for bpc in sorted({k['bpc'] for n, g, k in AC3 if not only or n in only}):
        r, work = ac3_free(bpc=bpc)
        res[f'free_bpc{bpc}'] = r
        AC3_STORE.write_text(json.dumps(res, indent=1, default=float))
        free[bpc] = (r.get('ring_hz_end_fit'), work)
        print('ac3 free', bpc, r.get('ring_hz_end_fit'), flush=True)
    cases = [(n, g, k) for n, g, k in AC3 if not only or n in only]
    with ThreadPoolExecutor(jobs) as ex:
        futs = {n: (g, ex.submit(ac3_one, n, k, *free[k['bpc']])) for n, g, k in cases}
        for n, (g, fu) in futs.items():
            res[n] = dict(fu.result(), gating=g)
            AC3_STORE.write_text(json.dumps(res, indent=1, default=float))
            print('ac3', n, {k: res[n].get(k) for k in ('bits_checked', 'bit_errors', 'ring_hz_end_fit', 'pass', 'error')}, flush=True)
    return res


def vz_node(pll_ext):
    """Extracted name of pt_pll_ring's C1 node (the R-C1 loop-filter integrator) inside the subckt."""
    for line in Path(pll_ext).read_text().splitlines():
        if line.startswith('XXC1_0 '):
            return line.split()[2]
    return None


def closed_one(name, kind, kw, pll_src=None):
    if kind == 'track':
        kw = dict(kw)
        res_ppm = kw.pop('fll_residual_ppm')
        r1 = closed_one(name + '_free', 'closed', dict(kw, bb=False, T=kw['tpre'] + 0.6e-6, thold=kw['tpre'],
                                                       settle=0.2e-6))
        f1 = r1.get('ring_hz_end_fit')
        if not f1:
            return dict(r1, pass_=False, error='free-running ring frequency not measured', kind=kind)
        # same pll_ring netlist as step 1 (the timing family may regenerate it meanwhile)
        r = closed_one(name, 'closed', dict(kw, data_rate=kw['bpc'] * f1 * (1 + res_ppm * 1e-6)),
                       pll_src=f.SCRATCH / 'closed' / (name + '_free') / 'pll.spice')
        r.update(kind=kind, free_running_ring_hz=f1, fll_residual_ppm=res_ppm)
        return r
    work = f.SCRATCH / 'closed' / name
    work.mkdir(parents=True, exist_ok=True)
    src = pll_src or f.PROJECT / 'analog/timing/generated/pll_ring.ext.spice'
    if Path(src).resolve() != (work / 'pll.spice').resolve():
        shutil.copy(src, work / 'pll.spice')
    shutil.copy(f.GENERATED / 'cdr.ext.spice', work / 'cdr.spice')
    csub = f.parse_spice(work / 'cdr.spice')
    psub = sims.subckt_ports(work / 'pll.spice', 'pt_pll_ring')
    if kind == 'acq':
        body, ctl, an = sims.tb_cdr_acq(psub, csub, **kw)
        inc = ['.include pll.spice', '.include cdr.spice']
    else:
        shutil.copy(f.GENERATED / 'slicer.ext.spice', work / 'sl.spice')
        if kw.get('track_only'):
            kw = dict(kw, vz_node=vz_node(work / 'pll.spice'))
        body, ctl, an = sims.tb_cdr_closed(psub, f.parse_spice(work / 'sl.spice'), csub, **kw)
        inc = ['.include pll.spice', '.include sl.spice', '.include cdr.spice']
    (work / 'tb.cir').write_text('\n'.join([f'* {name}', sims.sim_header('typical', 27), *inc, body, '.control',
                                            ctl, '.endc', '.end']))
    log = f.ngspice(work, 'tb.cir', timeout=10 * 3600)
    try:
        r = an(log, work / 'tran.txt')
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-500:])
        r['pass'] = False
    r['kwargs'] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}
    r['kind'] = kind
    r['pll_ring_ext_sha256'] = f.sha256(work / 'pll.spice')
    return r


def rtl_check():
    """Behavioural closed loop (pt_wrx_cdr_loop RTL + analog loop model calibrated on the extracted runs)."""
    rtl = f.HERE / 'rtl'
    res = {}
    # (bpc, UI ps, ppm, SSC ppm, UIs, hand-over step ppm, leak nA, FLL window k or None)
    #  * no step: the bang-bang loop alone (ppm, SSC tracking)
    #  * +/-2000 / 4000 ppm steps without the FLL: capture range of the bang-bang loop (non-gating)
    #  * +3.5 % / -2 % steps (the extracted hand-over moved the ring +1.3..3.4 %) with the
    #    frequency-counter hand-over (FLL, cfg_fll_en=1) and a +/-1 nA leak on VCTRL
    cases = [(4, 400.0, p, 0, 60000, 0, 0, None) for p in (0, 300, -300)] + [(4, 400.0, 0, -5000, 170000, 0, 0, None)] + \
            [(2, 800.0, p, 0, 60000, 0, 0, None) for p in (0, 300, -300)] + [(2, 800.0, 0, -5000, 90000, 0, 0, None)] + \
            [(1, 2083.3, p, 0, 40000, 0, 0, None) for p in (0, 500, -500)] + \
            [(b, 1600.0 / b, 0, 0, 60000, hs, 0, None) for b in (4, 2) for hs in (2000, -2000, 4000)] + \
            [(4, 400.0, 0, 0, 300000, 35000, 1, 6), (4, 400.0, 300, 0, 300000, -20000, -1, 6),
             (2, 800.0, 0, 0, 220000, 35000, 1, 7), (2, 800.0, -300, 0, 220000, -20000, -1, 7),
             (4, 400.0, 0, -5000, 400000, 35000, 1, 6)]
    def one(case):
        bpc, ui, ppm, ssc, nui, hs, leak, win = case
        par = dict(BPC=bpc, UI_PS=ui, PPM=ppm, SSC_PPM=ssc, HOLD_STEP_PPM=hs, ILEAK=f'{leak}e-9', NUI=nui,
                   CHECK_FROM_UI=min(30000, nui // 2) if win is None else 50000)
        if win is not None:
            par.update(FLL_EN=1, FLL_WIN=win)
        key = f'bpc{bpc}_ui{ui:g}ps_{ppm}ppm_ssc{ssc}' + (f'_holdstep{hs}ppm' if hs else '') + \
              (f'_leak{leak}nA' if leak else '') + (f'_fll_k{win}' if win is not None else '')
        vvp = f.SCRATCH / f'cdr_tb_{key}.vvp'
        subprocess.run(['iverilog', '-g2012', *[f'-Ptb_pt_wrx_cdr_loop.{k}={v}' for k, v in par.items()],
                        '-o', str(vvp), str(rtl / 'tb_pt_wrx_cdr_loop.sv'), str(rtl / 'pt_wrx_cdr_loop.sv')], check=True)
        out = subprocess.run(['vvp', str(vvp)], capture_output=True, text=True, timeout=4 * 3600).stdout
        return key, [l for l in out.splitlines() if l.startswith(('RESULT', 'PASS', 'FAIL'))]
    with ThreadPoolExecutor(6) as ex:      # iverilog processes (no containers)
        for key, lines in ex.map(one, cases):
            res[key] = lines
    syn = subprocess.run(['yosys', '-q', '-p', f'read_verilog -sv {rtl / "pt_wrx_cdr_loop.sv"}; synth -top pt_wrx_cdr_loop; stat'],
                         capture_output=True, text=True)
    res['yosys_generic_synth'] = dict(returncode=syn.returncode)
    (f.GENERATED / 'cdr-rtl-check.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blocks', nargs='*', default=list(netlists.BLOCKS))
    ap.add_argument('--no-corners', action='store_true')
    ap.add_argument('--no-layout', action='store_true')
    ap.add_argument('--no-closed', action='store_true', help='skip the multi-hour extracted CDR acquisition/tracking runs')
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--rtl-json', help='reuse a saved rtl_check() result instead of re-running it')
    a = ap.parse_args()
    netlists.write_all()
    results = {b: {} for b in a.blocks}
    if not a.no_layout:
        with ThreadPoolExecutor(4) as ex:
            for rep in ex.map(layout_block, a.blocks):
                results[rep['block']]['layout'] = rep
                print('layout', rep['block'], rep['drc_errors'], rep['lvs_final'], rep['area_um2'], flush=True)
    else:
        for b in a.blocks:
            results[b]['layout'] = json.loads((f.GENERATED / f'{b}-layout.json').read_text())
    jobs = []
    for b in a.blocks:
        jobs.append((b, 'sch', *NOMINAL))
        jobs.append((b, 'ext', *NOMINAL))
        if not a.no_corners:
            jobs += [(b, 'ext', *c) for c in CORNERS]
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = {j: ex.submit(sim_block, *j) for j in jobs}
        safes = {b: ex.submit(safe_block, b) for b in a.blocks}
        explores = {b: ex.submit(explore_block, b) for b in a.blocks if b in EXPLORE}
        loads = {b: ex.submit(loading_block, b) for b in a.blocks if b in LOADING}
        maxr = {(b, *c): ex.submit(maxrate_block, b, *c) for b in a.blocks if b in MAXRATE
                for c in ([] if a.no_corners else CORNERS) + [NOMINAL]}
        for j, fu in futs.items():
            b, kind, c, t, v = j
            results[b].setdefault('sims', {})[f'{kind}_{c}_{t}C_{v}V'] = fu.result()
            print('sim', j, all(m.get('pass') for m in fu.result().values()), flush=True)
        for (b, c, t, v), fu in maxr.items():
            results[b].setdefault('maxrate', {})[f'{c}_{t}C_{v}V'] = fu.result()
            print('maxrate', b, c, t, v, {k: m.get('pass') for k, m in fu.result().items()}, flush=True)
        for b, fu in loads.items():
            results[b]['bypass_loading_fF'] = fu.result()
            print('loading', b, fu.result(), flush=True)
        for b, fu in explores.items():
            results[b]['explore'] = fu.result()
            print('explore', b, {k: v.get('pass') for k, v in fu.result().items()}, flush=True)
        for b, fu in safes.items():
            results[b]['safe'] = fu.result()
            print('safe', b, {k: v.get('pass') for k, v in fu.result().items()}, flush=True)
    if 'cdr' in a.blocks:
        results['cdr']['rtl'] = json.loads(Path(a.rtl_json).read_text()) if a.rtl_json else rtl_check()
        if not a.no_closed:
            results['cdr']['ac3'] = run_ac3()
        elif AC3_STORE.exists():
            # --no-closed: reuse the last AC-3 extracted closed-loop results (each records its netlist shas)
            results['cdr']['ac3'] = dict(json.loads(AC3_STORE.read_text()), reused_from=str(AC3_STORE))
    for b in a.blocks:
        (f.SCRATCH / f'{b}-results.json').write_text(json.dumps(results[b], indent=1, default=str))
    import importlib.util    # by path: slicer_compact/wrx_compact put analog/timing (with its own evidence.py) on sys.path
    spec = importlib.util.spec_from_file_location('wrx_evidence', f.HERE / 'evidence.py')
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    for b in a.blocks:
        evidence.write(b, results[b])


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    main()
