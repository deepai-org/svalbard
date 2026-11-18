"""Independent read-back verification of generated/fast/wtx_ser8d.gds (fresh directory, GDS from disk).
usage: python3 verify.py [outdir=v]   One docker job at a time, sequential.
  Magic DRC (own session), Magic extraction (own session: LVS netlist + flat C-only netlist), Netgen LVS against
  ser8d_macro.top_spice() + cell netlists + the engine's antenna diodes, negative controls, KLayout DRC."""
import sys, subprocess, shutil, json, re, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
WTX = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
IMAGE, PDK = 'svalbard/librelane-gf180-canary:2026.08', '/pdk/gf180mcuD'
sys.path.insert(0, str(WTX))
import tools, ser8d_macro as D, serq4_macro as M
CELL = D.NAME

def docker(work, args, entry='/bin/sh'):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1',
           '--entrypoint', entry, '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', IMAGE] + args
    return subprocess.run(cmd, capture_output=True, text=True)

def magic(work, script):
    r = docker(work, ['-c', f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}'])
    (work / (script + '.log')).write_text(r.stdout + r.stderr)

def netgen(work, sch, out):
    r = docker(work, ['-batch', 'lvs', f'{CELL}.lvs.spice {CELL}', f'{sch} {CELL}', f'{PDK}/libs.tech/netgen/gf180mcuD_setup.tcl', out], entry='netgen')
    (work / (out + '.log')).write_text(r.stdout + r.stderr)
    t = (work / out).read_text() if (work / out).exists() else 'NO REPORT'
    fin = t[t.rfind('Final result'):].strip() if 'Final result' in t else t[-300:]
    return ' '.join(fin.split())[:200]

work = HERE / (sys.argv[1] if len(sys.argv) > 1 else 'v')
if work.exists(): shutil.rmtree(work)
work.mkdir()
gds = M.FAST / f'{CELL}.gds'
shutil.copy(gds, work / f'{CELL}.gds')
res = dict(gds=str(gds), gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(), hops={str(k): list(v) for k, v in D.HOPS.items()})
drc = ['crashbackups stop', f'gds read {CELL}.gds', f'load {CELL}', 'select top cell', 'expand',
       'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
       'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
       'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
       'set f [open bbox.txt w]', 'units microns', 'puts $f [box values]', 'close $f', 'quit -noprompt']
ext = ['crashbackups stop', f'gds read {CELL}.gds', f'load {CELL}', 'select top cell', 'expand',
       'extract all', 'ext2spice lvs', f'ext2spice -o {CELL}.lvs.spice',
       'ext2spice default', 'ext2spice hierarchy off', 'ext2spice subcircuit top on', 'ext2spice cthresh 0', f'ext2spice -o {CELL}.flatc.spice',
       'quit -noprompt']
(work / 'drc.tcl').write_text('\n'.join(drc) + '\n'); (work / 'ext.tcl').write_text('\n'.join(ext) + '\n')
magic(work, 'drc.tcl'); magic(work, 'ext.tcl')
res['magic_drc_count'] = (work / 'drc-count.txt').read_text().strip() if (work / 'drc-count.txt').exists() else 'missing'
res['bbox_um'] = (work / 'bbox.txt').read_text().strip() if (work / 'bbox.txt').exists() else 'missing'
# reference: cells + top_spice() (+ antenna diodes as recorded by the generator in generated/fast/wtx_ser8d.spice)
cells = ''.join((M.FAST / f'{n}.spice').read_text() for n in D.CELLS)
top = D.top_spice()
diodes = [l for l in (M.FAST / f'{CELL}.spice').read_text().splitlines() if l.startswith('DANT')]
res['antenna_diodes'] = diodes
sch = cells + top.replace(f'.ends {CELL}', '\n'.join(diodes) + f'\n.ends {CELL}')
(work / 'sch_nodiode.spice').write_text(cells + top)
(work / 'sch.spice').write_text(sch)
lvs = {}
lvs['ref = top_spice() + cells + diodes'] = netgen(work, 'sch.spice', 'lvs.txt')
lvs['ref = top_spice() + cells, NO diodes (expected to differ by the diodes only)'] = netgen(work, 'sch_nodiode.spice', 'lvs-nodiode.txt')
# negative controls (each must FAIL)
k2 = [k for k in D.HOPS][3:5]
fin = {k: f'XH{k}_{len(D.HOPS[k]) - 1}' for k in D.HOPS}
def line(inst): return next(l for l in sch.splitlines() if l.startswith(inst + ' '))
a, b = line(fin[k2[0]]), line(fin[k2[1]])
fa, fb = f' F{k2[0]} ', f' F{k2[1]} '
negs = {}
negs[f'neg_fswap (outputs of {fin[k2[0]]} and {fin[k2[1]]} swapped)'] = sch.replace(a, a.replace(fa, fb)).replace(b, b.replace(fb, fa))
h0 = line('XH0_0'); q = h0.split()[1]; q2 = f'Q{(int(q[1:]) + 1) % 8}'
negs[f'neg_hopclk (XH0_0 clocked by {q2} instead of {q})'] = sch.replace(h0, h0.replace(f' {q} ', f' {q2} ', 1).replace(f'XH0_0 {q} ', f'XH0_0 {q2} '))
p0 = next(l for l in sch.splitlines() if 'nfet_03v3' in l and 'w=2u' in l)
negs['neg_prop (first nfet with w=2u in the reference: w 2u -> 2.2u; Netgen names the cell)'] = sch.replace(p0, p0.replace('w=2u', 'w=2.2u'), 1)
d0 = line('XL0'); t = d0.split()
t2 = t[:]; t2[1], t2[2] = t[2], t[1]
negs['neg_dswap (XL0 data pins D0 / D8 swapped)'] = sch.replace(d0, ' '.join(t2))
res['negative_controls'] = {}
for i, (n, tx) in enumerate(negs.items()):
    assert tx != sch, n
    (work / f'neg{i}.spice').write_text(tx)
    res['negative_controls'][n] = netgen(work, f'neg{i}.spice', f'lvs-neg{i}.txt')
res['lvs'] = lvs
# port order of the extracted netlists
for f in (f'{CELL}.lvs.spice', f'{CELL}.flatc.spice'):
    tx = (work / f).read_text()
    m = re.search(rf'\.subckt {CELL} ((?:.*\n)(?:\+.*\n)*)', tx)
    ports = m.group(1).replace('\n+', ' ').split()
    res[f'ports_ok {f}'] = ports == D.PORTS
    res[f'sha256 {f}'] = hashlib.sha256((work / f).read_bytes()).hexdigest()
tools.DOCKER_LIMITS = ['--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1']
kl = tools.klayout_drc(work, work / f'{CELL}.gds', CELL)
res['klayout_drc'] = {k: v for k, v in kl.items() if k != 'report'}
(work / 'verify.json').write_text(json.dumps(res, indent=1) + '\n')
for f in list(work.glob('*.ext')) + list(work.glob('*.log')):   # keep the directory small
    if f.suffix == '.ext': f.unlink()
print(json.dumps({k: v for k, v in res.items() if k != 'antenna_diodes'}, indent=1)); print('diodes', len(diodes))
