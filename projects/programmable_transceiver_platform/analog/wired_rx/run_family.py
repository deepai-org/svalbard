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
               cdr=300000, wmon_sel=None)   # cdr: lead reallocated 300k for the speed pass
CORNERS = [(c, t, v) for c in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
NOMINAL = ('typical', 27, 3.3)
# one StrongARM sampler per device row keeps its sensitive nets row-local
COLUMNS = dict(slicer=40, detect=30, cdr=20)


def layout_block(block):
    sub = f.parse_spice(f.HERE / f'{block}.spice')
    work = f.SCRATCH / 'layout' / block
    lay = f.generate_layout(sub, work, columns=COLUMNS.get(block))
    lv = f.lvs(work, f'{sub.name}.lvs.spice', sub.name, f.HERE / f'{block}.spice', sub.name)
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
    for ext in ('mag', 'ext.spice'):
        shutil.copy(work / f'{sub.name}.{ext}', f.GENERATED / f'{block}.{ext}')
    shutil.copy(work / 'lvs.txt', f.SCRATCH / 'layout' / f'{block}-lvs.txt')
    drc_lines = (work / 'drc-details.txt').read_text().strip()
    rep = dict(block=block, subckt=sub.name, devices=len(sub.devices), nets=len(sub.nets),
               drc_errors=lay['drc_count'], drc_details=drc_lines[:2000] if lay['drc_count'] else '',
               lvs_unique_match=lv['unique_match'], lvs_final=lv['final_result'],
               size_um=lay['size_um'], area_um2=lay['area_um2'], area_ceiling_um2=CEILING.get(block),
               gds_export=gds_export,
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
        dl = f.slicer_delays(sub, net, (1e9, 480e6), tag, corner, temp, vdd)
        benches = [lambda s, n, **k: sims.tb_slicer(s, n, delays=dl, **k)]
    return f.run_cases(block, sub, net, benches, tag, corner=corner, temp=temp, vdd=vdd)


MAXRATE = dict(slicer=(1.5e9, 2e9, 2.5e9, 2.97e9))


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
            with ThreadPoolExecutor(3) as ex:     # at most 3 simulation containers
                futs = {n: (g, ex.submit(closed_one, n, k, kw)) for n, k, g, kw in CLOSED}
                results['cdr']['closed'] = {n: dict(fu.result(), gating=g) for n, (g, fu) in futs.items()}
            CLOSED_STORE.write_text(json.dumps(results['cdr']['closed'], indent=1, default=float))
        elif CLOSED_STORE.exists():
            # --no-closed: reuse the last extracted closed-loop results (each records its pll_ring sha)
            results['cdr']['closed'] = dict(json.loads(CLOSED_STORE.read_text()), reused_from=str(CLOSED_STORE))
            print('closed', {n: (r.get('bit_errors'), r.get('bits_checked')) for n, r in results['cdr']['closed'].items()
                             if isinstance(r, dict)}, flush=True)
    for b in a.blocks:
        (f.SCRATCH / f'{b}-results.json').write_text(json.dumps(results[b], indent=1, default=str))
    import evidence
    for b in a.blocks:
        evidence.write(b, results[b])


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    main()
