#!/usr/bin/env python3
"""pt_wrx_cap (capture.py) flow: compact cells, top assembly, DRC/LVS, GDS export and
schematic + extracted capture benches, written to generated/wrx_cap-evidence.json.

Benches (capture.bench): ideal ring phases CKP0..7 and ideal sampler outputs S0..7
(PRBS7 at bpc bits per ring cycle) into pt_wrx_cap; the recovered DW stream is aligned to
the PRBS and every bit compared.  This qualifies the capture front end only: the slicer,
ring and CDR are not in these benches.

usage: run_capture.py [--no-layout] [--assess-only] [--only TAG ...] [--jobs N]
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture  # noqa: E402
import wrx_flow as f  # noqa: E402

# tag, bpc, kwargs; every case runs schematic and extracted
# r2: full rate runs 8 words (the slot chain starts at the first LDE; r1's counter self-started).
# q625_lde50/60: LDE edge 0.5/0.6 ns after CKP0, i.e. on the extracted capture CK edge (~0.5 ns
# after CKP0), so the first LDE register samples it marginally; the second register must resolve it.
CASES = [('q625', 4, dict(f=625e6, words=12)),
         ('q810', 4, dict(f=810e6, words=12)),
         ('q480', 4, dict(f=480e6, words=12)),
         ('h625', 2, dict(f=625e6, words=12)),
         ('f480p0', 1, dict(f=480e6, words=8, psel=0)),
         ('f480p3', 1, dict(f=480e6, words=8, psel=3)),
         ('f480p5', 1, dict(f=480e6, words=8, psel=5)),
         ('q625_ss', 4, dict(f=625e6, words=12, corner='ss', temp=32, vdd=3.15)),
         ('q480_ss', 4, dict(f=480e6, words=12, corner='ss', temp=32, vdd=3.15)),
         ('q625_lde50', 4, dict(f=625e6, words=12, lde_delay=0.5e-9)),
         ('q625_lde60', 4, dict(f=625e6, words=12, lde_delay=0.6e-9)),
         # W1 r3a (2026-11-10): RCS=1 re-captures S_j one full period after sampling.  Its hold check is
         # local clock delay + hold < slicer minimum delay, so these cases use d_lat = 0.47 ns, the real
         # pt_slicer r2 minimum (extracted ff, README); with the r0 cases' 300 ps the hold check is not
         # the one the hardware sees.  The real slicer is in run_fallback.py.
         ('q480_r1', 4, dict(f=480e6, words=12, rcs=1, d_lat=0.47e-9)),
         ('q625_r1', 4, dict(f=625e6, words=12, rcs=1, d_lat=0.47e-9)),
         ('q810_r1', 4, dict(f=810e6, words=12, rcs=1, d_lat=0.47e-9)),
         ('h625_r1', 2, dict(f=625e6, words=12, rcs=1, d_lat=0.47e-9)),
         ('q625_ss_r1', 4, dict(f=625e6, words=12, corner='ss', temp=32, vdd=3.15, rcs=1, d_lat=0.47e-9)),
         ('q810_ss_r1', 4, dict(f=810e6, words=12, corner='ss', temp=32, vdd=3.15, rcs=1, d_lat=0.47e-9)),
         # r5 (2026-11-10): IX-1 top rate (ring 834 MHz) and the fast-corner hold side at the bottom rate
         ('q834_r1', 4, dict(f=834e6, words=12, rcs=1, d_lat=0.47e-9)),
         ('q834_ss_r1', 4, dict(f=834e6, words=12, corner='ss', temp=32, vdd=3.15, rcs=1, d_lat=0.47e-9)),
         ('q480_ff', 4, dict(f=480e6, words=12, corner='ff', temp=22, vdd=3.35)),
         ('q480_ff_r1', 4, dict(f=480e6, words=12, corner='ff', temp=22, vdd=3.35, rcs=1, d_lat=0.47e-9)),
         # safe state: EN=0, clocks/samples/LDE toggling; < 10 uA and every output < 0.3 V
         ('safe_q625', 4, dict(f=625e6, words=4, en_off=True)),
         # r6/r7 system safe state (W6-SAFE / W7-SAFE): EN=0 implies slicer_en=0, so S is static low
         ('safes_q625', 4, dict(f=625e6, words=4, en_off=True, s_static=True))]
MIN_BITS = {4: 150, 2: 120, 1: 60}
# r7 publish (2026-11-13, AP4-1 / SLI7-G): the gate is the EXTRACTED netlist at ring <= 625 MHz.  Ring 810/834 MHz is not
# a production mode (SLI7-G), so those cases are run and reported but do not gate; `safe_q625` (EN=0 with S toggling) is
# the unsupported stress state (W6-SAFE), the gating safe case is `safes_q625`.  Schematic runs are informational.
NON_GATING = {'q810', 'q810_r1', 'q810_ss_r1', 'q834_r1', 'q834_ss_r1', 'safe_q625'}


ASSESS_ONLY = False


def one(tag, bpc, kw, ext):
    name = ('ext_' if ext else 'sch_') + tag
    r = capture.run_bench(name, bpc, ext=ext, assess_only=ASSESS_ONLY, **kw)
    if kw.get('en_off'):
        r['pass'] = bool(r.get('pass_'))
    else:
        r['pass'] = bool(r.get('pass_') and (r.get('bits') or 0) >= MIN_BITS[bpc] and r.get('bit_errors') == 0)
        # 95 % upper bound on the bit error ratio from this window (rule of three for 0 errors); the
        # windows are short, so this bound is weak and is reported as such, not as a BER result
        n = (r.get('bits') or 0) + (r.get('edge_bits') or 0)
        r['ber_95_upper'] = (3.0 / n) if (n and r.get('bit_errors') == 0 and r.get('edge_errors') == 0) else None
    print(name, {k: r.get(k) for k in ('words', 'bits', 'bit_errors', 'edge_errors', 'i_mA', 'i_uA', 'outputs_max_v', 'pass', 'error')}, flush=True)
    return name, r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--no-layout', action='store_true')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--assess-only', action='store_true', help='re-judge the stored runs (implies --no-layout)')
    ap.add_argument('--results', help='build the evidence from this results store (runs made on the staged build of the '
                                      'published layout); no layout, no simulation')
    a = ap.parse_args()
    global ASSESS_ONLY
    ASSESS_ONLY = a.assess_only
    if a.assess_only or a.results:
        a.no_layout = True
    gen = HERE / 'generated'
    if not a.no_layout:
        cells = {n: capture.build_cell(n) for n in capture.CELLS}
        (gen / 'wrx_cap-cells.json').write_text(json.dumps(cells, indent=1, default=str) + '\n')
        top = capture.build_top()
        print('top', top.get('drc_errors'), top.get('lvs'), flush=True)
    cells = json.loads((gen / 'wrx_cap-cells.json').read_text())
    top = json.loads((gen / 'wrx_cap-layout.json').read_text())
    store = capture.SCRATCH / 'results.json'
    res = json.loads(store.read_text()) if (store.exists() and a.only) else {}
    jobs = [(t, b, k, e) for t, b, k in CASES for e in (False, True) if not a.only or t in a.only]
    if a.results:
        res, jobs = json.loads(Path(a.results).read_text()), []
    with ThreadPoolExecutor(a.jobs) as ex:
        for name, r in ex.map(lambda j: one(*j), jobs):
            res[name] = r
            store.write_text(json.dumps(res, indent=1, default=str))
    lvs = top.get('lvs') or {}
    lvs_ok = bool(lvs.get('unique_match')) if isinstance(lvs, dict) else False
    gx = top.get('gds_export') or {}
    cell_ok = all(c.get('drc_errors') == 0 and (c.get('lvs') or {}).get('unique_match') for c in cells.values())
    # r7: the gate is the extracted netlist over the gating cases (see NON_GATING); a gating case that was not run
    # counts as a failure of the gate and is listed in `gating_not_run`
    gate = ['ext_' + t for t, _, k in CASES if t not in NON_GATING and not k.get('en_off')]
    gate_safe = ['ext_' + t for t, _, k in CASES if t not in NON_GATING and k.get('en_off')]
    not_run = [n for n in gate + gate_safe if n not in res]
    failing = [n for n in gate + gate_safe if n in res and not res[n].get('pass')]
    sims_ok = all(res.get(n, {}).get('pass') for n in gate)
    safe_ok = all(res.get(n, {}).get('pass') for n in gate_safe)
    control = {k: {kk: v.get(kk) for kk in ('bits', 'bit_errors', 'edge_errors', 'pd_ok', 'pass', 'expected')}
               for k, v in res.items() if k.startswith('neg_')}
    control_ok = bool(control) and all(not v['pass'] for v in control.values())
    hashes = {p: f.sha256(HERE / p) for p in ['capture.py', 'wrx_compact.py', 'run_capture.py',
                                               'generated/wrx_cap.ext.spice', 'generated/wrx_cap.lvs.spice',
                                               'generated/wrx_cap.gds']
              if (HERE / p).exists()}
    ev = dict(block='wrx_cap', subckt='pt_wrx_cap', source_hashes=hashes,
              scope='Capture front end only (ideal ring phases and ideal sampler outputs). Slicer, ring PLL and CDR '
                    'loop are outside these benches; WCLK_IN -> slicer -> capture is not covered here.',
              tests=dict(
                  safe=dict(state='pass' if safe_ok else 'fail',
                            criterion='EN=0 with CKP0..7, S0..7 and LDE toggling at 625 MHz: VDD current < 10 uA and '
                                      'every DW/EW < 0.3 V (schematic and extracted)',
                            benches={k: {kk: v.get(kk) for kk in ('netlist', 'i_uA', 'outputs_max_v', 'pass', 'error')}
                                     for k, v in sorted(res.items()) if 'safe' in k}),
                  clean=dict(state='pass' if (cell_ok and top.get('drc_errors') == 0 and lvs_ok and gx.get('pass')
                                              and sims_ok and control_ok) else 'fail',
                             gate='extracted netlist, ring <= 625 MHz (SLI7-G); non-gating: ' + ', '.join(sorted(NON_GATING)),
                             gating_cases=gate + gate_safe, gating_not_run=not_run, gating_failing=failing,
                             negative_control=dict(ok=control_ok, runs=control,
                                                   criterion='a broken input (sampler output stuck) must be reported as failing'),
                             cells={n: dict(drc_errors=c.get('drc_errors'), lvs=(c.get('lvs') or {}).get('unique_match'),
                                            area_um2=c.get('area_um2')) for n, c in cells.items()},
                             top=dict(drc_errors=top.get('drc_errors'), lvs_unique=lvs_ok, gds_export=gx,
                                      devices=top.get('devices')),
                             benches={k: {kk: v.get(kk) for kk in ('netlist', 'bpc', 'f', 'psel', 'corner', 'temp', 'vdd', 'lde_delay',
                                                                   'words', 'bits', 'bit_errors', 'edge_bits', 'edge_errors', 'pd_ok', 'vote_activity', 'gear_ok',
                                                                   'word_timing', 'ber_95_upper', 'i_mA', 'i_uA',
                                                                   'outputs_max_v', 'pass', 'error')}
                                      for k, v in sorted(res.items())})))
    (gen / 'wrx_cap-evidence.json').write_text(json.dumps(ev, indent=1, default=str) + '\n')
    print('wrx_cap clean', ev['tests']['clean']['state'], flush=True)
    return 0 if ev['tests']['clean']['state'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
