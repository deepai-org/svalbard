#!/usr/bin/env python3
"""OBS-15: host D2H simultaneous-switching bounce per chip on the real bond set, with the chip PDN model of
scratch/integration/m1-pdn (bonds from integration/chips/<chip>/bond_map.txt at the provider bond centres, coupled bond
inductance, provider ring rails + core ring, mesh, the as-built 5.4 nF decap plan, COB 1 uF on provider supply fingers).
Aggressor: the 11 D2H outputs (10 data + clock) at their own south sites; a falling edge pushes the load current into
die VSS at that site, a rising edge pulls it from die VDD. Victim: a quiet D2H / MISO output = die VSS (quiet low) or die
VDD (quiet high) at its site, against the COB ground plane. Edge: triangular current, peak/rise from the package-channel
host_ssn table (11 x 42 mA / 0.76 ns fast, 35 mA / 1.0 ns, 30 mA / 1.4 ns slow). Stagger: odd lanes +0.6 ns (0.4-0.8).
Known answer first: the synthesis on Z = j w 0.8 nH must give L dI/dt. Usage: sso.py rf|wired"""
import sys, json, numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/integration/m1-pdn')
import chipcfg as P2
chip = sys.argv[1]; sys.argv = [sys.argv[0], f'chip={chip}']
P2.apply(chip)
import model as M
SITES = json.load(open('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/provider-sites.json'))['sites']
rows = [l.split() for l in open(f'/home/ubuntu/svalbard/projects/programmable_transceiver_platform/integration/chips/{chip}/bond_map.txt') if l.strip() and not l.startswith('#')]
d2h = [r[0] for r in rows if r[2].startswith('D2H')]
d2h_order = sorted(d2h, key=lambda s: SITES[s]['bond_center_um'][0])
quiet = [r[0] for r in rows if r[2] in ('SPI_MISO', 'D2H[9]', 'D2H[0]', 'D2H_CLK')]
assert len(d2h) == 11, d2h
N, DT = 1024, 25e-12
F = np.fft.rfftfreq(N, DT)[1:]

def pulse(tr, ipk, t0):
    # sin^2 current pulse whose peak slope equals ipk/tr (the table's dI/dt), no corners (no Gibbs ringing)
    t = np.arange(N)*DT - t0; tw = tr*np.pi/2
    return np.where((t > 0) & (t < 2*tw), ipk*np.sin(np.pi*t/(2*tw))**2, 0.0)

def synth(Zf, i_t):
    I = np.fft.rfft(i_t); V = np.zeros_like(I); V[1:] = Zf*I[1:]
    return np.fft.irfft(V, N)

# known answer: 0.8 nH, 0.462 A in 0.76 ns -> 0.486 V
ka = np.abs(synth(1j*2*np.pi*F*0.8e-9, pulse(0.76e-9, 0.462, 5e-9))).max()
assert abs(ka-0.486) < 0.03, ka
# negative control: a 4x smaller dI/dt must give a 4x smaller answer
assert abs(np.abs(synth(1j*2*np.pi*F*0.8e-9, pulse(3.04e-9, 0.462, 5e-9))).max()-0.486/4) < 0.02

EDGES = {'fast 0.76 ns': (0.76e-9, 0.042), 'mid 1.0 ns': (1.0e-9, 0.035), 'slow 1.4 ns': (1.4e-9, 0.030)}
res = {'chip': chip, 'known_answer_V': round(float(ka), 3), 'south_vss_bonds': [r[0] for r in rows if r[1] == 'south' and r[2] == 'VSS'],
       'south_vdd_bonds': [r[0] for r in rows if r[1] == 'south' and r[2] == 'VDD'], 'cases': {}}
ALLB = list(M.BONDS)
VARIANTS = [('opt', 'plan', True), ('nom', 'plan', True), ('pess', 'plan', True),
            ('pess', 'plan', False),        # bound: VSS bonds on signal sites (trace + connector, not the COB plane) ignored
            ('pess', 'none', True)]         # control: no die decap
for corner, dc, xv in VARIANTS:
    p = P2.pset(corner)
    M.BONDS[:] = [b for b in ALLB if xv or not (b['net'] == 'VSS' and str(b.get('inst', '')).startswith('pad_xvss'))]
    n, info = M.build(p, decap=P2.plan() if dc == 'plan' else [])
    corner_tag = corner + ('' if dc == 'plan' else ' no-decap') + ('' if xv else ' no-xvss')
    nodes = {s: M.near(*SITES[s]['bond_center_um']) for s in set(d2h) | set(quiet)}
    cols = []
    for s in d2h_order:
        for net in (M.gn, M.vn):
            x = np.zeros(len(n.names), complex); x[n.idx[net(*nodes[s])]] = 1.0 if net is M.gn else -1.0; cols.append(x)
    R = np.stack(cols, axis=1)
    Zg = np.zeros((len(F), len(quiet), len(d2h_order)), complex); Zv = np.zeros_like(Zg)
    for a, f in enumerate(F):
        V = n.solve(2*np.pi*f, R)
        for q, s in enumerate(quiet):
            Zg[a, q] = V[n.idx[M.gn(*nodes[s])], 0::2]; Zv[a, q] = V[n.idx[M.vn(*nodes[s])], 1::2]
    for ename, (tr, ipk) in (EDGES.items() if dc == 'plan' and xv else [('fast 0.76 ns', EDGES['fast 0.76 ns']), ('slow 1.4 ns', EDGES['slow 1.4 ns'])]):
        for stag in (0, 1):
            worst = {}
            for kind, Z in (('quiet_low_vss', Zg), ('quiet_high_vdd', Zv)):
                vmax = 0
                for q in range(len(quiet)):
                    v = sum(synth(Z[:, q, k], pulse(tr, ipk, 5e-9+(0.6e-9 if stag and k % 2 else 0))) for k in range(len(d2h_order)))
                    vmax = max(vmax, float(np.abs(v).max()))
                worst[kind] = round(vmax*1e3)
            res['cases'][f'{corner_tag} {ename} {"stagger" if stag else "no stagger"}'] = worst
    print(corner_tag, len(M.BONDS), 'bonds', flush=True)
json.dump(res, open(f'sso_{chip}.json', 'w'), indent=1)
for k, v in res['cases'].items(): print(f'{chip:5s} {k:36s} quiet-low {v["quiet_low_vss"]:4d} mV  quiet-high {v["quiet_high_vdd"]:4d} mV')
