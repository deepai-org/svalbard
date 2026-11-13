#!/usr/bin/env python3
"""Always-on audit: deck generator (audit benches only; reads design files, never writes them).

usage: gen.py <group>   groups: aosc por isw bias
Decks are written to /work/<group>/<name>.sp (container paths); run with run.sh.
"""
import re
import sys
from pathlib import Path

W = Path(__file__).resolve().parent
NG = '/foss/pdks/gf180mcuD/libs.tech/ngspice'
LIB = {'tt': 'typical', 'ff': 'ff', 'ss': 'ss'}


def hdr(corner, temp, opts='.option gmin=1e-15 reltol=1e-4', sc=False):
    c = LIB[corner]
    s = (f'* audit deck\n.include {NG}/design.ngspice\n.lib {NG}/sm141064.ngspice {c}\n'
         f'.lib {NG}/sm141064.ngspice res_{c}\n.lib {NG}/sm141064.ngspice mimcap_{c}\n'
         f'.lib {NG}/sm141064.ngspice diode_{c}\n.lib {NG}/sm141064.ngspice bjt_{c}\n')
    if sc:
        s += '.include /foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice\n'
    return s + f'.temp {temp}\n{opts}\n'


def put(group, name, text):
    d = W / group
    d.mkdir(exist_ok=True)
    (d / f'{name}.sp').write_text(text)
    (d / '.spiceinit').write_text('set ngbehavior=hsa\nset ng_nomodcheck\nset num_threads=1\n')


# ------------------------------------------------------------------ aosc
def aosc():
    ext = '/proj/analog/timing/generated/aosc.ext.spice'
    sch = '/proj/analog/timing/aosc.spice'

    def meas(t0, t1, v):
        # oscillation detector: rising edges of CLK in [t0, t1]
        return (f'.control\nrun\nmeas tran t1 when v(clk)={v/2} rise=1 td={t0}\n'
                f'meas tran t11 when v(clk)={v/2} rise=11 td={t0}\n'
                f'meas tran clk_avg avg v(clk) from={t0} to={t1}\n'
                f'meas tran x_avg avg v(x) from={t0} to={t1}\n'
                f'meas tran x_pp pp v(x) from={t0} to={t1}\n'
                f'meas tran ivdd_avg avg i(vdd) from={t0} to={t1}\n'
                'if ( t11 > t1 )\n let f_osc = 10/(t11-t1)\n print f_osc\nend\n.endc\n.end\n')

    for net, inc in (('ext', ext), ('sch', sch)):
        for corner, temp, v in (('tt', 27, 3.3), ('ss', 0, 3.15), ('ff', 85, 3.63)):
            tag = f'{net}_{corner}_{temp}_{v}'
            base = hdr(corner, temp) + f'.include {inc}\nX1 en clk x vdd 0 pt_aosc\nCL clk 0 20f\n'
            # (1) known answer: EN step on a settled supply (the published bench) -> ~47.7 MHz tt
            put('aosc', f'step_{tag}', base + f'VDD vdd 0 {v}\nVEN en 0 pwl(0 0 5n 0 5.1n {v})\n.tran 20p 400n\n'
                + meas(100e-9, 400e-9, v))
            # (2) negative control: EN stays 0 -> detector must report no oscillation
            if corner == 'tt':
                put('aosc', f'neg_{tag}', base + f'VDD vdd 0 {v}\nVEN en 0 0\n.tran 20p 400n\n' + meas(100e-9, 400e-9, v))
            # (3) real reset state: core.aosc.enable resets to 1 -> EN follows VDD during the ramp
            for tr in (1e-6, 10e-6, 100e-6, 1e-3):
                tend = tr + 1.5e-6
                put('aosc', f'ramp_{tag}_{tr:g}', base + f'VDD vdd 0 pwl(0 0 {tr} {v})\nREN vdd en 100\n'
                    f'.tran 50p {tend}\n' + meas(tr + 1.0e-6, tend, v))
            # (4) EN from a std-cell-like driver: low until VDD = 1.0 V, then follows VDD
            for tr in (10e-6, 1e-3):
                tend = tr + 1.5e-6
                put('aosc', f'rampgate_{tag}_{tr:g}', base + f'VDD vdd 0 pwl(0 0 {tr} {v})\n'
                    "BEN en 0 V = v(vdd) > 1.0 ? v(vdd) : 0\n"
                    f'.tran 50p {tend}\n' + meas(tr + 1.0e-6, tend, v))
    # (5) lock state existence (schematic, internal nodes reachable): both caps high, both latch outputs high
    for corner, temp, v in (('tt', 27, 3.3),):
        tag = f'sch_{corner}_{temp}_{v}'
        base = hdr(corner, temp) + f'.include {sch}\nX1 en clk x vdd 0 pt_aosc\nCL clk 0 20f\n'
        put('aosc', f'lockic_{tag}', base + f'VDD vdd 0 {v}\nVEN en 0 {v}\n'
            f'.ic v(x)={v} v(x1.xb)={v} v(x1.q)={v} v(x1.qb)={v} v(x1.da)=0 v(x1.db)=0 v(x1.na)=0 v(x1.nb)=0\n'
            '.tran 20p 2u uic\n' + meas(1.0e-6, 2e-6, v))
        # brownout while running: VDD 3.3 -> vdip -> 3.3 with EN following VDD
        for vdip in (0.3, 0.6, 0.9, 1.2):
            put('aosc', f'brown_{tag}_{vdip}', base
                + f'VDD vdd 0 pwl(0 0 1u {v} 3u {v} 13u {vdip} 23u {vdip} 33u {v})\nREN vdd en 100\n'
                '.tran 50p 35u\n' + meas(34e-6, 35e-6, v))


# ------------------------------------------------------------------ POR
def por():
    src = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/core_support/por/netlist/'
               'schematic/gf180mcu_ocd_ip__por.spice').read_text()
    # audit copy: a leakage current source on the hold-off node (vcap -> vss) and the node exported as a
    # global for probing. The vendored file is not touched.
    mod = src.replace('XC1 vcap vss cap_mim_2f0_m4m5_noshield',
                      'Ileak_audit vcap vss {ileak_audit}\nXC1 vcap vss cap_mim_2f0_m4m5_noshield', 1)
    assert mod != src
    (W / 'por').mkdir(exist_ok=True)
    (W / 'por' / 'por_leak.spice').write_text(mod)

    def deck(corner, temp, v, tr, ileak=0.0, ena='vdd', net='sch', tstop=None, extra=''):
        tstop = tstop or (tr + 0.09)
        if net == 'sch':
            inc = '.include /work/por/por_leak.spice'
            opts = '.option method=gear reltol=1e-4'
        else:
            inc = '.include /clean/por/layout_pex.spice'
            opts = '.option method=gear reltol=1e-3 rshunt=1e12 cshunt=1e-17'
        vena = 'Vena ena vdd 0' if ena == 'vdd' else 'Vena ena 0 0'
        tmax = max(min(tstop / 2000, 50e-6), 1e-7)
        return (hdr(corner, temp, opts, sc=True) + f'.param ileak_audit={ileak}\n{inc}\n'
                f'Vdd vdd 0 pwl(0 0 {tr} {v})\n{vena}\nX1 vdd ena por_unbuf 0 porb por gf180mcu_ocd_ip__por\n'
                f'Cpb porb 0 1p\nCp por 0 1p\n{extra}'
                + ('.save v(vdd) v(porb) v(por) i(vdd)' + (' v(x1.vcap)' if net == 'sch' else '') + '\n')
                + f'.tran {min(tmax / 10, 1e-6)} {tstop} 0 {tmax}\n'
                '.control\nrun\n'
                f'meas tran t_rel when v(porb)={v/2} rise=last\n'
                f'meas tran porb_end find v(porb) at={tstop*0.999}\n'
                f'meas tran porb_at_1v find v(porb) when v(vdd)=1.0 rise=1\n'
                f'meas tran vdd_at_rel find v(vdd) when v(porb)=0.5 rise=1\n'
                f'meas tran ivdd_end find i(vdd) at={tstop*0.999}\n'
                + ('meas tran vcap_end find v(x1.vcap) at=%g\n' % (tstop * 0.999) if net == 'sch' else '')
                + '.endc\n.end\n')

    # known answer + negative control
    put('por', 'kn_tt_27_3.3_1ms', deck('tt', 27, 3.3, 1e-3))
    put('por', 'neg_ena0_tt_27_3.3_1ms', deck('tt', 27, 3.3, 1e-3, ena='0'))
    # ramps x corners (safety, schematic)
    for corner, temp, v in (('tt', 27, 3.3), ('ff', 85, 3.63), ('ss', 0, 3.63), ('ss', 0, 3.15), ('ff', 0, 3.63)):
        for tr in (10e-6, 1e-3, 1.0):
            put('por', f'ramp_{corner}_{temp}_{v}_{tr:g}', deck(corner, temp, v, tr))
    # extracted at the safety corners the README says were schematic-only
    for corner, temp, v in (('ff', 85, 3.63), ('ss', 0, 3.15), ('tt', 27, 3.3)):
        put('por', f'pex_{corner}_{temp}_{v}_1ms', deck(corner, temp, v, 1e-3, net='pex'))
    # hold-off node leakage injection: trickle is ~0.4 nA
    for corner, temp, v in (('tt', 27, 3.3), ('ss', 0, 3.15), ('ff', 85, 3.63), ('ss', 85, 3.15)):
        for il in (50e-12, 100e-12, 200e-12, 300e-12, 400e-12, 600e-12):
            put('por', f'leak_{corner}_{temp}_{v}_{il*1e12:g}pA', deck(corner, temp, v, 1e-3, ileak=il, tstop=0.4))


# ------------------------------------------------------------------ island switches
def isw():
    names = ('wired', 'rf', 'pll', 'conv', 'debug')

    def base(n, corner, temp):
        return (hdr(corner, temp) + f'.include /isl/pex/isw_{n}/isw_{n}.pex.spice\n'
                f'XI VDD VISL 0 EN ISO PG isw_{n}_pex\n')
    for n in names:
        for corner, temp in (('ff', 85), ('tt', 27), ('ss', 0), ('ff', 0)):
            tag = f'{n}_{corner}_{temp}'
            # (a) off leakage, EN driven 0, island held at 0 V (loads hold it), 3.63 V
            put('isw', f'leak_{tag}', base(n, corner, temp) + 'VDD VDD 0 3.63\nVEN EN 0 0\nVISL VISL 0 0\n'
                '.control\nop\nlet ileak = i(visl)\nprint ileak\nlet ivdd = -i(vdd)\nprint ivdd\n'
                'let v_iso = v(iso)\nprint v_iso\nlet v_pg = v(pg)\nprint v_pg\n.endc\n.end\n')
            # (b) slow ramp == DC sweep of VDD, EN floating (only the cell's pull-down), island unloaded (1 Gohm)
            put('isw', f'dcfloat_{tag}', base(n, corner, temp) + 'VDD VDD 0 0\nRL VISL 0 1e9\nCEN EN 0 1f\n'
                '.control\ndc VDD 0 3.63 0.03\nmeas dc visl_max max v(visl)\nmeas dc en_max max v(en)\n'
                'meas dc iso_end find v(iso) at=3.6\nmeas dc ivdd_end find i(vdd) at=3.6\n'
                'meas dc visl_end find v(visl) at=3.6\n.endc\n.end\n')
        # (c) transient ramps, EN floating, extracted, ff/85/3.63: 10 us, 1 ms, 1 s
        for corner, temp in (('ff', 85), ('ss', 0)):
            for tr in (10e-6, 1e-3, 1.0):
                tend = tr * 1.5 + 50e-6
                put('isw', f'ramp_{n}_{corner}_{temp}_{tr:g}', base(n, corner, temp)
                    + f'VDD VDD 0 pwl(0 0 {tr} 3.63)\nCI VISL 0 150p\nRL VISL 0 1e9\n'
                    f'.tran {tr/1000} {tend} 0 {tr/200}\n.control\nrun\nmeas tran visl_max max v(visl)\n'
                    f'meas tran en_max max v(en)\nmeas tran iso_end find v(iso) at={tend*0.99}\n'
                    f'meas tran visl_end find v(visl) at={tend*0.99}\n.endc\n.end\n')
    # (d) negative control: EN tied to VDD must bring the island up (detector can fail)
    put('isw', 'neg_en1_conv_ff_85', base('conv', 'ff', 85) + 'VDD VDD 0 pwl(0 0 1e-3 3.63)\nREN VDD EN 100\n'
        'CI VISL 0 150p\nRL VISL 0 1e9\n.tran 1u 1.6e-3 0 5u\n.control\nrun\nmeas tran visl_max max v(visl)\n'
        'meas tran iso_end find v(iso) at=1.58e-3\nmeas tran visl_end find v(visl) at=1.58e-3\n.endc\n.end\n')


# ------------------------------------------------------------------ bias chain
def bias():
    text = (W / 'bias' / 'pt_core_bias.spice').read_text()
    m = re.search(r'^\.subckt pt_core_bias (.*?)$((?:\n\+.*)*)', text, re.M)
    pins = (m.group(1) + ' ' + m.group(2).replace('\n+', ' ')).split()
    islands = ['rf', 'conv', 'pll', 'wired', 'debug']
    outs = [p for p in pins if p.startswith('BIAS_')]

    def deck(corner, temp, v, mode, fault=None, tr=10e-6, rail_off=None):
        """mode: 'reset' (all controls at register reset, islands off), 'seq' (README bring-up sequence),
        'stuck' (every enable high from t=0, supply ramps)."""
        L = [hdr(corner, temp, '.option gmin=1e-14 reltol=1e-3 method=gear'), '.include /work/bias/pt_core_bias.spice',
             f'VDD VDD 0 pwl(0 0 {tr} {v})']
        t_a, t_b, t_c = tr + 200e-6, tr + 400e-6, tr + 600e-6   # ena+bgap ; ref_sel ; islands+dist+blocks
        tend = tr * 1.2 + 1.2e-3

        def ctl(net, kind):
            # kind: 0 const low, 1 follows VDD, 'a'/'b'/'c' rises at that sequence step
            if kind == 0:
                L.append(f'V{net} {net} 0 0')
            elif kind == 1 or mode == 'stuck':
                L.append(f'E{net} {net} 0 VDD 0 1')
            elif mode == 'reset':
                L.append(f'V{net} {net} 0 0')
            else:
                t = dict(a=t_a, b=t_b, c=t_c)[kind]
                L.append(f'V{net} {net} 0 pwl(0 0 {t} 0 {t+1e-7} {v})')
        seq = {}
        for p in pins:
            if p in ('VDD', 'VSS') or p in outs:
                continue
            if p.startswith('RAIL_'):
                isl = p[5:]
                if rail_off == isl:
                    L.append(f'V{p} {p} 0 0')
                elif mode == 'reset':
                    L.append(f'V{p} {p} 0 0')
                elif mode == 'stuck':
                    L.append(f'E{p} {p} 0 VDD 0 1')
                else:
                    L.append(f'V{p} {p} 0 pwl(0 0 {t_c} 0 {t_c+5e-6} {v})')
            elif p.startswith('ON_') or p.startswith('EN_') or p.startswith('C_core_refchain_dist_en'):
                ctl(p, 'c')
            elif p in ('C_core_biasgen_ena', 'C_core_refchain_bgap_ena'):
                ctl(p, 'a')
            elif p in ('C_core_biasgen_ref_sel_vbg', 'C_core_biasgen_ref_sel_coarse'):
                ctl(p, 'b')
            elif p == 'C_core_biasgen_ref_sel_fine':
                ctl(p, 0)
            elif p.startswith('C_core_biasgen_idac2_source_'):
                ctl(p, 1 if int(p[-1]) in (1, 3) else 0)          # reset code 10
            elif p.startswith('C_core_biasgen_bandgap_sink'):
                ctl(p, 1)                                           # reset 7 / 3
            elif p.startswith('C_core_refchain_bgap_trim_'):
                ctl(p, 1 if int(p.rsplit('_', 1)[1]) < 8 else 0)    # reset count 8
            elif p.startswith('C_core_biasgen_'):
                ctl(p, 0)                                           # idac1, voltgen: 0
            elif p in ('ROOT_REF', 'VREF0', 'VCM', 'VBG', 'IDAC1', 'VGEN_SOURCE', 'VGEN_SINK1', 'VGEN_SINK2') \
                    or p.startswith('TRK_'):
                pass                                                # observation nodes, left open
            else:
                raise SystemExit('unclassified pin ' + p)
        L.append('X1 ' + ' '.join('0' if p == 'VSS' else p for p in pins) + ' pt_core_bias')
        # consumers: NMOS diode (pll_ring.XNB model, 4/2 um) behind a 0 V ammeter
        for o in outs:
            L.append(f'Vm_{o} {o} d_{o} 0')
            L.append(f'XN_{o} d_{o} d_{o} 0 0 nfet_03v3 w=4u l=2u')
        for n in ('IDAC1', 'VGEN_SOURCE', 'VGEN_SINK1', 'VGEN_SINK2'):
            L.append(f'R{n} {n} 0 1e9')
        if fault:
            a, b = fault
            L.append(f'Rfault {a} {b} 1')
        te = tend * 0.995
        L.append(f'.tran {tend/2000} {tend} 0 {max(tend/4000, 2e-7)}')
        L.append('.control\nrun')
        for o in outs:
            L.append(f'meas tran i_{o.lower()} find i(vm_{o.lower()}) at={te}')
        for n in ('VBG', 'ROOT_REF', 'VREF0', 'VCM', 'TRK_RF', 'TRK_CONV', 'TRK_PLL', 'TRK_WIRE', 'TRK_DEBUG'):
            L.append(f'meas tran v_{n.lower()} find v({n.lower()}) at={te}')
        L.append(f'meas tran ivdd_end find i(vdd) at={te}')
        L.append(f'meas tran ivdd_pk min i(vdd)')
        L.append(f'meas tran vbg_pk max v(vbg)')
        L.append(f'meas tran vbg_pp pp v(vbg) from={tend*0.9} to={te}')
        L.append('.endc\n.end\n')
        return '\n'.join(L)

    # reset-state (the state die 1 powers up in): always-on current
    for corner, temp, v in (('tt', 27, 3.3), ('ff', 85, 3.63), ('ss', 0, 3.63)):
        put('bias', f'reset_{corner}_{temp}_{v}', deck(corner, temp, v, 'reset'))
    # documented bring-up sequence, function window + safety ends
    for corner, temp, v in (('tt', 27, 3.3), ('ss', 32, 3.15), ('ff', 22, 3.35), ('ss', 0, 3.15), ('ff', 85, 3.63)):
        put('bias', f'seq_{corner}_{temp}_{v}', deck(corner, temp, v, 'seq'))
    # negative control: bring-up sequence with the bandgap node shorted -> outputs must collapse
    put('bias', 'fault_tt_VBG_to_VSS', deck('tt', 27, 3.3, 'seq', fault=('VBG', '0')))
    faults = {
        'BIASlna_to_VSS': ('BIAS_lna', '0'), 'BIASlna_to_RAILrf': ('BIAS_lna', 'RAIL_rf'),
        'BIASadci_to_VSS': ('BIAS_adc_i', '0'),
        'TRKRF_to_VSS': ('TRK_RF', '0'), 'TRKRF_to_VDD': ('TRK_RF', 'VDD'), 'TRKRF_to_TRKCONV': ('TRK_RF', 'TRK_CONV'),
        'ROOTREF_to_VSS': ('ROOT_REF', '0'), 'ROOTREF_to_VDD': ('ROOT_REF', 'VDD'),
        'VREF0_to_VSS': ('VREF0', '0'), 'VCM_to_VSS': ('VCM', '0'), 'VCM_to_VDD': ('VCM', 'VDD'),
        'VBG_to_VDD': ('VBG', 'VDD'),
    }
    for k, f in faults.items():
        put('bias', f'fault_tt_{k}', deck('tt', 27, 3.3, 'seq', fault=f))
    put('bias', 'fault_tt_RAILrf_off', deck('tt', 27, 3.3, 'seq', rail_off='rf'))
    # stuck-on start-up (every enable follows VDD): ramps 10 us / 1 ms / 1 s
    for corner, temp, v in (('tt', 27, 3.3), ('ss', 0, 3.15), ('ff', 85, 3.63)):
        for tr in (10e-6, 1e-3, 1.0):
            put('bias', f'stuck_{corner}_{temp}_{v}_{tr:g}', deck(corner, temp, v, 'stuck', tr=tr))


if __name__ == '__main__':
    for g in sys.argv[1:]:
        dict(aosc=aosc, por=por, isw=isw, bias=bias)[g]()
