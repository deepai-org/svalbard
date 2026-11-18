"""Flat R+C extraction (Magic extresist, analog image; recipe of scratch/lo-ap4/rcx.py - the digital-image Magic
8.3.623 is recorded as crashing in extresist).  usage: rc.py <gds> <outdir>  -> <outdir>/wtx_ser8d.rc.spice
Supplies (VDD, VSS, substrate) are not resisted."""
import sys, shutil, subprocess, re
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
import tools, ser8d_macro as D
CELL = D.NAME
gds, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True)
shutil.copy(gds, out / 'in.gds')
(out / 'rc.tcl').write_text(f"""crashbackups stop
drc off
gds read in.gds
load {CELL}
flatten {CELL}_flat
load {CELL}_flat
select top cell
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2sim labels on
ext2sim
extresist tolerance 10
extresist ignore VSS
extresist ignore VDD
extresist ignore VSUBS
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice subcircuit top on
ext2spice -o {CELL}_flat.rc.spice
quit -noprompt
""")
subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1', '--entrypoint', '/bin/bash',
                '-v', f'{out}:/work', '-w', '/work', tools.ANALOG_IMAGE, '-lc',
                'magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/rc.tcl > rc.log 2>&1'])
f = out / f'{CELL}_flat.rc.spice'
if not f.exists():
    print('FAILED: no netlist; see', out / 'rc.log'); sys.exit(1)
t = f.read_text().replace(f'{CELL}_flat', CELL)
(out / f'{CELL}.rc.spice').write_text(t)
f.unlink()
for g in list(out.glob('*.ext')) + list(out.glob('*.sim')) + list(out.glob('*.nodes')) + [out / 'in.gds']:
    if g.exists(): g.unlink()
m = re.search(rf'\.subckt {CELL} ((?:.*\n)(?:\+.*\n)*)', t)
ports = m.group(1).replace('\n+', ' ').split()
L = t.splitlines()
print(out / f'{CELL}.rc.spice', 'R', sum(l.startswith('R') for l in L), 'C', sum(l.startswith('C') for l in L),
      'X', sum(l.startswith('X') for l in L), 'D', sum(l.startswith('D') for l in L), 'ports == ser8d_macro.PORTS:', ports == D.PORTS, len(ports))
