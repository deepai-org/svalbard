#!/usr/bin/env python3
"""Maintained core-bias routing flow (37 placed cells, 152 nets).

Stages (all tools pinned in container images, see IMAGES):
  1. precise abstracts        (KLayout)  real master metal as OBS; supply pins own their rails
  2. supply-first routing     (OpenROAD) 7 supply nets, NDR 4 um VDD/VSS, 2 um rails
  3. signal routing           (OpenROAD) 145 nets around the FIXED supply network,
                                         supply nets restored to special POWER/GROUND
  4. geometry export          (OpenROAD) all regular + special rectangles, NDR widths
  5. routed GDS + master XOR  (KLayout)
  6. independent audit        (KLayout)  connectivity / shorts incl. master-internal metal
  7. negative controls        audit must reject: deleted segment, deleted via,
                              cross-net bridge, detached supply pin
  8. KLayout GF180 DRC, Magic+Netgen LVS against pt_core_bias.spice, magic extraction
  9. supply current / IR / EM from the exported supply geometry against the GF180MCU
     DRM 14.2 via/metal ratings, max-corner resistance (supply_ir.py)

Writes report.json in the output directory. Exit status is non-zero on any failure.
"""
import argparse, copy, hashlib, json, os, subprocess, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
FLOW = Path(__file__).resolve().parent/'core_bias_routing'
IMAGES = dict(klayout='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
              openroad='svalbard/librelane-gf180-canary:2026.08')
PDKENV = ('export PDK=gf180mcuD PDK_ROOT=/foss/pdks PDKPATH=/foss/pdks/gf180mcuD '
          'KLAYOUT_PATH=/foss/pdks/gf180mcuD/libs.tech/klayout:/foss/pdks/gf180mcuD/libs.tech/klayout/tech '
          'SPICE_USERINIT_DIR=/foss/pdks/gf180mcuD/libs.tech/ngspice')
SUPPLY = lambda n: n in ('VDD', 'VSS') or n.startswith('RAIL_')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def docker(kind, inp, work, cmd, log, threads=8):
    args = ['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
            '-e', f'ROUTE_THREADS={threads}', '-v', f'{inp}:/input:ro', '-v', f'{work}:/work', '-v', f'{FLOW}:/flow:ro']
    if kind == 'openroad':
        args += ['--entrypoint', 'openroad', IMAGES[kind]] + cmd
    else:
        args += ['--entrypoint', '/bin/bash', IMAGES[kind], '-lc', cmd]
    with open(work/log, 'w') as f:
        rc = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT).returncode
    assert rc == 0, (log, rc, (work/log).read_text()[-2000:])


def drc_count(path):
    text = path.read_text() if path.exists() else ''
    return text.count('violation type:')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', type=Path, default=ROOT/'scratch/core-bias-physical-terminals-current')
    ap.add_argument('--output-dir', type=Path, default=ROOT/f'scratch/core-bias-routing-{time.strftime("%Y%m%d-%H%M%S")}')
    ap.add_argument('--from-stage', type=int, default=1)
    ap.add_argument('--supply-current-ma', type=float, default=1.0,
                    help='VDD current for IR/EM in mA (default: the 1 mA bias current_budget_ma); VSS = VDD + rail currents, see supply_ir.py.')
    a = ap.parse_args()
    inp = a.input.resolve(); work = a.output_dir.resolve(); work.mkdir(parents=True, exist_ok=True)
    rep = dict(status='running', input=str(inp), images=IMAGES, flow_hashes={p.name: sha(p) for p in sorted(FLOW.iterdir()) if p.is_file()},
               input_hashes={f: sha(inp/f) for f in ['geometry-audit.json', 'placement-inputs.json', 'physical-terminals.json',
                                                     'pin-inputs.json', 'pin-audit.json', 'pt_core_bias_placement.gds', 'pt_core_bias.spice']})
    s = a.from_stage
    if s <= 1:
        docker('klayout', inp, work, 'klayout -b -r /flow/precise_lefs.py', 'precise-lefs.log')
    if s <= 2:
        docker('openroad', inp, work, ['-python', '-exit', '/flow/prepare.py', 'power'], 'prepare-power.log')
        docker('openroad', inp, work, ['-exit', '/flow/route_power.tcl'], 'route-power.log')
        docker('openroad', inp, work, ['-python', '-exit', '/flow/export_wires.py', '/work/power-routed.odb',
                                       '/work/power-routed.def', '/work/power-wires.json', '7', '0'], 'export-power.log')
    rep['power_router_violations'] = drc_count(work/'power-route.drc')
    if s <= 3:
        docker('openroad', inp, work, ['-python', '-exit', '/flow/prepare.py', 'signal'], 'prepare-signal.log')
        docker('openroad', inp, work, ['-exit', '/flow/route_signal.tcl'], 'route-signal.log')
    rep['signal_router_violations'] = drc_count(work/'signal-route.drc')
    if s <= 4:
        docker('openroad', inp, work, ['-python', '-exit', '/flow/export_wires.py', '/work/routed.odb',
                                       '/work/routed.def', '/work/routed.json', '145', '7'], 'export.log')
    if s <= 5:
        docker('klayout', inp, work, 'klayout -b -r /flow/merge_gds.py', 'merge-gds.log')
        docker('klayout', inp, work, 'klayout -b -r /flow/def_crosscheck.py', 'def-crosscheck.log')
    routed = json.loads((work/'routed.json').read_text())
    rep['supply_roles'] = {n: v['sig_type'] for n, v in routed['nets'].items() if SUPPLY(n)}
    rep['supply_special'] = all(routed['nets'][n]['special'] for n in rep['supply_roles'])
    if s <= 6:
        docker('klayout', inp, work, 'klayout -b -rd wires=/work/routed.json -rd report=/work/audit.json -r /flow/audit_routes.py', 'audit.log')
    # Negative controls: each mutation must be rejected by the same auditor.
    controls = {}
    baseline_pass = json.loads((work/'audit.json').read_text())['status'] == 'pass'
    if s <= 7:
        expect = {'signal-segment': 'disconnected net', 'supply-segment': 'disconnected net', 'supply-via': 'disconnected net',
                  'supply-short': 'metal contact between distinct nets', 'supply-pin': 'boundary pin unattached'}

        def mutate(tag, fn):
            w = copy.deepcopy(routed); desc = fn(w['nets'])
            (work/f'neg-{tag}.json').write_text(json.dumps(w))
            docker('klayout', inp, work, f'klayout -b -rd wires=/work/neg-{tag}.json -rd report=/work/neg-{tag}-audit.json -r /flow/audit_routes.py', f'neg-{tag}.log')
            r = json.loads((work/f'neg-{tag}-audit.json').read_text())
            reasons = sorted({e['reason'] for e in r['errors']})
            # Meaningful only if the clean baseline passes and the mutation
            # trips the specific expected failure.
            controls[tag] = dict(mutation=desc, expected_reason=expect[tag], reasons=reasons,
                                 rejected=r['status'] == 'fail' and expect[tag] in reasons and baseline_pass)
            (work/f'neg-{tag}.json').unlink()

        def del_segment(nets):
            n = nets['C_core_biasgen_ena']; i = next(k for k, x in enumerate(n['shapes']) if x['kind'] == 'segment')
            return dict(net='C_core_biasgen_ena', removed=n['shapes'].pop(i))

        def del_supply_segment(nets):
            n = nets['VDD']; segs = [k for k, x in enumerate(n['shapes']) if x['kind'] == 'segment']
            k = max(segs, key=lambda k: (lambda b: (b[2]-b[0])*(b[3]-b[1]))(n['shapes'][k]['box_dbu']))
            return dict(net='VDD', removed=n['shapes'].pop(k))

        def del_via(nets):
            # a single-cut Via1 on a bringup_and M1 supply pin (not an array cut)
            n = nets['VSS']; i = next(k for k, x in enumerate(n['shapes']) if x['layer'] == 'Via1')
            return dict(net='VSS', removed=n['shapes'].pop(i))

        def bridge(nets):
            a = nets['VDD']['shapes']; b = nets['VSS']['shapes']
            sa = next(x for x in a if x['layer'] == 'Metal3' and x['kind'] == 'segment')
            sb = min((x for x in b if x['layer'] == 'Metal3' and x['kind'] == 'segment'),
                     key=lambda x: abs(x['box_dbu'][0]-sa['box_dbu'][0])+abs(x['box_dbu'][1]-sa['box_dbu'][1]))
            box = [min(sa['box_dbu'][0], sb['box_dbu'][0]), min(sa['box_dbu'][1], sb['box_dbu'][1]),
                   max(sa['box_dbu'][2], sb['box_dbu'][2]), max(sa['box_dbu'][3], sb['box_dbu'][3])]
            a.append(dict(layer='Metal3', box_dbu=box, kind='segment'))
            return dict(net='VDD', added_bridge_to='VSS', box=box)

        def detach_pin(nets):
            p = nets['RAIL_pll']['pins'][0]; p['box_dbu'] = [p['box_dbu'][0], p['box_dbu'][1]+40000, p['box_dbu'][2], p['box_dbu'][3]+40000]
            return dict(net='RAIL_pll', moved_boundary_pin_um=[0, 20])
        for tag, fn in [('signal-segment', del_segment), ('supply-segment', del_supply_segment), ('supply-via', del_via),
                        ('supply-short', bridge), ('supply-pin', detach_pin)]:
            mutate(tag, fn)
        (work/'negative-controls.json').write_text(json.dumps(controls, indent=2)+'\n')
    controls = json.loads((work/'negative-controls.json').read_text())
    if s <= 8:
        docker('klayout', inp, work, PDKENV+' && rm -rf /work/drc && mkdir -p /work/drc && '
               'cp /work/pt_core_bias_routed.gds /work/drc/pt_core_bias.gds && cd /work/drc && '
               'sak-drc.sh -k -w /work/drc/out /work/drc/pt_core_bias.gds && grep -q gf180mcu /work/drc/out/*/*.log', 'drc.log')
        docker('klayout', inp, work, PDKENV+' && bash /flow/lvs.sh', 'lvs.log')
    if s <= 9:
        subprocess.run([sys.executable, str(FLOW/'supply_ir.py'), str(work), str(a.supply_current_ma)], env={**os.environ, 'CORE_BIAS_INPUT': str(inp)})
    audit = json.loads((work/'audit.json').read_text()); gds = json.loads((work/'gds-report.json').read_text())
    defx = json.loads((work/'def-crosscheck.json').read_text()); ir = json.loads((work/'supply-ir.json').read_text())
    lvs = json.loads((work/'lvs.json').read_text())
    lyrdb = list((work/'drc/out').rglob('*.lyrdb'))
    drc = sum(open(p).read().count('<item>') for p in lyrdb) if lyrdb else None
    rep.update(audit=dict(status=audit['status'], nets=audit['nets'], terminals=audit['instance_terminals_checked'],
                          boundary_pins=audit['boundary_pins_checked'], errors=audit['error_count']),
               negative_controls=controls, master_xor=gds['master_xor'], gds_sha256=gds['gds_sha256'],
               def_crosscheck=defx['status'], klayout_drc_violations=drc, lvs=lvs, supply_ir=ir['status'])
    checks = [rep['power_router_violations'] == 0, rep['signal_router_violations'] == 0, rep['supply_special'],
              all(rep['supply_roles'][n] == ('GROUND' if n == 'VSS' else 'POWER') for n in rep['supply_roles']),
              audit['status'] == 'pass' and audit['nets'] == 152 and audit['instance_terminals_checked'] == 283 and audit['boundary_pins_checked'] == 122,
              all(c['rejected'] for c in controls.values()), defx['status'] == 'pass', drc == 0,
              lvs['status'] == 'pass', lvs.get('pex_status') == 'pass', ir['status'] == 'pass']
    rep['checks'] = checks
    rep['status'] = 'pass' if all(checks) else 'fail'
    rep['scope'] = ('Core-bias 37-cell block routing: 152 nets (7 supply), 283 instance terminals, 122 boundary pins. '
                    'Block-level only; full-chip floorplan, PDN, antenna/density and signoff remain separate gates.')
    (work/'report.json').write_text(json.dumps(rep, indent=2)+'\n')
    print(json.dumps({k: rep[k] for k in ['status', 'checks', 'power_router_violations', 'signal_router_violations',
                                         'klayout_drc_violations', 'def_crosscheck', 'supply_ir']}, indent=2), work)
    sys.exit(0 if rep['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
