#!/usr/bin/env python3
"""R+C audit extraction (2026-11-28): full-coverage Magic extresist (tolerance 0.001, simplify off, supplies RESISTED,
only VSUBS ignored) plus the C repair of MANDATE 4a (converters/rcext.py fixcap: ground C per net rebuilt from the C-only
extraction of the same flattened GDS, dropped coupling pairs restored). Same method as the rfdriver power_check views.

  python3 rcx.py <gds> <topcell> <outdir> [--ref <published C-only .ext.spice for port order>] [--tol 0.001]
  -> <outdir>/<top>.conly.spice, <outdir>/<top>.rc.spice (subckt <top>), <outdir>/rcx.json (coverage, C cross-check)
Image: the analog image sha256:bd7a702b (Magic 8.3.678, iic-osic-tools); the pinned canary image is not on this machine."""
import argparse, json, re, shutil, sys, hashlib
from pathlib import Path
A = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/converters')
sys.path.insert(0, str(A)); sys.path.insert(0, str(A / 'lib'))
import convkit as ck
from rcext import fixcap, netstats, joined, base

ap = argparse.ArgumentParser()
ap.add_argument('gds'); ap.add_argument('top'); ap.add_argument('out')
ap.add_argument('--ref'); ap.add_argument('--tol', default='0.001')
a = ap.parse_args()
out = Path(a.out).resolve()
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True)
shutil.copy(a.gds, out / 'in.gds')
top = a.top
common = f"""crashbackups stop
drc off
gds read in.gds
load {top}
flatten {top}_flat
load {top}_flat
select top cell
extract do capacitance
extract do coupling
"""
tail = """ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice subcircuit top on
"""
(out / 'conly.tcl').write_text(common + 'extract no resistance\nextract all\n' + tail + 'ext2spice -o conly.spice\nquit -noprompt\n')
(out / 'rc.tcl').write_text(common + f"""extract do resistance
extract all
ext2sim labels on
ext2sim
extresist tolerance {a.tol}
extresist ignore VSUBS
extresist simplify off
extresist all
""" + tail + 'ext2spice rthresh 0\next2spice extresist on\next2spice -o full.rc.spice\nquit -noprompt\n')
rc = '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc'
ck.docker(ck.ANALOG_IMAGE, out, f'export PATH=/foss/tools/bin:$PATH; mkdir -p c r; cp in.gds conly.tcl c/; cp in.gds rc.tcl r/; '
          f'cd /work/c && magic -dnull -noconsole -rcfile {rc} conly.tcl > ../conly.log 2>&1; '
          f'cd /work/r && magic -dnull -noconsole -rcfile {rc} rc.tcl > ../rc.log 2>&1; '
          'cp /work/c/conly.spice /work/r/full.rc.spice /work/ 2>/dev/null; true', timeout=4 * 3600)
for f in ('conly.spice', 'full.rc.spice'):
    assert (out / f).exists(), f'{f} missing, see {out}/*.log'
conly, full = (out / 'conly.spice').read_text(), (out / 'full.rc.spice').read_text()
# extresist drops '#' of generated names (a_x_y# -> a_x_y.tN): base() strips both, so the per-net match holds
fixed, info = fixcap(conly, full)
fixed = re.sub(rf'\b{top}_flat\b', top, fixed); conly = re.sub(rf'\b{top}_flat\b', top, conly)
L = joined(fixed); k = next(i for i, l in enumerate(L) if l.lower().startswith('.subckt'))
pf = L[k].split()[2:]; pr = pf
if a.ref:
    pr = next(l.split()[2:] for l in joined(Path(a.ref).read_text()) if l.lower().startswith(f'.subckt {top.lower()}') or l.lower().startswith('.subckt '))
    if sorted(pr) == sorted(pf): L[k] = f'.subckt {top} ' + ' '.join(pr)
(out / f'{top}.rc.spice').write_text('\n'.join(L) + '\n'); (out / f'{top}.conly.spice').write_text(conly)
st, gcf = netstats('\n'.join(L)); _, gcr = netstats(conly)
errs = sorted(((abs(gcf.get(n, 0) - x) / x, n) for n, x in gcr.items() if x > 1e-15), reverse=True)
rn = set()
for l in L:
    if l.startswith('R'):
        t = l.split(); rn |= {base(t[1]), base(t[2])}
routed = [n for n, c in gcr.items() if c > 2e-15 and n not in ('VSUBS',)]
miss = sorted(((round(gcr[n] * 1e15, 1), n) for n in routed if n not in rn), reverse=True)
rec = dict(gds=str(a.gds), gds_sha256=hashlib.sha256(open(a.gds, 'rb').read()).hexdigest(), top=top, tol=a.tol,
           image=ck.ANALOG_IMAGE + ' (Magic 8.3.678)', supplies_resisted='VDD' in rn or any(n.startswith('VDD') for n in rn),
           fixcap=info, stats=st, coverage_routed=dict(nets=len(routed), with_r=len(routed) - len(miss), without_r=miss[:20]),
           ground_c_check=dict(nets=len(errs), max_rel_err=round(errs[0][0], 4) if errs else None, worst=[(n, round(e, 4)) for e, n in errs[:5]]),
           ports_match_ref=sorted(pr) == sorted(pf))
(out / 'rcx.json').write_text(json.dumps(rec, indent=1) + '\n')
for d in ('c', 'r'): shutil.rmtree(out / d, ignore_errors=True)
(out / 'in.gds').unlink()
print(json.dumps(rec)[:1200])
