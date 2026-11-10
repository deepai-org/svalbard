#!/usr/bin/env python3
"""Maintained full-chip floorplan/assembly flow in the provider 1x1 template.

Stages (tools pinned in container images, see IMAGES):
  1. abstracts   (KLayout)  true GDS bounds, layer extents, labelled terminals, LEF for
                            every master, pad family and attachment; digital LEF parsed
  2. decap unit  (Magic)    cap_mim_2p0fF 100x100 um gencell, Magic DRC + extraction
  3. floorplan   (Python)   fixed pads/digital, island-seeded legal placement, MIM arrays,
                            independent pairwise legality check
  4. assemble    (KLayout)  ring (packaging-qualified retained ring + seal + ID cells),
                            stress-safe pad families incl. debug sites and the WMON B cell,
                            all masters (per-source cell prefixes), digital outline, decap,
                            core ring, island edge bars with >=4-point switch strapping,
                            shared debug buses, RESET_N pull-down tie, LO trunk
  5. geometry checks (KLayout) shape-level overlap between instances, bus/strap
                            connectivity with negative controls, ring site identity
  6. netlist     (Python)   full-chip SPICE binding of every instance + binding report
  7. signoff checks (precheck image) provider precheck: size/ID/pad mask, density,
                            zero-area, KLayout antenna, Magic DRC, KLayout DRC

Writes report.json; non-zero exit on any stage error (check failures are recorded).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOW = HERE/'chip_assembly'
sys.path.insert(0, str(FLOW))
import inventory as inv  # noqa: E402
import floorplan as fpl  # noqa: E402

ROOT = inv.ROOT
PROJECT = inv.PROJECT
IMAGES = dict(klayout='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
              precheck='svalbard/librelane-gf180-canary:2026.08')
PDKENV = ('export PDK=gf180mcuD PDK_ROOT=/foss/pdks PDKPATH=/foss/pdks/gf180mcuD '
          'KLAYOUT_PATH=/foss/pdks/gf180mcuD/libs.tech/klayout:/foss/pdks/gf180mcuD/libs.tech/klayout/tech')
DIGITAL_ORIGIN = inv.DIGITAL_ORIGIN   # v3 (1395, 3060): 40 um N escape channel; v4 (1398, 3090): top-aligned, H2D on E edge


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def docker(kind, work, cmd, log, threads=4, extra=()):
    args = ['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
            '-e', f'OMP_NUM_THREADS={threads}', '--cpus', str(threads), '-v', f'{ROOT}:/repo:ro', '-v', f'{work}:/work',
            '-v', f'{FLOW}:/flow:ro', *extra, '--entrypoint', '/bin/sh' if kind == 'precheck' else '/bin/bash', IMAGES[kind], '-c' if kind == 'precheck' else '-lc', cmd]
    t0 = time.time()
    with open(work/log, 'w') as f:
        rc = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT).returncode
    return rc, time.time()-t0


def master_spec(have_wrx_cap):
    spec = {}
    for name, (gds, top, *_rest) in inv.MASTERS.items():
        if name == 'wrx_cap' and not have_wrx_cap:
            continue
        spec[name] = ['/repo/'+gds, top]
    for fam, (gds, top, *_r) in inv.PAD_FAMILIES.items():
        spec['pad_'+fam] = ['/repo/'+gds, top]
    for cell in ('attached_tx_steering_driver', 'attached_tx_interlock', 'attached_tx_buffer'):
        spec[cell] = ['/repo/'+inv.BASE_RING_GDS, cell]
    return spec


def parse_digital_lef(path):
    import re
    t = Path(path).read_text()
    size = re.search(r'SIZE\s+([\d.]+)\s+BY\s+([\d.]+)', t)
    pins = {}
    for m in re.finditer(r'PIN (\S+)\n(.*?)\n\s*END (\S+)\s*\n', t, re.S):
        assert m.group(1) == m.group(3), m.group(0)[:200]
        r = re.search(r'LAYER (\S+) ;\s*RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)', m.group(2))
        if r:
            pins[m.group(1)] = dict(layer=r.group(1), rect=[float(v) for v in r.groups()[1:]])
    obs = sorted(set(re.findall(r'LAYER (\w+) ;\s*RECT\s+0 0 ', t.split('OBS')[-1])))
    return dict(size=[float(size.group(1)), float(size.group(2))], pins=pins, obs_layers=obs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--from-stage', type=int, default=1)
    ap.add_argument('--to-stage', type=int, default=7)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--magic-drc', action='store_true', help='also run the precheck Magic DRC (slow on the full chip)')
    a = ap.parse_args()
    work = a.output_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    s = a.from_stage
    have_wrx_cap = (ROOT/inv.MASTERS['wrx_cap'][0]).exists()
    report = dict(status='running', images=IMAGES, started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  flow_hashes={p.name: sha(p) for p in sorted(FLOW.glob('*.py'))}, stages={})
    if (work/'report.json').exists() and s > 1:
        report = json.loads((work/'report.json').read_text())

    def save():
        (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')

    def stage(n, name, ok, **info):
        report['stages'][f'{n}_{name}'] = dict(ok=bool(ok), **info)
        save()
        if not ok:
            report['status'] = f'failed_{name}'
            save()
            raise SystemExit(f'stage {n} {name} failed: ' + json.dumps({k: v for k, v in info.items() if k != 'input_sha256'})[:3000])

    # 1. abstracts
    if s <= 1 <= a.to_stage:
        spec = master_spec(have_wrx_cap)
        (work/'masters.json').write_text(json.dumps(spec, indent=1))
        inputs = {k: sha(ROOT/v[0][len('/repo/'):]) for k, v in spec.items()}
        rc, dt = docker('klayout', work, 'klayout -b -rd spec=/work/masters.json -rd out=/work -r /flow/kl_abstracts.py',
                        'abstracts.log', threads=1)
        ab = json.loads((work/'abstracts.json').read_text()) if rc == 0 else {}
        dig = parse_digital_lef(ROOT/inv.DIGITAL_OUTLINE/'pt_digital_macro.lef')
        (work/'digital.json').write_text(json.dumps(dig, indent=1))
        stage(1, 'abstracts', rc == 0 and len(ab) == len(spec), masters=len(ab), seconds=round(dt, 1),
              wrx_cap_gds=have_wrx_cap, input_sha256=inputs, digital_size=dig['size'],
              digital_pins=len(dig['pins']), digital_obs_layers=dig['obs_layers'])
    ab = json.loads((work/'abstracts.json').read_text())
    # 2. decap unit
    if s <= 2 <= a.to_stage:
        (work/'mim').mkdir(exist_ok=True)
        tcl = ('crashbackups stop\nload workspace\n'
               f'set cell [magic::gencell_makecell gf180mcu::cap_mim_2p0fF w {inv.MIM_UNIT_UM:g} l {inv.MIM_UNIT_UM:g}]\n'
               'load $cell\nsave decap_mim_unit_raw\nselect top cell\nexpand\ndrc check\ndrc catchup\n'
               'puts "MIM_DRC [drc list count total]"\nextract all\next2spice lvs\next2spice\n'
               'gds write decap_mim_unit_raw.gds\nquit -noprompt\n')
        (work/'mim/gen.tcl').write_text(tcl)
        rc, dt = docker('klayout', work, 'cd /work/mim && magic -dnull -noconsole -rcfile '
                        '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc gen.tcl', 'mim.log', threads=1)
        log = (work/'mim.log').read_text()
        spice = (work/'mim/decap_mim_unit_raw.spice').read_text() if rc == 0 else ''
        ok = rc == 0 and 'MIM_DRC 0' in log and 'cap_mim_2f0_m4m5_noshield' in spice
        stage(2, 'decap_unit', ok, magic_drc_zero='MIM_DRC 0' in log, device=[l for l in spice.splitlines() if l.startswith('X')])
    # 3. floorplan
    if s <= 3 <= a.to_stage:
        ab['pad_single_leg_b'] = dict(ab['pad_single_leg'])
        bb = list(ab['pad_single_leg']['bbox']); bb[2] = min(bb[2], 205.0)
        ab['pad_single_leg_b']['bbox'] = bb
        ring = {}
        for e in json.loads((ROOT/inv.PADS/'provider-assembly-inputs/placement-transforms.json').read_text()):
            ring[e['name']] = e['y']/1000.0 if e['rotation'] == 1 else e['x']/1000.0
        dig = json.loads((work/'digital.json').read_text())
        controls = json.loads((PROJECT/'spec/debug-controls.json').read_text())
        dig.setdefault('size_lef', dig['size'])      # the hardened macro's LEF outline (stage 1)
        dig['size'] = list(inv.DIGITAL_SIZE) if inv.DIGITAL_SIZE else list(dig['size_lef'])
        if inv.DIGITAL_SIZE:      # v4 requested re-aspect (interface I12): outline only, same area
            assert abs(dig['size'][0]*dig['size'][1]-dig['size_lef'][0]*dig['size_lef'][1]) < 1.0, 'macro area changed'
        (work/'digital.json').write_text(json.dumps(dig, indent=1))
        fp = fpl.build(ab, ring, controls, have_wrx_cap, dig['size'], DIGITAL_ORIGIN)
        errs = fpl.legality(fp)
        fp['legality_errors'] = errs
        fp['island_regions'] = fpl.island_regions(fp) if not fp['failures'] else {}
        fp['decap_total_f'] = sum(d['capacitance_f'] for d in fp['decaps'])
        fp['mitigation_space'] = fpl.mitigation_report(fp) if not fp['failures'] else {}
        fp['decap_pool_f'] = sum(d['capacitance_f'] for d in fp['decaps'] if d.get('pool'))
        (work/'floorplan.json').write_text(json.dumps(fp, indent=1))
        core_area = (inv.CORE[2]-inv.CORE[0])*(inv.CORE[3]-inv.CORE[1])
        used = sum((p['rect'][2]-p['rect'][0])*(p['rect'][3]-p['rect'][1]) for p in fp['placed'])
        used_dec = sum((d['rect'][2]-d['rect'][0])*(d['rect'][3]-d['rect'][1]) for d in fp['decaps'])
        dig_area = dig['size'][0]*dig['size'][1]
        def in_core(r):
            x1, y1, x2, y2 = max(r[0], inv.CORE[0]), max(r[1], inv.CORE[1]), min(r[2], inv.CORE[2]), min(r[3], inv.CORE[3])
            return max(0, x2-x1)*max(0, y2-y1)
        pad_core = sum(in_core(f['rect']) for f in fp['fixed'] if f['kind'] == 'pad_family')
        area = dict(core_um2=core_area, digital_um2=dig_area, blocks_um2=used, decap_um2=used_dec,
                    pad_families_in_core_um2=pad_core,
                    free_um2=core_area-dig_area-used-used_dec-pad_core)
        # The 1 nF pool is a recorded check (decap_pool_ok), not a stage gate: assembly and the
        # downstream checks still run when the pool does not fit.
        report.setdefault('checks', {})['decap_pool_ok'] = fp['decap_pool_f'] >= 1e-9-1e-15
        stage(3, 'floorplan', not fp['failures'] and not errs and not any(v['demanded'] and v['short_um'] > 0 for v in fp.get('mitigation_space', {}).values()),
              placed=len(fp['placed']), failures=fp['failures'], decap_failures=fp['decap_failures'],
              decap_pool_ok=report['checks']['decap_pool_ok'], legality_errors=errs[:20],
              mitigation_space_short={k: v['short_um'] for k, v in fp.get('mitigation_space', {}).items() if v['short_um'] > 0},
              mitigation_demanded_unmet=[k for k, v in fp.get('mitigation_space', {}).items() if v['demanded'] and v['short_um'] > 0],
              decap_total_f=fp['decap_total_f'], decap_pool_f=fp['decap_pool_f'], pll_rings=list(inv.PLL_RINGS), area_um2=area)
    if a.to_stage < 4:
        report['status'] = 'ok'
        save()
        return
    fp = json.loads((work/'floorplan.json').read_text())
    # 4.-5. assemble + geometry checks
    if s <= 4 <= a.to_stage:
        rc, dt = docker('klayout', work, 'klayout -b -rd work=/work -rd repo=/repo -r /flow/kl_assemble.py', 'assemble.log', threads=1)
        res = json.loads((work/'assembly.json').read_text()) if (work/'assembly.json').exists() else {}
        stage(4, 'assemble', rc == 0 and res.get('ok'), seconds=round(dt, 1),
              **{k: v for k, v in res.items() if k != 'ok'})
    if s <= 5 <= a.to_stage:
        rc, dt = docker('klayout', work, 'klayout -b -rd work=/work -r /flow/kl_checks.py', 'geometry-checks.log', threads=1)
        res = json.loads((work/'geometry-checks.json').read_text()) if (work/'geometry-checks.json').exists() else {}
        stage(5, 'geometry_checks', rc == 0 and bool(res), seconds=round(dt, 1), **res)
    # 6. netlist
    if s <= 6 <= a.to_stage:
        import netlist
        res = netlist.build(work, fp, have_wrx_cap)
        stage(6, 'netlist', res['ok'], **{k: v for k, v in res.items() if k != 'ok'})
    # 7. provider precheck on the assembled GDS
    if s <= 7 <= a.to_stage:
        pre = ROOT/'scratch/gf180mcu-precheck-8d58ff7'   # wafer.space precheck at revision 8d58ff75 (complete checkout)
        # All checks run to completion: the Checker gates are skipped so a density or DRC
        # count is recorded instead of aborting the flow; Magic DRC only with --magic-drc.
        skip = ['KLayout.GenerateID', 'KLayout.Render',  # GenerateID: python qrcode not in the image (ID insertion, not a check)
                 'Checker.KLayoutDensity', 'Checker.KLayoutZeroAreaPolygons',
                'Checker.KLayoutAntenna', 'Checker.MagicDRC', 'Checker.KLayoutDRC']
        if not a.magic_drc:
            skip.append('Magic.DRC')
        # KLayout 0.30.7 in this image: parallel deck workers crash in ReportDatabase::save
        # (rdb.cc:737 cell != 0, klayout issue #2339, the deck warns for < 0.30.9). One
        # worker process with N DRC threads instead.
        cmd = (f'rm -rf /work/precheck-run && cp -r /precheck /work/precheck-run && cd /work/precheck-run && '
               f'export PDK_ROOT=/pdk PDK=gf180mcuD && '
               f'python3 precheck.py --input /work/pt_chip_top.gds --top pt_chip_top --cob --threads {a.threads} --workers 1 '
               f'--run-tag chip --skip {" ".join(skip)} --output /work/pt_chip_top.precheck.gds')
        rc, dt = docker('precheck', work, cmd, 'precheck.log', threads=a.threads, extra=('-v', f'{pre}:/precheck:ro'))
        import precheck_summary
        res = precheck_summary.summarize(work)
        stage(7, 'precheck', rc == 0, returncode=rc, seconds=round(dt, 1), skipped=skip, **res)
    report['status'] = 'complete'
    save()


if __name__ == '__main__':
    main()
