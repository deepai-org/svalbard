"""ngspice load + operating-point smoke test of the R+C netlist (and the C-only one): syntax / models only, no function.
usage: smoke.py"""
import sys, shutil, re
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
import tools, ser8d_macro as D
tools.DOCKER_LIMITS = ['--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1']
H = Path(__file__).resolve().parent
w = H / 'smoke'
if w.exists(): shutil.rmtree(w)
w.mkdir()
for tag, src in (('rc', H / 'rcx/wtx_ser8d.rc.spice'), ('c', tools.GENERATED / 'fast/wtx_ser8d.ext.spice')):
    shutil.copy(src, w / f'{tag}.spice')
    conn = ' '.join('VDD' if p in ('VDD', 'SERQ') else '0' if p == 'VSS' else ('PHX' if p.startswith('PH') else p if p[0] in 'FW' else '0') for p in D.PORTS)
    deck = (f'* smoke {tag}\n' + tools.model_header('typical') + f'.include {tag}.spice\nVDD VDD 0 3.3\nVPH PHX 0 0\nX0 {conn} {D.NAME}\n'
            + '.option gmin=1e-12\n.op\n.control\nop\nprint v(F0) v(F7) v(WCKQ) i(VDD)\n.endc\n.end\n')
    (w / f'{tag}.sp').write_text(deck)
    tools.ngspice(w, f'{tag}.sp')
    t = (w / f'{tag}.sp.log').read_text(errors='replace')
    print(tag, 'errors:', [l[:150] for l in t.splitlines() if re.search(r'error|fatal|unknown|no such', l, re.I)][:5], '|', [l for l in t.splitlines() if re.match(r'(v\(|i\()', l)])
