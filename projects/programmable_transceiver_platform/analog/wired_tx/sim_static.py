"""DC/off-state checks for pt_wiredtx: tail-bias DAC transfer, reset-default
quiescent state, unpowered island with core-domain controls asserted, and a
supply ramp with reset-default controls."""
from pathlib import Path
import numpy as np
import sim_wiredtx as S
import tools

DEFAULT_CODES = dict(MAIN=109, POST=0, TMDS=102)


def _common(dut, subckt, *, vdd, corner, temp, phases='stopped', ctrl=None, codes=None, iso=0.0, ibias=True,
            vhi=3.3):
    ports = S.ports_of(Path(dut).read_text(), subckt)
    ctrl = ctrl or {}
    codes = codes or DEFAULT_CODES
    L = ['* pt_wiredtx static check', tools.model_header(corner, temp), f'.include {Path(dut).name}',
         f'VDD VDD 0 {vdd}', 'VSS VSS 0 0']
    if phases == 'stopped':
        L += [f'VPH{p} WTX_PH{p} 0 {v}' for p, v in (('0', 0), ('90', 0), ('180', vhi), ('270', vhi))]
    elif phases == 'high':
        L += [f'VPH{p} WTX_PH{p} 0 {vhi}' for p in ('0', '90', '180', '270')]
    else:
        L += S.phase_sources(phases, 3.3)
    if phases in ('stopped', 'high'):
        L += [f'VMODEH MODE_H 0 {ctrl.get("MODE_H", 0.0)}', f'VMODEF MODE_F 0 {ctrl.get("MODE_F", 0.0)}']
    for n in ('SER_EN', 'WTX_EXT', 'DX', 'EN_MAIN', 'EN_POST', 'EN_TMDS'):
        L.append(f'V{n} {n} 0 {ctrl.get(n, 0.0)}')
    L.append(f'VISO ISLAND_OFF 0 {iso}')
    for i in range(40 if 'D39' in ports else 20):
        L.append(f'VD{i} D{i} 0 {ctrl.get("D", 0.0)}')
    if 'POST_POL' in ports:
        L.append(f'VPOL POST_POL 0 {ctrl.get("POST_POL", 0.0)}')
    for b, code in codes.items():
        for k, bit in enumerate(S.code_bits(code)):
            L.append(f'V{b}C{k} {b}_CODE{k} 0 {bit*vhi}')
    # bias reference: 10 uA from the island bias distributor (Norton, 3.3 V compliance)
    if ibias:   # PMOS-like source from a 3.3 V core rail: 10 uA, falls to 0 at 3.3 V compliance
        L.append('BREF 0 IBIAS I=10u*(1-exp(-max(3.3-v(IBIAS),0)/0.1))')
    L.append('X0 ' + ' '.join(ports) + f' {subckt}')
    return L


def dac_sweep(work, dut, subckt='pt_wiredtx', codes=(0, 16, 32, 64, 102, 109, 125, 160, 200, 255), corner='typical',
              temp=27, vdd=3.3):
    """Mirror-replica tail current (pad tail geometry) vs code, all three DACs."""
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    (work / Path(dut).name).write_text(Path(dut).read_text())
    L = _common(dut, subckt, vdd=vdd, corner=corner, temp=temp,
                ctrl=dict(EN_MAIN=3.3, EN_POST=3.3, EN_TMDS=3.3), codes=dict(MAIN=0, POST=0, TMDS=0))
    for b, m in (('MAIN', 32), ('POST', 32), ('TMDS', 16)):
        L += [f'VT{b} T{b} 0 1.0', f'XT{b} T{b} {b}_BIAS 0 0 nfet_03v3 w=20u l=1u m={m}']
    L += ['.control', 'set wr_singlescale']
    for c in codes:
        for b in ('MAIN', 'POST', 'TMDS'):
            for k, bit in enumerate(S.code_bits(c)):
                L.append(f'alter V{b}C{k} dc = {bit*3.3}')
        L += ['op', f'echo CODE {c} $&i(VTMAIN) $&i(VTPOST) $&i(VTTMDS) $&v(MAIN_BIAS) $&v(TMDS_BIAS) '
                    '$&v(ATB_NBIAS) $&v(ATB_PBIAS) $&i(VDD)']
    L += ['.endc', '.end']
    (work / 'dac.sp').write_text('\n'.join(L) + '\n')
    _, log = tools.ngspice(work, 'dac.sp')
    rows = []
    for line in log.splitlines():
        if line.startswith('CODE '):
            v = [float(x) for x in line.split()[1:]]
            rows.append(dict(code=int(v[0]), i_tail_main_a=-v[1], i_tail_post_a=-v[2], i_tail_tmds_a=-v[3],
                             v_main_bias=v[4], v_tmds_bias=v[5], atb_nbias_v=v[6], atb_pbias_v=v[7],
                             i_vdd_a=-v[8]))
    return dict(corner=corner, temp_c=temp, vdd=vdd, replica='pad tail: MAIN/POST 32 x W20/L1, TMDS 16 x W20/L1, '
                'drain at 1.0 V', rows=rows)


def quiescent(work, dut, subckt='pt_wiredtx', *, vdd=3.3, corner='typical', temp=27, tag='reset', phases=2.5e9):
    """Reset defaults (all enables 0, default codes), island powered; ring phases
    running (phases = bit rate, quarter mode) or stopped (phases='stopped')."""
    work = Path(work) / tag; work.mkdir(parents=True, exist_ok=True)
    (work / Path(dut).name).write_text(Path(dut).read_text())
    L = _common(dut, subckt, vdd=vdd, corner=corner, temp=temp, phases=phases)
    L += ['.control', 'tran 20p 30n', 'meas tran iavg avg i(VDD) from=10n to=30n',
          'meas tran cmdmax max v(CMD_MAIN_N) from=5n to=30n', 'meas tran cmdmax2 max v(CMD_TMDS_P) from=5n to=30n',
          'meas tran biasmax max v(MAIN_BIAS) from=5n to=30n', 'meas tran tbiasmax max v(TMDS_BIAS) from=5n to=30n',
          'meas tran pmax max v(CMD_POST_P) from=5n to=30n', '.endc', '.end']
    (work / 'q.sp').write_text('\n'.join(L) + '\n')
    _, log = tools.ngspice(work, 'q.sp')
    return dict(case='island powered, reset-default controls, ' + ('ring phases stopped (clockmux default)' if phases ==
                'stopped' else f'ring phases running ({phases/1e9:g} Gb/s quarter mode)'),
                corner=corner, temp_c=temp, vdd=vdd, **_meas(log, ['iavg', 'cmdmax', 'cmdmax2', 'biasmax',
                                                                 'tbiasmax', 'pmax']))


def unpowered(work, dut, subckt='pt_wiredtx', *, vin=3.3, corner='typical', temp=27, tag='off'):
    """Island rail off (0 V through 1 kOhm, i.e. a discharged switched rail), every core-domain
    input driven high (worst case), ISLAND_OFF=1; report rail back-feed and input currents."""
    work = Path(work) / tag; work.mkdir(parents=True, exist_ok=True)
    (work / Path(dut).name).write_text(Path(dut).read_text())
    L = _common(dut, subckt, vdd=0.0, corner=corner, temp=temp, phases='high',
                ctrl=dict(SER_EN=vin, WTX_EXT=vin, DX=vin, EN_MAIN=vin, EN_POST=vin, EN_TMDS=vin, D=vin, MODE_H=vin, MODE_F=vin),
                codes=dict(MAIN=255, POST=255, TMDS=255), iso=vin, ibias=True, vhi=vin)
    L = [l.replace('VDD VDD 0 0.0', 'VDD VDDS 0 0\nRSW VDDS VDD 1k') for l in L]
    L += ['.control', 'op', 'echo RES $&v(VDD) $&i(VDD) $&v(CMD_MAIN_N) $&v(CMD_MAIN_P) $&v(CMD_TMDS_P) '
          '$&v(MAIN_BIAS) $&v(TMDS_BIAS) $&v(WORD_CLK) $&i(VSER_EN) $&i(VD0) $&i(VPH0) $&i(VISO) $&v(IBIAS)',
          '.endc', '.end']
    (work / 'off.sp').write_text('\n'.join(L) + '\n')
    _, log = tools.ngspice(work, 'off.sp')
    for line in log.splitlines():
        if line.startswith('RES '):
            v = [float(x) for x in line.split()[1:]]
            return dict(case='switched rail off (1 kOhm to 0 V), all core-domain controls/data/phases and codes '
                             'at vin, ISLAND_OFF=1, 10 uA bias source with 3.3 V compliance',
                        vin=vin, corner=corner, temp_c=temp, v_rail=v[0], i_rail_backfeed_a=v[1],
                        v_cmd_main_n=v[2], v_cmd_main_p=v[3], v_cmd_tmds_p=v[4], v_main_bias=v[5],
                        v_tmds_bias=v[6], v_word_clk=v[7], i_ser_en_a=v[8], i_d0_a=v[9], i_ph0_a=v[10],
                        i_island_off_a=v[11], v_ibias=v[12])
    return dict(case='unpowered', error=log[-600:])


def ramp(work, dut, subckt='pt_wiredtx', *, vdd=3.3, corner='typical', temp=27, tag='ramp'):
    """Supply ramp 0 -> vdd in 2 us with reset-default controls: no output pulse."""
    work = Path(work) / tag; work.mkdir(parents=True, exist_ok=True)
    (work / Path(dut).name).write_text(Path(dut).read_text())
    L = _common(dut, subckt, vdd=vdd, corner=corner, temp=temp, phases='stopped')
    L = [f'VDD VDD 0 PWL(0 0 2u {vdd})' if l.startswith('VDD VDD 0') else l for l in L]
    L += ['.control', 'tran 2n 3u', 'meas tran m1 max v(CMD_MAIN_N)', 'meas tran m2 max v(CMD_MAIN_P)',
          'meas tran m3 max v(CMD_TMDS_P)', 'meas tran m4 max v(CMD_TMDS_N)', 'meas tran m5 max v(CMD_POST_P)',
          'meas tran m6 max v(MAIN_BIAS)', 'meas tran m7 max v(TMDS_BIAS)', 'meas tran ipk max i(VDD)',
          'meas tran imin min i(VDD)', '.endc', '.end']
    (work / 'ramp.sp').write_text('\n'.join(L) + '\n')
    _, log = tools.ngspice(work, 'ramp.sp')
    m = _meas(log, ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'ipk', 'imin'])
    return dict(case=f'VDD ramp 0->{vdd} V in 2 us, reset-default controls, phases stopped', corner=corner,
                temp_c=temp, max_cmd_v=max(m.get(k, 9) for k in ('m1', 'm2', 'm3', 'm4', 'm5')),
                max_bias_v=max(m.get('m6', 9), m.get('m7', 9)), peak_supply_current_a=-m.get('imin', 0), raw=m)


def _meas(log, names):
    out = {}
    for line in log.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] in names and parts[1] == '=':
            try:
                out[parts[0]] = float(parts[2])
            except ValueError:
                pass
    return out
