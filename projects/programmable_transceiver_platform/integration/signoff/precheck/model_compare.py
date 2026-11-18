#!/usr/bin/env python3
"""Device-model comparison, PDK f6eeac7 (project) vs 792ef67 (shuttle precheck), ngspice 47 (project sim image).
  model_compare.py <old ngspice model dir> <new ngspice model dir> <work dir>
Per model set and corner (tt/ss/ff, 27 C): Id and gm of nfet_03v3 / pfet_03v3 (W/L 10/0.28, |Vgs| 1.2, |Vds| 1.65),
nfet_06v0 (10/0.7) / pfet_06v0 (10/0.55) (|Vgs| 1.5, |Vds| 3.0), R of ppolyf_u_1k 1u x 10u, its capacitance to the
substrate terminal (2u x 20u, 1 MHz), C of cap_mim_2f0_m4m5_noshield 10u x 10u (1 MHz).
Writes <work dir>/model_compare.json and prints a table. One ngspice run per (set, corner), 1 cpu."""
import json, math, os, re, subprocess, sys
IMG = 'svalbard/transceiver-pad-sim:ngspice47-corrected'; NG = '/opt/pad-ngspice47/bin/ngspice'
CORN = {'tt': ('typical', 'res_typical', 'mimcap_typical'), 'ss': ('ss', 'res_ss', 'mimcap_ss'), 'ff': ('ff', 'res_ff', 'mimcap_ff')}
DECK = """* model compare {c}
.include /m/design.ngspice
.lib /m/sm141064.ngspice {f}
.lib /m/sm141064.ngspice {r}
.lib /m/sm141064.ngspice {m}
.temp 27
vsw sw 0 0
en3 g3 0 vol='1.2+v(sw)'
vd3 d3 0 1.65
xn3 d3 g3 0 0 nfet_03v3 w=10u l=0.28u
ep3 gp3 0 vol='-1.2-v(sw)'
vdp3 dp3 0 -1.65
xp3 dp3 gp3 0 0 pfet_03v3 w=10u l=0.28u
en6 g6 0 vol='1.5+v(sw)'
vd6 d6 0 3.0
xn6 d6 g6 0 0 nfet_06v0 w=10u l=0.7u
ep6 gp6 0 vol='-1.5-v(sw)'
vdp6 dp6 0 -3.0
xp6 dp6 gp6 0 0 pfet_06v0 w=10u l=0.55u
vr r1 0 1
xr r1 0 0 ppolyf_u_1k r_width=1u r_length=10u
vac a 0 dc 0 ac 1
xr2 a a sub ppolyf_u_1k r_width=2u r_length=20u
vsub sub 0 0
xc a m2 cap_mim_2f0_m4m5_noshield c_width=10u c_length=10u
vm m2 0 0
.control
dc vsw -0.005 0.005 0.005
print i(vd3) i(vdp3) i(vd6) i(vdp6) i(vr)
ac lin 1 1meg 1meg
print imag(i(vsub)) imag(i(vm))
.endc
.end
"""
def run(mdir, corner, wd):
    f, r, m = CORN[corner]
    open(os.path.join(wd, 'd.spice'), 'w').write(DECK.format(c=corner, f=f, r=r, m=m))
    p = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '2g', '-e', 'OMP_NUM_THREADS=1',
                        '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp', '-v', f'{os.path.abspath(mdir)}:/m:ro',
                        '-v', f'{os.path.abspath(wd)}:/w', '-w', '/w', '--entrypoint', NG, IMG, '-b', 'd.spice'],
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    open(os.path.join(wd, 'last.log'), 'w').write(out)
    col = {}; hdr = None
    for l in out.splitlines():
        t = l.split()
        if t[:2] == ['Index', 'v-sweep']: hdr = t[2:]
        elif hdr and re.match(r'^\d+$', t[0] if t else ''):
            for h, v in zip(hdr, t[2:]): col.setdefault(h, []).append(float(v))
    acv = {m.group(1): float(m.group(2)) for m in re.finditer(r'imag\(i\((\w+)\)\) = (\S+)', out)}
    assert all(len(v) == 3 for v in col.values()) and len(col) == 5 and len(acv) == 2, out[-2000:]
    dc = [[col[f'i({n})'][j] for n in ('vd3', 'vdp3', 'vd6', 'vdp6', 'vr')] for j in range(3)]
    ac = [[acv['vsub'], acv['vm']]]
    res = {}
    for i, n in enumerate(['nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0']):
        res[n + '.id_uA'] = abs(dc[1][i]) * 1e6
        res[n + '.gm_uS'] = abs(dc[2][i] - dc[0][i]) / 0.01 * 1e6
    res['ppolyf_u_1k.R_ohm'] = 1 / abs(dc[1][4])
    w = 2 * math.pi * 1e6
    res['ppolyf_u_1k.Csub_fF'] = abs(ac[0][0]) / w * 1e15
    res['cap_mim_2f0.C_fF'] = abs(ac[0][1]) / w * 1e15
    res['_warnings'] = sorted(set(l.strip()[:120] for l in out.splitlines() if re.search(r'warning|unrecognized|unknown param', l, re.I)))
    return res
if __name__ == '__main__':
    old, new, wd = sys.argv[1:4]; os.makedirs(wd, exist_ok=True)
    R = {c: {'f6eeac7': run(old, c, wd), '792ef67': run(new, c, wd)} for c in CORN}
    json.dump(R, open(os.path.join(wd, 'model_compare.json'), 'w'), indent=1)
    print('| quantity | corner | f6eeac7 | 792ef67 | delta % |\n|---|---|---|---|---|')
    for k in [k for k in R['tt']['f6eeac7'] if not k.startswith('_')]:
        for c in CORN:
            a, b = R[c]['f6eeac7'][k], R[c]['792ef67'][k]
            print(f'| {k} | {c} | {a:.6g} | {b:.6g} | {((b - a) / a * 100 if a else float("nan")):+.4f} |')
    for c in CORN:
        for s in R[c]: print(c, s, 'warnings:', R[c][s]['_warnings'])
