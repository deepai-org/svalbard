"""Capture r7e: LVS and DRC on the GDS READ BACK FROM DISK (the staged, uniquified gen/wrx_cap.gds), device parameters
compared (netgen property errors counted), plus a negative control (one device width changed in the reference must fail).
Run through ../../../slot.sh."""
import sys, shutil, subprocess, hashlib, json, re
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W)); sys.path.insert(0, str(W.parent / 'timing'))
import wrx_flow as f, layout_engine as le
H = Path(__file__).resolve().parent
S = Path('/home/ubuntu/svalbard/scratch/wired_rx/r10cap/r7e')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
shutil.copy(S / 'gen' / 'wrx_cap.gds', H / 'in.gds'); shutil.copy(S / 'cap' / 'top' / 'schematic.spice', H / 'schematic.spice')
(H / 'rb.tcl').write_text('\n'.join(['crashbackups stop', 'gds read in.gds', 'load pt_wrx_cap', 'select top cell', 'drc euclidean on', 'drc style drc(full)',
    'drc check', 'drc catchup', 'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f', 'extract all', 'ext2spice lvs',
    'ext2spice -o rb.lvs.spice', 'quit -noprompt']) + '\n')
(H / 'rb.sh').write_text('export PDK_ROOT=/foss/pdks PDK=gf180mcuD\n/foss/tools/bin/magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc rb.tcl > rb.log 2>&1\n')
subprocess.run(['docker', 'run', '--rm', *f.DOCKER_LIMITS, '--entrypoint', '/bin/bash', '--mount', f'type=bind,src={H},dst=/work', '-w', '/work', f.ANALOG_IMAGE, '/work/rb.sh'],
               capture_output=True, text=True, timeout=7200)
rep = dict(gds=str(S / 'gen' / 'wrx_cap.gds'), gds_sha256=sha(H / 'in.gds'), schematic_sha256=sha(H / 'schematic.spice'),
           drc_raw=(H / 'drc-count.txt').read_text().strip() if (H / 'drc-count.txt').exists() else 'missing')
def verdict(out):
    t = (H / out).read_text() if (H / out).exists() else ''
    fin = t[t.rfind('Final result'):][:300] if 'Final result' in t else 'no final result'
    return dict(final=fin.strip(), property_error_lines=len(re.findall(r'[Pp]roperty errors', t)), top_devices=re.findall(r'Number of devices: (\d+)', t)[-2:],
                clean=bool('Circuits match uniquely' in fin and 'roperty errors' not in t))
le.netgen_lvs(H, 'rb.lvs.spice', 'pt_wrx_cap', 'schematic.spice', 'pt_wrx_cap', out='lvs-readback.txt')
rep['lvs'] = verdict('lvs-readback.txt')
# negative control: first pfet with w=4u in the reference becomes w=4.1u
t = (H / 'schematic.spice').read_text(); t2, n = re.subn(r'(pfet_03v3[^\n]*?\bw=)4(u?\b)', r'\g<1>4.1\2', t, count=1, flags=re.I)
(H / 'schematic_neg.spice').write_text(t2); rep['neg_edit_count'] = n
le.netgen_lvs(H, 'rb.lvs.spice', 'pt_wrx_cap', 'schematic_neg.spice', 'pt_wrx_cap', out='lvs-negative.txt')
rep['lvs_negative_control'] = verdict('lvs-negative.txt')
(H / 'in.gds').unlink()
(H / 'readback.json').write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))
