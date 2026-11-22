#!/usr/bin/env python3
"""padc_ref.py <model.spice> <tag> [--ctest F]: pad_refpad small-signal pad C per leg (R+C model, wrapper tx_protected_pad, any ports).
Bench: AC 1 V on PAD_x at DC bias (VCM 1.65 V source on the VCM port, pad at 1.65 V DC), other pad AC-grounded at 1.65 V, VSS 0, DVDD (ring
supply, option A) 3.3 V, ESD_RAIL / ATB_ESD_RAIL (published) left to the model's own nodes through 1 Gohm. Y = I/V at the pad pin:
C = Im(Y)/w; also Z = 1/Y -> series R = Re(Z), series C = -1/(w Im(Z)). Frequencies 1 GHz (like for like with the USB rows) and 2.45 GHz
(external LO on pt_rf). tt 27 C and ss / ff 27 C. Known answer: --ctest F adds F farad from PAD_P to VSS (must read +F on P only).
Output bench/<tag>-padc.json. ONE ngspice run at a time."""
import sys, re, json, math
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_family_sims as f, stress_safe_clamp as s
from loading_audit import anchor_floating_conductors
HERE = Path(__file__).resolve().parent; W = HERE / 'benchrun'
model, tag = sys.argv[1], sys.argv[2]; ctest = float(sys.argv[sys.argv.index('--ctest') + 1]) if '--ctest' in sys.argv else 0.
text = re.sub(r'\n\+\s*', ' ', Path(model).read_text())
text = '\n'.join(l for l in text.splitlines() if not l.startswith('.lib '))
text = re.sub(r'#(?=[\s=)]|$)', '_h', text, flags=re.M)
body, _ = anchor_floating_conductors(text + '\n', 1e12)
wrap = next(l for l in body.splitlines() if l.startswith('.subckt tx_protected_pad ')).split()
ports = wrap[2:]
FR = (1e9, 2.45e9)
res = {}
for proc in ('typical', 'ss', 'ff'):
    for leg in 'PN':
        o = 'N' if leg == 'P' else 'P'
        d = f.header() + body + '\n'
        nodes = []
        for p in ports:
            if p == f'PAD_{leg}': nodes.append('PADX')
            elif p == f'PAD_{o}': nodes.append('PADO')
            elif p == 'VSS': nodes.append('0')
            elif p == 'DVDD': nodes.append('DV'); d += 'VDV DV 0 3.3\n'
            elif p == 'VCM': nodes.append('VCMN'); d += 'VVCM VCMN 0 1.65\n'
            else: nodes.append(p); d += f'R{p} {p} 0 1g\n'
        d += 'Xpad ' + ' '.join(nodes) + ' tx_protected_pad\n'
        d += 'VAC PADS 0 DC 1.65 AC 1\nVM PADS PADX 0\nVO PADO 0 1.65\n'
        if ctest and leg == 'P': d += f'CTEST PADX 0 {ctest}\n'
        d = s.corner(d, proc, 27)
        name = f'{tag}_{proc}_{leg}'
        d += s.control(W, name, 'ac lin 30 1e9 2.45e9\nlet yr=real(i(VM))\nlet yi=imag(i(VM))', 'yr yi')
        x = s.run(W, name, d, timeout_s=1800)
        if x.ndim == 1: raise SystemExit(f"unexpected output {x} see {W}/{name}.log")
        row = {}
        for fr in FR:
            k = int(np.argmin(np.abs(x[:, 0] - fr))); fr_ = x[k, 0]
            if abs(fr_ - fr) > 1e6: raise SystemExit(f'frequency {fr} not in the sweep')
            y = complex(x[k, 1], x[k, 2]); w = 2 * math.pi * fr_; z = 1 / y
            row[f'{fr_ / 1e9:g}GHz'] = dict(c_pf=round(y.imag / w * 1e12, 4), series_r_ohm=round(z.real, 3), series_c_pf=round(-1 / (w * z.imag) * 1e12, 4))
        res[f'{proc}_{leg}'] = row; print(tag, proc, leg, row, flush=True)
        for e in ('spice', 'dat', 'log'): (W / f'{name}.{e}').unlink(missing_ok=True)
(HERE / 'bench').mkdir(exist_ok=True)
(HERE / 'bench' / f'{tag}-padc.json').write_text(json.dumps(dict(tag=tag, model=str(Path(model).resolve()), model_sha256=s.sha(model), ctest_f=ctest, results=res), indent=1) + '\n')
