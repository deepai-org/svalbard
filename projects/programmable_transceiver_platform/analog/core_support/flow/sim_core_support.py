#!/usr/bin/env python3
"""Transistor-level qualification campaign for the vendored POR and biasgen.

Runs inside the pinned iic-osic-tools image (ngspice + GF180MCU-D models +
Avalon 3.3 V std-cell netlists).  Every job writes its own netlist and raw
waveform table under /work/sim/<job>/ and one summary record; the collected
records go to /work/sim/results.json.

Measurement conventions (also recorded in results.json):
  * "released" means porb > 0.5*V(vdd) while V(vdd) >= 1.0 V; the release
    instant is the first such time after which porb never falls back.
  * "asserted" means porb < 0.5*V(vdd) while V(vdd) >= 1.0 V.  Below 1.0 V the
    3.3 V logic it feeds is not defined, so that region is reported separately.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

PDK = os.environ.get('PDK_ROOT', '/foss/pdks') + '/' + os.environ.get('PDK', 'gf180mcuD')
SCLIB = PDK + '/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice'
SRC = '/src'
WORK = '/work/sim'
CLEAN = '/work/clean'
VNOM = 3.3
CORNERS = ('typical', 'ff', 'ss')
TEMPS = (-40, 27, 125)


def models(corner):
    aux = {'typical': 'typical', 'ff': 'ff', 'ss': 'ss'}[corner]
    m = PDK + '/libs.tech/ngspice/sm141064.ngspice'
    return '\n'.join([
        '.include ' + PDK + '/libs.tech/ngspice/design.ngspice',
        '.lib %s %s' % (m, corner),
        '.lib %s res_%s' % (m, aux),
        '.lib %s mimcap_%s' % (m, aux),
        '.lib %s diode_%s' % (m, aux),
        '.lib %s bjt_%s' % (m, aux),
        '.include ' + SCLIB,
    ])


def run_ngspice(name, deck, vectors, analysis_is_dc=False):
    d = os.path.join(WORK, name)
    os.makedirs(d, exist_ok=True)
    data = os.path.join(d, 'wave.txt')
    # The vendored netlists carry their own .save lines, which would otherwise
    # restrict the stored vectors; save exactly what is measured.
    saves = ['.save ' + ' '.join(v for v in vectors if not v.startswith('v(v-sweep'))]
    ctl = saves + ['.control', 'set num_threads=1', 'set wr_singlescale', 'set wr_vecnames',
           'option numdgt=7', 'run',
           'wrdata %s %s' % (data, ' '.join(vectors)), 'quit', '.endc', '.end']
    with open(os.path.join(d, '.spiceinit'), 'w') as f:
        # same settings as the image's /headless/.spiceinit (HOME is /tmp in the bounded run)
        f.write('set ngbehavior=hsa\nset ng_nomodcheck\nset num_threads=1\n')
    with open(os.path.join(d, 'deck.spice'), 'w') as f:
        f.write(deck + '\n' + '\n'.join(ctl) + '\n')
    p = subprocess.run(['ngspice', '-b', 'deck.spice'], cwd=d, capture_output=True, text=True,
                       timeout=int(os.environ.get('SIM_TIMEOUT', '3000')))
    with open(os.path.join(d, 'ngspice.log'), 'w') as f:
        f.write(p.stdout + p.stderr)
    log = p.stdout + p.stderr
    if not os.path.exists(data):
        return None, log[-2000:]
    if 'simulation(s) aborted' in log or 'Timestep too small' in log:
        return None, 'ngspice aborted: ' + log[-1500:]
    rows = []
    with open(data) as f:
        header = f.readline().split()
        for line in f:
            parts = line.split()
            if len(parts) == len(header):
                rows.append([float(x) for x in parts])
    cols = {h: [r[i] for r in rows] for i, h in enumerate(header)}
    return cols, None


def file_sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


# --------------------------------------------------------------------------- POR
# Tried in order for extracted (PEX) runs until ngspice completes; the record
# keeps the option string that was used.
PEX_OPTION_LADDER = (
    '.option method=gear reltol=1e-3 rshunt=1e12 cshunt=1e-17',
    '.option method=gear reltol=1e-3 rshunt=1e12',
    '.option method=gear maxord=2 reltol=1e-3 rshunt=1e12 cshunt=1e-16',
)


def por_deck(corner, temp, vdd_pwl, tstop, tmax, netlist='schematic', cload='1p', options=None):
    if netlist == 'schematic':
        inc = '.include %s/por/netlist/schematic/gf180mcu_ocd_ip__por.spice' % SRC
    else:
        inc = '.include %s/por/layout_pex.spice' % CLEAN
    return '\n'.join([
        '* POR qualification deck (%s, %s C, %s netlist)' % (corner, temp, netlist),
        models(corner), inc,
        '.temp %g' % temp,
        # The R+C extracted netlist needs a looser reltol plus tiny node shunts
        # (1 Tohm, 10 aF) to step through the release edge; without them ngspice
        # aborts with "timestep too small" at 5 of 13 window points.
        options or os.environ.get('POR_OPTIONS', '.option method=gear reltol=1e-4' if netlist == 'schematic'
                                  else PEX_OPTION_LADDER[0]),
        'Vdd vdd 0 PWL(%s)' % vdd_pwl,
        'Vena ena vdd 0',
        'X1 vdd ena por_unbuf 0 porb por gf180mcu_ocd_ip__por',
        'Cpb porb 0 %s' % cload, 'Cp por 0 %s' % cload,
        '.tran %g %g 0 %g' % (min(tmax / 10, 1e-6), tstop, tmax),
    ])


def por_analyse(c, events=()):
    t, v, pb = c['time'], c['v(vdd)'], c['v(porb)']
    n = len(t)
    valid = [v[i] >= 1.0 for i in range(n)]
    high = [valid[i] and pb[i] > 0.5 * v[i] for i in range(n)]
    low = [valid[i] and pb[i] < 0.5 * v[i] for i in range(n)]
    # Release instants: transitions low->high under valid supply.
    rel, asr = [], []
    state = None
    for i in range(n):
        if high[i] and state != 'H':
            if state == 'L':
                rel.append(i)
            state = 'H'
        elif low[i] and state != 'L':
            if state == 'H':
                asr.append(i)
            state = 'L'
    first_high = next((i for i in range(n) if high[i]), None)
    out = {
        'final_vdd_v': round(v[-1], 4), 'final_porb_v': round(pb[-1], 4),
        'final_state': 'released' if high[-1] else ('asserted' if low[-1] else 'undefined'),
        'release_times_s': [t[i] for i in rel], 'release_vdd_v': [round(v[i], 4) for i in rel],
        'assert_times_s': [t[i] for i in asr], 'assert_vdd_v': [round(v[i], 4) for i in asr],
        'first_valid_state': ('released' if first_high is not None and
                              (first_high == next((i for i in range(n) if valid[i]), None)) else 'asserted'),
        'first_high_time_s': t[first_high] if first_high is not None else None,
        'first_high_vdd_v': round(v[first_high], 4) if first_high is not None else None,
    }
    if 'v(x1.vcap)' in c:
        out['final_vcap_v'] = round(c['v(x1.vcap)'][-1], 4)
    if 'i(vdd)' in c:
        out['final_supply_current_a'] = -c['i(vdd)'][-1]
        # time-weighted mean over the last 10 ms, and the peak over the whole run
        i = [-x for x in c['i(vdd)']]
        k0 = next((k for k in range(n) if t[k] >= t[-1] - 10e-3), 0)
        span = t[-1] - t[k0]
        if span > 0:
            out['mean_supply_current_last_10ms_a'] = sum((t[k + 1] - t[k]) * i[k] for k in range(k0, n - 1)) / span
        out['peak_supply_current_a'] = max(i)
    return out


def t_cross_up(t, v, level):
    for i in range(1, len(t)):
        if v[i - 1] < level <= v[i]:
            return t[i - 1] + (level - v[i - 1]) * (t[i] - t[i - 1]) / (v[i] - v[i - 1])
    return None


def por_ramp_job(corner, temp, trise, vfinal=VNOM, netlist='schematic'):
    name = 'por_ramp_%s_%s_%gs_%gV_%s' % (corner, temp, trise, vfinal, netlist)
    t0 = 10e-6
    tstop = t0 + trise + float(os.environ.get('POR_HOLD', '0.25'))
    # The PWL corners are simulator breakpoints, so a fixed 100 us step ceiling
    # resolves even the 1 us ramp; the hold-off timer itself is a ~40 ms ramp.
    tmax = float(os.environ.get('POR_TMAX', '1e-4'))
    pwl = '0 0 %g 0 %g %g' % (t0, t0 + trise, vfinal)
    vecs = ['v(vdd)', 'v(porb)', 'v(por)', 'i(vdd)']
    if netlist == 'schematic':
        vecs.append('v(x1.vcap)')
    ladder = PEX_OPTION_LADDER if (netlist == 'pex' and 'POR_OPTIONS' not in os.environ) else (None,)
    for opt in ladder:
        c, err = run_ngspice(name, por_deck(corner, temp, pwl, tstop, tmax, netlist, options=opt), vecs)
        if c is not None:
            break
    rec = {'job': name, 'kind': 'por_ramp', 'corner': corner, 'temp_c': temp, 'trise_s': trise,
           'vfinal_v': vfinal, 'netlist': netlist}
    if opt:
        rec['sim_options'] = opt
    if netlist == 'pex':
        rec['pex_netlist_sha256'] = file_sha256('%s/por/layout_pex.spice' % CLEAN)
    if c is None:
        rec['error'] = err
        return rec
    a = por_analyse(c)
    rec.update(a)
    t, v = c['time'], c['v(vdd)']
    t90 = t_cross_up(t, v, 0.9 * vfinal)
    rec['t_vdd_90pct_s'] = t90
    if a['release_times_s']:
        tr = a['release_times_s'][-1]
        rec['release_time_s'] = tr
        rec['release_vdd_v'] = a['release_vdd_v'][-1]
        rec['delay_from_ramp_start_s'] = tr - t0
        rec['delay_after_vdd_90pct_s'] = (tr - t90) if t90 is not None else None
        rec['released_before_vdd_90pct'] = (t90 is None) or (tr < t90)
    elif a['first_valid_state'] == 'released':
        rec['release_time_s'] = a['first_high_time_s']
        rec['release_vdd_v'] = a['first_high_vdd_v']
        rec['note'] = 'porb high at first valid supply (no hold-off observed)'
        rec['released_before_vdd_90pct'] = True
    return rec


def por_event_job(kind, corner, temp, params):
    """Brownout dips, repeated ramps and slow falling rails after a cold start."""
    t0, tup = 10e-6, 100e-6
    tsettle = 0.15  # cold-start release completes well before this at all corners checked
    pts = [(0, 0), (t0, 0), (t0 + tup, VNOM), (tsettle, VNOM)]
    if kind == 'dip':
        vdip, tdip, tedge = params['vdip_v'], params['tdip_s'], params.get('edge_s', 10e-6)
        pts += [(tsettle + tedge, vdip), (tsettle + tedge + tdip, vdip),
                (tsettle + 2 * tedge + tdip, VNOM)]
        tend = tsettle + 2 * tedge + tdip
    elif kind == 'repeat':
        toff, tfall = params['toff_s'], params.get('tfall_s', 100e-6)
        pts += [(tsettle + tfall, 0), (tsettle + tfall + toff, 0), (tsettle + tfall + toff + tup, VNOM)]
        tend = tsettle + tfall + toff + tup
    elif kind == 'fall':
        tfall = params['tfall_s']
        pts += [(tsettle + tfall, 0)]
        tend = tsettle + tfall
    else:
        raise ValueError(kind)
    tstop = tend + (0.25 if kind != 'fall' else 0.01)
    pwl = ' '.join('%g %g' % p for p in pts)
    name = 'por_%s_%s_%s_%s' % (kind, corner, temp, '_'.join('%s%g' % kv for kv in sorted(params.items())))
    c, err = run_ngspice(name, por_deck(corner, temp, pwl, tstop, float(os.environ.get('POR_TMAX', '1e-4'))),
                         ['v(vdd)', 'v(porb)', 'v(por)', 'v(x1.vcap)'])
    rec = {'job': name, 'kind': 'por_' + kind, 'corner': corner, 'temp_c': temp}
    rec.update(params)
    if c is None:
        rec['error'] = err
        return rec
    t, v, pb, vc = c['time'], c['v(vdd)'], c['v(porb)'], c['v(x1.vcap)']
    i_ev = next(i for i in range(len(t)) if t[i] >= tsettle)
    rec['released_before_event'] = pb[i_ev] > 0.5 * v[i_ev] and v[i_ev] > 3.0
    rec['vcap_before_event_v'] = round(vc[i_ev], 4)
    # Behaviour during/after the event
    ev = range(i_ev, len(t))
    asserted_valid = [i for i in ev if v[i] >= 1.0 and pb[i] < 0.5 * v[i]]
    rec['reset_asserted_with_vdd_ge_1v'] = bool(asserted_valid)
    if asserted_valid:
        rec['assert_first_time_s'] = t[asserted_valid[0]]
        rec['assert_vdd_v'] = round(v[asserted_valid[0]], 4)
    rec['vdd_min_v'] = round(min(v[i] for i in ev), 4)
    rec['porb_max_while_vdd_lt_1v_v'] = round(max([pb[i] for i in ev if v[i] < 1.0] or [0.0]), 4)
    if kind == 'fall':
        # highest supply at which porb is asserted (if ever) during the fall
        rec['note'] = 'porb is a buffered logic output on vdd; it tracks vdd down when not asserted'
        return rec
    # After recovery to nominal: when (if ever) is reset released again, and for how long was it held
    i_rec = next((i for i in range(len(t)) if t[i] >= tend), len(t) - 1)
    held = [i for i in range(i_rec, len(t)) if pb[i] < 0.5 * v[i]]
    rel_after = None
    if held:
        later = [i for i in range(held[-1] + 1, len(t)) if pb[i] > 0.5 * v[i]]
        rel_after = t[later[0]] if later else None
    rec['reset_hold_after_recovery_s'] = (rel_after - tend) if (held and rel_after) else (0.0 if not held else None)
    rec['released_at_end'] = pb[-1] > 0.5 * v[-1]
    rec['vcap_at_recovery_v'] = round(vc[i_rec], 4)
    return rec


# ------------------------------------------------------------------------ biasgen
BG_SOURCES = ('idac1_source_ibias', 'idac2_source_ibias', 'voltgen_source_ibias')
BG_SINKS = ('bandgap_sink1_ibias', 'bandgap_sink2_ibias', 'voltgen_sink1_ibias', 'voltgen_sink2_ibias')
BG_CODES = {'bandgap_sink2': 1, 'voltgen_source': 4, 'voltgen_sink1': 4, 'idac1_source': 4,
            'idac2_source': 31, 'bandgap_sink1': 4, 'voltgen_sink2': 4}
BG_WIDTH = {'bandgap_sink2': 2, 'voltgen_source': 5, 'voltgen_sink1': 3, 'idac1_source': 5,
            'idac2_source': 5, 'bandgap_sink1': 3, 'voltgen_sink2': 3}
BG_PINS = ('ena avdd avss ref_in dvdd vbg ref_sel_vbg dvss bandgap_sink2[1] bandgap_sink2[0] '
           'voltgen_source[4] voltgen_source[3] voltgen_source[2] voltgen_source[1] voltgen_source[0] '
           'bandgap_sink2_ibias voltgen_sink1[2] voltgen_sink1[1] voltgen_sink1[0] voltgen_source_ibias '
           'idac1_source[4] idac1_source[3] idac1_source[2] idac1_source[1] idac1_source[0] voltgen_sink1_ibias '
           'idac1_source_ibias idac2_source_ibias idac2_source[4] idac2_source[3] idac2_source[2] idac2_source[1] '
           'idac2_source[0] ref_sel_coarse ref_sel_fine bandgap_sink1[2] bandgap_sink1[1] bandgap_sink1[0] '
           'bandgap_sink1_ibias voltgen_sink2[2] voltgen_sink2[1] voltgen_sink2[0] voltgen_sink2_ibias').split()
SRC_LOAD_V = 1.0   # source outputs drive a node held 1.0 V above ground
SNK_LOAD_V = 1.0   # sink outputs pull from a node held 1.0 V below the supply


def bg_netlist(netlist):
    """'schematic' = regenerated schematic of the patched (pin fix + vfb compensation) biasgen,
    'vendored' = regenerated schematic of the unmodified upstream biasgen,
    'pex' = C-only extraction of the patched layout."""
    return {'schematic': '%s/biasgen_patched/sch.spice' % CLEAN,
            'vendored': '%s/biasgen/sch.spice' % CLEAN,
            'pex': '%s/biasgen_patched/layout_pex.spice' % CLEAN}[netlist]


def bg_deck(corner, temp, supply, analysis, mode='self', ena='vdd', netlist='schematic',
            src_load=SRC_LOAD_V, snk_load=SNK_LOAD_V, extra=''):
    inc = '.include ' + bg_netlist(netlist)
    conn = {}
    for p in BG_PINS:
        conn[p] = p
    lines = ['* biasgen qualification deck (%s, %s C, mode=%s)' % (corner, temp, mode), models(corner), inc,
             '.temp %g' % temp, os.environ.get('BG_OPTIONS', '.option method=gear'),
             'Vdd vdd 0 %s' % supply,
             'Vavdd vdd avdd 0', 'Vdvdd vdd dvdd 0', 'Vavss avss 0 0', 'Vdvss dvss 0 0',
             'Vref ref_in avdd 0']
    lines.append('Vvbg vbg 0 1.2' if mode == 'vbg' else 'Vvbg vbg 0 0')
    lines.append('Bsel ref_sel_vbg 0 V=%s' % ('v(vdd)' if mode == 'vbg' else '0'))
    lines.append('Bcoarse ref_sel_coarse 0 V=0')
    lines.append('Bfine ref_sel_fine 0 V=0')
    lines.append('Bena ena 0 V=%s' % {'vdd': 'v(vdd)', 'off': '0'}.get(ena, ena))
    for bus, code in BG_CODES.items():
        for b in range(BG_WIDTH[bus]):
            lines.append('B%s_%d %s[%d] 0 V=%s' % (bus, b, bus, b, 'v(vdd)' if (code >> b) & 1 else '0'))
    for o in BG_SOURCES:
        lines.append('Vl_%s %s 0 %g' % (o, o, src_load))
    for o in BG_SINKS:
        lines.append('Bl_%s %s 0 V=max(v(vdd)-%g,0)' % (o, o, snk_load))
    # Connect by pin name using the included netlist's own .subckt header
    # (the extracted netlist orders ports differently and, having joined
    # avss to dvss through the substrate, exports no separate avss port).
    ports = subckt_ports(inc.split(None, 1)[1], 'gf180mcu_ocd_ip__biasgen')
    lines.append('X1 ' + ' '.join(conn[p] for p in ports) + ' gf180mcu_ocd_ip__biasgen')
    lines.append(extra)
    lines.append(analysis)
    return '\n'.join(lines)


def subckt_ports(path, name):
    toks, grab = [], False
    with open(path) as f:
        for line in f:
            if line.lower().startswith('.subckt') and line.split()[1] == name:
                grab = True
                toks += line.split()[2:]
                continue
            if grab:
                if line.startswith('+'):
                    toks += line[1:].split()
                else:
                    break
    return [t for t in toks if '=' not in t]


def bg_vectors(netlist='schematic'):
    # internal bias nodes keep their schematic names only in the schematic netlist
    internal = ['v(x1.nbias)', 'v(x1.pbias)'] if netlist == 'schematic' else []
    return (['v(vdd)', 'i(vdd)'] + ['i(vl_%s)' % o for o in BG_SOURCES] +
            ['i(bl_%s)' % o for o in BG_SINKS] + internal)


def bg_currents(c, i):
    out = {}
    for o in BG_SOURCES:
        out[o] = c['i(vl_%s)' % o][i]          # current delivered into the load (A, + = sourcing)
    for o in BG_SINKS:
        out[o] = c['i(bl_%s)' % o][i]          # + = current flowing from the load into the sink
    return out


def expected_currents(mode):
    unit = 250e-9
    e = {}
    for o, bus in (('idac1_source_ibias', 'idac1_source'), ('idac2_source_ibias', 'idac2_source'),
                   ('voltgen_source_ibias', 'voltgen_source'), ('bandgap_sink1_ibias', 'bandgap_sink1'),
                   ('bandgap_sink2_ibias', 'bandgap_sink2'), ('voltgen_sink1_ibias', 'voltgen_sink1'),
                   ('voltgen_sink2_ibias', 'voltgen_sink2')):
        e[o] = BG_CODES[bus] * unit
    return e


def bg_dc_job(corner, temp, mode, netlist='schematic', ena='vdd'):
    name = 'bg_dc_%s_%s_%s_%s_%s' % (corner, temp, mode, netlist, ena)
    deck = bg_deck(corner, temp, 'DC 3.3', '.dc Vdd 3.65 1.5 -0.05', mode=mode, netlist=netlist, ena=ena)
    c, err = run_ngspice(name, deck, bg_vectors(netlist), analysis_is_dc=True)
    rec = {'job': name, 'kind': 'bg_dc', 'corner': corner, 'temp_c': temp, 'mode': mode,
           'netlist': netlist, 'ena': ena}
    if netlist == 'pex':
        rec['pex_netlist_sha256'] = file_sha256('%s/biasgen_patched/layout_pex.spice' % CLEAN)
    if c is None:
        rec['error'] = err
        return rec
    sweep = c['v(v-sweep)'] if 'v(v-sweep)' in c else c[list(c)[0]]

    def idx(v):
        return min(range(len(sweep)), key=lambda i: abs(sweep[i] - v))
    pts = {}
    for v in (1.8, 2.5, 3.0, 3.15, 3.3, 3.35, 3.6):
        pts['%.2f' % v] = bg_currents(c, idx(v))
        pts['%.2f' % v]['supply_current_a'] = -c['i(vdd)'][idx(v)]
    rec['currents_a'] = pts
    sens, win = {}, {}
    for o in BG_SOURCES + BG_SINKS:
        i30, i36, i33 = pts['3.00'][o], pts['3.60'][o], pts['3.30'][o]
        sens[o] = ((i36 - i30) / 0.6 / i33 * 100.0) if abs(i33) > 1e-12 else None
        a, b = pts['3.15'][o], pts['3.35'][o]
        win[o] = ((b - a) / 0.2 / i33 * 100.0) if abs(i33) > 1e-12 else None
    rec['supply_sensitivity_pct_per_v_3v0_3v6'] = sens
    rec['supply_sensitivity_pct_per_v_3v15_3v35'] = win
    rec['expected_upstream_nominal_a'] = expected_currents(mode)
    if 'v(x1.nbias)' in c:
        rec['nbias_v_3v3'] = c['v(x1.nbias)'][idx(3.3)]
        rec['pbias_v_3v3'] = c['v(x1.pbias)'][idx(3.3)]
    return rec


def bg_compliance_job(corner, temp, mode):
    """Output current vs output voltage at 3.3 V (sources swept 0..3.3 V)."""
    name = 'bg_comp_%s_%s_%s' % (corner, temp, mode)
    deck = bg_deck(corner, temp, 'DC 3.3', '.dc Vl_idac1_source_ibias 0 3.3 0.05', mode=mode)
    c, err = run_ngspice(name, deck, ['i(vl_idac1_source_ibias)'], analysis_is_dc=True)
    rec = {'job': name, 'kind': 'bg_compliance', 'corner': corner, 'temp_c': temp, 'mode': mode}
    if c is None:
        rec['error'] = err
        return rec
    sw = c[list(c)[0]]
    i = c['i(vl_idac1_source_ibias)']
    iref = i[min(range(len(sw)), key=lambda k: abs(sw[k] - 1.0))]
    ok = [sw[k] for k in range(len(sw)) if abs(i[k] - iref) <= 0.05 * abs(iref)]
    rec['idac1_at_1v0_a'] = iref
    rec['idac1_within_5pct_max_vout_v'] = max(ok) if ok else None
    rec['idac1_within_5pct_min_vout_v'] = min(ok) if ok else None
    return rec


def bg_tran_job(corner, temp, mode, trise, netlist='schematic', ena='vdd'):
    name = 'bg_tran_%s_%s_%s_%gs_%s_%s' % (corner, temp, mode, trise, netlist, ena)
    t0 = 1e-6
    hold = max(2e-3, 0.2 * trise)
    tstop = t0 + trise + hold
    # PWL corners are breakpoints; a 1 us ceiling (10 us for slow ramps)
    # resolves the start-up while keeping 600-device runs tractable.
    tmax = 1e-6 if trise <= 100e-6 else 1e-5
    pwl = 'PWL(0 0 %g 0 %g 3.3)' % (t0, t0 + trise)
    deck = bg_deck(corner, temp, pwl, '.tran %g %g 0 %g' % (tmax / 10, tstop, tmax), mode=mode,
                   netlist=netlist, ena=ena)
    c, err = run_ngspice(name, deck, bg_vectors(netlist))
    rec = {'job': name, 'kind': 'bg_tran', 'corner': corner, 'temp_c': temp, 'mode': mode, 'trise_s': trise,
           'netlist': netlist, 'ena': ena}
    if netlist == 'pex':
        rec['pex_netlist_sha256'] = file_sha256('%s/biasgen_patched/layout_pex.spice' % CLEAN)
    if c is None:
        rec['error'] = err
        return rec
    t = c['time']
    rec['final_currents_a'] = bg_currents(c, len(t) - 1)
    rec['final_supply_current_a'] = -c['i(vdd)'][-1]
    # settle time of idac1 to within 5 % of its final value after the supply reaches 3.0 V
    i1 = c['i(vl_idac1_source_ibias)']
    fin = i1[-1]
    t30 = t_cross_up(t, c['v(vdd)'], 3.0)
    last_out = max([k for k in range(len(t)) if abs(i1[k] - fin) > 0.05 * abs(fin)] or [0])
    rec['idac1_settle_5pct_after_vdd_3v0_s'] = (t[min(last_out + 1, len(t) - 1)] - t30) if t30 else None
    return rec


STEP = 'v(vdd)*min(max((time-{t0})/1e-6,0),1)'
# Bandgap-mode (ref_sel_vbg=1) loop probes.  name -> (supply PWL template, vbg source, ena, ref_sel_vbg)
# {v} = settled supply.  Abrupt events happen at t0 = 50 us (supply already settled after a 10 us ramp).
BG_PROBES = {
    'ramp1us':       ('PWL(0 0 1e-6 0 2e-6 {v})', 'Vvbg vbg 0 1.2', 'vdd', 'v(vdd)'),
    'ramp1us_vbg_tracks': ('PWL(0 0 1e-6 0 2e-6 {v})', 'Bvbg vbg 0 V=min(v(vdd),1.2)', 'vdd', 'v(vdd)'),
    'ramp10us':      ('PWL(0 0 1e-6 0 11e-6 {v})', 'Vvbg vbg 0 1.2', 'vdd', 'v(vdd)'),
    'ena_on':        ('PWL(0 0 1e-6 0 11e-6 {v})', 'Vvbg vbg 0 1.2', STEP.format(t0=50e-6), 'v(vdd)'),
    'refsel_on':     ('PWL(0 0 1e-6 0 11e-6 {v})', 'Vvbg vbg 0 1.2', 'vdd', STEP.format(t0=50e-6)),
    'supply_step':   ('PWL(0 0 1e-6 0 11e-6 {v} 150e-6 {v} 151e-6 {vm} 250e-6 {vm} 251e-6 {v})', 'Vvbg vbg 0 1.2',
                      'vdd', 'v(vdd)'),
}


def bg_probe_job(name, corner='typical', temp=27, vdd=VNOM, netlist='schematic', tstop=400e-6, tmax=5e-9,
                 avdd=None):
    """Transient with a 5 ns step ceiling (the loop's unity-gain frequency is <= 20 MHz),
    so an oscillation cannot be hidden by integrator damping."""
    pwl, vbgline, ena, sel = BG_PROBES[name]
    pwl = pwl.format(v=vdd, vm=vdd - 0.15)
    deck = bg_deck(corner, temp, pwl, '.tran 1e-9 %g 0 %g' % (tstop, tmax), mode='vbg', ena=ena,
                   netlist=netlist)
    deck = deck.replace('Vvbg vbg 0 1.2', vbgline)
    deck = deck.replace('Bsel ref_sel_vbg 0 V=v(vdd)', 'Bsel ref_sel_vbg 0 V=' + sel)
    if avdd:
        deck = deck.replace('Vavdd vdd avdd 0', 'Vavdd avdd 0 %g' % avdd)
    job = 'bg_probe_%s_%s_%s_%gV_%s%s' % (name, corner, temp, vdd, netlist, '_avdd%g' % avdd if avdd else '')
    c, err = run_ngspice(job, deck, ['v(vdd)', 'i(vdd)', 'i(vl_idac1_source_ibias)'])
    rec = {'job': job, 'kind': 'bg_probe', 'probe': name, 'corner': corner, 'temp_c': temp, 'vdd_v': vdd,
           'netlist': netlist, 'avdd_v': avdd, 'supply_pwl': pwl, 'vbg_source': vbgline, 'ena': ena,
           'ref_sel_vbg': sel, 'tstop_s': tstop, 'tmax_s': tmax}
    if netlist == 'pex':
        rec['pex_netlist_sha256'] = file_sha256(bg_netlist('pex'))
    if c is None:
        rec['error'] = err
        return rec
    t, i1 = c['time'], c['i(vl_idac1_source_ibias)']
    win = {}
    for a, b in ((100e-6, 140e-6), (200e-6, 240e-6), (tstop - 50e-6, tstop)):
        seg = [i1[k] for k in range(len(t)) if a <= t[k] <= b]
        if seg:
            win['%g-%gus' % (a * 1e6, b * 1e6)] = {'idac1_min_a': min(seg), 'idac1_max_a': max(seg)}
    rec['windows'] = win
    last = win['%g-%gus' % ((tstop - 50e-6) * 1e6, tstop * 1e6)]
    rec['final_idac1_a'] = i1[-1]
    rec['last_window_pp_a'] = last['idac1_max_a'] - last['idac1_min_a']
    rec['settled_in_last_window'] = rec['last_window_pp_a'] <= 0.02 * abs(last['idac1_max_a'])
    return rec


def bg_loopgain_job(corner='typical', temp=27, vdd=VNOM, netlist='schematic', avdd=None, coarse=0, fine=0):
    """AC loop gain of the bandgap-mode loop, broken at the bias_amp_large '+' input (vfb)
    with a 1 GH / 1 F DC-closed break; T = -v(vfb)/v(vfb_amp)."""
    base = open(bg_netlist(netlist)).read()
    a = 'x3 avdd pbias vbg vfb nbias avss ena_vbg_5v0 bias_amp_large'
    assert a in base
    t = base.replace(a, 'x3 avdd pbias vbg vfb_amp nbias avss ena_vbg_5v0 bias_amp_large')
    i = t.index('.subckt bias_generator_fe'); j = t.index('.ends', i)
    t = t[:j] + 'Lbrk vfb vfb_amp 1e9\nCbrk vfb_amp vac_in 1\nVac vac_in avss DC 0 AC 1\n' + t[j:]
    job = 'bg_loop_%s_%s_%gV_%s%s%s' % (corner, temp, vdd, netlist, '_avdd%g' % avdd if avdd else '',
                                        '_c%df%d' % (coarse, fine) if (coarse or fine) else '')
    d = os.path.join(WORK, job); os.makedirs(d, exist_ok=True)
    net = os.path.join(d, 'net.spice'); open(net, 'w').write(t)
    deck = bg_deck(corner, temp, 'DC %g' % vdd, '.ac dec 40 10 1e9', mode='vbg', netlist=netlist)
    deck = deck.replace('.include ' + bg_netlist(netlist), '.include ' + net)
    if avdd:
        deck = deck.replace('Vavdd vdd avdd 0', 'Vavdd avdd 0 %g' % avdd)
    if coarse:
        deck = deck.replace('Bcoarse ref_sel_coarse 0 V=0', 'Bcoarse ref_sel_coarse 0 V=v(vdd)')
    if fine:
        deck = deck.replace('Bfine ref_sel_fine 0 V=0', 'Bfine ref_sel_fine 0 V=v(vdd)')
    rec = {'job': job, 'kind': 'bg_loopgain', 'corner': corner, 'temp_c': temp, 'vdd_v': vdd, 'netlist': netlist,
           'avdd_v': avdd, 'ref_sel_coarse': coarse, 'ref_sel_fine': fine}
    path = os.path.join(d, 'ac.txt')
    ctl = ['.save v(x1.x1.vfb) v(x1.x1.vfb_amp)', '.control', 'set num_threads=1', 'run',
           'wrdata %s vr(x1.x1.vfb) vi(x1.x1.vfb) vr(x1.x1.vfb_amp) vi(x1.x1.vfb_amp)' % path, 'quit', '.endc', '.end']
    with open(os.path.join(d, '.spiceinit'), 'w') as f:
        f.write('set ngbehavior=hsa\nset ng_nomodcheck\nset num_threads=1\n')
    open(os.path.join(d, 'deck.spice'), 'w').write(deck + '\n' + '\n'.join(ctl) + '\n')
    p = subprocess.run(['ngspice', '-b', 'deck.spice'], cwd=d, capture_output=True, text=True, timeout=3000)
    open(os.path.join(d, 'ngspice.log'), 'w').write(p.stdout + p.stderr)
    if not os.path.exists(path):
        rec['error'] = (p.stdout + p.stderr)[-1500:]
        return rec
    import cmath
    T = []
    for line in open(path):
        x = line.split()
        if len(x) < 8:
            continue
        try:
            f = float(x[0]); vf = complex(float(x[1]), float(x[3])); va = complex(float(x[5]), float(x[7]))
        except ValueError:
            continue
        T.append((f, -vf / va))
    ph, prev, off = [], None, 0.0
    for f, h in T:
        q = math.degrees(cmath.phase(h))
        if prev is not None:
            while q + off - prev > 180: off -= 360
            while q + off - prev < -180: off += 360
        prev = q + off; ph.append(prev)
    rec['dc_loop_gain_db'] = 20 * math.log10(abs(T[0][1]))
    for k in range(1, len(T)):
        if abs(T[k - 1][1]) >= 1 > abs(T[k][1]):
            rec['unity_gain_hz'] = T[k][0]; rec['phase_margin_deg'] = 180 + ph[k]; break
    for k in range(1, len(T)):
        if ph[k - 1] > -180 >= ph[k]:
            rec['gain_margin_db'] = -20 * math.log10(abs(T[k][1])); break
    return rec


# ------------------------------------------------------------------------- driver
# Operating envelope (spec/tapeout-plan.md "Operating envelope"):
#   function: tt/ss/ff x 22/32 C x 3.15/3.35 V, plus nominal tt/27 C/3.3 V
#   safety:   0 -> 3.63 V ramps, brownout, repeated ramps, 0..85 C
#   -40/125 C and 3.0/3.6 V are exploratory only.
FUNC_TEMPS = (22, 32)
FUNC_SUPPLIES = (3.15, 3.35)
SAFE_TEMPS = (0, 27, 85)
VMAX = 3.63


def func_points():
    pts = [('typical', 27, VNOM)]
    for c in CORNERS:
        for T in FUNC_TEMPS:
            for v in FUNC_SUPPLIES:
                pts.append((c, T, v))
    return pts


def plan(which):
    jobs = []
    if 'por' in which:
        # function window (schematic), 100 us ramp
        for c, T, v in func_points():
            jobs.append((por_ramp_job, (c, T, 100e-6, v)))
        # nominal ramp-rate sweep to 3.3 V
        for tr in (1e-6, 10e-6, 1e-3, 10e-3, 100e-3, 300e-3, 1.0):
            jobs.append((por_ramp_job, ('typical', 27, tr)))
        # safety: ramps to the 3.63 V limit, all corners, 0..85 C
        for c in CORNERS:
            for T in SAFE_TEMPS:
                for tr in (1e-6, 10e-6, 1e-3, 10e-3, 100e-3, 1.0):
                    jobs.append((por_ramp_job, (c, T, tr, VMAX)))
        # brownout dips after a completed cold start
        for vd in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
            for td in (10e-6, 1e-3, 10e-3, 100e-3):
                jobs.append((por_event_job, ('dip', 'typical', 27, {'vdip_v': vd, 'tdip_s': td})))
        for c, T in (('ss', 0), ('ff', 85), ('ss', 85), ('ff', 0)):
            for vd in (0.0, 1.0, 2.0):
                jobs.append((por_event_job, ('dip', c, T, {'vdip_v': vd, 'tdip_s': 1e-3})))
        # repeated ramps (power cycle with off-time) and slow falling rails
        for c, T in (('typical', 27), ('ss', 0), ('ff', 85)):
            for toff in (100e-6, 1e-3, 10e-3, 100e-3, 1.0):
                jobs.append((por_event_job, ('repeat', c, T, {'toff_s': toff})))
            for tf in (1e-3, 100e-3):
                jobs.append((por_event_job, ('fall', c, T, {'tfall_s': tf})))
        # exploratory only
        for c, T in (('ss', -40), ('ff', 125)):
            for tr in (10e-6, 1e-3, 1.0):
                jobs.append((por_ramp_job, (c, T, tr)))
    if 'por_pex' in which:
        for c, T, v in func_points():
            jobs.append((por_ramp_job, (c, T, 100e-6, v, 'pex')))
    if 'bg' in which:
        for c in CORNERS:
            for T in (22, 27, 32):
                for m in ('self', 'vbg'):
                    jobs.append((bg_dc_job, (c, T, m)))
            jobs.append((bg_compliance_job, (c, 27, 'self')))
            for T in SAFE_TEMPS:
                for tr in (1e-6, 100e-6, 10e-3):
                    jobs.append((bg_tran_job, (c, T, 'self', tr)))
            jobs.append((bg_tran_job, (c, 27, 'vbg', 100e-6)))
        jobs.append((bg_dc_job, ('typical', 27, 'self', 'schematic', 'off')))
        jobs.append((bg_tran_job, ('typical', 27, 'self', 100e-3)))
        jobs.append((bg_tran_job, ('typical', 27, 'vbg', 1e-6)))
        for c, T in (('ss', -40), ('ff', 125)):  # exploratory only
            jobs.append((bg_dc_job, (c, T, 'self')))
    if 'bg_loop' in which:
        for c in CORNERS:
            for T in (0, 22, 32, 85):
                for v in (3.15, 3.35):
                    jobs.append((bg_loopgain_job, (c, T, v, 'schematic')))
            jobs.append((bg_loopgain_job, (c, 27, VNOM, 'vendored')))
        jobs.append((bg_loopgain_job, ('typical', 27, VNOM, 'schematic')))
        jobs.append((bg_loopgain_job, ('typical', 27, VNOM, 'vendored', 5.0)))
        jobs.append((bg_loopgain_job, ('typical', 27, VNOM, 'schematic', 5.0)))
        for cf in ((1, 0), (0, 1), (1, 1)):
            jobs.append((bg_loopgain_job, ('typical', 27, VNOM, 'schematic', None) + cf))
            jobs.append((bg_loopgain_job, ('typical', 27, VNOM, 'vendored', None) + cf))
    if 'bg_loop_coarse' in which:
        # coarse range (1 uA unit) is the setting that feeds the bias distribution (idac2 code 10)
        for c in CORNERS:
            for T in (0, 22, 32, 85):
                for v in (3.15, 3.35):
                    jobs.append((bg_loopgain_job, (c, T, v, 'schematic', None, 1, 0)))
    if 'bg_probe' in which:
        # unmodified upstream: the oscillation at 3.3 V and at upstream's 5 V avdd
        jobs.append((bg_probe_job, ('refsel_on', 'typical', 27, VNOM, 'vendored')))
        jobs.append((bg_probe_job, ('ramp1us', 'typical', 27, VNOM, 'vendored')))
        jobs.append((bg_probe_job, ('refsel_on', 'typical', 27, VNOM, 'vendored', 400e-6, 5e-9, 5.0)))
        # compensated design
        for name in BG_PROBES:
            jobs.append((bg_probe_job, (name, 'typical', 27, VNOM)))
        for c, T, v in (('ff', 22, 3.35), ('ss', 32, 3.15), ('ff', 0, 3.63), ('ss', 85, 3.15), ('typical', 0, 3.35)):
            for name in ('ramp1us', 'ena_on', 'refsel_on'):
                jobs.append((bg_probe_job, (name, c, T, v)))
        jobs.append((bg_probe_job, ('refsel_on', 'typical', 27, VNOM, 'schematic', 400e-6, 5e-9, 5.0)))
        jobs.append((bg_probe_job, ('refsel_on', 'typical', 27, VNOM, 'pex')))
    if 'bg_pex' in which:
        for c in CORNERS:
            for T in (22, 27, 32) if c != 'typical' else (22, 27, 32):
                jobs.append((bg_dc_job, (c, T, 'self', 'pex')))
        jobs.append((bg_tran_job, ('typical', 27, 'self', 100e-6, 'pex')))
    return jobs


def main():
    which = sys.argv[1:] or ['por', 'por_pex', 'bg', 'bg_pex', 'bg_loop', 'bg_probe']
    os.makedirs(WORK, exist_ok=True)
    jobs = plan(which)
    workers = int(os.environ.get('SIM_JOBS', '4'))
    results = []

    def go(j):
        fn, args = j
        try:
            r = fn(*args)
        except Exception as e:  # keep the campaign going; record the failure
            r = {'job': '%s%r' % (fn.__name__, args), 'error': repr(e)}
        print('done', r.get('job'), 'ERROR' if 'error' in r else '', flush=True)
        return r
    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(go, jobs))
    out = os.path.join(WORK, 'results_%s.json' % '_'.join(which))
    with open(out, 'w') as f:
        json.dump(results, f, indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x)
    print('wrote', out)


if __name__ == '__main__':
    main()
