#!/usr/bin/env python3
"""hsdiag.py <model> <process> <temp> <vdd> <code> [variant ...]: HS delivered-current trace (esdopt/usb, b7 task a).
The fbench.py hs_term deck (stress_safe_usb, mirror bias 17.78 mA/14 into one 20/1 replica), as an OP: reports V(PAD_P), I(far 45),
I(termination, via VTERM_VCM), I(VDD), I(replica), mirror-output drain / switch-node voltages.  Variants: vbias=<V> (gate held at a
voltage), ideal=<A> (ideal current into PAD_P instead of the driver: termination split only), noterm (TERM_ENABLE 0)."""
import sys, re, json
from pathlib import Path
sys.argv = [sys.argv[0], sys.argv[1], 'diag'] + sys.argv[2:]
ARGS = sys.argv[3:]
sys.argv = sys.argv[:3]
exec(open(Path(__file__).with_name('fbench.py')).read().split('import os\n')[0])
pr, tc, vd, code = ARGS[0], int(ARGS[1]), float(ARGS[2]), int(ARGS[3]); var = ARGS[4:]
u.TERM_TRIM[pr] = code
d, _ = u.deck('hs_term', pr, tc, vd, W, 'hsdiag')
d = d.split('.control')[0]
for v in var:
    if v.startswith('vbias='):
        d = re.sub(r'^XHSREF.*\n|^IHSREF.*\n', '', d, flags=re.M); d = d.replace('\nXpad ', f'\nVHSB HS_PBIAS 0 {v[6:]}\nXpad ', 1)
    if v.startswith('ideal='):
        d = re.sub(r'^VHS_P HS_P 0 \S+', 'VHS_P HS_P 0 0', d, flags=re.M); d += f'IIDEAL 0 PAD_P {v[6:]}\n'
    if v == 'noterm':
        d = re.sub(r'^VTERM_ENABLE TERM_ENABLE 0 \S+', 'VTERM_ENABLE TERM_ENABLE 0 0', d, flags=re.M)
        d = re.sub(r'^VTERM_TRIM(\d) TERM_TRIM\d 0 \S+', r'VTERM_TRIM\1 TERM_TRIM\1 0 0', d, flags=re.M)
d = d.replace('RFAR_P PAD_P 0 45', 'RFAR_P PAD_P far 45\nVFAR far 0 0')
hs = sorted(set(re.findall(r'\b(HS_P_\d+)\b', Path(sys.argv[1]).read_text())), key=lambda s: int(s[5:]))
sw = sorted(set(re.findall(r'^X\S+ HS_P_\d+ HS_P (PAD_P__\d+)', Path(sys.argv[1]).read_text(), re.M)))
vec = ['v(PAD_P)', 'i(VFAR)', 'i(VTERM_VCM)', 'i(VDD)', 'v(HS_PBIAS)'] + [f'v(xpad.xphysical.{n.lower()})' for n in hs + sw]
d += f'.control\nop\nprint {" ".join(vec)}\nquit\n.endc\n.end\n'
d = s.corner(d, pr, tc)
(W / 'hsdiag.spice').write_text(d)
import subprocess
cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '6g', '-e', 'OMP_NUM_THREADS=1', '--user', '1000:1000',
       '--entrypoint', s.NGSPICE, '--mount', f'type=bind,src={s.SCRATCH},dst={s.SCRATCH}', '-w', str(W), s.SIM_IMAGE, '-b', 'hsdiag.spice']
o = subprocess.run(cmd, capture_output=True, text=True, timeout=3000).stdout
vals = dict((m[0].lower(), float(m[1])) for m in re.findall(r'^(\S+) = (\S+)$', o, re.M))
if not vals: print(o[-3000:]); raise SystemExit(1)
vp = vals['v(pad_p)']; ifar = -vals['i(vfar)'] if vals['i(vfar)'] < 0 else vals['i(vfar)']; it = -vals['i(vterm_vcm)']
print(json.dumps(dict(model=sys.argv[1], corner=[pr, tc, vd], code=code, var=var, pad_p_v=vp, i_far_ma=vals['i(vfar)'] * 1e3, i_term_ma=it * 1e3,
      i_vdd_ma=vals['i(vdd)'] * 1e3, hs_pbias=vals['v(hs_pbias)'],
      nodes={k[16:-1]: round(v, 4) for k, v in vals.items() if k.startswith('v(xpad')})))
