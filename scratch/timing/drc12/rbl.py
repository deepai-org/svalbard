"""Read-back LVS of a GDS from disk (Magic extract in the project image, netgen with property comparison through
layout_engine.netgen_lvs) against a reference netlist, plus a negative control (first w=<x>u in the reference +0.5 um).
  rbl.py TAG GDS TOP REF_SPICE [REF_TOP]   -> drc12/rbl/<TAG>/readback.json"""
import sys, shutil, subprocess, hashlib, json, re
from pathlib import Path
A = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog')
sys.path.insert(0, str(A / 'wired_rx')); sys.path.insert(0, str(A / 'timing'))
import wrx_flow as f, layout_engine as le
tag, gds, top, ref = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4]).resolve()
rtop = sys.argv[5] if len(sys.argv) > 5 else top
H = Path(__file__).resolve().parent / 'rbl' / tag; shutil.rmtree(H, ignore_errors=True); H.mkdir(parents=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
shutil.copy(gds, H / 'in.gds'); shutil.copy(ref, H / 'ref.spice')
(H / 'rb.tcl').write_text('\n'.join(['crashbackups stop', 'gds read in.gds', f'load {top}', 'select top cell', 'extract all',
                                     'ext2spice lvs', 'ext2spice -o rb.lvs.spice', 'quit -noprompt']) + '\n')
(H / 'rb.sh').write_text('export PDK_ROOT=/foss/pdks PDK=gf180mcuD\n/foss/tools/bin/magic -dnull -noconsole -rcfile '
                         '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc rb.tcl > rb.log 2>&1\n')
subprocess.run(['docker', 'run', '--rm', *f.DOCKER_LIMITS, '--entrypoint', '/bin/bash', '--mount', f'type=bind,src={H},dst=/work',
                '-w', '/work', f.ANALOG_IMAGE, '/work/rb.sh'], capture_output=True, text=True, timeout=7200)
import os
if os.environ.get('RBL_NODIODE'):
    # antenna diodes (diode_nd2ps_03v3) are added by the layout flow and are not in the schematic: removed from the layout
    # netlist for the schematic comparison (counted in the report)
    lt = (H / 'rb.lvs.spice').read_text().splitlines(); keep = [l for l in lt if 'diode_nd2ps_03v3' not in l]
    (H / 'rb.lvs.spice').write_text('\n'.join(keep) + '\n'); ndiode = len(lt) - len(keep)
else:
    ndiode = 0
r1 = le.netgen_lvs(H, 'rb.lvs.spice', top, 'ref.spice', rtop, out='lvs.txt')
t = (H / 'ref.spice').read_text()
t2, n = re.subn(r'(\bw=)([\d.]+)(u)', lambda m: f'{m.group(1)}{float(m.group(2)) + 0.5:g}{m.group(3)}', t, count=1)
(H / 'ref_neg.spice').write_text(t2)
r2 = le.netgen_lvs(H, 'rb.lvs.spice', top, 'ref_neg.spice', rtop, out='lvs_neg.txt')
for p in H.glob('*.ext'): p.unlink()
(H / 'in.gds').unlink()
rep = dict(antenna_diodes_removed=ndiode, gds=str(gds), gds_sha256=sha(gds), ref=str(ref), ref_sha256=sha(ref), lvs=r1, negative_control=dict(edits=n, **r2),
           clean=bool(r1['unique_match'] and not r1['property_errors'] and not r2['unique_match']))
(H / 'readback.json').write_text(json.dumps(rep, indent=1)); print(tag, 'clean' if rep['clean'] else 'NOT CLEAN', r1['summary'][:200].replace('\n', ' '), '| neg:', r2['summary'][:80].replace('\n', ' '))
