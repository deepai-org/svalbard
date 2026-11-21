"""AP4-5 lo_mmd old/new extracted comparison.  Same deck as lcvco/run_loop.py tb_mmd / run_mmd_rc (rung 4a) plus two
extra measures (absolute FB edge time, for the divider latency; average supply current).  One dir per run.
usage: mmd_bench.py <tag> <rc_netlist> <cases.json> [jobs]     results: mmd/<tag>/<run>/result.json, mmd/<tag>.json
Pass criterion (fixed, from run_mmd_rc): ratio over 3 periods within 0.02 of N and single period within 0.05."""
import sys, json, math, shutil, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
L = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/lcvco'
sys.path.insert(0, L)
import run_loop as rl
tf = rl.tf
tag, net, cases = sys.argv[1], Path(sys.argv[2]).resolve(), json.load(open(sys.argv[3]))
jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
ROOT = Path('/home/ubuntu/svalbard/scratch/lo-ap4/mmd') / tag
src = net.read_text().replace('.subckt pt_lo_mmd_flat', '.subckt pt_lo_mmd').replace('.ends pt_lo_mmd_flat', '.ends')
md5 = hashlib.md5(net.read_bytes()).hexdigest()

_h0 = rl.header
def _hdr(corner, temp):      # sf / fs: MOS skewed, MIM / MOS-cap typical (no skewed libs in the PDK)
    if corner in ('sf', 'fs'):
        return (tf.header(corner, temp) + f'.lib {tf.MODELS}/sm141064.ngspice mimcap_typical\n'
                + f'.lib {tf.MODELS}/sm141064.ngspice moscap_typical\n')
    return _h0(corner, temp)
rl.header = _hdr


def one(c):
    corner, temp, v, f, n, amp, cm = c[:7]
    expect = c[7] if len(c) > 7 else 'pass'
    run = f'{corner}{temp}_{v}_{f / 1e9:.2f}_{n}_{amp}_{cm}'
    wd = ROOT / run
    if (wd / 'result.json').exists():
        return json.loads((wd / 'result.json').read_text())
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    (wd / 'mmd_rc.spice').write_text(src)
    ncyc = 6
    T = (ncyc + 1) * n / f + 8e-9
    td = T - (ncyc - 1) * n / f - 1e-9
    extra = (f'.measure tran tfb when v(fb)={v / 2} td={td} rise=1\n'
             f'.measure tran tfbf when v(fb)={v / 2} td={td} fall=1\n'
             f'.measure tran trf trig v(fb) val={0.2 * v} td={td} rise=1 targ v(fb) val={0.8 * v} td={td} rise=1\n')
    m = tf.ngspice(wd, 'mmd', rl.header(corner, temp) + rl.tb_mmd('mmd_rc.spice', f, n, v, amp, cm, ncyc) + extra + '.end\n')
    nm = (m.get('per', 0) / 3) * f if m.get('per') else None
    n1 = m.get('per1', 0) * f if m.get('per1') else None
    tfb = m.get('tfb')
    r = dict(run=run, tag=tag, corner=corner, temp_c=temp, vdd=v, f_in_hz=f, n_set=n, amp_v_per_leg=amp, cm_v=cm,
             n_measured=nm, n_single=n1, fb_width_ns=m.get('wid', 0) * 1e9, idd_ma=-m.get('idd', math.nan) * 1e3,
             t_fb_s=tfb, t_fb_mod_2tin_ps=(math.fmod(tfb, 2 / f) * 1e12 if tfb else None), fb_rise_ps=(m.get('trf', math.nan) * 1e12),
             netlist_md5=md5, errors=m['_errors'][:3], expect=expect)
    r['pass'] = bool(nm and abs(nm - n) < 0.02 and n1 and abs(n1 - n) < 0.05)
    r['as_expected'] = r['pass'] == (expect == 'pass')
    (wd / 'result.json').write_text(json.dumps(r, indent=1) + '\n')
    return r

with ThreadPoolExecutor(jobs) as ex:
    res = []
    for r in ex.map(one, cases):
        print(tag, r['run'], 'pass' if r['pass'] else 'FAIL', 'exp', r['expect'], 'N=%s' % r['n_measured'], 'idd %.1f' % r['idd_ma'],
              'tfbmod %s' % r['t_fb_mod_2tin_ps'], r['errors'], flush=True)
        res.append(r)
old = json.loads((ROOT.parent / f'{tag}.json').read_text()) if (ROOT.parent / f'{tag}.json').exists() else []
keep = [o for o in old if o['run'] not in {x['run'] for x in res}]
(ROOT.parent / f'{tag}.json').write_text(json.dumps(keep + res, indent=1) + '\n')
