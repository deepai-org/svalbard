"""Flat C-only extraction of a GDS (digital image, extraction-only Magic session).  usage: flatc.py <gds> <outdir>"""
import sys, shutil, subprocess
from pathlib import Path
gds, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
CELL = 'wtx_ser8d'
out.mkdir(parents=True, exist_ok=True)
shutil.copy(gds, out / f'{CELL}.gds')
(out / 'ext.tcl').write_text('\n'.join(['crashbackups stop', f'gds read {CELL}.gds', f'load {CELL}', 'select top cell', 'expand', 'extract all',
    'ext2spice default', 'ext2spice hierarchy off', 'ext2spice subcircuit top on', 'ext2spice cthresh 0', f'ext2spice -o {CELL}.flatc.spice', 'quit -noprompt']) + '\n')
subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1', '--entrypoint', '/bin/sh',
    '--mount', f'type=bind,src={out},dst=/work', '-w', '/work', 'svalbard/librelane-gf180-canary:2026.08', '-c',
    'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/ext.tcl > ext.log 2>&1'])
for f in out.glob('*.ext'): f.unlink()
(out / f'{CELL}.gds').unlink()
