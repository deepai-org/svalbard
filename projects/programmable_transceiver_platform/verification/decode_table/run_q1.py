import random, subprocess, sys, collections
from gen import *; import model
random.seed(1)
PWR = [f'debug.island_power.{k}' for k in ('wired', 'rf', 'pll', 'usb', 'conv', 'debug')]
def base(rand=True):
    F = {}
    for f in FIELDS:
        F[f['name']] = random.choice(list(legal(f))) if rand and random.random() < 0.8 else default(f)
    for n in PWR: F[n] = 1
    for f in FIELDS:
        if f['name'].startswith('debug.pgood_override'): F[f['name']] = 0
        if f['name'].startswith(('debug.atb', 'monitor.', 'debug.dbg_obs', 'debug.host_link', 'debug.pattern', 'digital.', 'debug.freq_count')): F[f['name']] = default(f)
    if F['core.biasgen.ref_sel_fine'] and not F['core.biasgen.ref_sel_coarse']: F['core.biasgen.ref_sel_fine'] = 0
    D = {n: random.getrandbits(w) for n, w in DYN}
    B = {'fault_pin': 0, 'pg': 0x3FF, 'wired_on_ext': 0}
    return F, D, B
V = []
for _ in range(600): V.append(base())
for f in FIELDS:                                   # every legal value of every field (<= 64 values, else walking bits + random)
    vals = list(legal(f))
    if len(vals) > 64: vals = sorted(set([0, vals[-1]] + [1 << b for b in range(f['w']) if (1 << b) <= vals[-1]] + [vals[-1] ^ (1 << b) for b in range(f['w']) if 0 <= (vals[-1] ^ (1 << b)) <= vals[-1]] + random.sample(vals, 8)))
    if f['name'] in PWR or f['name'].startswith('debug.pgood'): continue
    for x in vals:
        F, D, B = base(rand=random.random() < 0.5); F[f['name']] = x
        if f['name'] == 'core.biasgen.ref_sel_fine': F['core.biasgen.ref_sel_coarse'] = 1
        V.append((F, D, B))
for g in range(128):                                # every opcode-4 gain word, fast gain active
    F, D, B = base(); D['rx_gain'] = g; D['rx_gain_active'] = 1; V.append((F, D, B))
write_tb(len(V), 300); write_vec(V)
RTL = sys.argv[1] if len(sys.argv) > 1 else str(P/'rtl')
c = subprocess.run(['iverilog', '-g2012', '-I', RTL, '-s', 'tb_dec', '-o', 'tb.vvp', 'tb_dec.sv', *map(str, sorted(Path(RTL).glob('*.sv')))], capture_output=True, text=True)
if c.returncode: sys.exit(c.stderr[:3000])
subprocess.run(['vvp', '-n', 'tb.vvp'], capture_output=True, text=True)
R = read_out(); bad = collections.Counter(); ex = {}
for (F, D, B), O in zip(V, R):
    Oi = {k: (int(v, 16) if 'x' not in v and 'z' not in v else None) for k, v in O.items()}
    E = model.expect(F, D, Oi)
    for n, w, _ in PORTS:
        if n in model.DYNAMIC: continue
        if n not in E: bad['NO MODEL ' + n] += 1; continue
        if E[n] is None: continue
        if Oi[n] != E[n]:
            bad[n] += 1; ex.setdefault(n, (E[n], O[n]))
print(len(V), 'vectors;', 'mismatching ports:', len(bad))
for n, k in bad.most_common(): print(f'  {n}: {k} vectors, e.g. expected {ex.get(n, ("", ""))[0]} got {ex.get(n, ("", ""))[1]}')
