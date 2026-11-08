"""P3-10: can neighbouring debug pads share one stress-safe macro?

Shared candidate: pair A keeps the drawn macro (network + discharge + ATB +
v2.1 shunt, Magic-extracted). The neighbour B (another pair, or the single WMON
leg) keeps only its local steering diodes (4 x pd2nw PAD->rail, 4 x nd2ps
VSS->PAD per pad, the drawn junction geometry) and reaches A's isolated rail and
VSS through a rail bus and a return bus of resistance R each. Every leg of both
sites is attached. Stimulus: the selection pulse (+/-100 mA, 2 ns) into B's
pad, bare unpowered die, tt/27 C and ss/0 C. Reference: the same pulse into A's
own pad. The added peak (B - A) must fit the 0.105 V margin left at ss/0 C in
the retained-fixture worst case (5.895 V vs 6.0 V) for the share to be adopted.
R values: metal4 || metal5 bus, 211 um (WMON next to WTX_EXT_N) or 422 um
(BB_Q pair next to BB_I pair) long, 20/40/80 um wide (sheet 0.09 || 0.04 ohm/sq).
"""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import stress_safe_clamp as s
import stress_safe_family_sims as f

PAIR = f.PADS / 'generated/stress-safe-families/rf-pair/pad-extracted.spice'
SHEET = 1 / (1 / .09 + 1 / .04)


def model():
    from loading_audit import anchor_floating_conductors
    text = re.sub(r'\n\+\s*', ' ', PAIR.read_text())
    head = next(l for l in text.splitlines() if l.startswith('.subckt rf_protected_pad'))
    text = text.replace(head, head + ' ESD_RAIL', 1)          # expose the isolated rail
    body, _ = anchor_floating_conductors(text, 1e12)
    return body, head.split()[2:] + ['ESD_RAIL']


def deck(target, legs_b, r_bus, proc, temp, sign, work, name):
    body, ports = model()
    d = f.header() + body + 'VSS VSS 0 0\n'
    m = {'PAD_P': 'PA_P', 'PAD_N': 'PA_N', 'VSS': 'VSS', 'ATB_ESD_RAIL': 'ATB', 'ESD_RAIL': 'RAIL_A'}
    d += 'XA ' + ' '.join(m[p] for p in ports) + ' rf_protected_pad\nRATB ATB 0 10meg\n'
    d += f'RBUS RAIL_A RAIL_B {r_bus}\nRRET VSS VSS_B {r_bus}\n'
    for leg in legs_b:
        for k in range(4):
            d += f'DUP_{leg}{k} PB_{leg} RAIL_B diode_pd2nw_06v0 pj=51.8u area=22.5p\nDDN_{leg}{k} VSS_B PB_{leg} diode_nd2ps_06v0 pj=51.8u area=22.5p\n'
    for node in ['PA_P', 'PA_N'] + [f'PB_{l}' for l in legs_b]:
        d += f'RPEER_{node} {node} 0 1meg\nCPEER_{node} {node} 0 1p\n'
    a, b = ('VSS', target) if sign == 'pos' else (target, 'VSS')
    d += f'IINJECT {a} {b} PULSE(0 .1 100n .1n .1n 2n 20u)\n'
    d = s.corner(d, proc, temp)
    return d + s.control(work, name, 'tran .02n 140n', f'v({target}) v(RAIL_A) v(RAIL_B)')


def run(job, work):
    target, legs_b, length, width, proc, temp, sign = job
    r_bus = 1e-3 if length == 0 else SHEET * length / width
    name = f'share_{target}_{len(legs_b)}_{length}_{width}_{proc}_{temp}_{sign}'
    d = deck(target, legs_b, r_bus, proc, temp, sign, work, name)
    x = s.run(work, name, d, timeout_s=1800)
    return dict(target=target, b_legs=legs_b, bus_length_um=length, bus_width_um=width, bus_ohm_each=r_bus,
                process=proc, temp_c=temp, sign=sign, peak_v=float(x[:, 1].max()), min_v=float(x[:, 1].min()),
                rail_a_max_v=float(x[:, 2].max()), rail_b_max_v=float(x[:, 3].max()), op_fallback=f.op_fallback(work, name),
                deck_sha256=hashlib.sha256(d.encode()).hexdigest())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=1)
    a = p.parse_args()
    work = a.output_dir.resolve()
    jobs = []
    for proc, temp in (('ss', 0), ('typical', 27)):
        jobs.append(('PA_P', ['P', 'N'], 0, 1, proc, temp, 'pos'))                    # reference: own pad, B pair attached
        for length, legs in ((422, ['P', 'N']), (211, ['P'])):
            for width in (20, 40, 80):
                jobs.append((f'PB_P', legs, length, width, proc, temp, 'pos'))
        jobs.append(('PB_P', ['P', 'N'], 422, 40, proc, temp, 'neg'))
    with ThreadPoolExecutor(a.jobs) as pool:
        res = list(pool.map(lambda j: run(j, work), jobs))
    ref = {(r['process'], r['temp_c']): r['peak_v'] for r in res if r['target'] == 'PA_P'}
    for r in res:
        if r['sign'] == 'pos':
            r['added_v'] = r['peak_v'] - ref[(r['process'], r['temp_c'])]
            r['fits_0p105_margin'] = r['added_v'] <= .105
    a.report.write_text(json.dumps(dict(scope=__doc__.strip(), pair_model=dict(path=str(PAIR), sha256=s.sha(PAIR)), results=res,
                                        source_sha256={'shared_protection_check.py': s.sha(Path(__file__))}), indent=1) + '\n')
    for r in res:
        print(r['target'], len(r['b_legs']), r['bus_length_um'], r['bus_width_um'], r['process'], r['sign'], round(r['peak_v'], 3), round(r.get('added_v', 0), 3))


if __name__ == '__main__':
    main()
