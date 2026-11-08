"""Debug-site protection: loading/isolation checks with the drawn stress-safe pads.

Pads: the regenerated stress-safe pair (BB_I, BB_Q, AUX_CLK, WCLK_IN, WTX_EXT;
same physical protection as rfpad/refpad) and the single-leg cell (WMON; the
same cell as ESD_TEST), both Magic-extracted with the v2.1 shunt.
Debug cells (owned elsewhere, used read-only):
  bb_tap  analog/rf_rx/generated/bb_tap.ext.spice (pt_bb_tap)   BB_I/BB_Q, WMON
  diff_clk_rx  analog/timing/generated/diff_clk_rx.ext.spice     AUX_CLK, WCLK_IN, WTX_EXT
Checks (tt/27, ss/22, ff/32; VDD 3.3 V):
  tap_load    bb_tap disabled (obs_en=inj_en=0, island on): capacitance added to the
              tapped nodes in_p (observed) and inj_p (injected) by the pad + protection,
              at 10 MHz / 100 MHz / 1 GHz (difference with and without the pad)
  tap_iso     bb_tap disabled: 1 V at the pad through 50 ohm, tapped nodes held by
              1 kohm to their DC level: |V(in_p)|, |V(inj_p)| in dB
  rx_load     diff_clk_rx enabled and disabled: differential input capacitance at the
              pad seen from a 50 ohm/leg source at 742.5 MHz and 2.45 GHz
  rx_iso      diff_clk_rx disabled: 0.5 V differential at 2.45 GHz on the pads;
              |OUTP-OUTN| (transient)
Pad ESD for these sites is the stress-safe macro (pulse/peer/ramp evidence: the
rfpad runs in family-sims.json use the same physical pair; single-leg pulses are
run here as single_pulse).
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

ANALOG = f.PADS.parent
BB = ANALOG / 'rf_rx/generated/bb_tap.ext.spice'
RX = ANALOG / 'timing/generated/diff_clk_rx.ext.spice'
PADS = {'pair': f.PADS / 'generated/stress-safe-families/rf-pair/pad-extracted.spice',
        'single': f.PADS / 'generated/stress-safe-families/single-leg/pad-extracted.spice'}
CORNERS = [('typical', 27), ('ss', 22), ('ff', 32)]


def pad_model(kind):
    from loading_audit import anchor_floating_conductors
    text = re.sub(r'\n\+\s*', ' ', PADS[kind].read_text())
    body, _ = anchor_floating_conductors(text, 1e12)
    ports = next(l.split()[2:] for l in body.splitlines() if l.startswith('.subckt rf_protected_pad'))
    return body, ports


def pad_inst(kind, ports):
    return 'XPADCELL ' + ' '.join({'ATB_ESD_RAIL': 'ATB'}.get(p, p) for p in ports) + ' rf_protected_pad\nRATB ATB 0 10meg\n'


def head(proc, temp):
    return f.header() + 'VSS VSS 0 0\nVDD VDD 0 3.3\n'


def tap_deck(case, kind, with_pad, freq_node, proc, temp, work, name):
    d = head(proc, temp) + BB.read_text() + '\n'
    if with_pad:
        model, ports = pad_model(kind); d += model + pad_inst(kind, ports)
    pad_n = 'PAD_N' if kind == 'pair' else 'PADN_FLOAT'
    d += f'XTAP IN_P IN_N PAD_P {pad_n} INJ_P INJ_N IBIAS 0 0 0 ATBN VDD VSS pt_bb_tap\nIBIAS VDD IBIAS 10u\n'
    if kind == 'single':
        d += 'RINN IN_N 0 1\nRPADNF PADN_FLOAT 0 1g\n'
    else:
        d += 'RINN IN_N INNB 1k\nVINN INNB 0 0.9\n'
    if case == 'tap_load':
        for node in ('IN_P', 'INJ_P'):
            if node == freq_node:
                d += f'VAC_{node} {node} 0 DC 0.9 AC 1\n'
            else:
                d += f'R_{node} {node} {node}B 1k\nV_{node} {node}B 0 0.9\n'
        d += 'RINJN INJ_N INJNB 1k\nVINJN INJNB 0 0.9\n'
        if not with_pad:
            d += 'RPADP PAD_P 0 1g\n' + ('RPADN PAD_N 0 1g\n' if kind == 'pair' else '')
        an, vec = 'ac dec 1 1e7 1e9', f'i(VAC_{freq_node})'
    else:
        d += 'VSRC SRC 0 DC 0 AC 1\nRSRC SRC PAD_P 50\n'
        if kind == 'pair':
            d += 'RPN PAD_N 0 50\n'
        for node in ('IN_P', 'INJ_P'):
            d += f'R_{node} {node} {node}B 1k\nV_{node} {node}B 0 0.9\n'
        d += 'RINJN INJ_N INJNB 1k\nVINJN INJNB 0 0.9\n'
        an, vec = 'ac dec 1 1e7 1e9', 'v(PAD_P) v(IN_P) v(INJ_P)'
    d = s.corner(d, proc, temp)
    return d + s.control(work, name, an, vec)


def rx_deck(case, en, freq, proc, temp, work, name):
    model, ports = pad_model('pair')
    d = head(proc, temp) + RX.read_text() + '\n' + model + pad_inst('pair', ports)
    d += f'XRX PAD_P PAD_N {"VDD" if en else "0"} 0 OUTP OUTN PRESENT ATBD VDD VSS pt_diff_clk_rx\nCOP OUTP 0 20f\nCON OUTN 0 20f\n'
    if case == 'rx_load':
        d += 'VACP SP 0 DC 1.65 AC 0.5\nVACN SN 0 DC 1.65 AC -0.5\nRSP SP PAD_P 50\nRSN SN PAD_N 50\nCCP PAD_P 0 1f\n'
        an, vec = f'ac lin 1 {freq} {freq}', 'v(PAD_P) v(PAD_N) i(VACP)'
    else:
        d += f'VSP SP 0 SIN(1.65 0.25 {freq})\nVSN SN 0 SIN(1.65 -0.25 {freq})\nRSP SP PAD_P 50\nRSN SN PAD_N 50\n'
        an, vec = 'tran 5p 20n', 'v(PAD_P) v(PAD_N) v(OUTP) v(OUTN)'
    d = s.corner(d, proc, temp)
    return d + s.control(work, name, an, vec)


def run(job, work):
    kind = job[0]
    if kind in ('tap_load', 'tap_iso'):
        _, padkind, with_pad, node, proc, temp = job
        name = f'{kind}_{padkind}_{"pad" if with_pad else "nopad"}_{node}_{proc}_{temp}'
        d = tap_deck(kind, padkind, with_pad, node, proc, temp, work, name)
    else:
        _, en, freq, proc, temp = job
        name = f'{kind}_{"en" if en else "dis"}_{freq:.4g}_{proc}_{temp}'
        d = rx_deck(kind, en, freq, proc, temp, work, name)
    x = np.atleast_2d(s.run(work, name, d, timeout_s=3600))
    r = dict(job=[str(v) for v in job], op_fallback=f.op_fallback(work, name), deck_sha256=hashlib.sha256(d.encode()).hexdigest())
    if kind == 'tap_load':
        r['capacitance_f'] = {f'{row[0]:.3g}': float(abs(row[2]) / (2 * np.pi * row[0])) for row in x}
    elif kind == 'tap_iso':
        r['isolation_db'] = {f'{row[0]:.3g}': dict(in_p=float(20 * np.log10(abs(complex(row[3], row[4])) / abs(complex(row[1], row[2])))),
                                                   inj_p=float(20 * np.log10(abs(complex(row[5], row[6])) / abs(complex(row[1], row[2])))))
                             for row in x}
    elif kind == 'rx_load':
        vp, vn = complex(x[0, 1], x[0, 2]), complex(x[0, 3], x[0, 4])
        ip = complex(x[0, 5], x[0, 6])
        # Differential: source 1 V diff through 2 x 50 ohm; Zin_diff = Vdiff / I
        z = (vp - vn) / -ip
        r.update(zin_diff_ohm=[z.real, z.imag], cdiff_f=float(-1 / (2 * np.pi * float(x[0, 0]) * z.imag)) if z.imag < 0 else None,
                 vdiff_over_source=float(abs(vp - vn)))
    else:
        late = x[:, 0] > 10e-9
        r.update(out_diff_pp_v=float(np.ptp(x[late, 3] - x[late, 4])), pad_diff_pp_v=float(np.ptp(x[late, 1] - x[late, 2])))
    return r


def single_pulse(proc, temp, sign, work):
    """Single-leg cell (WMON, ESD_TEST): +/-100 mA 2 ns on PAD_P, unpowered."""
    model, ports = pad_model('single')
    name = f'single_pulse_{sign}_{proc}_{temp}'
    d = f.header() + model + 'VSS VSS 0 0\nRPEER PAD_P 0 1meg\nCB PAD_P 0 1p\n' + pad_inst('single', ports)
    a, b = ('VSS', 'PAD_P') if sign == 'pos' else ('PAD_P', 'VSS')
    d += f'IINJECT {a} {b} PULSE(0 .1 100n .1n .1n 2n 20u)\n'
    d = s.corner(d, proc, temp) + s.control(work, name, 'tran .02n 140n', 'v(PAD_P) v(xpadcell.esd_rail)')
    x = s.run(work, name, d, timeout_s=1800)
    return dict(job=['single_pulse', sign, proc, str(temp)], pad_max_v=float(x[:, 1].max()), pad_min_v=float(x[:, 1].min()),
                rail_max_v=float(x[:, 2].max()), op_fallback=f.op_fallback(work, name), deck_sha256=hashlib.sha256(d.encode()).hexdigest())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=3)
    a = p.parse_args()
    work = a.output_dir.resolve()
    jobs = []
    for pr, t in CORNERS:
        for padkind in ('pair', 'single'):
            for node in ('IN_P', 'INJ_P'):
                jobs += [('tap_load', padkind, True, node, pr, t), ('tap_load', padkind, False, node, pr, t)]
            jobs.append(('tap_iso', padkind, True, 'IN_P', pr, t))
        for en in (True, False):
            for fr in (742.5e6, 2.45e9):
                jobs.append(('rx_load', en, fr, pr, t))
        jobs.append(('rx_iso', False, 2.45e9, pr, t))
    pulses = [(pr, t, sg) for pr, t in (('typical', 27), ('ss', 0)) for sg in ('pos', 'neg')]

    def go(j):
        try:
            return run(j, work) if j[0] != 'single_pulse' else single_pulse(*j[1:], work)
        except Exception as e:
            return dict(job=[str(v) for v in j], error=repr(e)[:300])
    with ThreadPoolExecutor(a.jobs) as pool:
        res = list(pool.map(go, jobs + [('single_pulse',) + p for p in pulses]))
    a.report.write_text(json.dumps(dict(scope=__doc__.strip(), pads={k: dict(path=str(v), sha256=s.sha(v)) for k, v in PADS.items()},
                                        cells={'bb_tap': dict(path=str(BB), sha256=s.sha(BB)), 'diff_clk_rx': dict(path=str(RX), sha256=s.sha(RX))},
                                        results=res, source_sha256={'stress_safe_debug.py': s.sha(Path(__file__))}), indent=1) + '\n')


if __name__ == '__main__':
    main()
