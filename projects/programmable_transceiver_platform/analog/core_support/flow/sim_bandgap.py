#!/usr/bin/env python3
"""Bandgap (gf180mcu_ocd_ip__bandgap, vendored) qualification, standalone and
in the full reference chain:

    biasgen self-referenced sinks (bandgap_sink1 -> ibias2_1u, bandgap_sink2 -> ibias1_250n)
      -> bandgap -> vbg -> compensated biasgen (bandgap mode, coarse, idac2 code 10)
      -> pt_bias_root -> five island banks (20 x 10 uA outputs)

Runs in the pinned analog image; writes /work/sim/results_bandgap.json.
The extracted bandgap netlist names its PNPs pnp_10p00x00p42 (PDK Magic device-
recognition issue, see README); the PEX deck substitutes the 5x5 model that the
layout actually contains.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/src/flow')
sys.path.insert(0, '/src/distribution')
import sim_core_support as s  # noqa: E402
import sim_dist as d  # noqa: E402

CLEAN = '/work/clean'
BG_CELL = 'gf180mcu_ocd_ip__bandgap'
TRIM_DEFAULT = int(os.environ.get('BANDGAP_TRIM', '8'))
SINK1_CODE, SINK2_CODE = 7, 3       # maximum codes: the sinks are weak at 3.3 V (see README)
ATB_R = 2350.0                      # atb_tap_f on-resistance (analog/island_support README)


def bandgap_netlist(netlist, jobdir):
    if netlist == 'schematic':
        return '%s/bandgap/sch.spice' % CLEAN
    src = open('%s/bandgap/layout_pex.spice' % CLEAN).read()
    out = os.path.join(jobdir, 'bandgap_pex_pnpfix.spice')
    os.makedirs(jobdir, exist_ok=True)
    open(out, 'w').write(src.replace('pnp_10p00x00p42', 'pnp_05p00x05p00'))
    with open(os.path.join(jobdir, 'pex_source_sha256.txt'), 'w') as f:
        f.write(s.file_sha256('%s/bandgap/layout_pex.spice' % CLEAN))
    return out


def bandgap_inst(path, conn):
    ports = s.subckt_ports(path, BG_CELL)
    return 'Xbgap ' + ' '.join(conn.get(p, p) for p in ports) + ' ' + BG_CELL


def trim_lines(code, supply='v(vdd)'):
    # thermometer code: the number of bits set is what matters
    return ['Btrim%d trim[%d] 0 V=%s' % (b, b, supply if b < code else '0') for b in range(16)]


def standalone_job(corner, temp, vdd, trim=TRIM_DEFAULT, netlist='schematic', scale=1.0, kind='bgap_dc'):
    """Bandgap alone with ideal bias sinks (upstream's 250 nA / 1 uA, optionally scaled)."""
    job = '%s_%s_%s_%gV_t%d_%s_x%g' % (kind, corner, temp, vdd, trim, netlist, scale)
    jd = os.path.join(s.WORK, job)
    path = bandgap_netlist(netlist, jd)
    conn = {'dvss': '0', 'dvdd': 'vdd', 'ena': 'vdd', 'vbg': 'vbg', 'ibias1_250n': 'ib1', 'ibias2_1u': 'ib2'}
    deck = [s.models(corner), '.include ' + path, '.temp %g' % temp, '.option method=gear',
            'Vdd vdd 0 DC %g' % vdd, 'I1 ib1 0 DC %g' % (250e-9 * scale), 'I2 ib2 0 DC %g' % (1e-6 * scale),
            bandgap_inst(path, conn)] + trim_lines(trim, 'v(vdd)') + ['.op']
    c, err = s.run_ngspice(job, '\n'.join(deck), ['v(vbg)', 'i(vdd)'])
    rec = dict(job=job, kind=kind, corner=corner, temp_c=temp, vdd_v=vdd, trim=trim, netlist=netlist,
               bias_scale=scale)
    if netlist == 'pex':
        rec['pex_netlist_sha256'] = s.file_sha256('%s/bandgap/layout_pex.spice' % CLEAN)
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    rec['vbg_v'] = c['v(vbg)'][0]
    rec['supply_current_a'] = -c['i(vdd)'][0]
    return rec


def chain_deck(corner, temp, supply, analysis, netlist='schematic', dist=True, bg_ena='v(vdd)', force=None,
               jobdir=None, trim=TRIM_DEFAULT):
    """Full chain deck: compensated biasgen + bandgap (+ distribution)."""
    bg = s.bg_deck(corner, temp, supply, analysis, mode='vbg')
    # biasgen sink codes feeding the bandgap; coarse range; idac2 code 10 to the distribution root
    for bus, code, width in (('bandgap_sink1', SINK1_CODE, 3), ('bandgap_sink2', SINK2_CODE, 2), ('idac2_source', 10, 5)):
        for b in range(width):
            bg = re.sub(r'B%s_%d %s\[%d\] 0 V=\S+' % (bus, b, bus, b),
                        'B%s_%d %s[%d] 0 V=%s' % (bus, b, bus, b, 'v(vdd)' if (code >> b) & 1 else '0'), bg)
    bg = bg.replace('Bcoarse ref_sel_coarse 0 V=0', 'Bcoarse ref_sel_coarse 0 V=v(vdd)')
    # the bandgap replaces the ideal vbg source and the ideal sink loads on its two bias pins
    bg = bg.replace('Vvbg vbg 0 1.2', '* vbg from the bandgap')
    bg = re.sub(r'Bl_bandgap_sink1_ibias .*', 'Vs_ib2 ib2 bandgap_sink1_ibias 0', bg)
    bg = re.sub(r'Bl_bandgap_sink2_ibias .*', 'Vs_ib1 ib1 bandgap_sink2_ibias 0', bg)
    lines = bg.split('\n')
    k = lines.index(analysis)
    path = bandgap_netlist(netlist, jobdir)
    conn = {'dvss': '0', 'dvdd': 'vdd', 'ena': 'bg_ena', 'vbg': 'vbg', 'ibias1_250n': 'ib1', 'ibias2_1u': 'ib2'}
    extra = ['.include ' + path, bandgap_inst(path, conn), 'Bbg_ena bg_ena 0 V=%s' % bg_ena] + trim_lines(trim)
    if force is not None:
        extra.append('Vforce atb0 0 DC %g' % force)
        extra.append('Ratb atb0 vbg %g' % ATB_R)
    if dist:
        inc, dl = d.dist_lines('schematic', en_out='DC 0', en_trunk='DC 0', loads=True)
        dl = [l for l in dl if not l.startswith('Ven_')] + ['Ben_out en_out 0 V=v(vdd)', 'Ben_trk en_trk 0 V=v(vdd)']
        extra += inc + dl
        bg_lines = lines[:k]
        bg_lines = [l.replace('Vl_idac2_source_ibias idac2_source_ibias 0 1',
                              'Vl_idac2_source_ibias idac2_source_ibias root_ref 0') for l in bg_lines]
        lines = bg_lines + lines[k:]
    return '\n'.join(lines[:k] + extra + lines[k:])


def chain_tran_job(corner, temp, vfinal, trise, netlist='schematic', dist=True, hold=None, tmax=None,
                   bg_ena='v(vdd)', kind='chain_tran'):
    hold = hold if hold is not None else max(3e-3, 0.3 * trise)
    tmax = tmax if tmax is not None else (1e-6 if trise <= 100e-6 else min(trise / 100, 2e-4))
    t0 = 1e-6
    job = '%s_%s_%s_%gV_%gs_%s%s' % (kind, corner, temp, vfinal, trise, netlist, '' if dist else '_nodist')
    jd = os.path.join(s.WORK, job)
    deck = chain_deck(corner, temp, 'PWL(0 0 %g 0 %g %g)' % (t0, t0 + trise, vfinal),
                      '.tran %g %g 0 %g' % (min(tmax / 10, 1e-7), t0 + trise + hold, tmax),
                      netlist=netlist, dist=dist, jobdir=jd, bg_ena=bg_ena)
    vecs = ['v(vdd)', 'i(vdd)', 'v(vbg)', 'i(vl_idac2_source_ibias)', 'i(vs_ib1)', 'i(vs_ib2)'] + \
        (d.out_vectors() if dist else [])
    c, err = s.run_ngspice(job, deck, vecs)
    rec = dict(job=job, kind=kind, corner=corner, temp_c=temp, vdd_v=vfinal, trise_s=trise, netlist=netlist,
               distribution=dist, tmax_s=tmax, hold_s=hold, trim=TRIM_DEFAULT,
               sink_codes={'bandgap_sink1': SINK1_CODE, 'bandgap_sink2': SINK2_CODE})
    if netlist == 'pex':
        rec['pex_netlist_sha256'] = s.file_sha256('%s/bandgap/layout_pex.spice' % CLEAN)
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    t, vbg = c['time'], c['v(vbg)']
    rec['vbg_final_v'] = vbg[-1]
    rec['idac2_final_a'] = c['i(vl_idac2_source_ibias)'][-1]
    rec['bandgap_bias_ibias1_a'] = c['i(vs_ib1)'][-1]
    rec['bandgap_bias_ibias2_a'] = c['i(vs_ib2)'][-1]
    rec['supply_current_final_a'] = -c['i(vdd)'][-1]
    rec['supply_current_peak_a'] = max(-x for x in c['i(vdd)'])
    if dist:
        outs = [c[v][-1] for v in d.out_vectors()]
        rec['dist_out_min_a'], rec['dist_out_max_a'] = min(outs), max(outs)
    t90 = s.t_cross_up(t, c['v(vdd)'], 0.9 * vfinal)
    bad = [k for k in range(len(t)) if abs(vbg[k] - vbg[-1]) > 0.01 * abs(vbg[-1])]
    rec['vbg_settle_1pct_after_vdd90_s'] = (t[bad[-1] + 1] - t90) if (bad and t90 and bad[-1] + 1 < len(t)) else 0.0
    tail = [vbg[k] for k in range(len(t)) if t[k] >= t[-1] - 0.2 * hold]
    rec['vbg_tail_pp_v'] = max(tail) - min(tail)
    rec['started'] = 1.0 < vbg[-1] < 1.4 and rec['vbg_tail_pp_v'] < 0.005
    return rec


def atb_force_job(corner='typical', temp=27, vdd=3.3, bg_on=False):
    """ATB0 fallback: 1.2 V forced on the bandgap output node through the force leaf (2.35 kohm)."""
    job = 'chain_atbforce_%s_%s_%gV_bg%s' % (corner, temp, vdd, 'on' if bg_on else 'off')
    jd = os.path.join(s.WORK, job)
    deck = chain_deck(corner, temp, 'DC %g' % vdd, '.op', dist=True, bg_ena='v(vdd)' if bg_on else '0',
                      force=1.2, jobdir=jd)
    c, err = s.run_ngspice(job, deck, ['v(vbg)', 'i(vforce)', 'i(vl_idac2_source_ibias)'] + d.out_vectors())
    rec = dict(job=job, kind='chain_atb_force', corner=corner, temp_c=temp, vdd_v=vdd, bandgap_enabled=bg_on,
               force_v=1.2, force_series_ohm=ATB_R)
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    rec['vbg_v'] = c['v(vbg)'][0]
    rec['force_current_a'] = -c['i(vforce)'][0]
    rec['idac2_a'] = c['i(vl_idac2_source_ibias)'][0]
    outs = [c[v][0] for v in d.out_vectors()]
    rec['dist_out_min_a'], rec['dist_out_max_a'] = min(outs), max(outs)
    return rec


def probe_job(corner='typical', temp=27, vdd=3.3, event='bg_ena'):
    """Fine-step (5 ns) check of the bandgap buffer + biasgen loop together: bandgap ena 0->1 at 50 us
    on a settled supply, or a 1 us supply ramp."""
    job = 'chain_probe_%s_%s_%s_%gV' % (event, corner, temp, vdd)
    jd = os.path.join(s.WORK, job)
    if event == 'bg_ena':
        sup, ena = 'PWL(0 0 1e-6 0 11e-6 %g)' % vdd, 'v(vdd)*min(max((time-50e-6)/1e-6,0),1)'
    else:
        sup, ena = 'PWL(0 0 1e-6 0 2e-6 %g)' % vdd, 'v(vdd)'
    tstop = 600e-6
    deck = chain_deck(corner, temp, sup, '.tran 1e-9 %g 0 5e-9' % tstop, dist=False, bg_ena=ena, jobdir=jd)
    c, err = s.run_ngspice(job, deck, ['v(vbg)', 'i(vl_idac2_source_ibias)'])
    rec = dict(job=job, kind='chain_probe', event=event, corner=corner, temp_c=temp, vdd_v=vdd, tstop_s=tstop,
               tmax_s=5e-9)
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    t, i2, vbg = c['time'], c['i(vl_idac2_source_ibias)'], c['v(vbg)']
    seg = [k for k in range(len(t)) if t[k] >= tstop - 50e-6]
    rec['idac2_last50us_pp_a'] = max(i2[k] for k in seg) - min(i2[k] for k in seg)
    rec['vbg_last50us_pp_v'] = max(vbg[k] for k in seg) - min(vbg[k] for k in seg)
    rec['idac2_final_a'], rec['vbg_final_v'] = i2[-1], vbg[-1]
    rec['settled'] = rec['idac2_last50us_pp_a'] <= 0.02 * abs(i2[-1]) and rec['vbg_last50us_pp_v'] < 0.005
    return rec


def plan():
    J = []
    for t in range(0, 17, 2):
        J.append((standalone_job, ('typical', 27, 3.3, t, 'schematic', 1.0, 'bgap_trim')))
    for c in s.CORNERS:
        for T in (-40, 0, 22, 27, 32, 85, 125):
            J.append((standalone_job, (c, T, 3.3)))
        for sc in (0.25, 0.5):
            J.append((standalone_job, (c, 27, 3.3, TRIM_DEFAULT, 'schematic', sc, 'bgap_biasscale')))
    J.append((standalone_job, ('typical', 27, 3.3, TRIM_DEFAULT, 'pex')))
    # function window: full chain, settled after a 100 us ramp
    for c, T, v in [('typical', 27, 3.3)] + [(c, T, v) for c in s.CORNERS for T in (22, 32) for v in (3.15, 3.35)]:
        J.append((chain_tran_job, (c, T, v, 100e-6)))
    J.append((chain_tran_job, ('typical', 27, 3.3, 100e-6, 'pex')))
    # safety: bandgap start-up (biasgen sinks + bandgap + biasgen, no distribution) over ramp rates
    for c, T in (('typical', 27), ('typical', 0), ('typical', 85), ('ff', 0), ('ff', 85), ('ss', 0), ('ss', 85)):
        for tr in (1e-6, 100e-6, 10e-3, 1.0):
            J.append((chain_tran_job, (c, T, 3.63, tr, 'schematic', False, None, None, 'v(vdd)', 'startup')))
    for c, T in (('typical', 27), ('ss', 85), ('ff', 0)):
        J.append((atb_force_job, (c, T, 3.3, False)))
    J.append((atb_force_job, ('typical', 27, 3.3, True)))
    J.append((probe_job, ('typical', 27, 3.3, 'bg_ena')))
    J.append((probe_job, ('typical', 27, 3.3, 'ramp1us')))
    J.append((probe_job, ('ff', 22, 3.35, 'bg_ena')))
    J.append((probe_job, ('ss', 32, 3.15, 'bg_ena')))
    return J


def main():
    res = []
    with ThreadPoolExecutor(int(os.environ.get('SIM_JOBS', '3'))) as ex:
        for r in ex.map(lambda j: j[0](*j[1]), plan()):
            res.append(r)
            print('done', r['job'], 'ERROR' if 'error' in r else '', flush=True)
    json.dump(res, open('/work/sim/results_bandgap.json', 'w'), indent=1)
    print('wrote /work/sim/results_bandgap.json')


if __name__ == '__main__':
    main()
