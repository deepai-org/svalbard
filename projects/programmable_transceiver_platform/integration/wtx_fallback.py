"""Physical WTX_EXT fallback assembly for the live pt_chip bring-up fixture.

Uses the extracted receiver, serializer/selector/bias macro, stress-safe pads,
steering buffers, bias bank, ATB switches and core-boundary clamps. The only
new circuit is slow CMOS branch-decode glue; its layout is still outstanding.
The master bias and clocks remain off. A board current sink at ATB0 supplies
the documented TRK_WIRE force route, with the root trunk disabled.
"""
import re
from pathlib import Path

from check_chip_power import PROJECT, compact_parallel_fets, instance, node, ports


def namespace(text, prefix):
    """Keep independently extracted private cell definitions from colliding."""
    names = re.findall(r'^\.subckt\s+(\S+)', text, re.M | re.I)
    pattern = r'(?<!\S)('+ '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))+r')(?!\S)'
    return re.sub(pattern, lambda m: prefix+m.group(), text)


GLUE = '''
.subckt bringup_inv A Y VDD VSS
XN Y A VSS VSS nfet_03v3 w=2u l=0.28u
XP Y A VDD VDD pfet_03v3 w=4u l=0.28u
.ends bringup_inv
.subckt bringup_and A B Y VDD VSS
XP0 YB A VDD VDD pfet_03v3 w=4u l=0.28u
XP1 YB B VDD VDD pfet_03v3 w=4u l=0.28u
XN0 YB A MID VSS nfet_03v3 w=4u l=0.28u
XN1 MID B VSS VSS nfet_03v3 w=4u l=0.28u
XI YB Y VDD VSS bringup_inv
.ends bringup_and
'''


def extension(read, support, pdk, library, scenario):
    models = [GLUE]
    def model(path, cell, prefix):
        source = read(path)
        # Exported pads carry their own diode/MIM .lib cards. The assembled
        # deck owns one common PDK/corner; repeating a MIM section corrupts
        # local parameter scoping in ngspice.
        if any(line.lower().startswith('.include') for line in source.splitlines()):
            raise ValueError(f'Unresolved extracted-model include: {path}')
        source = '\n'.join(line for line in source.splitlines() if not line.lower().startswith('.lib '))
        text = compact_parallel_fets(namespace(source, prefix))
        models.append(text)
        return text, prefix+cell
    a = PROJECT/'analog'
    rx, rx_cell = model(a/'timing/generated/diff_clk_rx.ext.spice', 'pt_diff_clk_rx', 'rx_')
    tx, tx_cell = model(a/'wired_tx/generated/wiredtx.ext.spice', 'pt_wiredtx', 'tx_')
    pad, pad_cell = model(a/'pads/generated/stress-safe-families/wired-transmit/physical.spice',
                          'tx_protected_pad', 'out_')
    protection, protection_cell = model(a/'pads/generated/stress-safe-families/rf-pair/pad-extracted.spice',
                                        'rf_protected_pad', 'in_')
    steering, steering_cell = model(a/'pads/generated/steering-buffer-compact/physical.spice',
                                    'tx_steering_buffer_flat_physical', 'steer_')
    interlock, interlock_cell = model(a/'pads/generated/transmit-control-candidate/thick-logic/physical.spice',
                                      'tx_mode_interlock_flat_physical', 'ctl_')
    bank, bank_cell = model(a/'core_support/distribution/generated/pt_bias_bank3.ext.spice',
                            'pt_bias_bank3', 'bias_')
    root, root_cell = model(a/'core_support/distribution/generated/pt_bias_root.ext.spice',
                            'pt_bias_root', 'root_')
    # These are the default-mode extractions used by the island-support checks.
    island_pex = Path(scenario['island_pex'])
    iso, iso_cell = model(island_pex/'pexd/iso_clamp/iso_clamp.pex.spice', 'iso_clamp_flat', 'iso_')
    leaf, leaf_cell = model(island_pex/'pexd/atb_leaf_f/atb_leaf_f.pex.spice', 'atb_leaf_f_flat', 'leaf_')
    group, group_cell = model(island_pex/'pexd/atb_grp/atb_grp.pex.spice', 'atb_grp_flat', 'grp_')
    atbpad, atbpad_cell = model(island_pex/'pexd/atb_pad/atb_pad.pex.spice', 'atb_pad_flat', 'atb_')
    body = []
    def add(label, cell, text, **connections):
        body.append(instance(label, cell, text, connections))
    def clamp(label, source, target, island):
        add(label, iso_cell, iso, A=source, ISO=f'ISO_{island}', Y=target, VDD='VDD', VSS='VSS')
    control = ['RX_ENABLE', 'EXT_ENABLE', 'BRANCH0', 'BRANCH1', 'STATE0', 'STATE1', 'IDLE', 'STAGE_TMDS']
    control += [f'CODE{k}' for k in range(8)]
    analog_pins = ['WTX_EXT_P', 'WTX_EXT_N', 'WIRE_TX_P', 'WIRE_TX_N', 'ATB0', 'EXT_DATA_OBS']
    analog_pins += control+['FORCE_LEAF', 'FORCE_GROUP', 'FORCE_PAD']
    for pin in control:
        clamp('Xisolate_'+pin, pin, 'L_'+pin, 'debug' if pin == 'RX_ENABLE' else 'wired')
    add('Xinput_protection', protection_cell, protection,
        PAD_P='WTX_EXT_P', PAD_N='WTX_EXT_N', VSS='VSS', ATB_ESD_RAIL='INPUT_ESD_MON')
    body += ['Resd_monitor INPUT_ESD_MON VSS 10meg']
    # As in the qualified data-mode fixture, swap legs and take OUTN.
    add('Xexternal_receiver', rx_cell, rx,
        INP='WTX_EXT_N', INN='WTX_EXT_P', EN='L_RX_ENABLE', SE='VSS',
        OUTP='DXB', OUTN='DX', PRESENT='PRESENT_DEBUG', ATB_DET='RX_ATB', VDD='RAIL_debug', VSS='VSS')
    clamp('Xreceiver_to_core', 'DX', 'DX_CORE', 'debug')
    clamp('Xpresent_to_core', 'PRESENT_DEBUG', 'PRESENT_CORE', 'debug')
    clamp('Xcore_to_tx', 'DX_CORE', 'DX_WIRED', 'wired')
    clamp('Xtx_status_to_core', 'EXT_DATA', 'EXT_DATA_OBS', 'wired')
    # TMDS branch decode: branch == 2, external route selected. The extracted
    # interlock supplies actual enables, gated by island ISO and power-good.
    # The clock-present detector is diagnostic: valid serial data may contain
    # a run of identical bits, so activity must not gate its output driver.
    body += ['Xbranch_inv L_BRANCH0 BRANCH0_B RAIL_wired VSS bringup_inv',
             'Xbranch_decode L_BRANCH1 BRANCH0_B TMDS_SELECTED RAIL_wired VSS bringup_and',
             'Xstate_inv L_STATE0 STATE0_B RAIL_wired VSS bringup_inv',
             'Xstate_active L_STATE1 STATE0_B STATE_ACTIVE RAIL_wired VSS bringup_and',
             'Xidle_inv L_IDLE NOT_IDLE RAIL_wired VSS bringup_inv',
             'Xrun STATE_ACTIVE NOT_IDLE RUN RAIL_wired VSS bringup_and',
             'Xstage RUN L_STAGE_TMDS RUN_TMDS RAIL_wired VSS bringup_and',
             'Xexternal_request TMDS_SELECTED L_EXT_ENABLE EXT_REQUEST RAIL_wired VSS bringup_and',
             'Xdrive_request EXT_REQUEST RUN_TMDS TMDS_REQUEST RAIL_wired VSS bringup_and',
             'Xwire_on ISO_wired WIRED_ON VDD VSS bringup_inv']
    add('Xmode_interlock', interlock_cell, interlock,
        VDD='RAIL_wired', VSS='VSS', REQ_MAIN='VSS', REQ_POST='VSS', REQ_TMDS='TMDS_REQUEST',
        REQ_DETECT='VSS', REQ_TERM='VSS', RESET='ISO_wired', QUALIFIED='WIRED_ON',
        SUPPLY_OK='PG_wired', CONFLICT='CONFLICT', VALID='VALID', EN_MAIN='EN_MAIN',
        EN_POST='EN_POST', EN_TMDS='EN_TMDS', EN_DETECT='EN_DETECT', EN_TERM='EN_TERM')
    # Core ATB force path into the island PMOS diode. It disconnects when ISO
    # asserts; no force source enters the switched domain while isolated.
    body += ['Xforce_isolation FORCE_LEAF WIRED_ON FORCE_SELECTED VDD VSS bringup_and']
    add('Xatb_provider_pad', 'gf180mcu_fd_io__asig_5p0', library,
        ASIG5V='ATB0', DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS')
    add('Xatb_pad_switch', atbpad_cell, atbpad, PAD='ATB0', BUS='ATB_FORCE', SEL='FORCE_PAD', VDD='VDD', VSS='VSS')
    add('Xatb_group_switch', group_cell, group, NODE='TRUNK_GROUP', BUS='ATB_FORCE', SEL='FORCE_GROUP', VDD='VDD', VSS='VSS')
    add('Xatb_force_leaf', leaf_cell, leaf, NODE='TRK_WIRE', BUS='TRUNK_GROUP', SEL='FORCE_SELECTED', VDD='VDD', VSS='VSS')
    # Retain the disabled root leg as an electrical load on the forced trunk.
    # The sequence verifies all root enables and master bias remain reset off.
    root_connections = {'VSS': 'VSS', 'ROOT_REF': 'ROOT_REF'}
    for island in ('RF', 'CONV', 'PLL', 'WIRE', 'DEBUG'):
        root_connections['EN_'+island] = 'VSS'
        root_connections['TRK_'+island] = 'TRK_'+island
    body.append(instance('Xdisabled_bias_root', root_cell, root, root_connections))
    add('Xbias_bank', bank_cell, bank, VDD='RAIL_wired', VSS='VSS', TRK='TRK_WIRE',
        EN0='VSS', EN1='VSS', EN2='EN_TMDS', OUT0='BIAS_UNUSED0', OUT1='BIAS_UNUSED1', OUT2='IBIAS_BANK')
    body += ['Vbias_measure IBIAS_BANK IBIAS 0']
    tx_ports = ports(tx, tx_cell)
    tx_connections = {p: p for p in tx_ports}
    tx_connections.update(VDD='RAIL_wired', VSS='VSS', WTX_PH0='VSS', WTX_PH90='VSS',
                          WTX_PH180='RAIL_wired', WTX_PH270='RAIL_wired', MODE_H='VSS', MODE_F='VSS',
                          SER_EN='VSS', WTX_EXT='L_EXT_ENABLE', DX='DX_WIRED', ISLAND_OFF='ISO_wired')
    for k in range(20):
        tx_connections[f'D{k}'] = 'VSS'
    for k in range(8):
        tx_connections[f'MAIN_CODE{k}'] = 'VSS'
        tx_connections[f'POST_CODE{k}'] = 'VSS'
        tx_connections[f'TMDS_CODE{k}'] = f'L_CODE{k}'
    tx_connections['WTX_EXT_DATA'] = 'EXT_DATA'
    body.append(instance('Xwiredtx', tx_cell, tx, tx_connections))
    for branch in ('MAIN', 'POST', 'TMDS'):
        for leg in ('P', 'N'):
            add(f'Xsteer_{branch}_{leg}', steering_cell, steering,
                VDD='RAIL_wired', VSS='VSS', IN=f'CMD_{branch}_{leg}', OUT=f'{branch}_{leg}')
    add('Xoutput_pad', pad_cell, pad,
        PAD_P='WIRE_TX_P', PAD_N='WIRE_TX_N', VDD='RAIL_wired', VSS='VSS', CASCODE='RAIL_wired',
        MAIN_P='MAIN_P', MAIN_N='MAIN_N', MAIN_BIAS='MAIN_BIAS', POST_P='POST_P', POST_N='POST_N', POST_BIAS='POST_BIAS',
        TMDS_P='TMDS_P', TMDS_N='TMDS_N', TMDS_BIAS='TMDS_BIAS', DETECT_ENABLE='EN_DETECT',
        DETECT_PBIAS='RAIL_wired', TERM_ENABLE='EN_TERM', TERM_VCM='VSS', ATB_ESD_RAIL='OUTPUT_ESD_MON')
    body += ['Resd_output_monitor OUTPUT_ESD_MON VSS 10meg']
    outputs = ['rx_en_wtx_ext', 'wdbg_obs', 'wdbg_obs_oe', 'atb0_en', 'force_wire', 'force_group']
    outputs += ['tx_branch[1]', 'tx_branch[0]']+[f'tmds_code[{k}]' for k in range(7, -1, -1)]+['wtx_ext']
    outputs += ['tx_state[1]', 'tx_state[0]', 'tx_idle', 'tx_stage']
    connections = ['WTX_EXT_P', 'WTX_EXT_N', 'WIRE_TX_P', 'WIRE_TX_N', 'ATB0', 'EXT_DATA_OBS']
    connections += ['A_rx_en_wtx_ext', 'A_wtx_ext', 'A_tx_branch_0', 'A_tx_branch_1']
    connections += ['A_tx_state_0', 'A_tx_state_1', 'A_tx_idle', 'A_tx_stage']
    connections += [f'A_tmds_code_{k}' for k in range(8)]
    connections += ['A_force_wire', 'A_force_group', 'A_atb0_en']
    external_pins = ['WTX_EXT_P', 'WTX_EXT_N', 'WIRE_TX_P', 'WIRE_TX_N', 'ATB0', 'WDBG_OBS']
    return dict(models=models, analog_pins=analog_pins, analog_body=body,
                # 950 pF is already distributed behind the five switches.
                # Keep the assembled total at the plan's 1 nF allocation.
                global_decap_f=50e-12,
                # Lump the 8 supply and 10 return bond DC resistances together.
                bond_loop_r_ohm=.1/8+.1/10,
                analog_connections=connections, chip_pins=external_pins, outputs=outputs,
                inputs={'wire_analog_status[12]': 'EXT_DATA_OBS'},
                chip_body=['Xwired_debug_pad VDD VSS A_wdbg_obs A_wdbg_obs_oe WDBG_OBS pt_debug_physical'],
                probes=['v(WIRE_TX_P)', 'v(WIRE_TX_N)', 'v(WDBG_OBS)', 'v(ATB0)',
                        'v(Xchip.Xanalog.TMDS_BIAS)', 'v(Xchip.Xanalog.IBIAS)',
                        'v(Xchip.Xanalog.EN_TMDS)', 'v(Xchip.Xanalog.DX)',
                        'v(Xchip.Xanalog.PRESENT_CORE)', 'v(Xchip.Xanalog.TRK_WIRE)',
                        'v(BOARD_P)', 'v(BOARD_N)', 'i(v.Xchip.Xanalog.Vbias_measure)'],
                bench_body=board(scenario))


def board(scenario):
    """Finite external source, AC coupling, board TMDS load and bias force."""
    start, rate = scenario['data_start'], scenario['data_rate']
    bits = scenario['data_bits']
    result = []
    for leg, sign in [('P', 1), ('N', -1)]:
        points = [(0., 1.65-sign*.125)]
        previous = 0
        for k, bit in enumerate(bits):
            if bit != previous:
                when = start+k/rate
                points += [(when, 1.65+sign*.125*(2*previous-1)),
                           (when+.1/rate, 1.65+sign*.125*(2*bit-1))]
                previous = bit
        result += [f'Vexternal_{leg} SOURCE_{leg} 0 PWL('+ ' '.join(f'{t:.15g} {v:.9g}' for t, v in points)+')',
                   f'Rexternal_{leg} SOURCE_{leg} AC_SOURCE_{leg} 50',
                   f'Cexternal_{leg} AC_SOURCE_{leg} IN_BOARD_{leg} 10p',
                   f'Rinput_bond_{leg} IN_BOARD_{leg} IN_BOND_{leg} 1',
                   f'Linput_bond_{leg} IN_BOND_{leg} WTX_EXT_{leg} 1n',
                   f'Rbond_{leg} WIRE_TX_{leg} BOND_{leg} 1',
                   f'Lbond_{leg} BOND_{leg} BOARD_{leg} 1n',
                   f'Rpullup_{leg} PEER BOARD_{leg} 50']
    peer = scenario['peer_start']
    result += [f'Vpeer PEER 0 PWL(0 0 {peer:.15g} 0 {peer+1e-6:.15g} 3.3)',
               # Finite-compliance bench sink, current-limited below B7's 1 mA.
               'Bforce ATB0 0 I=10u*min(max(V(ATB0)/0.1,0),1)',
               'CWDBG WDBG_OBS 0 5p', 'RWDBG WDBG_OBS 0 1g']
    return result
