"""USB behaviour of the wirepad attachment with the stress-safe protection drawn in.

Model: the regenerated wired RX/USB layout (drop-in network with discharge, ATB
tap and v2 shunt; Magic device-level extraction, floating conductors anchored as
in the canonical screens). Controls are the attachment's active-high pad ports
driven directly (the receive_control_guard would produce the same levels).
Cases:
  fs   FS J then K at 60 ns: per leg 15 kohm host pull-down and 50 pF; VOH/VOL
       and 10-90 % edge times (USB 2.0 FS: VOH >= 2.8 V, VOL <= 0.3 V, 4-20 ns)
  ls   same drivers into 450 pF (LS needs 75-300 ns; no slew control exists)
  hs   HS_P switch with HS_PBIAS = VDD - 3.11 V (lifecycle bias) into a far-end
       45 ohm to ground, with and without the on-chip termination; reports the
       delivered current against 17.78 mA (17.78 mA x 22.5 ohm = 400 mV)
  handoff  PULLUP_P on, then at 40 ns pull-up off and termination on (2 ns
       break-before-make); host 15 kohm pull-down
  cap  all controls off, VDD 3.3 V: small-signal capacitance at 1 GHz on PAD_P
       with PAD_N AC-grounded, against the 2.7 pF wired allocation
The HS current source is the attachment's own PMOS (HS_PBIAS); the wired_tx
current cells are not part of this layout. Diagnostics, not USB compliance.
"""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import stress_safe_clamp as s
import stress_safe_family_sims as f

ENV = f.ENVELOPE
MIRROR_BIAS = False
WIREPAD_MODEL = None
HS_TRIM = 1.0


def deck(case, process, temp_c, vdd, work, name, canonical=False):
    f.DRAWN_SHUNT = True
    f.FAMILIES.update(f.FAMILIES_V3)
    if WIREPAD_MODEL is not None:
        f.FAMILIES_V3['wirepad'] = dict(model=WIREPAD_MODEL, lifecycle=f.PADS / 'generated/wired-receive-usb-lifecycle.spice')
        f.FAMILIES.update(f.FAMILIES_V3)
    if canonical:
        # Original (pre-stress-safe) published layout model, same fixture.
        f.FAMILIES['wirepad'] = dict(model=f.PADS / 'generated/wired-receive-usb-extracted-c.spice', lifecycle=None)
    model, cell, ports = f.model_text('wirepad')
    f.FAMILIES.update(f.FAMILIES_V3)
    d = f.header() + model + f'VSS VSS 0 0\nVDD VDD 0 {vdd}\nRATB ATB 0 10meg\n'
    on = {}
    if case in ('fs', 'ls'):
        on = {'FS_HIGH_P': f'PWL(0 {vdd} 60n {vdd} 60.1n 0)', 'FS_LOW_N': f'PWL(0 {vdd} 60n {vdd} 60.1n 0)',
              'FS_HIGH_N': f'PWL(0 0 60n 0 60.1n {vdd})', 'FS_LOW_P': f'PWL(0 0 60n 0 60.1n {vdd})'}
    elif case.startswith('hs'):
        on = {'HS_P': f'{vdd}'}
        if case in ('hs_term', 'hs_vsweep'):
            on['TERM_ENABLE'] = f'{vdd}'
    elif case == 'term':
        on = {'TERM_ENABLE': f'{vdd}'}
    elif case == 'handoff':
        on = {'PULLUP_P': f'PWL(0 {vdd} 40n {vdd} 40.1n 0)', 'TERM_ENABLE': f'PWL(0 0 42n 0 42.1n {vdd})'}
    for p in ports:
        if p in ('PAD_P', 'PAD_N', 'VSS', 'VDD', 'ATB_ESD_RAIL'):
            continue
        if p in ('RX_P', 'RX_N'):
            d += f'CCORE_{p} {p} 0 50f\nRCORE_{p} {p} 0 1g\n'; continue
        if p == 'HS_PBIAS' and case == 'hs_vsweep':
            d += 'VHSB HS_PBIAS 0 0\n'; continue
        if p == 'HS_PBIAS':
            if case.startswith('hs') and MIRROR_BIAS:
                # Bias-block mirror: replica diode PMOS (one 20/1 unit) carrying I_leg/14
                # from a trimmed current DAC (ideal here, nominal code).
                from circuits import Mos
                d += Mos('HSREF', ('HS_PBIAS', 'HS_PBIAS', 'VDD', 'VDD'), 'pfet_03v3', 20., 1.).spice() + '\n'
                d += f'IHSREF HS_PBIAS 0 {17.78e-3 / 14 * HS_TRIM:.6g}\n'
            else:
                d += f'VHS_PBIAS HS_PBIAS 0 {vdd - 3.11 if case.startswith("hs") else vdd}\n'
            continue
        val = on.get(p, '0')
        d += f'V{p} {p} 0 {val}\n'
    d += 'Xpad ' + ' '.join('ATB' if p == 'ATB_ESD_RAIL' else p for p in ports) + f' {cell}\n'
    if case in ('fs', 'ls', 'handoff'):
        c = '450p' if case == 'ls' else '50p'
        for leg in ('P', 'N'):
            d += f'RHOST_{leg} PAD_{leg} 0 15k\nCLOAD_{leg} PAD_{leg} 0 {c}\n'
        stop = 1200e-9 if case == 'ls' else 120e-9
        an = f'tran .02n {stop * 1e9:.0f}n'
        vec = 'v(PAD_P) v(PAD_N)'
    elif case == 'term':
        d += 'ITERM 0 PAD_P DC 8.9m\n'
        an, vec, stop = 'op', 'v(PAD_P) v(PAD_N)', None
    elif case == 'hs_vsweep':
        d += 'RFAR_P PAD_P 0 45\nRFAR_N PAD_N 0 45\n'
        an, vec, stop = 'dc VHSB 0 1.2 0.02', 'v(PAD_P)', None
    elif case.startswith('hs'):
        d += 'RFAR_P PAD_P 0 45\nRFAR_N PAD_N 0 45\n'
        an, vec, stop = 'tran .02n 40n', 'v(PAD_P) v(PAD_N)', 40e-9
    else:
        d = d.replace('PAD_P', 'PAD_P')  # no-op for clarity
        d += 'VACP PAD_P 0 DC 1.65 AC 1\nVACN PAD_N 0 DC 1.65\n'
        an, vec, stop = 'ac lin 1 1e9 1e9', 'i(VACP)', None
    d = s.corner(d, process, temp_c)
    d += s.control(work, name, an, vec)
    return d, stop


def run(case, process, temp_c, vdd, work, canonical=False):
    name = f'usb_{"orig_" if canonical else ""}{case}_{process}_{temp_c}_{vdd}'
    d, stop = deck(case, process, temp_c, vdd, work, name, canonical)
    x = np.atleast_2d(s.run(work, name, d, timeout_s=3600))
    r = dict(case=case, process=process, temp_c=temp_c, vdd_v=vdd, canonical_layout=canonical, op_fallback=f.op_fallback(work, name),
             deck_sha256=hashlib.sha256(d.encode()).hexdigest())
    if case in ('fs', 'ls'):
        t = x[:, 0]
        settle = (t > 0.8 * 60e-9) & (t < 60e-9)
        voh, vol = float(x[settle, 1].mean()), float(x[settle, 2].mean())
        after = t > 60e-9
        def edge(v, rising):
            lo, hi = min(voh, vol), max(voh, vol)
            a, b = lo + .1 * (hi - lo), lo + .9 * (hi - lo)
            tt, vv = t[after], v[after]
            if rising:
                i1 = np.argmax(vv >= a); i2 = np.argmax(vv >= b)
            else:
                i1 = np.argmax(vv <= b); i2 = np.argmax(vv <= a)
            return float(tt[i2] - tt[i1]) if i2 > i1 else None
        r.update(voh_v=voh, vol_v=vol, rise_s=edge(x[:, 2], True), fall_s=edge(x[:, 1], False),
                 final_p_v=float(x[-1, 1]), final_n_v=float(x[-1, 2]))
    elif case == 'hs_vsweep':
        vg, vp = x[:, 0], x[:, 1]
        def at(target):
            i = np.nonzero(vp <= target)[0]
            return float(vg[i[0]]) if len(i) else None
        r.update(gate_v=vg.tolist(), pad_mv=(vp * 1e3).tolist(), pad_mv_at_0v=float(vp[0] * 1e3),
                 gate_for_440mv=at(.44), gate_for_400mv=at(.40), gate_for_360mv=at(.36))
    elif case.startswith('hs'):
        late = x[:, 0] > 30e-9
        v = float(x[late, 1].mean())
        r.update(pad_p_v=v, far_current_a=v / 45., delivered_current_a=v / (22.5 if case == 'hs_term' else 45.),
                 target_current_a=17.78e-3, pad_n_v=float(x[late, 2].mean()))
    elif case == 'term':
        r.update(pad_v=float(x[0, 1]), resistance_ohm=float(x[0, 1]) / 8.9e-3)
    elif case == 'handoff':
        t = x[:, 0]
        r.update(pullup_level_v=float(x[(t > 30e-9) & (t < 40e-9), 1].mean()),
                 gap_min_v=float(x[(t > 40e-9) & (t < 42.1e-9), 1].min()),
                 terminated_level_v=float(x[t > 100e-9, 1].mean()),
                 min_v=float(x[t > 40e-9, 1].min()), max_v=float(x[t > 40e-9, 1].max()))
    else:
        y = complex(x[0, 1], x[0, 2])
        r.update(capacitance_f=float(abs(y.imag) / (2 * np.pi * 1e9)), conductance_s=float(abs(y.real)), limit_f=2.7e-12)
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--usbfix', action='store_true', help='USB-fixed wirepad layout + mirror-biased HS source')
    p.add_argument('--only', nargs='*', help='run only these per-corner cases (e.g. hs_vsweep)')
    a = p.parse_args()
    global MIRROR_BIAS, WIREPAD_MODEL
    if a.usbfix:
        MIRROR_BIAS = True
        WIREPAD_MODEL = f.PADS / 'generated/stress-safe-families/wired-receive-usb/physical.spice'
    work = a.output_dir.resolve()
    p_cases = ('fs', 'hs', 'hs_term') + (('term',) if a.usbfix else ())
    if a.only:
        p_cases = tuple(a.only)
    jobs = [(c, pr, t, v) for c in p_cases for pr, t, v in ENV]
    if not a.only:
      jobs += [('ls', 'typical', 27, 3.3), ('ls', 'ss', 22, 3.15), ('ls', 'ff', 32, 3.35),
             ('handoff', 'typical', 27, 3.3), ('handoff', 'ss', 22, 3.15), ('handoff', 'ff', 32, 3.35),
             ('cap', 'typical', 27, 3.3), ('cap', 'ss', 22, 3.3), ('cap', 'ff', 32, 3.3)]
      # Same fixture on the original (pre-stress-safe) layout, nominal point.
      jobs += [(c, 'typical', 27, 3.3, True) for c in ('fs', 'hs', 'hs_term', 'handoff', 'cap')]

    def go(j):
        try:
            return run(*j[:4], work, *j[4:])
        except Exception as e:
            return dict(job=list(map(str, j)), error=repr(e)[:300])
    with ThreadPoolExecutor(a.jobs) as pool:
        res = list(pool.map(go, jobs))
    m = WIREPAD_MODEL or f.FAMILIES_V3['wirepad']['model']
    a.report.write_text(json.dumps(dict(scope=__doc__.strip(), model=str(m), usbfix=a.usbfix, mirror_bias=MIRROR_BIAS,
                                        model_sha256=s.sha(m), results=res,
                                        source_sha256={n: s.sha(Path(__file__).with_name(n)) for n in ('stress_safe_usb.py', 'stress_safe_family_sims.py')}), indent=1) + '\n')


if __name__ == '__main__':
    main()
