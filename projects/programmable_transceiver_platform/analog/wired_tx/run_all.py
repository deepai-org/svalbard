"""Regenerate every wired-TX deliverable: netlist, layout, DRC/LVS, extraction,
simulations and the evidence records in generated/.

Stages (each can be selected with --only):
  layout   cells.py -> wiredtx.spice; layoutgen.py (Magic, digital image);
           GDS re-export with the analog image's Magic + KLayout DRC; Netgen LVS
  sims     extracted transient/static simulations (<= 3 concurrent jobs)
  evidence generated/*-evidence.json from the stored results
"""
import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cells as C
import layoutgen
import sim_integration as I
import sim_static as T
import sim_wiredtx as S
import tools

W = tools.SCRATCH
LAY = W / 'layout'
GEN = tools.GENERATED
PEX = LAY / 'pt_wiredtx_pex.spice'
NOMINAL = dict(rate=1.25e9, bpc=2)          # half-rate mode, ring 625 MHz
# Performance envelope (spec/tapeout-plan.md, MANDATE.md): every process corner at 22/32 C and
# 3.15/3.35 V (20 points; sf/fs were missing before).  Safety benches stay wide (sim_static).
CORNERS = [(c, t, v) for c in ('typical', 'ss', 'ff', 'sf', 'fs') for t in (22, 32) for v in (3.15, 3.35)]
SWEEP = [(1.92e9, 4), (2.5e9, 4), (2.97e9, 4), (3.24e9, 4), (0.96e9, 2), (1.25e9, 2), (1.62e9, 2), (0.48e9, 1),
         (0.81e9, 1)]
NW = 14            # 280 bits: nominal / integration runs, more than two PRBS7 periods (127 bits)
NWC = 10           # 200 bits per envelope-corner run (> 1.5 PRBS7 periods)
QRATES = (2.5e9, 3.24e9)   # quarter rate: PCIe Gen1 and the top of the 480-810 MHz ring plan
ROW_W = 540.0   # parent row width = width of the hand-placed core macro (wtx_serq4, row 0)


def with_antenna_diodes(src, dst, top, summary, cell=None):
    """LVS reference = schematic + the generator's antenna diodes (layoutgen summary).

    Diodes sit on flat (layout) net names such as CG/A0, which only exist inside subcircuits of the
    hierarchical schematic, so when diodes were placed the top subckt is replaced by its flattened
    device list (the same list layoutgen places); macros stay black-box subcircuits."""
    import re
    import antenna_diodes as ad
    text = Path(src).read_text()
    lines = ad.spice_lines(summary.get('antenna_diodes', []))
    if lines:
        cell = cell or C.TOP
        k = text.index(f'.subckt {top} ')
        e = text.index('\n', text.index('.ends', k))
        flat = [f'.subckt {top} {" ".join(cell.ports)}']
        for d in C.layout_devices(cell):
            if isinstance(d, C.MacroDev):
                flat.append(f'X{d.name.replace("/", "__")} {" ".join(d.nodes)} {d.model}')
            else:
                flat.append(d.spice().replace(f'X{d.name}', 'X' + d.name.replace('/', '__'), 1))
        flat += lines + [f'.ends {top}']
        text = text[:k] + '\n'.join(flat) + text[e:]
    Path(dst).write_text(text)


def publish_gds(gds, block, top, work):
    """Block-unique subcell names, then the required KLayout precheck (DRC + antenna) record."""
    from gds_uniquify import publish_checked
    return publish_checked(gds, block, top)


def stage_layout():
    subprocess.run([sys.executable, str(tools.HERE / 'cells.py')], check=True)
    if LAY.exists():
        shutil.rmtree(LAY)
    summary = layoutgen.generate(LAY, row_width=ROW_W)
    with_antenna_diodes(tools.HERE / 'wiredtx.spice', LAY / 'wiredtx.spice', 'pt_wiredtx', summary)
    lvs = tools.netgen_lvs(LAY, 'pt_wiredtx_lvs.spice', 'pt_wiredtx', 'wiredtx.spice')
    gds = tools.gds_export_analog(LAY, 'pt_wiredtx')
    kl = tools.klayout_drc(LAY, gds, 'pt_wiredtx')
    GEN.mkdir(exist_ok=True)
    shutil.copy(gds, GEN / 'wiredtx.gds')
    precheck = publish_gds(GEN / 'wiredtx.gds', 'wiredtx', 'pt_wiredtx', LAY)
    magdir = GEN / 'mag'
    if magdir.exists():
        shutil.rmtree(magdir)
    magdir.mkdir()
    for m in LAY.glob('pt_wiredtx__p*.mag'):
        shutil.copy(m, magdir / m.name)
    shutil.copy(LAY / 'pt_wiredtx.mag', magdir / 'pt_wiredtx.mag')
    shutil.copy(PEX, GEN / 'wiredtx.ext.spice')
    shutil.copy(LAY / 'pt_wiredtx_lvs.spice', GEN / 'wiredtx.lvs.spice')
    shutil.copy(LAY / 'lvs.out', GEN / 'wiredtx-lvs.txt')
    (GEN / 'wiredtx-drc.txt').write_text(f"magic drc(full) flat error count: {summary['drc_count']}\n"
                                         + (LAY / 'drc-why.txt').read_text())
    res = dict(layout=summary, lvs=lvs, klayout=kl, klayout_precheck=precheck,
               gds_export='analog image Magic 8.3.678, cif ostyle gdsii',
               magic_drc_lvs_extract_image=tools.DIGITAL_IMAGE)
    tools.write_json(W / 'layout-result.json', res)
    return res


def stage_hsbias():
    """USB HS bias DAC (P3-12): layout, DRC/LVS/KLayout, extracted checks."""
    import sim_hsbias as H
    L = W / 'hs_layout'
    if L.exists():
        shutil.rmtree(L)
    s = layoutgen.generate(L, cell=C.HSBIAS, row_width=120)
    with_antenna_diodes(tools.HERE / 'hsbias.spice', L / 'hsbias.spice', 'pt_wtx_hsbias', s, C.HSBIAS)
    lvs = tools.netgen_lvs(L, 'pt_wtx_hsbias_lvs.spice', 'pt_wtx_hsbias', 'hsbias.spice')
    g = tools.gds_export_analog(L, 'pt_wtx_hsbias')
    kl = tools.klayout_drc(L, g, 'pt_wtx_hsbias')
    tools.write_json(W / 'hs-layout-result.json', dict(layout=s, lvs=lvs, klayout=kl,
                                                       gds_export='analog image Magic 8.3.678, cif ostyle gdsii'))
    P = L / 'pt_wtx_hsbias_pex.spice'
    res = dict(tt=H.sweep(W / 'hs_sim', P), settle=H.settle(W / 'hs_sim', P),
               **{f'{c}_{t}_{v}': H.sweep(W / 'hs_sim', P, c, t, v) for c, t, v in CORNERS})
    tools.write_json(W / 'hs-sim-results.json', res)
    shutil.copy(g, GEN / 'hsbias.gds')
    publish_gds(GEN / 'hsbias.gds', 'hsbias', 'pt_wtx_hsbias', L)
    (GEN / 'mag_hsbias').mkdir(exist_ok=True)
    for m in L.glob('*.mag'):
        shutil.copy(m, GEN / 'mag_hsbias' / m.name)
    shutil.copy(P, GEN / 'hsbias.ext.spice')
    shutil.copy(L / 'lvs.out', GEN / 'hsbias-lvs.txt')


def jobs():
    j = []
    j.append(('nominal', lambda: S.run_case(W / 'sim', PEX, 'pt_wiredtx', nwords=NW, tag='nominal', **NOMINAL)))
    j.append(('schematic_q3g24', lambda: S.run_case(W / 'sim', tools.HERE / 'wiredtx.spice', 'pt_wiredtx',
                                                    rate=3.24e9, bpc=4, nwords=NW, tag='sch_q3g24')))
    for rate, bpc in SWEEP:
        j.append((f'sweep_{bpc}_{rate/1e9:g}', lambda r=rate, b=bpc: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', rate=r, bpc=b, nwords=NW, tag=f'sweep_{b}_{r/1e9:g}')))
    # quarter rate (compact core) across the envelope
    for rate in QRATES:
        for c, t, v in CORNERS:
            k = f'cornerq{rate/1e9:g}_{c}_{t}_{v}'
            j.append((k, lambda c=c, t=t, v=v, r=rate, k=k: S.run_case(
                W / 'sim', PEX, 'pt_wiredtx', rate=r, bpc=4, nwords=NWC, corner=c, temp=t, vdd=v, tag=k)))
    # half rate (compact core): top of the half-rate range (ring 810 MHz) across the envelope
    for c, t, v in CORNERS:
        k = f'cornerh1.62_{c}_{t}_{v}'
        j.append((k, lambda c=c, t=t, v=v, k=k: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', rate=1.62e9, bpc=2, nwords=NWC, corner=c, temp=t, vdd=v, tag=k)))
    # full rate (compact core, UI >= 1.23 ns): slow/skewed corners
    for c, t, v in [(c, t, v) for c in ('ss', 'sf', 'fs') for t, v in ((22, 3.15), (32, 3.15))]:
        k = f'cornerf0.81_{c}_{t}_{v}'
        j.append((k, lambda c=c, t=t, v=v, k=k: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', rate=0.81e9, bpc=1, nwords=NWC, corner=c, temp=t, vdd=v, tag=k)))
    j.append(('nominal_0g96', lambda: S.run_case(W / 'sim', PEX, 'pt_wiredtx', rate=0.96e9, bpc=2, nwords=NW,
                                                tag='nominal_0g96')))
    # generic serializer, kept as the fallback (rate code 11 = half rate)
    for rate, (c, t, v) in ((0.96e9, ('typical', 27, 3.3)), (0.96e9, ('ss', 22, 3.15)), (1.25e9, ('typical', 27, 3.3))):
        k = f'fallback_h{rate/1e9:g}_{c}_{t}_{v}'
        j.append((k, lambda r=rate, c=c, t=t, v=v, k=k: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', rate=r, bpc=2, nwords=NW, corner=c, temp=t, vdd=v, tag=k, fallback=True)))
    iw = W / 'integration'
    j += [('int_serial_h1g25', lambda: I.run(iw, PEX, mode='serial', rate=1.25e9, bpc=2, nwords=NW, tag='serial_h1g25')),
          ('int_tmds_h1g25', lambda: I.run(iw, PEX, mode='tmds', rate=1.25e9, bpc=2, nwords=NW, tag='tmds_h1g25')),
          ('int_tmds_h1g485', lambda: I.run(iw, PEX, mode='tmds', rate=1.485e9, bpc=2, nwords=NW, tag='tmds_h1g485')),
          ('int_tmds_q2g97', lambda: I.run(iw, PEX, mode='tmds', rate=2.97e9, bpc=4, nwords=NW, tag='tmds_q2g97')),
          ('int_serial_q2g5', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=NW, tag='serial_q2g5')),
          ('int_serial_q2g5_main200', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=NW,
                                                    codes=(200, 32, 125), tag='serial_q2g5_main200')),
          ('int_serial_q2g5_main240', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=NW,
                                                    codes=(240, 32, 125), tag='serial_q2g5_main240')),
          ('int_serial_q3g24', lambda: I.run(iw, PEX, mode='serial', rate=3.24e9, bpc=4, nwords=NW, tag='serial_q3g24')),
          ('int_stretch_5g_lossy', lambda: I.run(iw, PEX, mode='serial', rate=5e9, bpc=4, nwords=6, lossy=True,
                                                 tag='stretch_q5g_lossy')),
          # package channel (spec/package-channel.md): bond, COB, connector, carrier P1..P4, AC caps (B22)
          ('int_pkg_q3g24_P1', lambda: I.run(iw, PEX, mode='serial', rate=3.24e9, bpc=4, nwords=NW,
                                             codes=(200, 0, 125), pkg=('P1', 0.0), tag='pkg_q3g24_P1')),
          ('int_pkg_q2g5_main200_P4', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=NW,
                                                    codes=(200, 0, 125), pkg=('P4', 0.3), tag='pkg_q2g5_main200_P4')),
          # PCIe-style -3.5 dB (post 48 with main 200) and -6 dB (post 80) de-emphasis, P4 (worst placement)
          ('int_pkg_q2g5_deemph35_P4', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=NW,
                                                     codes=(200, 48, 125), pkg=('P4', 0.3), tag='pkg_q2g5_de35_P4')),
          ('int_pkg_q2g5_deemph6_P4', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=NW,
                                                    codes=(200, 80, 125), pkg=('P4', 0.3), tag='pkg_q2g5_de6_P4')),
          ('ext_ideal_1g', lambda: I.run_ext(iw, PEX, rate=1e9, tag='ext_ideal_1g')),
          ('ext_rx_0g5', lambda: I.run_ext(iw, PEX, rate=0.5e9, rx=True, tag='ext_rx_0g5')),
          ('ext_rx_1g', lambda: I.run_ext(iw, PEX, rate=1e9, rx=True, tag='ext_rx_1g')),
          ('ext_rx_1g6', lambda: I.run_ext(iw, PEX, rate=1.6e9, rx=True, tag='ext_rx_1g6')),
          ('ext_rx_2g', lambda: I.run_ext(iw, PEX, rate=2e9, rx=True, tag='ext_rx_2g')),
          ('ext_handover', lambda: I.run_ext(iw, PEX, handover=True, tag='ext_handover'))]
    sw = W / 'static'
    j += [('dac_tt', lambda: T.dac_sweep(sw / 'dac', PEX)),
          ('quiescent_tt', lambda: T.quiescent(sw, PEX, tag='q_tt')),
          ('quiescent_ff_85_3v63', lambda: T.quiescent(sw, PEX, corner='ff', temp=85, vdd=3.63, tag='q_ff')),
          ('quiescent_stopped_tt', lambda: T.quiescent(sw, PEX, tag='qs_tt', phases='stopped')),
          ('quiescent_stopped_ff_85_3v63', lambda: T.quiescent(sw, PEX, corner='ff', temp=85, vdd=3.63, tag='qs_ff',
                                                              phases='stopped')),
          ('unpowered_tt', lambda: T.unpowered(sw, PEX, tag='off_tt')),
          ('unpowered_ff_85_3v63', lambda: T.unpowered(sw, PEX, vin=3.63, corner='ff', temp=85, tag='off_ff')),
          ('ramp_tt', lambda: T.ramp(sw, PEX, tag='ramp_tt')),
          ('ramp_ff_85_3v63', lambda: T.ramp(sw, PEX, vdd=3.63, corner='ff', temp=85, tag='ramp_ff'))]
    return j


def stage_sims(only=None):
    out_path = W / 'sim-results.json'
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [(k, f) for k, f in jobs() if not only or k in only]

    def wrap(item):
        k, f = item
        # hash of the netlist the bench reads, taken before the run; benches that
        # know their DUT (sim_wiredtx) record it themselves and win
        dut = tools.HERE / 'wiredtx.spice' if k.startswith('schematic') else PEX
        pre = tools.sha(dut) if dut.exists() else None
        try:
            r = f()
        except Exception as e:  # recorded, not hidden
            r = dict(ok=False, error=repr(e))
        if isinstance(r, dict):
            r.setdefault('dut_sha256', pre)
            r['dut_kind'] = 'schematic' if k.startswith('schematic') else 'extracted'
        return k, r
    with ThreadPoolExecutor(int(__import__('os').environ.get('WTX_JOBS', '3'))) as ex:
        for k, r in ex.map(wrap, todo):
            results[k] = r
            tools.write_json(out_path, results)
            print(k, 'ok' if r.get('ok', True) else 'FAIL', flush=True)
    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', choices=['layout', 'sims', 'hsbias', 'evidence', 'all'], default='all')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    if a.stage in ('layout', 'all'):
        print(json.dumps(stage_layout(), indent=1)[:1500])
    if a.stage in ('sims', 'all'):
        stage_sims(a.only)
    if a.stage in ('hsbias', 'all'):
        stage_hsbias()
    if a.stage in ('evidence', 'all'):
        import evidence
        evidence.build()
