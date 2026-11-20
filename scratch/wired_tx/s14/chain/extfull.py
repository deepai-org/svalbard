"""Full-coverage Magic extresist of the snapshot GDS in net/ (tolerance 0.001, simplify off). usage: extfull.py <cell> [tol]"""
import sys, shutil, subprocess
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
import tools
FAST = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx/generated/fast')
cell = sys.argv[1]; tol = sys.argv[2] if len(sys.argv) > 2 else '0.001'
out = Path(__file__).resolve().parent / 'xk' / cell
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True)
shutil.copy(Path(__file__).resolve().parent / 'net' / f'{cell}.gds', out / 'in.gds')
(out / 'rc.tcl').write_text(f"""crashbackups stop
drc off
gds read in.gds
load {cell}
flatten {cell}_flat
load {cell}_flat
select top cell
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2sim labels on
ext2sim
extresist tolerance {tol}
extresist ignore VSS
extresist ignore VDD
extresist ignore VSUBS
extresist simplify off
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice subcircuit top on
ext2spice -o full.rc.spice
quit -noprompt
""")
subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1',
                '--entrypoint', '/bin/bash', '-v', f'{out}:/work', '-w', '/work', tools.ANALOG_IMAGE, '-lc',
                f'magic -dnull -noconsole -rcfile {tools.ANALOG_PDK}/libs.tech/magic/gf180mcuD.magicrc /work/rc.tcl > rc.log 2>&1'])
for g in [] and list(out.glob('*.ext')) + list(out.glob('*.sim')) + list(out.glob('*.nodes')) + [out / 'in.gds']:
    if g.exists(): g.unlink()
f = out / 'full.rc.spice'
print(cell, 'OK' if f.exists() else 'FAILED', f.stat().st_size if f.exists() else '')
