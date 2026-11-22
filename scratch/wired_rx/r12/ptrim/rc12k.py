"""R+C netlist of pt_ptrim from a GDS (RCOV.md recipe + the r11 rc_ctle mkrc.py C handling).  Call through ../../slot.sh.
usage: rc12.py GDS OUTDIR [ignore_supply=0|1]
Magic (pinned analog image): gds read -> flatten pt_ptrim -> extract (C, coupling, cthresh 0) -> ext2spice C-only (flat)
-> extresist tolerance 0, simplify off (supplies resisted unless ignore_supply=1) -> ext2spice extresist on (raw).
mkrc.py: devices + capacitors of the C-only flat extraction VERBATIM (cap=dist: split over resistor nodes, totals per net pair
conserved: the extresist double-counted substrate C is NOT used), resistors from extresist.
Coverage: nets with >1 resistor node / non-supply nets; per-net C cross-check (rc vs C-only, ratio) -> OUTDIR/rc.json.
Output OUTDIR/ptrim.rc.spice with the subckt renamed pt_ptrim (port order of the flat extraction)."""
import sys, re, json, shutil, subprocess, collections
from pathlib import Path
gds, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
ign = len(sys.argv) > 3 and sys.argv[3].endswith('1')
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True); shutil.copy(gds, out / 'in.gds')
ig = 'extresist ignore VSS\nextresist ignore VDD_WIRE_SW\n' if ign else ''
(out / 'rc.tcl').write_text(f"""crashbackups stop
drc off
gds read in.gds
load pt_ptrim
flatten pt_ptrim_flat
load pt_ptrim_flat
select top cell
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice subcircuit top on
ext2spice -o c.spice
ext2sim labels on
ext2sim
extresist tolerance 0
extresist simplify off
{ig}extresist ignore VSUBS
extresist all
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o raw.spice
quit -noprompt
""")
(out / 'rc.sh').write_text('export PDK_ROOT=/foss/pdks PDK=gf180mcuD\n/foss/tools/bin/magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc rc.tcl > rc.log 2>&1\n')
subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1', '--user', '1000:1000', '-e', 'HOME=/tmp',
                '--entrypoint', '/bin/bash', '--mount', f'type=bind,src={out},dst=/work', '-w', '/work',
                'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305', '/work/rc.sh'], timeout=7200)
for g in [x for x in out.glob('*.ext') if not x.name.endswith('.res.ext')] + list(out.glob('*.sim')) + list(out.glob('*.nodes')) + [out / 'in.gds']:
    g.unlink(missing_ok=True)
for f in ('c.spice', 'raw.spice'):          # strip '**FLOATING' comments
    p = out / f; p.write_text(re.sub(r'\s*\*\*FLOATING', '', p.read_text()))
r = subprocess.run([sys.executable, '/home/ubuntu/svalbard/scratch/wired_rx/r11/rc_ctle/mkrc.py', str(out / 'c.spice'), str(out / 'raw.spice'), str(out / 'rc0.spice')],
                   capture_output=True, text=True)
(out / 'mkrc.log').write_text(r.stdout + r.stderr)
if r.returncode: print(r.stdout[-1500:], r.stderr[-1500:]); sys.exit(1)
t = (out / 'rc0.spice').read_text().replace('pt_ptrim_flat', 'pt_ptrim'); (out / 'ptrim.rc.spice').write_text(t)
(out / 'rc0.spice').unlink()
# coverage + per-net C cross-check
join = lambda p: re.sub(r'\n\+\s*', ' ', Path(p).read_text()).splitlines()
base = lambda n: re.sub(r'\.[nt]\d+$', '', n)
def csum(lines, b=lambda n: n):
    s = collections.Counter()
    for l in lines:
        p = l.split()
        if p and p[0][0] == 'C' and len(p) >= 4:
            v = p[3]; m = re.match(r'([\d.eE+-]+)([fpn]?)', v); x = float(m.group(1)) * dict(f=1, p=1e3, n=1e6, **{'': 1e15})[m.group(2)]
            for n in (b(p[1]), b(p[2])): s[n] += x
    return s
Cc = csum(join(out / 'c.spice')); Cr = csum(join(out / 'ptrim.rc.spice'), base)
nets_r = collections.defaultdict(set)
for l in join(out / 'ptrim.rc.spice'):
    p = l.split()
    if p and p[0][0] == 'R' and len(p) >= 4:
        for n in p[1:3]: nets_r[base(n)].add(n)
sup = {'VSS', 'VDD_WIRE_SW', 'VSUBS', '0'}
allnets = {n for n in Cc if n not in sup}
res = {n for n in nets_r if n not in sup}
ratio = {n: Cr[n] / Cc[n] for n in Cc if Cc[n] > 0.01}
clock = [n for n in allnets if re.match(r'^(PH\d|CKP\d|.*t[nab]\d?$|.*tc)', n.split('/')[-1])]
rep = dict(gds=str(gds), ignore_supply=ign, nets_nonsupply=len(allnets), nets_resisted=len(res), resisted_share=round(len(res) / max(1, len(allnets)), 4),
           supplies_resisted=sorted(n for n in nets_r if n in sup), resistors=sum(1 for l in join(out / 'ptrim.rc.spice') if l[:1] == 'R'),
           clock_nets=len(clock), clock_nets_resisted=sum(1 for n in clock if n in res), clock_not_resisted=sorted(n for n in clock if n not in res)[:40],
           c_ratio_min=round(min(ratio.values()), 6), c_ratio_max=round(max(ratio.values()), 6), mkrc_tail=r.stdout.splitlines()[:3])
(out / 'rc.json').write_text(json.dumps(rep, indent=1)); print(json.dumps({k: v for k, v in rep.items() if k != 'clock_not_resisted'}))
