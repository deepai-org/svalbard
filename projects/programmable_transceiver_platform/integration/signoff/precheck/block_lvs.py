#!/usr/bin/env python3
"""Read-back extraction of published block GDS under the project tool/PDK set (P) and the shuttle's (L).
  block_lvs.py <blocks.json> <outdir> --only name,name
  P: Magic 8.3.623 + tech f6eeac7 + netgen 1.5.316 (canary image); KLayout 0.30.9 + LVS deck f6eeac7 (analog image)
  L: Magic 8.3.677 + tech 792ef67 + netgen 1.5.323, KLayout 0.30.12 + LVS deck 792ef67 (nix dev shell of precheck 1.7.4)
Per block and configuration:
  magic   gds read -> extract all -> ext2spice lvs; flattened device census (model, W, L, nf, m, r_*, c_*, area, pj);
          netgen LVS against the published reference netlist (<block>.ext.spice without lumped parasitics)
  klayout PDK LVS deck gf180mcu.lvs with the switches run_lvs.py --variant=D --net_only gives (deep); per-model device summary of the extracted netlist
and the P-versus-L comparison of both extractions (exact census equality; per-model summary equality).
Census/parse helpers are the predecessor's (scratch/integration/signoff-gap/lvs/rb_lvs.py, kl_lvs.py).
Result: <outdir>/<block>.lvs.json. Work files are deleted. Nothing under analog/ is written."""
import json, os, re, shutil, subprocess, sys, time
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../../../..'))
sys.path.insert(0, os.path.join(ROOT, 'scratch/integration/signoff-gap/lvs'))
from rb_lvs import census, fold, strip_parasitics            # noqa: E402
from kl_lvs import summary_klayout, add                      # noqa: E402
PROJ = os.path.join(ROOT, 'projects/programmable_transceiver_platform')
PC = os.environ.get('PC_ENV', os.path.join(ROOT, 'scratch/integration/signoff-run/pc'))
KL309 = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
CANARY = 'svalbard/librelane-gf180-canary:2026.08'; NIX = 'nixos/nix:2.28.3'
UG = f'{os.getuid()}:{os.getgid()}'
BASE = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '16g', '--user', UG, '-e', 'HOME=/tmp', '-e', 'OMP_NUM_THREADS=1']
def sh(cfg, w, cmd, kl=False):
    v = ['-v', f'{w}:/work', '-w', '/work']
    if cfg == 'P' and not kl: full = BASE + v + ['-e', 'PDK_ROOT=/pdk', '--entrypoint', '/bin/sh', CANARY, '-c', cmd]
    elif cfg == 'P': full = BASE + v + ['--entrypoint', '/bin/bash', KL309, '-c', 'export PATH=$PATH:/foss/tools/bin:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout PDK_ROOT=/foss/pdks PDK=gf180mcuD; ' + cmd]
    else: full = BASE + v + ['-e', 'PDK_ROOT=/pdkn', '-e', 'PDK=gf180mcuD', '-v', 'signoff_nix:/nix:ro', '-v', f'{PC}/pdk:/pdkn:ro', NIX, '/nix/var/signoff-devshell/entrypoint', 'sh', '-c', cmd]
    t = time.time(); p = subprocess.run(full, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr, round(time.time() - t, 1)
def one(cfg, b, rel, top, out):
    w = os.path.join(out, 'work', f'{b}_{cfg}'); shutil.rmtree(w, ignore_errors=True); os.makedirs(w)
    shutil.copyfile(os.path.join(PROJ, 'analog', rel), os.path.join(w, 'in.gds'))
    ref = os.path.join(PROJ, 'analog', rel[:-4] + '.ext.spice'); R = {}
    open(os.path.join(w, 'rb.tcl'), 'w').write('\n'.join(['crashbackups stop', 'gds read in.gds', f'load {top}', 'select top cell',
        'extract do local', 'extract all', 'ext2spice lvs', 'ext2spice -o rb.lvs.spice', 'quit -noprompt']) + '\n')
    rc, log, dt = sh(cfg, w, 'magic --version; magic -dnull -noconsole -rcfile $PDK_ROOT/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/rb.tcl < /dev/null')
    R['magic'] = {'exit': rc, 'seconds': dt, 'tool': (re.search(r'^8\.\d+\.\d+', log, re.M) or [None])[0]}
    rb = os.path.join(w, 'rb.lvs.spice'); txt = None
    if os.path.exists(rb):
        txt = open(rb, errors='replace').read(); c = census(txt, top)
        R['magic']['devices'] = int(sum(c.values())); R['magic']['_census'] = dict(c)
        if os.path.exists(ref):
            reft = strip_parasitics(open(ref, errors='replace').read()); open(os.path.join(w, 'ref.spice'), 'w').write(reft)
            cr = census(reft, top); R['magic']['ref_devices'] = int(sum(cr.values()))
            R['magic']['census_equals_reference'] = fold(c) == fold(cr)
            rc2, log2, dt2 = sh(cfg, w, f'netgen -batch lvs "rb.lvs.spice {top}" "ref.spice {top}" $PDK_ROOT/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl lvs.txt')
            t = open(os.path.join(w, 'lvs.txt'), errors='replace').read() if os.path.exists(os.path.join(w, 'lvs.txt')) else ''
            R['netgen'] = {'exit': rc2, 'seconds': dt2, 'final': t[t.rfind('Final result'):].strip()[:200].replace('\n', ' | ') if 'Final result' in t else None,
                           'property_errors': 'property errors' in t.lower(), 'tool': (re.search(r'Netgen \S+', log2) or [None])[0]}
    else: R['magic']['error'] = log[-300:]
    open(os.path.join(w, 'dummy.spice'), 'w').write(f'.subckt {top}\n.ends\n')
    lvsdir = '$PDK_ROOT/gf180mcuD/libs.tech/klayout/tech/lvs'
    os.makedirs(os.path.join(w, 'run'))
    # same -rd switches as the PDK's run_lvs.py --variant=D --run_mode=deep --net_only (run_lvs.py needs docopt, absent in the live shell)
    sw = ('thr=2 run_mode=deep metal_top=11K mim_option=B metal_level=5LM poly_res=1k mim_cap=2 lvs_sub=gf180mcu_gnd verbose=false spice_net_names=true '
          'spice_comments=false scale=false schematic_simplify=false net_only=true top_lvl_pins=false combine=false purge=false purge_nets=false '
          f'topcell={top} input=/work/in.gds schematic=/work/dummy.spice report=/work/run/out.lvsdb target_netlist=/work/run/out.cir')
    rc, log, dt = sh(cfg, w, f'klayout -v; klayout -b -r {lvsdir}/gf180mcu.lvs ' + ' '.join('-rd ' + x for x in sw.split()) + ' 2>&1 | tail -30', kl=True)
    R['klayout'] = {'exit': rc, 'seconds': dt, 'tool': (re.search(r'KLayout \S+', log) or [None])[0]}
    cirs = [os.path.join(w, 'run', f) for f in os.listdir(os.path.join(w, 'run'))] if os.path.isdir(os.path.join(w, 'run')) else []
    cirs = [c for c in cirs if c.endswith('.cir')]
    if cirs:
        cells, _ = summary_klayout(open(cirs[0], errors='replace').read()); lower = {k.lower(): k for k in cells}
        summ = defaultdict(lambda: dict(n=0.0, q=0.0, unit=''))
        def walk(c, mult, depth=0):
            for kind, model, par in cells[c]:
                if kind == 'X' and model.lower() in lower and depth < 40: walk(lower[model.lower()], mult, depth + 1)
                else: add(summ, model.lower(), par, mult)
        walk(lower.get(top.lower()) or max(cells, key=lambda c: len(cells[c])), 1.0)
        R['klayout']['summary'] = {k: [round(v['n'], 3), round(v['q'], 4), v['unit']] for k, v in sorted(summ.items())}
        R['klayout']['devices'] = int(sum(v['n'] for v in summ.values()))
    else: R['klayout']['error'] = log[-600:]
    shutil.rmtree(w, ignore_errors=True)
    return R
def main():
    blocks = json.load(open(sys.argv[1])); out = os.path.abspath(sys.argv[2]); only = sys.argv[4].split(',')
    for b in only:
        rel, top = blocks[b]; R = {'block': b, 'top': top}
        for cfg in ('P', 'L'): R[cfg] = one(cfg, b, rel, top, out)
        cp, cl = R['P']['magic'].pop('_census', None), R['L']['magic'].pop('_census', None)
        if cp is not None and cl is not None:
            d = {k: [cp.get(k, 0), cl.get(k, 0)] for k in sorted(set(cp) | set(cl)) if cp.get(k, 0) != cl.get(k, 0)}
            R['magic_P_vs_L'] = {'identical_census': not d, 'n_diff_keys': len(d), 'diff_sample': dict(list(d.items())[:30])}
        sp, sl = R['P']['klayout'].get('summary'), R['L']['klayout'].get('summary')
        if sp is not None and sl is not None:
            d = {k: [sp.get(k), sl.get(k)] for k in sorted(set(sp) | set(sl)) if sp.get(k) != sl.get(k)}
            R['klayout_P_vs_L'] = {'identical_summary': not d, 'diff': d}
        json.dump(R, open(os.path.join(out, b + '.lvs.json'), 'w'), indent=1)
        print(b, 'magic', R.get('magic_P_vs_L', {}).get('identical_census'), R['P'].get('netgen', {}).get('final'), '|', R['L'].get('netgen', {}).get('final'),
              'klayout', R.get('klayout_P_vs_L', {}).get('identical_summary'), R['P']['klayout'].get('devices'), R['L']['klayout'].get('devices'), flush=True)
if __name__ == '__main__': main()
