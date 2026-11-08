#!/usr/bin/env python3
"""Simulations of the bias distribution (root + island banks), schematic and
capacitance-extracted netlists, standalone (ideal 10 uA reference) and chained
behind the compensated biasgen.  Runs in the pinned analog image; writes
/work/sim/results_dist.json.

Consumers are modelled as voltage sources at 0.95 V (the NMOS diode level the
rf_tx/rf_rx READMEs give for their IBIAS pins) so the output current can be
read directly; a compliance sweep covers 0.4-2.4 V.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/src/flow')
import sim_core_support as s  # noqa: E402  (models(), run_ngspice(), bg_deck())

GEN = '/src/distribution/generated'
import circuits_dist  # noqa: E402
ISL = {k: len(v) for k, v in circuits_dist.ISLANDS.items()}
VLOAD = 0.95


def ports(path, name):
    return s.subckt_ports(path, name)


def netfile(cell, netlist):
    return '%s/%s.%s' % (GEN, cell, 'spice' if netlist == 'schematic' else 'ext.spice')


def dist_lines(netlist, en_trunk='1', en_out='1', visl='vdd', loads=True, vload=VLOAD):
    """loads=True: ideal 0.95 V sources (read the current directly);
    loads='diode': each output drives an NMOS diode (nfet_03v3 4/1 um, ~0.9 V at 10 uA) on the
    same island rail domain, through a 0 V sense source - used whenever the island rail can be off."""
    """Root + five banks; returns (include lines, instance lines)."""
    inc = ['.include ' + netfile('pt_bias_root', netlist)]
    for n in sorted(set(ISL.values())):
        inc.append('.include ' + netfile('pt_bias_bank%d' % n, netlist))
    rp = ports(netfile('pt_bias_root', netlist), 'pt_bias_root')
    conn = {'VSS': '0', 'ROOT_REF': 'root_ref'}
    for i in ISL:
        conn['EN_' + i.upper()] = 'en_trk'
        conn['TRK_' + i.upper()] = 'trk_' + i
    lines = ['Xroot ' + ' '.join(conn[p] for p in rp) + ' pt_bias_root',
             'Ven_trk en_trk 0 %s' % ('DC 0' if en_trunk == '0' else 'DC 0' if en_trunk is None else en_trunk)]
    lines.append('Ven_out en_out 0 %s' % en_out)
    for i, n in ISL.items():
        bp = ports(netfile('pt_bias_bank%d' % n, netlist), 'pt_bias_bank%d' % n)
        c = {'VDD': visl, 'VSS': '0', 'TRK': 'trk_' + i}
        for k in range(n):
            c['EN%d' % k] = 'en_out'
            c['OUT%d' % k] = 'o_%s%d' % (i, k)
            if loads == 'diode':
                lines.append('Vl_%s%d o_%s%d d_%s%d 0' % (i, k, i, k, i, k))
                lines.append('Xd_%s%d d_%s%d d_%s%d 0 0 nfet_03v3 w=4u l=1u' % (i, k, i, k, i, k))
            elif loads:
                lines.append('Vl_%s%d o_%s%d 0 %g' % (i, k, i, k, vload))
        lines.append('Xb_%s ' % i + ' '.join(c[p] for p in bp) + ' pt_bias_bank%d' % n)
    return inc, lines


def out_vectors():
    return ['i(vl_%s%d)' % (i, k) for i, n in ISL.items() for k in range(n)]


def dc_job(corner, temp, vdd, netlist='schematic', en_trunk='v(vdd)', en_out='v(vdd)', visl='vdd', ref='ideal',
           loads=True):
    job = 'dist_dc_%s_%s_%gV_%s_trk%s_out%s_%s_%s' % (corner, temp, vdd, netlist, en_trunk != '0', en_out != '0',
                                                      visl, ref)
    job = job.replace('(', '').replace(')', '')
    inc, lines = dist_lines(netlist, en_out=en_out if en_out == '0' else 'DC %g' % vdd,
                            en_trunk=None, visl=visl, loads=loads)
    if loads == 'diode':
        job += '_diodeload'
    lines = [l for l in lines if not l.startswith('Ven_trk')]
    lines.append('Ven_trk en_trk 0 DC %s' % ('0' if en_trunk == '0' else '%g' % vdd))
    deck = [s.models(corner)] + inc + ['.temp %g' % temp, '.option method=gear', 'Vdd vdd 0 DC %g' % vdd,
                                       'Vvisl_off visl_off 0 0']
    if visl == 'visl_off':
        pass
    if ref == 'ideal':
        deck.append('Iref vdd root_ref DC 10u')
        deck += lines + ['.op']
        vecs = out_vectors() + ['i(vdd)', 'v(root_ref)'] + ['v(trk_%s)' % i for i in ISL]
        c, err = s.run_ngspice(job, '\n'.join(deck), vecs)
    else:
        # chained behind the compensated biasgen: bandgap mode, coarse, idac2 = 10 -> root_ref
        bg = s.bg_deck(corner, temp, 'DC %g' % vdd, '.op', mode='vbg')
        bg = bg.replace('Bcoarse ref_sel_coarse 0 V=0', 'Bcoarse ref_sel_coarse 0 V=v(vdd)')
        for b in range(5):
            bg = bg.replace('Bidac2_source_%d idac2_source[%d] 0 V=v(vdd)' % (b, b),
                            'Bidac2_source_%d idac2_source[%d] 0 V=0' % (b, b))
        for b in (1, 3):  # code 10 = 0b01010
            bg = bg.replace('Bidac2_source_%d idac2_source[%d] 0 V=0' % (b, b),
                            'Bidac2_source_%d idac2_source[%d] 0 V=v(vdd)' % (b, b))
        bg = bg.replace('Vl_idac2_source_ibias idac2_source_ibias 0 1', 'Vl_idac2_source_ibias idac2_source_ibias root_ref 0')
        bgl = bg.split('\n')
        k = bgl.index('.op')
        deck = bgl[:k] + inc + lines + bgl[k:]
        vecs = out_vectors() + ['i(vdd)', 'v(root_ref)', 'i(vl_idac2_source_ibias)']
        c, err = s.run_ngspice(job, '\n'.join(deck), vecs)
    rec = dict(job=job, kind='dist_dc', corner=corner, temp_c=temp, vdd_v=vdd, netlist=netlist,
               trunk_enabled=en_trunk != '0', outputs_enabled=en_out != '0', island_rail=visl, reference=ref,
               loads='nmos_diode' if loads == 'diode' else 'ideal_0.95V')
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    outs = {v[5:-1]: c[v][0] for v in out_vectors()}   # current delivered into each consumer (A)
    rec['outputs_a'] = outs
    rec['out_min_a'], rec['out_max_a'] = min(outs.values()), max(outs.values())
    rec['supply_current_a'] = -c['i(vdd)'][0]
    rec['root_ref_v'] = c['v(root_ref)'][0]
    if 'i(vl_idac2_source_ibias)' in c:
        rec['biasgen_idac2_a'] = c['i(vl_idac2_source_ibias)'][0]
    return rec


def compliance_job(corner='typical', temp=27, vdd=3.3, netlist='schematic'):
    job = 'dist_comp_%s_%s_%gV_%s' % (corner, temp, vdd, netlist)
    inc, lines = dist_lines(netlist, en_out='DC %g' % vdd, en_trunk='DC %g' % vdd)
    lines = [l.replace('Vl_rf0 o_rf0 0 0.95', 'Vl_rf0 o_rf0 0 DC 0.95') for l in lines]
    deck = [s.models(corner)] + inc + ['.temp %g' % temp, '.option method=gear', 'Vdd vdd 0 DC %g' % vdd,
                                       'Iref vdd root_ref DC 10u'] + lines + ['.dc Vl_rf0 0.2 2.8 0.05']
    c, err = s.run_ngspice(job, '\n'.join(deck), ['i(vl_rf0)', 'i(vl_rf1)'])
    rec = dict(job=job, kind='dist_compliance', corner=corner, temp_c=temp, vdd_v=vdd, netlist=netlist)
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    sw = c[list(c)[0]]
    i0 = list(c['i(vl_rf0)'])
    iref = i0[min(range(len(sw)), key=lambda k: abs(sw[k] - VLOAD))]
    ok = [sw[k] for k in range(len(sw)) if abs(i0[k] - iref) <= 0.05 * iref]
    rec['i_at_0p95_a'] = iref
    rec['within_5pct_vout_range_v'] = [min(ok), max(ok)] if ok else None
    rec['neighbour_rf1_change_pct'] = (max(c['i(vl_rf1)']) - min(c['i(vl_rf1)'])) / iref * 100
    return rec


def atb_force_job(corner='typical', temp=27, vdd=3.3, netlist='schematic'):
    """Trunks disabled (EN_<island>=0); bench sinks 10 uA from TRK_RF through the ATB force path."""
    job = 'dist_atb_%s_%s_%gV_%s' % (corner, temp, vdd, netlist)
    inc, lines = dist_lines(netlist, en_out='DC %g' % vdd, en_trunk='DC 0')
    deck = [s.models(corner)] + inc + ['.temp %g' % temp, '.option method=gear', 'Vdd vdd 0 DC %g' % vdd,
                                       'Iref vdd root_ref DC 10u', 'Iforce trk_rf 0 DC 10u'] + lines + ['.op']
    c, err = s.run_ngspice(job, '\n'.join(deck), out_vectors() + ['v(trk_rf)'])
    rec = dict(job=job, kind='dist_atb_force', corner=corner, temp_c=temp, vdd_v=vdd, netlist=netlist)
    if c is None:
        rec['error'] = err[-1500:]
        return rec
    outs = {v[5:-1]: c[v][0] for v in out_vectors()}
    rec['rf_outputs_a'] = {k: v for k, v in outs.items() if k.startswith('rf')}
    rec['other_islands_max_a'] = max(abs(v) for k, v in outs.items() if not k.startswith('rf'))
    rec['trk_rf_sense_v'] = c['v(trk_rf)'][0]
    return rec


def ramp_job(corner='typical', temp=27, trise=10e-6, netlist='schematic', vmax=3.63):
    """Safety: VDD 0 -> vmax with every enable tied low (reset) and then with all tied high."""
    out = []
    for en in ('low', 'high'):
        job = 'dist_ramp_%s_%s_%gs_%s_en%s' % (corner, temp, trise, netlist, en)
        inc, lines = dist_lines(netlist, en_out='DC 0', en_trunk='DC 0', loads='diode')
        lines = [l for l in lines if not l.startswith('Ven_')]
        lines += ['Ben_out en_out 0 V=%s' % ('v(vdd)' if en == 'high' else '0'),
                  'Ben_trk en_trk 0 V=%s' % ('v(vdd)' if en == 'high' else '0')]
        deck = [s.models(corner)] + inc + ['.temp %g' % temp, '.option method=gear',
                                           'Vdd vdd 0 PWL(0 0 1e-6 0 %g %g)' % (1e-6 + trise, vmax),
                                           'Bref vdd root_ref I=10u*min(v(vdd)/3.3,1)'] + lines + \
            ['.tran 1e-8 %g 0 %g' % (1e-6 + trise + 200e-6, min(trise / 20, 1e-6))]
        c, err = s.run_ngspice(job, '\n'.join(deck), ['v(vdd)', 'i(vdd)'] + out_vectors())
        rec = dict(job=job, kind='dist_ramp', corner=corner, temp_c=temp, trise_s=trise, vmax_v=vmax,
                   enables=en, netlist=netlist)
        if c is None:
            rec['error'] = err[-1500:]
        else:
            t = c['time']
            rec['peak_supply_current_a'] = max(-x for x in c['i(vdd)'])
            rec['final_supply_current_a'] = -c['i(vdd)'][-1]
            rec['final_out_max_a'] = max(c[v][-1] for v in out_vectors())
            rec['peak_out_a'] = max(x for v in out_vectors() for x in c[v])
        out.append(rec)
    return out


def plan():
    J = []
    pts = [('typical', 27, 3.3)] + [(c, T, v) for c in s.CORNERS for T in (22, 32) for v in (3.15, 3.35)]
    for c, T, v in pts:
        J.append((dc_job, (c, T, v, 'schematic')))
        J.append((dc_job, (c, T, v, 'pex')))
        J.append((dc_job, (c, T, v, 'schematic', 'v(vdd)', 'v(vdd)', 'vdd', 'biasgen')))
        J.append((dc_job, (c, T, v, 'schematic', 'v(vdd)', 'v(vdd)', 'vdd', 'ideal', 'diode')))
    J.append((dc_job, ('typical', 27, 3.3, 'pex', 'v(vdd)', 'v(vdd)', 'vdd', 'biasgen')))
    for c in s.CORNERS:
        for T in (0, 85):
            J.append((dc_job, (c, T, 3.63, 'schematic', 'v(vdd)', '0')))        # outputs disabled
            J.append((dc_job, (c, T, 3.63, 'schematic', '0', 'v(vdd)')))        # trunks disabled
            J.append((dc_job, (c, T, 3.63, 'schematic', 'v(vdd)', 'v(vdd)', 'visl_off', 'ideal', 'diode')))  # island rail off
    J.append((compliance_job, ()))
    J.append((compliance_job, ('typical', 27, 3.3, 'pex')))
    J.append((atb_force_job, ()))
    J.append((atb_force_job, ('typical', 27, 3.3, 'pex')))
    for c, T in (('typical', 27), ('ff', 0), ('ss', 85)):
        J.append((ramp_job, (c, T, 10e-6)))
    J.append((ramp_job, ('typical', 27, 10e-6, 'pex')))
    return J


def main():
    res = []
    with ThreadPoolExecutor(int(os.environ.get('SIM_JOBS', '3'))) as ex:
        for r in ex.map(lambda j: j[0](*j[1]), plan()):
            res += r if isinstance(r, list) else [r]
            for x in (r if isinstance(r, list) else [r]):
                print('done', x['job'], 'ERROR' if 'error' in x else '', flush=True)
    json.dump(res, open('/work/sim/results_dist.json', 'w'), indent=1)
    print('wrote /work/sim/results_dist.json')


if __name__ == '__main__':
    main()
