"""Probe the published lo_mmd (fixcap16 RC) at ss/32/3.15, 2.987 GHz, 1.308 V per leg, CM 1.40 (failing top case):
average period of the prescaler master / slave outputs and the K0 follower pair over 40 cycles, vs 2/f."""
import sys, json
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/lcvco')
import run_loop as rl
tf = rl.tf
H = Path(__file__).resolve().parent
f, n, v, amp, cm = 2.987e9, 50, 3.15, 1.308, 1.40
src = Path('/home/ubuntu/svalbard/scratch/lo-ap4/rc/lo_mmd_old/pt_lo_mmd_flat.rcfix16.spice').read_text()
PR = dict(zpmp='a_992_12072.n0', zpmn='a_2248_12072.n0', zslp='a_13552_12072.n0', zsln='a_14682_716.t0', zk0p='a_912_12228.n0', zk0n='a_2168_12228.n0')
t = src.replace('.subckt pt_lo_mmd_flat LP LN EN N0 N1 N2 N3 N4 N5 FB VDD VSS', '.subckt pt_lo_mmd LP LN EN N0 N1 N2 N3 N4 N5 FB VDD VSS ' + ' '.join(PR))
i = t.rindex('.ends')
t = t[:i] + ''.join(f'RPRB{k} {k} {v} 1\n' for k, v in PR.items()) + t[i:]
(H / 'mmd_rc.spice').write_text(t)
T = 7 * n / f + 8e-9
td = 20e-9
pairs = dict(master=('zpmp', 'zpmn'), slave=('zslp', 'zsln'), k0=('zk0p', 'zk0n'))
m = ''.join(f'E{k} zd{k} 0 {a} {b} 1\n' for k, (a, b) in pairs.items()) + ''.join(f'.measure tran p_{k} trig v(zd{k}) val=0 td={td} rise=1 targ v(zd{k}) val=0 td={td} rise=41\n'
            f'.measure tran amp_{k} pp v(zd{k}) from={td} to={T}\n' for k, (a, b) in pairs.items())
tb = rl.tb_mmd('mmd_rc.spice', f, n, v, amp, cm).replace('n4 n5 fb vdd 0 pt_lo_mmd', 'n4 n5 fb vdd 0 ' + ' '.join(PR) + ' pt_lo_mmd')
r = tf.ngspice(H, 'probe', rl.header('ss', 32) + tb + m + '.end\n')
out = {k: (r.get(f'p_{k}', 0) / 40 * f / 2 if r.get(f'p_{k}') else None) for k in pairs}
out.update({f'amp_{k}': r.get(f'amp_{k}') for k in pairs}, N=(r.get('per', 0) / 3 * f if r.get('per') else None), errors=r['_errors'][:3])
(H / 'probe.json').write_text(json.dumps(out, indent=1)); print(out)
