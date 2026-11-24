"""cbench.py <model> <tag> [legs]: (2026-11-24: .ac card + run; the old control-only ac wrote the op point) per-leg pad C at 2.4 GHz (and 0.1 GHz) = Im(I)/(w V) with the other leg AC-grounded; pad DC 0 V,
DVDD 3.3 V, VSS 0 (all diodes at operating bias; junction C from the PDK models). Control: --ctest adds 100 fF on PAD_P."""
import sys, json, numpy as np
sys.argv += [] ; import esd3 as E
VPAD = float(sys.argv[sys.argv.index('--vpad') + 1]) if '--vpad' in sys.argv else 0.
model, tag = sys.argv[1:3]; legs = (sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else 'P,N').split(',')
body, cell, ports, inner = E.load_model(model)
out = {}
for L in legs:
    d = E.f.header() + f'.lib {E.f.PDK}/sm141064.ngspice moscap_typical\n' + body + '\n'
    top = {'PAD_P': 'PP', 'PAD_N': 'PN', 'VSS': '0', 'DVDD': 'DV', 'ATB_ESD_RAIL': 'ATB'}
    d += 'VDV DV 0 3.3\nRATB ATB 0 10meg\n'
    for q in ('P', 'N'):
        if f'PAD_{q}' in ports: d += f'V{q} P{q} 0 dc {VPAD}' + (' ac 1' if q == L else '') + '\n'
    if '--ctest' in sys.argv: d += 'CTEST PP 0 100f\n'
    d += 'Xpad ' + ' '.join(top[p] for p in ports) + f' {cell}\n'
    d += f'.ac lin 24 0.1e9 2.4e9\n.control\nrun\nsetplot ac1\nwrdata {E.HERE}/esdrun/{tag}_{L}.dat i(V{L})\n.endc\n.end\n'
    x = E.s.run(E.HERE / 'esdrun', f'{tag}_{L}', d, timeout_s=600)
    c = lambda r: -float(r[2]) / (2 * np.pi * float(r[0]))     # columns: f, Re(i), Im(i)
    out[L] = dict(c_pf_0p1ghz=round(c(x[0]) * 1e12, 4), c_pf_2p4ghz=round(c(x[-1]) * 1e12, 4))
    (E.HERE / 'esdrun' / f'{tag}_{L}.dat').unlink(missing_ok=True)
json.dump(dict(model=model, vpad=VPAD, legs=out, ctest='--ctest' in sys.argv), open(E.HERE / 'esd' / f'c_{tag}.json', 'w'), indent=1); print(tag, out)
