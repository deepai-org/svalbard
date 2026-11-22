"""Known-answer for mismatch in the LO benches' header path (envq: run_lcvco.hdr + '.param sw_stat_mismatch=1' +
'.option seed'): matched nfet_03v3 X-instance pair W 10 / L 1 um, 20 uA diodes each, tt/27: sigma(dVgs) over 40 seeds
vs 2.45 mV expected (rf_rx mc_selftest, row RQ-18; limit +-20 %). Negative control: same seeds without the param -> 0.
One deck per seed (op), sequential."""
import sys, json, statistics
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/lcvco')
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/lo/r5_pn')
import run_lcvco as rlc
import corners  # noqa: same patched hdr as envq
tf = rlc.tf
H = Path(__file__).resolve().parent
out = {}
for mode in ('mc', 'off'):
    dv = []
    for s in range(1, 41):
        wd = H / 'runs' / f'{mode}{s}'
        d = rlc.hdr('tt', 27) + (f'.param sw_stat_mismatch=1\n' if mode == 'mc' else '') + f""".option seed={s}
VDD vdd 0 3.3
I1 vdd a 20u
I2 vdd b 20u
XA a a 0 0 nfet_03v3 w=10u l=1u
XB b b 0 0 nfet_03v3 w=10u l=1u
.op
.control
op
print v(a)-v(b)
.endc
.end
"""
        m = tf.ngspice(wd, 'ka', d)
        log = (wd / 'ka.log').read_text()
        import re
        x = re.search(r'v\(a\)-v\(b\)\s*=\s*([-+0-9.eE]+)', log)
        dv.append(float(x.group(1)) if x else None)
    good = [v for v in dv if v is not None]
    out[mode] = dict(n=len(good), sigma_mv=(statistics.pstdev(good) * 1e3 if len(good) > 2 else None), missing=len(dv) - len(good))
out['expected_sigma_mv'] = 2.45
out['pass'] = bool(out['mc']['sigma_mv'] and abs(out['mc']['sigma_mv'] / 2.45 - 1) <= 0.2 and out['off']['sigma_mv'] is not None and out['off']['sigma_mv'] < 0.01)
(H / 'ka.json').write_text(json.dumps(out, indent=1)); print(out)
