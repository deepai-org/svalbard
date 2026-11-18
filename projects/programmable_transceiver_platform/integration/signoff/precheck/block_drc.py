#!/usr/bin/env python3
"""DRC of published block GDS under the project tool/PDK set and the shuttle's, with the KLayout cross terms.
  block_drc.py <blocks.json> <outdir> [--only name,name] [--cfg P,L,X1,X2] [--checks main,antenna,magic]
blocks.json: {name: [gds path relative to analog/, topcell]}.  One job at a time, 4 threads, network off.
Configurations
  P   project:  KLayout 0.30.9 (analog image) + deck f6eeac7 (image tree);   Magic 8.3.623 (canary image) + tech f6eeac7
  L   live:     KLayout 0.30.12 (nix dev shell of precheck 1.7.4) + deck 792ef67;  Magic 8.3.677 + tech 792ef67
  X1  live deck 792ef67 on KLayout 0.30.9        (deck effect at the project's tool version)
  X2  project deck f6eeac7 on KLayout 0.30.12    (tool-version effect at the project's deck)
KLayout arguments are those of the precheck: -rd decks=<all,-antenna,-density,-cup | antenna> -rd variant=gf180mcuD
-rd workers=1 -rd threads=4 (the precheck passes no threads to the antenna deck; the count does not enter the result).
Magic: magic_drc.tcl (LibreLane's drc.tcl with the precheck's flatglob list).
Result: <outdir>/<block>.json {cfg: {check: {total, rules, seconds, exit}}}; lyrdb/rpt files are deleted after counting.
The GDS are copied to <outdir>/gds/ first; nothing under analog/ is written."""
import collections, hashlib, json, os, re, shutil, subprocess, sys, time
import xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../../../..'))
PROJ = os.path.join(ROOT, 'projects/programmable_transceiver_platform')
PC = os.environ.get('PC_ENV', os.path.join(ROOT, 'scratch/integration/signoff-run/pc'))
KL309 = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
CANARY = 'svalbard/librelane-gf180-canary:2026.08'; NIX = 'nixos/nix:2.28.3'
NEW = os.path.join(PC, 'pdk/gf180mcuD'); OLDT = os.path.join(PC, 'diff/old/libs.tech')   # f6eeac7 libs.tech copied out of the image
DECKS = {'main': 'all,-antenna,-density,-cup', 'antenna': 'antenna'}
UG = f'{os.getuid()}:{os.getgid()}'
BASE = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '4', '--memory', '28g', '--user', UG, '-e', 'HOME=/tmp', '-e', 'OMP_NUM_THREADS=1']
def lyrdb(p):
    c = collections.Counter()
    for _, el in ET.iterparse(p):
        if el.tag == 'item': c[(el.findtext('category') or '').strip("'").split(':')[0].strip("' ")] += 1; el.clear()
    return dict(sorted(c.items()))
def magrpt(p):
    c = collections.Counter(); cur = None
    for l in open(p, errors='replace').read().splitlines()[2:]:
        if l.startswith('[INFO]'): break
        if re.match(r'^ -?[\d.]+um ', l): c[cur] += 1
        elif l.strip() and not l.startswith('---'): cur = l.strip()
    return dict(sorted(c.items()))
def kl(cfg, gds, top, deck, wd):
    rep = os.path.join(wd, 'r.lyrdb')
    if os.path.exists(rep): os.remove(rep)
    args = f"-b -zz -r /deck/gf180mcu.drc -rd input=/in/in.gds -rd topcell={top} -rd report=/wd/r.lyrdb -rd decks='{DECKS[deck]}' -rd variant=gf180mcuD -rd workers=1 -rd threads=4"
    vol = ['-v', f'{gds}:/in/in.gds:ro', '-v', f'{wd}:/wd']
    newdeck, olddeck = os.path.join(NEW, 'libs.tech/klayout/tech/drc'), os.path.join(OLDT, 'klayout/tech/drc')
    if cfg in ('P', 'X1'):
        d = '/foss/pdks/gf180mcuD/libs.tech/klayout/tech/drc' if cfg == 'P' else None
        cmd = BASE + vol + ([] if d else ['-v', f'{newdeck}:/deck:ro']) + ['--entrypoint', '/bin/bash', KL309, '-c',
              'export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; ' + (f'ln -s {d} /tmp/deck; ' if d else '') +
              'klayout -v; klayout ' + (args.replace('/deck/', '/tmp/deck/') if d else args)]
    else:
        cmd = BASE + vol + ['-v', 'signoff_nix:/nix:ro', '-v', f"{newdeck if cfg == 'L' else olddeck}:/deck:ro", NIX,
              '/nix/var/signoff-devshell/entrypoint', 'sh', '-c', 'klayout -v; klayout ' + args]
    t = time.time(); p = subprocess.run(cmd, capture_output=True, text=True)
    open(os.path.join(wd, f'{cfg}_{deck}.log'), 'w').write((p.stdout + p.stderr)[-20000:])
    r = {'exit': p.returncode, 'seconds': round(time.time() - t, 1)}
    m = re.search(r'KLayout (\S+)', p.stdout); r['tool'] = m.group(0) if m else None
    if os.path.exists(rep): r['rules'] = lyrdb(rep); r['total'] = sum(r['rules'].values()); os.remove(rep)
    else: r['error'] = 'no report'
    return r
def magic(cfg, gds, top, wd):
    rep = os.path.join(wd, 'm.rpt')
    if os.path.exists(rep): os.remove(rep)
    vol = ['-v', f'{gds}:/in/in.gds:ro', '-v', f'{wd}:/wd', '-v', f'{HERE}/magic_drc.tcl:/s/magic_drc.tcl:ro', '-w', '/tmp',
           '-e', 'CURRENT_GDS=/in/in.gds', '-e', f'DESIGN_NAME={top}', '-e', 'REPORT=/wd/m.rpt']
    run = 'magic --version; magic -dnull -noconsole -rcfile $PDK_ROOT/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /s/magic_drc.tcl < /dev/null'
    if cfg == 'P': cmd = BASE + vol + ['-e', 'PDK_ROOT=/pdk', '--entrypoint', '/bin/sh', CANARY, '-c', run]
    else: cmd = BASE + vol + ['-e', 'PDK_ROOT=/pdkn', '-v', 'signoff_nix:/nix:ro', '-v', f'{os.path.dirname(NEW)}:/pdkn:ro', NIX, '/nix/var/signoff-devshell/entrypoint', 'sh', '-c', run]
    t = time.time(); p = subprocess.run(cmd, capture_output=True, text=True)
    open(os.path.join(wd, f'{cfg}_magic.log'), 'w').write((p.stdout + p.stderr)[-20000:])
    r = {'exit': p.returncode, 'seconds': round(time.time() - t, 1)}
    m = re.search(r'^(8\.\d+\.\d+)', p.stdout, re.M); r['tool'] = 'Magic ' + m.group(1) if m else None
    if os.path.exists(rep): r['rules'] = magrpt(rep); r['total'] = sum(r['rules'].values()); os.remove(rep)
    else: r['error'] = 'no report'
    return r
def main():
    blocks = json.load(open(sys.argv[1])); out = os.path.abspath(sys.argv[2])
    opt = dict(zip(sys.argv[3::2], sys.argv[4::2]))
    only = opt.get('--only', '').split(',') if '--only' in opt else list(blocks)
    cfgs = opt.get('--cfg', 'P,L,X1,X2').split(','); checks = opt.get('--checks', 'main,antenna,magic').split(',')
    os.makedirs(os.path.join(out, 'gds'), exist_ok=True)
    for b in only:
        rel, top = blocks[b]; src = os.path.join(PROJ, 'analog', rel); gds = os.path.join(out, 'gds', b + '.gds'); shutil.copyfile(src, gds)
        wd = os.path.join(out, 'work', b); os.makedirs(wd, exist_ok=True)
        jf = os.path.join(out, b + '.json'); R = json.load(open(jf)) if os.path.exists(jf) else {}
        R.update({'block': b, 'gds': rel, 'top': top, 'gds_sha256': hashlib.sha256(open(gds, 'rb').read()).hexdigest()})
        for c in cfgs:
            for k in checks:
                if k == 'magic' and c not in ('P', 'L'): continue
                if k in R.get(c, {}) and 'total' in R[c][k]: continue
                R.setdefault(c, {})[k] = magic(c, gds, top, wd) if k == 'magic' else kl(c, gds, top, k, wd)
                json.dump(R, open(jf, 'w'), indent=1)
                print(b, c, k, R[c][k].get('total'), R[c][k].get('seconds'), R[c][k].get('error', ''), flush=True)
        os.remove(gds)
if __name__ == '__main__': main()
