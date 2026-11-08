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
CORNERS = [(c, t, v) for c in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
SWEEP = [(1.92e9, 4), (2.5e9, 4), (2.97e9, 4), (0.96e9, 2), (1.62e9, 2), (0.48e9, 1), (0.81e9, 1)]


def stage_layout():
    subprocess.run([sys.executable, str(tools.HERE / 'cells.py')], check=True)
    if LAY.exists():
        shutil.rmtree(LAY)
    summary = layoutgen.generate(LAY)
    shutil.copy(tools.HERE / 'wiredtx.spice', LAY / 'wiredtx.spice')
    lvs = tools.netgen_lvs(LAY, 'pt_wiredtx_lvs.spice', 'pt_wiredtx', 'wiredtx.spice')
    gds = tools.gds_export_analog(LAY, 'pt_wiredtx')
    kl = tools.klayout_drc(LAY, gds, 'pt_wiredtx')
    GEN.mkdir(exist_ok=True)
    shutil.copy(gds, GEN / 'wiredtx.gds')
    magdir = GEN / 'mag'
    if magdir.exists():
        shutil.rmtree(magdir)
    magdir.mkdir()
    for m in LAY.glob('wtx_p*.mag'):
        shutil.copy(m, magdir / m.name)
    shutil.copy(LAY / 'pt_wiredtx.mag', magdir / 'pt_wiredtx.mag')
    shutil.copy(PEX, GEN / 'wiredtx.ext.spice')
    shutil.copy(LAY / 'pt_wiredtx_lvs.spice', GEN / 'wiredtx.lvs.spice')
    shutil.copy(LAY / 'lvs.out', GEN / 'wiredtx-lvs.txt')
    (GEN / 'wiredtx-drc.txt').write_text(f"magic drc(full) flat error count: {summary['drc_count']}\n"
                                         + (LAY / 'drc-why.txt').read_text())
    res = dict(layout=summary, lvs=lvs, klayout=kl, gds_export='analog image Magic 8.3.678, cif ostyle gdsii',
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
    shutil.copy(tools.HERE / 'hsbias.spice', L / 'hsbias.spice')
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
    (GEN / 'mag_hsbias').mkdir(exist_ok=True)
    for m in L.glob('*.mag'):
        shutil.copy(m, GEN / 'mag_hsbias' / m.name)
    shutil.copy(P, GEN / 'hsbias.ext.spice')
    shutil.copy(L / 'lvs.out', GEN / 'hsbias-lvs.txt')


def jobs():
    j = []
    j.append(('nominal', lambda: S.run_case(W / 'sim', PEX, 'pt_wiredtx', nwords=6, tag='nominal', **NOMINAL)))
    j.append(('schematic_q2g5', lambda: S.run_case(W / 'sim', tools.HERE / 'wiredtx.spice', 'pt_wiredtx', rate=2.5e9,
                                                   bpc=4, nwords=6, tag='sch_q2g5')))
    for rate, bpc in SWEEP:
        j.append((f'sweep_{bpc}_{rate/1e9:g}', lambda r=rate, b=bpc: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', rate=r, bpc=b, nwords=6, tag=f'sweep_{b}_{r/1e9:g}')))
    for c, t, v in CORNERS:
        j.append((f'corner_{c}_{t}_{v}', lambda c=c, t=t, v=v: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', nwords=6, corner=c, temp=t, vdd=v, tag=f'corner_{c}_{t}_{v}', **NOMINAL)))
    # reduced nominal (lowest ring frequency, half rate): 0.96 Gb/s
    j.append(('nominal_0g96', lambda: S.run_case(W / 'sim', PEX, 'pt_wiredtx', rate=0.96e9, bpc=2, nwords=6,
                                                tag='nominal_0g96')))
    for c, t, v in CORNERS:
        j.append((f'corner096_{c}_{t}_{v}', lambda c=c, t=t, v=v: S.run_case(
            W / 'sim', PEX, 'pt_wiredtx', rate=0.96e9, bpc=2, nwords=6, corner=c, temp=t, vdd=v,
            tag=f'corner096_{c}_{t}_{v}')))
    iw = W / 'integration'
    j += [('int_serial_h1g25', lambda: I.run(iw, PEX, mode='serial', rate=1.25e9, bpc=2, nwords=6, tag='serial_h1g25')),
          ('int_tmds_h1g25', lambda: I.run(iw, PEX, mode='tmds', rate=1.25e9, bpc=2, nwords=6, tag='tmds_h1g25')),
          ('int_tmds_q2g97', lambda: I.run(iw, PEX, mode='tmds', rate=2.97e9, bpc=4, nwords=6, tag='tmds_q2g97')),
          ('int_serial_q2g5', lambda: I.run(iw, PEX, mode='serial', rate=2.5e9, bpc=4, nwords=6, tag='serial_q2g5')),
          ('int_stretch_5g_lossy', lambda: I.run(iw, PEX, mode='serial', rate=5e9, bpc=4, nwords=6, lossy=True,
                                                 tag='stretch_q5g_lossy')),
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
        try:
            r = f()
        except Exception as e:  # recorded, not hidden
            r = dict(ok=False, error=repr(e))
        return k, r
    with ThreadPoolExecutor(3) as ex:
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
