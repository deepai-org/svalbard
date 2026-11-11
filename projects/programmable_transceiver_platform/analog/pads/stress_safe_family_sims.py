"""Per-family safe and functional runs for the stress-safe foundation.

Models: each family's regenerated extracted pad (canonical layout + stress-safe
drop-in network with clamp-gate discharge and ATB tap) plus the extracted
3 x 12000 um shunt macro instanced between ESD_RAIL and VSS. For the wired
families the shunt is NOT routed in their layouts (it does not fit); for the RF
pair it is (stress_safe_rf_layout.py) and this model omits only its straps.

Safe runs (reset controls; every disabled branch attached):
  pulse  +/-100 mA, 0.1 ns edges, 2 ns flat into PAD_P or PAD_N, chip unpowered
         (VDD held at 0 V through 1 ohm), bare die (1 Mohm / 1 pF peers)
  ramp   VDD 0 -> 3.63 V in 10 ns and in 1 us, peers at 0 V
  peer   chip unpowered, both pads driven to 3.63 V through 50 ohm
Functional runs: the family's published lifecycle fixture with the new model,
at tt/ss/ff x 22/32 C x VDD 3.15/3.35 V plus tt/27 C/3.3 V (and a baseline with
the canonical model at nominal). RF: 50 ohm AC transfer at 1 and 2.45 GHz.
All results are compact-model diagnostics, not ESD or functional qualification.
"""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import stress_safe_clamp as s

PADS = Path(__file__).resolve().parent
SCR = s.SCRATCH
PDK = SCR / 'transceiver-pad-pdk/ngspice'
SHUNT = PADS / 'generated/stress-safe-families/shunt-v2/rail_shunt_flat.spice'
# v3: drawn layouts that already contain the v2 shunt (protection_network_shunt v2 macro).
FAMILIES_V3 = {
    'refpad': dict(model=SCR / 'pad-ss3-reference_clock/pad/physical.spice', lifecycle=PADS / 'generated/reference-clock-lifecycle.spice'),
    'txpad': dict(model=SCR / 'pad-ss3-wired_transmit/pad/physical.spice', lifecycle=PADS / 'generated/wired-transmit-lifecycle.spice'),
    'wirepad': dict(model=SCR / 'pad-ss3-wired_receive_usb/pad/physical.spice', lifecycle=PADS / 'generated/wired-receive-usb-lifecycle.spice'),
    'rfpad': dict(model=SCR / 'pad-ss3-rf/pad/pad-extracted.spice', lifecycle=None),
}
# v4 (current): macro v2.1 layouts; wirepad with the USB fixes. Published copies of the extracted models.
FAMILIES_V4 = {
    'refpad': dict(model=PADS / 'generated/stress-safe-families/reference/physical.spice', lifecycle=PADS / 'generated/reference-clock-lifecycle.spice'),
    'txpad': dict(model=PADS / 'generated/stress-safe-families/wired-transmit/physical.spice', lifecycle=PADS / 'generated/wired-transmit-lifecycle.spice'),
    'wirepad': dict(model=PADS / 'generated/stress-safe-families/wired-receive-usb/physical.spice', lifecycle=PADS / 'generated/wired-receive-usb-lifecycle.spice'),
    'rfpad': dict(model=PADS / 'generated/stress-safe-families/rf-pair/pad-extracted.spice', lifecycle=None),
}
FAMILIES = {
    'refpad': dict(model=SCR / 'pad-ss-ref/pad/physical.spice', lifecycle=PADS / 'generated/reference-clock-lifecycle.spice',
                   canonical=PADS / 'generated/reference-clock-extracted-c.spice'),
    'txpad': dict(model=SCR / 'pad-ss-wired_transmit/pad/physical.spice', lifecycle=PADS / 'generated/wired-transmit-lifecycle.spice',
                  canonical=PADS / 'generated/wired-transmit-extracted-c.spice'),
    'wirepad': dict(model=SCR / 'pad-ss-wired_receive_usb/pad/physical.spice', lifecycle=PADS / 'generated/wired-receive-usb-lifecycle.spice',
                    canonical=PADS / 'generated/wired-receive-usb-extracted-c.spice'),
    'rfpad': dict(model=SCR / 'pad-ss-rf/pad/pad-extracted.spice', lifecycle=None, canonical=None),
}
DRAWN_SHUNT = False
HIGH_DEFAULT = ('CASCODE', 'DETECT_PBIAS', 'HS_PBIAS')
MOS = ('nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0')
CORE_SIDE = ('RX_P', 'RX_N', 'VCM')     # loaded/driven core-side ports, observed directly (PD13)


def header():
    return (f'.include {PDK}/design.ngspice\n.lib {PDK}/sm141064.ngspice typical\n.lib {PDK}/sm141064.ngspice res_typical\n'
            f'.lib {PDK}/sm141064.ngspice diode_typical\n.lib {PDK}/sm141064.ngspice mimcap_typical\n.temp 27\n')


def model_text(family):
    """Pad model with the extracted shunt instanced inside the physical subckt."""
    text = re.sub(r'\n\+\s*', ' ', FAMILIES[family]['model'].read_text())
    text = '\n'.join(l for l in text.splitlines() if not l.startswith('.lib '))
    # PD13: extracted node names end in '#' (not addressable in ngspice vectors); rename so every
    # internal MOS terminal (RC-clamp trigger chain, clamp gate, GC shunt gate) can be observed.
    text = re.sub(r'#(?=[\s=)]|$)', '_h', text, flags=re.M)
    lines = text.splitlines()
    inner = next(i for i, l in enumerate(lines) if l.startswith('.subckt ') and 'ESD_RAIL' in l.split()[2:])
    end = next(i for i in range(inner, len(lines)) if lines[i].startswith('.ends'))
    drawn = DRAWN_SHUNT
    if not drawn:
        lines.insert(end, 'XRAILSHUNT ESD_RAIL VSS rail_shunt_flat')
    wrapper = next(l for l in lines if l.startswith('.subckt ') and 'ESD_RAIL' not in l.split()[2:])
    # Same declared numerical DC path for capacitor-only extracted conductors
    # as the canonical retained-network screens (loading_audit, 1 Tohm).
    from loading_audit import anchor_floating_conductors
    body, _ = anchor_floating_conductors('\n'.join(lines) + '\n' + ('' if drawn else SHUNT.read_text()) + '\n', 1e12)
    return body, wrapper.split()[1], wrapper.split()[2:]


def op_fallback(work, name):
    log = (work / f'{name}.log').read_text()
    return 'Transient op started' in log or 'gmin stepping failed' in log.lower()


def safe_deck(family, case, process, temp_c, work, name):
    model, cell, ports = model_text(family)
    d = header() + model
    d += 'VSS VSS 0 0\n'
    if case.startswith('ramp'):
        rise = '10n' if case == 'ramp_fast' else '1u'
        d += f'VDDSRC VDDS 0 PWL(0 0 {rise} 3.63 3u 3.63)\nRVDD VDDS VDD 1\n'
    else:
        d += 'VDDSRC VDDS 0 0\nRVDD VDDS VDD 1\n'
    d += 'CVDD VDD 0 100n\n'
    peer = 3.63 if case == 'peer' else 0.
    for leg in ('P', 'N'):
        # Pulses: bare die, no board peer (1 Mohm, 1 pF). Ramps/peer: 50 ohm peer.
        rp, cb = ('1meg', '1p') if case.startswith(('pulse', 'hbm')) else ('50', '10p')
        d += f'VPEER_{leg} PEER_{leg} 0 {peer}\nRPEER_{leg} PEER_{leg} BRD_{leg} {rp}\nCBRD_{leg} BRD_{leg} 0 {cb}\nLB_{leg} BRD_{leg} PAD_{leg} 1n\n'
    known = ['PAD_P', 'PAD_N', 'VDD', 'ATB']
    for p in ports:
        if p in ('PAD_P', 'PAD_N', 'VSS', 'VDD', 'ATB_ESD_RAIL'):
            continue
        if p in ('RX_P', 'RX_N'):
            d += f'RCORE_{p} {p} 0 1g\nCCORE_{p} {p} 0 50f\n'; known.append(p); continue
        if p == 'VCM':
            d += 'BVCM VCM 0 V=0.5*V(VDD)\n'; known.append(p); continue
        d += f'V{p} {p} ' + ('VDD 0' if p in HIGH_DEFAULT else '0 0') + '\n'
    d += 'RATB ATB 0 10meg\nCATB ATB 0 10p\n'
    d += 'Xpad ' + ' '.join('ATB' if p == 'ATB_ESD_RAIL' else p for p in ports) + f' {cell}\n'
    if case.startswith('pulse'):
        _, leg, sign = case.split('_')
        a, b = ('VSS', f'PAD_{leg}') if sign == 'pos' else (f'PAD_{leg}', 'VSS')
        d += f'IINJECT {a} {b} PULSE(0 .1 100n .1n .1n 2n 20u)\n'
        analysis, stop = 'tran .02n 140n', 140e-9
    elif case.startswith('hbm'):
        # PD13: HBM-like 2 kV (1.33 A peak, 2 ns rise, 150 ns decay; same waveform as esd04.hbm),
        # unpowered bare die. Compact-model diagnostic, not HBM qualification.
        _, leg, sign = case.split('_')
        a, b = ('VSS', f'PAD_{leg}') if sign == 'pos' else (f'PAD_{leg}', 'VSS')
        d += f'IINJECT {a} {b} EXP(0 1.3333 5n 2n 15n 150n)\n'
        analysis, stop = 'tran .05n 600n', 600e-9
    elif case == 'ramp_slow':
        analysis, stop = 'tran 1n 3u', 3e-6
    else:
        analysis, stop = 'tran .05n 400n', 400e-9
    vec = ['v(PAD_P)', 'v(PAD_N)', 'v(VDD)', 'v(ATB)', 'v(xpad.esd_rail)', 'i(VDDSRC)', 'i(VPEER_P)', 'i(VPEER_N)']
    vec += [f'v(xpad.{inst}.{n})' for inst, n in internal_mos_nodes(model)]
    vec += [f'v({q})' for q in CORE_SIDE if q in ports]       # core-side ports (after the internal nodes)
    d = s.corner(d, process, temp_c)
    d += s.control(work, name, analysis, ' '.join(vec))
    return d, ports, stop


def internal_mos_nodes(deck_model):
    """(instance, node) for every internal (non-port) MOS terminal of the inner ESD_RAIL subckt."""
    lines = deck_model.splitlines()
    head = next(l for l in lines if l.startswith('.subckt ') and 'ESD_RAIL' in l.split()[2:])
    inner, iports = head.split()[1], set(head.split()[2:])
    inst = next(l.split()[0] for l in lines if l.startswith('X') and l.split()[-1] == inner).lower()
    out, inside = [], False
    for l in lines:
        if l == head:
            inside = True; continue
        if inside and l.startswith('.ends'):
            break
        f = l.split()
        if inside and len(f) > 5 and f[0].startswith('X') and f[5] in MOS:
            for n in f[1:5]:
                if n not in iports and n not in ('0',) and (inst, n) not in out:
                    out.append((inst, n))
    return out


def exposure(deck_model, ports, x, mask):
    """Gate-terminal screen on devices whose terminals are all observed nodes (PD13: internal MOS
    terminals are saved too, so the RC-clamp trigger chain and the shunt gates are observed)."""
    limits, _ = s.gate_limits()
    known = {'VSS': np.zeros(len(x)), '0': np.zeros(len(x)), 'PAD_P': x[:, 1], 'PAD_N': x[:, 2], 'VDD': x[:, 3],
             'ATB_ESD_RAIL': x[:, 4], 'ESD_RAIL': x[:, 5]}
    for p in ports:
        if p not in known and p not in ('RX_P', 'RX_N', 'VCM'):
            known[p] = known['VDD'] if p in HIGH_DEFAULT else np.zeros(len(x))
    nodes = internal_mos_nodes(deck_model)
    for k, (_, n) in enumerate(nodes):
        known.setdefault(n, x[:, 9 + k])
    for j, q in enumerate([q for q in CORE_SIDE if q in ports]):
        if x.shape[1] > 9 + len(nodes) + j:
            known[q] = x[:, 9 + len(nodes) + j]
    inside, worst, exceeded, seen, partial = False, [], 0, 0, 0
    for line in deck_model.splitlines():
        if line.startswith('.subckt ') and 'ESD_RAIL' in line.split()[2:]:
            inside = True; continue
        if inside and line.startswith('.ends'):
            break
        f = line.split()
        if inside and len(f) > 5 and f[0].startswith('X') and f[5] in MOS:
            nodes = dict(zip('DGSB', f[1:5]))
            vals = {}
            for pair in ('GS', 'GD', 'GB'):
                a, b = (nodes[c] for c in pair)
                if a in known and b in known:
                    vals[pair] = float(np.max(np.abs(known[a] - known[b])[mask]))
            if len(vals) < 3:
                partial += 1
            if vals:
                seen += 1
                v = max(vals.values()); bad = v > limits[f[5]]
                exceeded += bad
                worst.append((v / limits[f[5]], f[0], f[5], round(v, 3)))
    worst.sort(reverse=True)
    return dict(observed_mos=seen, partially_observed_mos=partial, exceeding=int(exceeded), worst=[dict(device=w[1], model=w[2], gate_v=w[3]) for w in worst[:4]])


def run_safe(family, case, process, temp_c, work):
    name = f'{family}_{case}_{process}_{temp_c}'
    deck, ports, stop = safe_deck(family, case, process, temp_c, work, name)
    x = s.run(work, name, deck, timeout_s=1800)
    if not np.isfinite(x).all() or x[-1, 0] < stop * .999:
        return dict(family=family, case=case, process=process, temp_c=temp_c, complete=False)
    mask = x[:, 0] >= 0
    late = x[:, 0] >= stop * .9
    model, _, _ = model_text(family)
    r = dict(family=family, case=case, process=process, temp_c=temp_c, complete=True,
             pad_p_range_v=[float(x[:, 1].min()), float(x[:, 1].max())], pad_n_range_v=[float(x[:, 2].min()), float(x[:, 2].max())],
             rail_max_v=float(x[:, 5].max()), pad_peak_abs_v=float(np.abs(x[:, 1:3]).max()),
             pad_within_6v0_screen=bool(np.abs(x[:, 1:3]).max() <= 6.0), vdd_max_v=float(x[:, 3].max()), atb_range_v=[float(x[:, 4].min()), float(x[:, 4].max())],
             supply_current_end_a=float(-x[late, 6].mean()), peer_current_end_a=[float(-x[late, 7].mean()), float(-x[late, 8].mean())],
             vdd_backfeed_peak_a=float(max(x[:, 6].max(), 0.)),
             exposure=exposure(model, ports, x, mask),
             op_fallback=op_fallback(work, name),
             deck_sha256=hashlib.sha256(deck.encode()).hexdigest(), waveform_sha256=s.sha(work / f'{name}.dat'))
    return r


def lifecycle_deck(family, process, temp_c, vdd, work, name, baseline=False):
    text = re.sub(r'\n\+\s*', ' ', FAMILIES[family]['lifecycle'].read_text())
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith('.subckt tx_protected_pad'))
    inner = next(i for i in range(start + 1, len(lines)) if l_is_inner(lines[i]))
    end = next(i for i in range(inner, len(lines)) if lines[i].startswith('.ends'))
    if baseline:
        block = lines[start:end + 1]
        xpad_extra = ''
    else:
        model, _, ports = model_text(family)
        block = model.splitlines()
        xpad_extra = ' ATB'
    out = lines[:start] + block + lines[end + 1:]
    for i, l in enumerate(out):
        if l.startswith('Xpad ') and l.endswith(' tx_protected_pad'):
            # PD28: candidate models with extra trim ports (TERM_TRIM<k>, wirepad usbfix6v2) get them tied to
            # VSS (trim code 0) in the published fixture; models without them are unchanged.
            trims = '' if baseline else ''.join(' VSS' for p in ports if p.startswith('TERM_TRIM'))
            out[i] = l[:-len(' tx_protected_pad')] + trims + xpad_extra + ' tx_protected_pad'
        if l.split()[:2] == ['VDD', 'VDD'] and 'PWL(' in l:
            out[i] = re.sub(r'(?<=[ (])3\.3(?=[ )])', f'{vdd}', l)
    d = '\n'.join(out) + '\n'
    if not baseline:
        d = d.replace('.control', 'RATB ATB 0 10meg\nCATB ATB 0 10p\n.control', 1)
    ctrl = d[d.index('.control'):]
    tran = re.search(r'(?m)^tran .*$', ctrl)[0]
    vec = 'v(PAD_P) v(PAD_N) v(VDD)' + ('' if baseline else ' v(ATB) v(xpad.esd_rail)')
    d = d[:d.index('.control')] + s.control(work, name, tran, vec)
    return s.corner(d, process, temp_c)


def l_is_inner(line):
    return line.startswith('.subckt combined_flat ')


def run_lifecycle(family, process, temp_c, vdd, work, baseline=False):
    name = f'{family}_life_{"base_" if baseline else ""}{process}_{temp_c}_{vdd}'
    deck = lifecycle_deck(family, process, temp_c, vdd, work, name, baseline)
    x = s.run(work, name, deck, timeout_s=3600)
    stop = float(re.search(r'tran \S+ (\S+)', deck)[1].rstrip('n')) * 1e-9
    complete = bool(np.isfinite(x).all() and x[-1, 0] >= stop * .999)
    tail = x[:, 0] >= x[-1, 0] * .85
    diff = x[tail, 1] - x[tail, 2]
    r = dict(family=family, process=process, temp_c=temp_c, vdd_v=vdd, baseline=baseline, complete=complete,
             final_window_s=[float(x[tail, 0][0]), float(x[-1, 0])],
             final_diff_pp_v=float(diff.max() - diff.min()), final_pad_p_mean_v=float(x[tail, 1].mean()),
             final_pad_n_mean_v=float(x[tail, 2].mean()), pad_max_v=float(x[:, 1:3].max()), pad_min_v=float(x[:, 1:3].min()),
             op_fallback=op_fallback(work, name),
             deck_sha256=hashlib.sha256(deck.encode()).hexdigest(), waveform_sha256=s.sha(work / f'{name}.dat'))
    if not baseline:
        r.update(rail_final_v=float(x[tail, 5].mean()), atb_final_v=float(x[tail, 4].mean()),
                 atb_rail_ratio=float(x[tail, 4].mean() / max(x[tail, 5].mean(), 1e-9)))
    return r


def run_rf_ac(process, temp_c, bias_v, work):
    name = f'rfpad_ac_{process}_{temp_c}_{bias_v}'
    model, cell, ports = model_text('rfpad')
    d = header() + model + 'VSS VSS 0 0\nRATB ATB 0 10meg\n'
    for leg, sgn in (('P', 1), ('N', -1)):
        d += f'VS_{leg} S_{leg} 0 DC {bias_v} AC {0.5 * sgn}\nRS_{leg} S_{leg} PAD_{leg} 50\nRL_{leg} PAD_{leg} 0 50\n'
    d += 'Xpad ' + ' '.join('ATB' if p == 'ATB_ESD_RAIL' else p for p in ports) + f' {cell}\n'
    d = s.corner(d, process, temp_c)
    d += s.control(work, name, 'ac lin 30 1e9 2.45e9', 'v(PAD_P) v(PAD_N) i(VS_P)')
    x = np.atleast_2d(s.run(work, name, d, timeout_s=600))
    rows = [x[0], x[-1]]
    return dict(process=process, temp_c=temp_c, bias_v=bias_v, frequency_hz=[float(r[0]) for r in rows],
                diff_transfer_db=[float(20 * np.log10(abs(complex(r[1], r[2]) - complex(r[3], r[4])))) for r in rows],
                ideal_50ohm_divider_db=float(20 * np.log10(0.5)), deck_sha256=hashlib.sha256(d.encode()).hexdigest())


HBM = [(c, p, t) for c in ('hbm_P_pos', 'hbm_N_neg') for p, t in (('typical', 27), ('ss', 0), ('ff', 85))]
ENVELOPE = [('typical', 27, 3.3)] + [(p, t, v) for p in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
SAFE = [(c, p, t) for c in ('pulse_P_pos', 'pulse_P_neg', 'pulse_N_pos', 'pulse_N_neg') for p, t in (('typical', 27), ('ss', 0))] + \
       [('ramp_fast', 'typical', 27), ('ramp_slow', 'typical', 27), ('peer', 'typical', 27), ('peer', 'ff', 85)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--families', nargs='*', default=list(FAMILIES))
    p.add_argument('--parts', nargs='*', default=['safe', 'function'])
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--drawn', action='store_true', help='v3 drawn layouts already containing the shunt')
    p.add_argument('--drawn-v4', action='store_true', help='v4: macro v2.1 layouts, USB-fixed wirepad')
    p.add_argument('--models', nargs='*', default=[], metavar='FAMILY=PATH',
                   help='override the model of a family (e.g. candidate layouts before publication)')
    a = p.parse_args()
    global DRAWN_SHUNT
    if a.drawn or a.drawn_v4:
        DRAWN_SHUNT = True
        FAMILIES.update(FAMILIES_V4 if a.drawn_v4 else FAMILIES_V3)
    for item in a.models:
        fam, path = item.split('=', 1)
        FAMILIES[fam] = dict(FAMILIES[fam], model=Path(path).resolve())
    work = a.output_dir.resolve()
    jobs = []
    for f in a.families:
        if 'safe' in a.parts:
            jobs += [('safe', f, c, pr, t) for c, pr, t in SAFE]
        if 'hbm' in a.parts:
            jobs += [('safe', f, c, pr, t) for c, pr, t in HBM]
        if 'function' in a.parts:
            if f == 'rfpad':
                jobs += [('rfac', pr, t, b) for pr, t, _ in ENVELOPE for b in (0.9, 1.65)]
            else:
                jobs += [('life', f, pr, t, v, False) for pr, t, v in ENVELOPE] + [('life', f, 'typical', 27, 3.3, True)]

    jobs.sort(key=lambda j: {'safe': 0, 'rfac': 1, 'life': 2}[j[0]])

    def go(j):
        try:
            if j[0] == 'safe':
                return run_safe(j[1], j[2], j[3], j[4], work)
            if j[0] == 'rfac':
                return dict(family='rfpad', kind='ac', **run_rf_ac(j[1], j[2], j[3], work))
            return dict(kind='lifecycle', **run_lifecycle(j[1], j[2], j[3], j[4], work, j[5]))
        except Exception as e:  # recorded, never hidden
            return dict(job=list(map(str, j)), error=repr(e)[:400])
    with ThreadPoolExecutor(a.jobs) as pool:
        results = list(pool.map(go, jobs))
    a.report.write_text(json.dumps(dict(
        image_id=s.SIM_IMAGE, models={f: dict(path=str(FAMILIES[f]['model']), sha256=s.sha(FAMILIES[f]['model'])) for f in a.families},
        shunt_model=('drawn in the family layouts (extracted with the layout)' if DRAWN_SHUNT else dict(path=str(SHUNT), sha256=s.sha(SHUNT))), results=results,
        source_sha256={n: s.sha(PADS / n) for n in ('stress_safe_family_sims.py', 'stress_safe_clamp.py')}), indent=1) + '\n')


if __name__ == '__main__':
    main()
