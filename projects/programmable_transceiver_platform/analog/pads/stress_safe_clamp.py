"""Stress-first comparison of isolated-rail protection variants.

Every variant reuses the exact retained RX/USB long-hold fixture recorded in
`rail-supervisor-screen.json` (extracted pad, all attachments, board peers,
100 kohm gate-discharge release fix) and adds only the named rail devices.
The 100 mA / 2 ns diagnostic pulse, observation windows and gate screens are
unchanged from `rail_supervisor.clamp_release_pulse_screen`.

Selection rule (project decision): prefer the variant that keeps observed pad
terminal stress under the PDK DC screens, then accept the normal-signal swing
and loading cost. Compact-model pulse response is not ESD qualification.
"""
import argparse
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from circuits import Mos
from design import PROJECT

SIM_IMAGE = 'svalbard/transceiver-pad-sim:ngspice47-corrected'
NGSPICE = '/opt/pad-ngspice47/bin/ngspice'
SCRATCH = PROJECT.parents[1] / 'scratch'
BASE_DECK = 'clamp_long_hold_discharge.spice'
BASE_DECK_SHA256 = 'c2f1b725a5e34cd1ff4aa63ec4d08e0624686a8f03a7e35b1278bdaf611c8d22'
GATE = 'a_42245_162628#'
PULSE = 'IINJECT VSS PAD_P PULSE(0 .1 1000n .1n .1n 2n 20u)\n'
NODES = ['PAD_P', 'PAD_N', 'RX_P', 'RX_N', 'xpad.ESD_RAIL', f'xpad.xphysical.{GATE}']
FINGER_UM = 50.
LENGTH_UM = .7

# name -> (series stages, total width per stage in um[, primary diode multiplier]);
# None is the released baseline. A diode multiplier k adds k-1 schematic copies of
# every pad-to-rail and VSS-to-pad primary diode (same junction geometry).
VARIANTS = {
    'released_baseline': None,
    'diode2_only': (0, 0., 2),
    'stack2_w1000': (2, 1000.),
    'stack2_w1500': (2, 1500.),
    'stack2_w2000': (2, 2000.),
    'stack2_w4000': (2, 4000.),
    'stack3_w3000': (3, 3000.),
    'stack3_w6000': (3, 6000.),
    'stack3_w9000': (3, 9000.),
    'stack3_w12000': (3, 12000.),
    'stack3_w6000_d2': (3, 6000., 2),
    'stack3_w4000_d2': (3, 4000., 2),
    'stack2_w2000_d2': (2, 2000., 2),
    # Device-level Magic extraction of the generated 3 x 12000 um macro.
    'stack3_w12000_extracted': ('extracted', 'generated/stress-safe-families/shunt-v2/rail_shunt_flat.spice'),
}
PRIMARY_DIODE = re.compile(r'^(D\d+) (PAD_[PN] ESD_RAIL diode_pd2nw_06v0|VSS PAD_[PN] diode_nd2ps_06v0) (.*)$')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shunt_lines(stages, width_um, model='nfet_06v0'):
    """Diode-connected series NMOS stack from ESD_RAIL to a probed return."""
    if stages == 0:
        return []
    fingers = int(round(width_um / FINGER_UM))
    if fingers * FINGER_UM != width_um or stages < 1:
        raise ValueError('Shunt width must be whole 50 um fingers')
    lines, node = [], 'ESD_RAIL'
    for stage in range(stages):
        end = 'SHUNT_RETURN' if stage == stages - 1 else f'SHUNT_MID_{stage}'
        for finger in range(fingers):
            lines.append(Mos(f'RAIL_SHUNT_{stage}_{finger}', (node, node, end, 'VSS'), model,
                             FINGER_UM, LENGTH_UM).spice())
        node = end
    lines.append('VSHUNTPROBE SHUNT_RETURN VSS 0')
    return lines


def diode_copies(base, multiplier):
    """Extra parallel copies of the extracted primary pad diodes."""
    if multiplier == 1:
        return []
    inside, lines = False, []
    for line in base.splitlines():
        if line.startswith('.subckt combined_flat '):
            inside = True
        elif line.startswith('.ends'):
            inside = False
        m = PRIMARY_DIODE.match(line) if inside else None
        if m:
            lines += [f'{m[1]}_COPY{k} {m[2]} {m[3]}' for k in range(1, multiplier)]
    if len(lines) != 16 * (multiplier - 1):
        raise ValueError('Expected sixteen extracted primary diodes')
    return lines


def variant_lines(base, spec):
    if spec is None:
        return []
    if spec[0] == 'extracted':
        return ['XRAILSHUNT ESD_RAIL SHUNT_RETURN rail_shunt_flat', 'VSHUNTPROBE SHUNT_RETURN VSS 0']
    stages, width, multiplier = (*spec, 1)[:3]
    lines = shunt_lines(stages, width) + diode_copies(base, multiplier)
    if stages == 0:
        lines.append('VSHUNTPROBE SHUNT_UNUSED VSS 0')
    return lines


def insert(base, lines):
    out, inside, done = [], False, False
    for line in base.splitlines():
        if line.startswith('.subckt combined_flat '):
            inside = True
        if inside and line.startswith('.ends'):
            out.extend(lines)
            inside, done = False, True
        out.append(line)
    if not done:
        raise ValueError('combined_flat not found')
    return '\n'.join(out) + '\n'


def corner(deck, process, temp_c):
    if process == 'typical':
        return deck.replace('.temp 27\n', f'.temp {temp_c}\n')
    table = {'ss': ('ss', 'res_ss', 'diode_ss', 'mimcap_ss'), 'ff': ('ff', 'res_ff', 'diode_ff', 'mimcap_ff')}[process]
    for old, new in zip(('typical', 'res_typical', 'diode_typical', 'mimcap_typical'), table):
        deck = re.sub(rf'(sm141064\.ngspice) {old}\n', rf'\1 {new}\n', deck)
    return deck.replace('.temp 27\n', f'.temp {temp_c}\n')


def run(work, name, deck, timeout_s=900, attempts=3):
    work.mkdir(parents=True, exist_ok=True)
    (work / '.spiceinit').write_text('set ngbehavior=hs\n')
    spice, dat, log = work / f'{name}.spice', work / f'{name}.dat', work / f'{name}.log'
    # Resume: reuse a waveform only when the exact deck produced it. The data
    # file is deleted before each run and written by wrdata only after the
    # analysis completes (deterministic simulator; waveform hashes are recorded).
    if spice.exists() and spice.read_text() == deck and dat.exists() and dat.stat().st_size > 0:
        return np.loadtxt(dat, skiprows=1)
    for attempt in range(attempts):
        try:
            return _run_once(work, name, deck, timeout_s)
        except subprocess.CalledProcessError:
            if attempt == attempts - 1:
                raise


def _run_once(work, name, deck, timeout_s):
    (work / f'{name}.spice').write_text(deck)
    (work / f'{name}.dat').unlink(missing_ok=True)
    command = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g', '-e', 'OMP_NUM_THREADS=1',
               '--user', '1000:1000', '--entrypoint', NGSPICE,
               '--mount', f'type=bind,src={SCRATCH},dst={SCRATCH}', '-w', str(work), SIM_IMAGE,
               '-b', str(work / f'{name}.spice')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
    (work / f'{name}.log').write_text(result.stdout + result.stderr + f'\nEXIT {result.returncode}\n')
    result.check_returncode()
    return np.loadtxt(work / f'{name}.dat', skiprows=1)


def control(work, name, analysis, vectors):
    return ('.control\nset wr_singlescale\nset wr_vecnames\n' + analysis +
            f'\nwrdata {work}/{name}.dat ' + vectors + '\nquit\n.endc\n.end\n')


def gate_limits():
    spec = PROJECT / 'spec/schematic-implementation.json'
    policy = json.loads(spec.read_text())['io_pad_first_pass']['primary_protection']['core_boundary_policy']
    return policy['gate_voltage_screen']['max_abs_gate_terminal_v'], sha(spec)


def exposure(deck, x, limits):
    """Same lower-bound terminal audit as rail_supervisor.pulse_terminal_exposure."""
    def value(token):
        m = re.fullmatch(r'([+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?)([numk]?)', token)
        if not m:
            raise ValueError('Unsupported fixture numeric token: ' + token)
        return float(m[1]) * {'': 1., 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3}[m[2]]
    known = {'0': np.zeros(len(x))}
    for i, node in enumerate(['PAD_P', 'PAD_N', 'RX_P', 'RX_N', 'ESD_RAIL', GATE], 1):
        known[node] = x[:, i]
    sources, devices, inside = [], [], False
    for line in deck.splitlines():
        if line.startswith('.subckt combined_flat '):
            inside = True
        elif line.startswith('.ends'):
            inside = False
        f = line.split()
        if inside and len(f) > 5 and f[0].startswith('X') and f[5] in ('nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0'):
            devices.append(f)
        if line.startswith('V') and not inside:
            if 'PWL(' in line:
                pts = line.split('PWL(', 1)[1].split(')', 1)[0].split()
                sources.append((f[1], f[2], np.interp(x[:, 0], [value(v) for v in pts[::2]], [value(v) for v in pts[1::2]])))
            elif len(f) == 4:
                sources.append((f[1], f[2], value(f[3])))
    for _ in range(len(sources)):
        changed = False
        for a, b, v in sources:
            if a not in known and b in known:
                known[a] = known[b] + v; changed = True
            elif b not in known and a in known:
                known[b] = known[a] - v; changed = True
        if not changed:
            break
    known['VDD'] = known['PAD_VDD']
    mask = (x[:, 0] >= 990e-9) & (x[:, 0] <= 1499e-9)
    records, exceeded, full, by_model = [], 0, 0, {}
    for f in devices:
        nodes = dict(zip('DGSB', f[1:5])); pairs = {}
        for pair in ('GS', 'GD', 'GB', 'DS', 'DB', 'SB'):
            a, b = (nodes[c] for c in pair)
            if a in known and b in known:
                pairs[pair] = float(np.max(np.abs((known[a] - known[b])[mask])))
        failed = any(pairs.get(p, 0) > limits[f[5]] for p in ('GS', 'GD', 'GB'))
        exceeded += failed; full += len(pairs) == 6
        if failed:
            by_model[f[5]] = by_model.get(f[5], 0) + 1
        if pairs:
            records.append(dict(device=f[0], model=f[5], nodes=nodes, gate_screen_v=limits[f[5]],
                                worst_gate_terminal_v=max(pairs.get(p, 0) for p in ('GS', 'GD', 'GB')),
                                gate_screen_exceeded=failed))
    records.sort(key=lambda r: r['worst_gate_terminal_v'] / r['gate_screen_v'], reverse=True)
    return dict(observed_mos_exceeding_gate_screen=int(exceeded), exceeding_by_model=by_model,
                mos_count=len(devices), fully_observed_mos_count=int(full),
                partly_observed_mos_count=len(records) - int(full), unobserved_mos_count=len(devices) - len(records),
                worst_ratio_to_screen=[dict(device=r['device'], model=r['model'], gate_v=round(r['worst_gate_terminal_v'], 4),
                                            screen_v=r['gate_screen_v']) for r in records[:6]])


def pulse_variant(work, base, name, spec, process='typical', temp_c=27):
    lines = variant_lines(base, spec)
    deck = corner(insert(base, lines) if lines else base, process, temp_c) + PULSE
    if spec is not None and spec[0] == 'extracted':
        deck += (Path(__file__).resolve().parent / spec[1]).read_text()
    probe = ' i(v.xpad.xphysical.vshuntprobe)' if lines else ''
    tag = f'{name}_{process}_{temp_c}'
    deck += control(work, tag, 'tran .05n 1500n', ' '.join(f'v({n})' for n in NODES) + probe)
    x = run(work, tag, deck)
    if not np.isfinite(x).all() or x[-1, 0] < 1499.9e-9:
        raise ValueError(f'Incomplete pulse {tag}')
    win = {}
    for label, a, b in [('active', 80, 99), ('before', 990, 999), ('pulse', 1000, 1002.2), ('recovery', 1450, 1499)]:
        y = x[(x[:, 0] >= a * 1e-9) & (x[:, 0] <= b * 1e-9)]
        win[label] = dict(pad_p_min_v=float(y[:, 1].min()), pad_p_max_v=float(y[:, 1].max()),
                          rail_max_v=float(y[:, 5].max()), clamp_gate_max_v=float(y[:, 6].max()),
                          rx_p_max_abs_v=float(np.abs(y[:, 3]).max()),
                          shunt_mean_current_a=float(y[:, 7].mean()) if lines else 0.,
                          shunt_peak_current_a=float(y[:, 7].max()) if lines else 0.)
    peer_thevenin_v, peer_thevenin_ohm = 3.3 * 15000 / 16500, 1500 * 15000 / 16500
    for label in ('active', 'before', 'recovery'):
        v = (win[label]['pad_p_min_v'] + win[label]['pad_p_max_v']) / 2
        win[label]['peer_loading_current_a'] = (peer_thevenin_v - v) / peer_thevenin_ohm
    limits, spec_sha = gate_limits()
    return dict(variant=name, process=process, temp_c=temp_c,
                shunt=None if spec is None else dict(extracted_netlist=spec[1], extracted_sha256=sha(Path(__file__).resolve().parent / spec[1])) if spec[0] == 'extracted' else dict(stages=spec[0], width_per_stage_um=spec[1], finger_um=FINGER_UM,
                                                     length_um=LENGTH_UM, model='nfet_06v0', connection='diode-connected series stack ESD_RAIL->VSS',
                                                     primary_diode_multiplier=(*spec, 1)[2]),
                windows=win, exposure=exposure(deck, x, limits), gate_screen_spec_sha256=spec_sha,
                deck_sha256=hashlib.sha256(deck.encode()).hexdigest(),
                waveform_sha256=sha(work / f'{tag}.dat'))


def shunt_dc(work, spec, process, temp_c):
    """Static I-V of the shunt stack alone, rail swept 0..6 V."""
    pdk = SCRATCH / 'transceiver-pad-pdk/ngspice'
    stages, width = spec[:2]
    name = f'dc_s{stages}_w{int(width)}_{process}_{temp_c}'
    lib = {'typical': ('typical', 'diode_typical'), 'ss': ('ss', 'diode_ss'), 'ff': ('ff', 'diode_ff')}[process]
    deck = (f'shunt dc\n.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice {lib[0]}\n'
            f'.lib {pdk}/sm141064.ngspice {lib[1]}\n.temp {temp_c}\nVSS VSS 0 0\nVRAIL ESD_RAIL 0 0\n' +
            '\n'.join(shunt_lines(stages, width)) + '\n' +
            control(work, name, 'dc VRAIL 0 6 0.01', 'i(VSHUNTPROBE)'))
    x = run(work, name, deck, timeout_s=300)
    v, i = x[:, 0], x[:, 1]

    def onset(level):
        above = np.nonzero(i >= level)[0]
        return float(v[above[0]]) if len(above) else None
    return dict(process=process, temp_c=temp_c, rail_v_at_current_a={'1e-06': onset(1e-6), '1e-05': onset(1e-5),
                '0.0001': onset(1e-4), '0.001': onset(1e-3), '0.1': onset(.1)},
                current_a_at_rail_v={str(r): float(np.interp(r, v, i)) for r in (1.2, 1.5, 1.8, 2.0, 2.4, 2.7, 3.0)},
                deck_sha256=hashlib.sha256(deck.encode()).hexdigest())


def pad_loading(work, spec, process, temp_c):
    """DC current drawn from one driven pad through its primary up-diodes.

    Includes the released 4000 um main clamp (gate at VSS) and the shunt stack.
    The second pad of the pair is left floating; the RC trigger is not modelled.
    """
    pdk = SCRATCH / 'transceiver-pad-pdk/ngspice'
    stages, width = (spec or (0, 0.))[:2]
    multiplier = (*(spec or (0, 0.)), 1)[2]
    name = f'load_s{stages}_w{int(width)}_d{multiplier}_{process}_{temp_c}'
    lib = {'typical': ('typical', 'diode_typical'), 'ss': ('ss', 'diode_ss'), 'ff': ('ff', 'diode_ff')}[process]
    lines = [f'DUP{k} PAD ESD_RAIL diode_pd2nw_06v0 pj=51.8u area=22.5p' for k in range(4 * multiplier)]
    lines += [f'DDN{k} VSS PAD diode_nd2ps_06v0 pj=51.8u area=22.5p' for k in range(4 * multiplier)]
    lines += [Mos(f'MAINCLAMP{k}', ('ESD_RAIL', 'VSS', 'VSS', 'VSS'), 'nfet_06v0', FINGER_UM, LENGTH_UM).spice() for k in range(80)]
    lines += shunt_lines(stages, width) if stages else ['VSHUNTPROBE SHUNT_UNUSED VSS 0']
    deck = (f'pad loading\n.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice {lib[0]}\n'
            f'.lib {pdk}/sm141064.ngspice {lib[1]}\n.temp {temp_c}\nVSS VSS 0 0\nVPAD PAD 0 0\n' +
            '\n'.join(lines) + '\n' + control(work, name, 'dc VPAD 0 3.63 0.01', 'i(VPAD) v(ESD_RAIL)'))
    x = run(work, name, deck, timeout_s=300)
    v, i = x[:, 0], -x[:, 1]
    return dict(process=process, temp_c=temp_c, stages=stages, width_per_stage_um=width, primary_diode_multiplier=multiplier,
                pad_current_a_at_pad_v={str(p): float(np.interp(p, v, i)) for p in (1.65, 2.5, 2.8, 3.0, 3.15, 3.3, 3.35, 3.63)},
                rail_v_at_pad_v={str(p): float(np.interp(p, v, x[:, 3] if x.shape[1] > 3 else x[:, 2])) for p in (3.0, 3.3, 3.63)},
                pad_v_at_current_a={str(c): (float(v[np.nonzero(i >= c)[0][0]]) if (i >= c).any() else None) for c in (1e-6, 1e-5, 1e-4, 1e-3)},
                deck_sha256=hashlib.sha256(deck.encode()).hexdigest())


def diode_capacitance(work, multiplier, pad_v, rail_v=3.3, process='typical', temp_c=27):
    """Small-signal 1 GHz capacitance of one pad's primary diodes to AC ground.

    The isolated rail is held as an AC ground: the upper bound for diode loading.
    Rail-side additions (the shunt stack) therefore add no pad capacitance here.
    """
    pdk = SCRATCH / 'transceiver-pad-pdk/ngspice'
    name = f'cap_d{multiplier}_{pad_v}_{process}_{temp_c}'
    lib = {'typical': 'diode_typical', 'ss': 'diode_ss', 'ff': 'diode_ff'}[process]
    lines = []
    for k in range(4 * multiplier):
        lines += [f'DUP{k} PAD ESD_RAIL diode_pd2nw_06v0 pj=51.8u area=22.5p',
                  f'DDN{k} VSS PAD diode_nd2ps_06v0 pj=51.8u area=22.5p']
    deck = (f'pad diode capacitance\n.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice {lib}\n.temp {temp_c}\n'
            f'VSS VSS 0 0\nVRAIL ESD_RAIL 0 {rail_v}\nVPAD PAD 0 DC {pad_v} AC 1\n' + '\n'.join(lines) + '\n' +
            control(work, name, 'ac lin 1 1e9 1e9', 'imag(i(VPAD))'))
    x = run(work, name, deck, timeout_s=120)
    return float(abs(np.atleast_2d(x)[0, -1]) / (2 * np.pi * 1e9))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture-dir', type=Path, default=SCRATCH / 'pad-supervised-receive')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--variants', nargs='*', default=list(VARIANTS))
    parser.add_argument('--corners', nargs='*', default=['typical:27'])
    parser.add_argument('--dc', nargs='*', default=[])
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--capacitance', action='store_true')
    parser.add_argument('--loading', nargs='*', default=[])
    args = parser.parse_args()
    source = args.fixture_dir.resolve() / BASE_DECK
    if sha(source) != BASE_DECK_SHA256:
        raise ValueError('Retained long-hold fixture differs from the recorded release candidate')
    base = source.read_text().split('.control')[0]
    work = args.output_dir.resolve()
    jobs = [(n, *c.split(':')) for n in args.variants for c in args.corners]
    with ThreadPoolExecutor(args.jobs) as pool:
        pulses = list(pool.map(lambda j: pulse_variant(work, base, j[0], VARIANTS[j[0]], j[1], int(j[2])), jobs))
        dcs = []
        for item in args.dc:
            name, c = item.split('@')
            dcs += [(name, p, int(t)) for p, t in (x.split(':') for x in c.split(','))]
        dc = list(pool.map(lambda j: dict(variant=j[0], **shunt_dc(work, VARIANTS[j[0]], j[1], j[2])), dcs))
        loads = []
        if args.loading:
            jobs2 = []
            for item in args.loading:
                name, c = item.split('@')
                jobs2 += [(name, p, int(tt)) for p, tt in (x.split(':') for x in c.split(','))]
            loads = list(pool.map(lambda j: dict(variant=j[0], **pad_loading(work, VARIANTS[j[0]], j[1], j[2])), jobs2))
        caps = []
        if args.capacitance:
            cases = [(m, v) for m in (1, 2) for v in (0.5, 1.65, 3.0)]
            caps = [dict(primary_diode_multiplier=m, pad_v=v, rail_v=3.3, frequency_hz=1e9, capacitance_f=c)
                    for (m, v), c in zip(cases, pool.map(lambda j: diode_capacitance(work, *j), cases))]
    image = subprocess.run(['docker', 'image', 'inspect', SIM_IMAGE, '--format', '{{.Id}}'],
                           capture_output=True, text=True, check=True).stdout.strip()
    report = dict(fixture=str(source), fixture_sha256=BASE_DECK_SHA256, sim_image=SIM_IMAGE, sim_image_id=image,
                  stimulus='100 mA positive, 0.1 ns edges, 2 ns flat into PAD_P at 1000 ns, VDD=1.5 V brownout after 1 us; '
                           'retained 3.3 V / 1.5 kohm / 15 kohm board peers, 1 ohm + 1 nH bond, 10 pF board',
                  pulses=pulses, shunt_dc=dc, pad_loading=loads, primary_diode_capacitance=caps,
                  source_sha256={str(p.relative_to(PROJECT)): sha(p) for p in (Path(__file__), Path(__file__).with_name('circuits.py'))})
    args.report.write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
