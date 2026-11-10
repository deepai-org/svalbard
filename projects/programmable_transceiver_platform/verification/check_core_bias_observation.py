#!/usr/bin/env python3
"""Live SPI -> physical reference chain -> complete ATB tree -> provider pads.

Checks real core-node bindings, physical island switches and all bias banks.
The fixture uses explicit diode consumer loads and a board reset/POR boundary;
it does not claim the remaining payload macros or full-chip physical signoff.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import numpy as np

import check_chip_power as power
from cosim_bridge import compile_bridge
from check_chip_fallback import Registers

PROJECT, ROOT = power.PROJECT, power.ROOT
sys.path.insert(0, str(PROJECT/'integration'))
import core_bias
import atb_tree


def sequence(idac1_smu=False):
    spi = power.Spi(start=10e-6)
    regs = Registers(spi)
    mapping = json.loads((PROJECT/'spec/register-map.json').read_text())
    spi.read(0, 0x5356)
    spi.read(8, 2)
    spi.read(9, mapping['map_hash16'])
    regs.write(**{f'debug.island_power.{name}': 1 for name in core_bias.CONSUMERS})
    regs.commit()
    spi.time += 20e-6
    spi.read(0x0a, 0x3737)
    normal = {'core.biasgen.ena': 1, 'core.biasgen.ref_sel_vbg': 1,
              'core.biasgen.ref_sel_coarse': 1, 'core.biasgen.ref_sel_fine': 0,
              'core.refchain.bgap_ena': 1, 'core.refchain.bgap_trim': 8}
    normal.update({f'core.refchain.dist_en_{name}': 1 for name in ['rf', 'conv', 'pll', 'wire', 'debug']})
    regs.write(**normal)
    regs.commit()
    spi.time += 80e-6
    normal_at = spi.time
    spi.read(5, 0)
    if idac1_smu:
        regs.write(**{'debug.atb.atb1': 57})
        regs.commit()
        measurements = []
        for code in (0, 4, 8, 0):
            regs.write(**{'core.biasgen.idac1_source': code})
            regs.commit()
            spi.time += 8e-6
            measurements.append(dict(code=code, time_s=spi.time))
        regs.write(**{'debug.atb.atb1': 0})
        regs.commit()
        spi.read(5, 0)
        return dict(spi=spi, reads=spi.reads, normal_at=normal_at, observations=[],
                    current_observations=measurements, forced_at=None,
                    idac1_smu=True, stop=spi.time+5e-6)
    observations = []
    for code in [55, 1, 2, 3, 14, 22, 29, 35, 56, 5, 6, 7, 8, 9, 10, 11, 12, 13, 31]:
        regs.write(**{'debug.atb.atb1': code})
        regs.commit()
        spi.time += 8e-6
        observations.append(dict(code=code, time_s=spi.time))
        regs.write(**{'debug.atb.atb1': 0})
        regs.commit()
        spi.time += 100e-9
    # VBG force is legal only after its on-chip source is disabled. Both bus
    # selections follow the real generated commit/zero-gap rules.
    regs.write(**{'core.refchain.bgap_ena': 0, 'debug.atb.atb0': 55, 'debug.atb.atb1': 55})
    regs.commit()
    spi.time += 30e-6
    forced_at = spi.time
    spi.read(5, 0)
    return dict(spi=spi, reads=spi.reads, normal_at=normal_at, observations=observations,
                forced_at=forced_at, stop=spi.time+5e-6)


def build(out, pdk, support, ng, reuse_bridge=False, idac1_smu=False):
    used = {}
    def read(path):
        path = Path(path).resolve()
        used[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text()
    core = core_bias.build(read)
    library = read(pdk/'gf180mcu_fd_io.spice')
    tree = atb_tree.build(read, support, library)
    for module in [core_bias, atb_tree]:
        read(Path(module.__file__))
    read(Path(__file__))
    read(PROJECT/'verification/check_chip_fallback.py')
    read(PROJECT/'verification/check_chip_power.py')
    read(PROJECT/'verification/audit_core_bias_observation.py')
    read(PROJECT/'verification/audit_chip_bringup.py')
    graph = power.chip_connectivity(read(PROJECT/'integration/pt_chip.sv'))
    for port in ['debug_cfg', 'island_en', 'island_on', 'island_pgood',
                 'atb0_sw', 'atb1_sw', 'atb0_grp', 'atb1_grp', 'atb0_en', 'atb1_en']:
        assert graph['digital'][port] == graph['analog'][port], 'Parent connection mismatch: '+port
    projected = {}
    for pin, binding in {**core['control_bindings'], **tree['control_bindings']}.items():
        match = re.fullmatch(r'(\w+)\[(\d+)\]', binding)
        projected[pin] = (match[1], int(match[2]), 1) if match else (binding, 0, 1)
    selected = ['spi_miso', 'spi_miso_oe', 'island_en', 'island_on']
    if reuse_bridge:
        bridge = json.loads((out/'bridge/ports.json').read_text())
        assert bridge['projections'] == {k: list(v) for k, v in projected.items()}, 'Changed projection interface'
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in bridge['source_hashes'].items()), 'Stale bridge'
    else:
        bridge = compile_bridge(sorted((PROJECT/'rtl').glob('*.sv')), 'pt_digital_macro', out/'bridge', ng,
                            includes=[PROJECT/'rtl'], expose_outputs=selected, projections=projected,
                            expose_inputs=['reset_n_pad', 'por_n', 'spi_sclk', 'spi_cs_n', 'spi_mosi',
                                           'island_pgood', 'analog_status', 'fault'])
    plan = sequence(idac1_smu)
    spi = plan.pop('spi')
    bits = dict(wired=0, rf=1, pll=2, conv=4, debug=5)
    bindings = {int(k): v for k, v in core['observation_bindings'].items()}
    # Core and host supply sites are separate nodes (each with its own bond),
    # joined on die by the retained ring (RRING below), so codes 5 and 6 are
    # distinguishable. Code 10 taps WIRE_VDD at the USB branch root; code 31
    # the line PLL's charge-pump bias input (bank output BIAS_pll_ring_tx).
    bindings.update({5: 'VDD', 6: 'VDD_HOST', 7: 'RAIL_wired', 8: 'RAIL_rf', 9: 'RAIL_pll',
                     10: 'RAIL_wired', 11: 'RAIL_conv', 12: 'RAIL_debug', 13: 'VSS', 31: 'BIAS_pll_ring_tx'})
    nodes = json.loads(read(PROJECT/'spec/debug-controls.json'))['atb_nodes']
    unbound = ['NODE_'+n['name'] for n in nodes if n.get('hardware', True) and n['code'] not in bindings]
    consumers = [name for group in core['consumers'].values() for name in group]
    models = []
    switches = {}
    for name in bits:
        switches[name] = power.compact_parallel_fets(read(support/f'pex/isw_{name}/isw_{name}.pex.spice'))
        models.append(switches[name])
    model_root = ng/'src/xspice/icm'
    (out/'.spiceinit').write_text('set ngbehavior=hs\n'+
        '\n'.join(f'codemodel {model_root}/{name}/{name}.cm' for name in ['analog', 'digital'])+'\n')
    deck = ['* Live SPI-controlled physical core bias / ATB assembly', f'.include {pdk}/ngspice/design.ngspice']
    deck += [f'.lib {pdk}/ngspice/sm141064.ngspice {section}' for section in
             ['typical', 'res_typical', 'diode_typical', 'mimcap_typical', 'moscap_typical', 'bjt_typical']]
    deck += ['.temp 27', library, core['text'], tree['text'], *models,
             '.model to_logic adc_bridge(in_low=1.0 in_high=2.3)', '.model zero d_pulldown',
             '.model to_voltage dac_bridge(out_low=0 out_high=1 out_undef=0.5 input_load=0 t_rise=1e-10 t_fall=1e-10)',
             f'.model macro d_cosim(simulation="{bridge["library"]}" delay=1e-9 queue_size=4096)']
    host_pins = ['VDD', 'VSS', 'RESET_N', 'SCLK', 'CS_N', 'MOSI', 'MISO',
                 'RESET_Y', 'CLK_Y', 'CS_Y', 'MOSI_Y', 'MISO_A', 'MISO_OE']
    host = []
    for label, pad, output, kind in [('reset', 'RESET_N', 'RESET_Y', 'in_c'),
                                      ('clock', 'SCLK', 'CLK_Y', 'bi_24t'),
                                      ('select', 'CS_N', 'CS_Y', 'bi_24t'), ('data', 'MOSI', 'MOSI_Y', 'bi_24t')]:
        connect = dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD=pad,
                       PU='VSS', PD='VDD' if label == 'reset' else 'VSS', Y=output)
        if kind == 'bi_24t':
            connect.update(A='VSS', CS='VSS', SL='VSS', OE='VSS', IE='VDD')
        host.append(power.instance('X'+label, 'gf180mcu_fd_io__'+kind, library, connect))
    host.append(power.instance('Xmiso', 'gf180mcu_fd_io__bi_t', library,
                dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD='MISO', PU='VSS', PD='VSS',
                     Y='UNUSED', A='MISO_A', CS='VSS', SL='VSS', OE='MISO_OE', IE='VSS', PDRV0='VSS', PDRV1='VDD')))
    deck += ['.subckt pt_host_physical '+' '.join(host_pins), *host, '.ends pt_host_physical']
    controls = list(core['control_bindings'])+list(tree['control_bindings'])
    analog_pins = ['VDD', 'VDD_HOST', 'VSS', 'ATB0', 'ATB1', 'LOAD_EN']+controls
    analog_pins += [f'{prefix}_{name}' for name in bits for prefix in ['EN', 'ON', 'PG']]
    analog_pins += ['BIAS_'+name for name in consumers]+unbound
    body = []
    for name in bits:
        body.append(power.instance('Xswitch_'+name, 'isw_'+name+'_pex', switches[name],
                    dict(VDD='VDD', VSS='VSS', VISL='RAIL_'+name, EN='EN_'+name, ISO='ISO_'+name, PG='PG_'+name)))
        capacitance = dict(wired=150e-12, rf=200e-12, pll=250e-12, conv=250e-12, debug=100e-12)[name]
        body.append(f'Cdecap_{name} RAIL_{name} VSS {capacitance}')
    connect = {pin: pin for pin in core['pins']}
    connect.update({'EN_'+name: 'LOAD_EN' for name in consumers if name != 'lc_vco_reserved'})
    body.append(power.instance('Xcore_bias', 'pt_core_bias', core['text'], connect))
    connect = {pin: pin for pin in tree['pins']}
    for node in nodes:
        if node['code'] in bindings:
            connect['NODE_'+node['name']] = bindings[node['code']]
    body.append(power.instance('Xatb_tree', 'pt_atb_tree', tree['text'], connect))
    deck += ['.subckt pt_analog_physical '+' '.join(analog_pins), *body, '.ends pt_analog_physical']
    chip_pins = ['VDD', 'VDD_HOST', 'VSS', 'RESET_N', 'SCLK', 'CS_N', 'MOSI', 'MISO', 'ATB0', 'ATB1', 'POR_N', 'LOAD_EN']
    chip_pins += ['BIAS_'+name for name in consumers]+unbound
    deck += ['.subckt pt_chip '+' '.join(chip_pins),
             'Xhost VDD_HOST VSS RESET_N SCLK CS_N MOSI MISO RESET_Y CLK_Y CS_Y MOSI_Y A_spi_miso A_spi_miso_oe pt_host_physical',
             'Azero D_ZERO zero']
    inputs = {pin: '0' for pin in bridge['inputs']}
    inputs.update(reset_n_pad='RESET_Y', por_n='POR_N', spi_sclk='CLK_Y', spi_cs_n='CS_Y', spi_mosi='MOSI_Y')
    inputs['analog_status[4]'] = 'POR_N'
    inputs.update({f'island_pgood[{bit}]': 'PG_'+name for name, bit in bits.items()})
    for index, (pin, source) in enumerate(inputs.items()):
        if source != '0':
            deck.append(f'Ain{index} [{source}] [I_{power.node(pin)}] to_logic')
    deck.append('Adigital ['+' '.join('I_'+power.node(pin) if source != '0' else 'D_ZERO' for pin, source in inputs.items())+
                '] ['+' '.join('O_'+power.node(pin) for pin in bridge['outputs'])+'] NULL macro')
    for index, pin in enumerate(bridge['outputs']):
        deck += [f'Aout{index} [O_{power.node(pin)}] [U_{power.node(pin)}] to_voltage',
                 f'Bscale{index} A_{power.node(pin)} VSS V=V(U_{power.node(pin)})*V(VDD,VSS)']
    analog_connect = {pin: pin for pin in analog_pins}
    analog_connect.update({pin: 'A_'+pin for pin in controls})
    for name, bit in bits.items():
        analog_connect['EN_'+name] = 'A_island_en_'+str(bit)
        analog_connect['ON_'+name] = 'A_island_on_'+str(bit)
    deck += [power.instance('Xanalog', 'pt_analog_physical', '\n'.join(deck), analog_connect), '.ends pt_chip']
    deck += ['VBOARD BOARD 0 PWL(0 0 1u 3.3)', 'RBOND BOARD BOND 0.0225', 'LBOND BOND VDD 2n',
             'RDAMP BOND VDD 2', 'CCORE VDD 0 50p',
             'BBACKGROUND VDD 0 I=0.13*min(max(V(VDD)/3.3,0),1)',
             # Host supply site: same board source (spec/contract.json power_topology:
             # one external supply), its own 1-ohm board sense shunt and bond, an
             # 80 mA host-domain load, and the on-die ring tie to the core site
             # (declared 1 ohm, not an extracted value). Fixture-only: it makes the
             # two supply taps differ by ~40 mV so a swapped leaf binding fails.
             'RSHUNT_HOST BOARD BOARD_HOST 1', 'RBOND_HOST BOARD_HOST BOND_HOST 0.0225',
             'LBOND_HOST BOND_HOST VDD_HOST 2n', 'RDAMP_HOST BOND_HOST VDD_HOST 2', 'CHOST VDD_HOST 0 20p',
             'RRING VDD VDD_HOST 1',
             'BHOSTLOAD VDD_HOST 0 I=0.08*min(max(V(VDD_HOST)/3.3,0),1)',
             # Declared fixture boundary, distinct from the real 40-ms POR.
             'VRESET RESET_N 0 PWL(0 0 2u 0 2.000002u 3.3)',
             'VPOR POR_N 0 PWL(0 0 2u 0 2.000002u 3.3)',
             '.model host_switch sw(Ron=1 Roff=1e12 Vt=3.2 Vh=0.05)', *spi.sources(),
             'RMISO MISO 0 1g', 'CMISO MISO 0 5p', 'RMETER ATB1 0 1g', 'CMETER ATB1 0 10p',
             'VFORCE FORCE_BOARD 0 PWL(0 0 3u 0 3.00001u 1.2)', 'RFORCE FORCE_BOARD ATB0 100']
    if idac1_smu:
        # A real current measurement loads the sense pad at its documented
        # compliance voltage; a high-impedance voltage probe cannot test IDAC1.
        deck += ['VSMU SMU_BOARD 0 1', 'RSMU SMU_BOARD ATB1 10']
    chip_connect = {pin: pin for pin in chip_pins}
    chip_connect.update(VSS='0', LOAD_EN='VDD')
    deck.append(power.instance('Xchip', 'pt_chip', '\n'.join(deck), chip_connect))
    for name in consumers:
        deck += [f'Vload_{name} BIAS_{name} DIODE_{name} 0',
                 f'Xload_{name} DIODE_{name} DIODE_{name} 0 0 nfet_03v3 w=4u l=1u']
    for pin in unbound:
        deck.append(f'Runbound_{pin} {pin} 0 1g')
    sources = {'VDD': 'VDD', 'VDD_HOST': 'VDD_HOST', 'MISO': 'MISO', 'ATB1': 'ATB1', 'ATB0': 'ATB0',
               'BIAS_pll_ring_tx': 'BIAS_pll_ring_tx'}
    sources.update({net: 'Xchip.Xanalog.'+net for net in core['observation_bindings'].values()})
    sources.update({f'RAIL_{name}': 'Xchip.Xanalog.RAIL_'+name for name in bits})
    meter_probes = {'ATB1_SMU': 'VSMU'} if idac1_smu else {}
    probes = (['v('+net+')' for net in sources.values()]+[f'i(Vload_{name})' for name in consumers]
              +[f'i({name})' for name in meter_probes.values()])
    last_measurement = (plan['current_observations'] if idac1_smu else plan['observations'])[-1]['time_s']
    checkpoints = sorted({50e-6, plan['normal_at'], last_measurement})
    deck += ['.options klu reltol=1e-3 abstol=1e-13 method=gear rshunt=1e12 cshunt=1e-17', '.control',
             'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16', 'save '+' '.join(probes)]
    deck += [f'stop when time = {when:.16g}' for when in checkpoints]
    deck.append(f'tran 20n {plan["stop"]:.16g} 0 1u')
    for index, when in enumerate(checkpoints):
        # stop/resume retains the same transient state and circuit. Write
        # complete probe prefixes so a wall-clock timeout preserves evidence.
        deck += [f'wrdata checkpoint-{index}.txt '+' '.join(probes), 'resume']
    deck += ['wrdata wave.txt '+' '.join(probes), 'quit', '.endc', '.end']
    (out/'pt_chip.spice').write_text('\n'.join(deck)+'\n')
    for path in (pdk/'ngspice').glob('*'):
        if path.is_file():
            used[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    frozen = {}
    for name, sha in {**used, **bridge['source_hashes']}.items():
        original = Path(name)
        assert hashlib.sha256(original.read_bytes()).hexdigest() == sha, 'Source changed during build: '+name
        copy = out/'frozen-sources'/original.relative_to('/')
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, copy)
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == sha
        frozen[name] = dict(path=str(copy.relative_to(out)), sha256=sha)
    (out/'frozen-sources/manifest.json').write_text(json.dumps(frozen, indent=2)+'\n')
    experiment = dict(**plan, bridge=bridge, parent_connectivity=graph,
                      core={k: v for k, v in core.items() if k != 'text'},
                      tree={k: v for k, v in tree.items() if k != 'text'},
                      node_bindings=bindings, unbound_node_ports=unbound, voltage_probes=sources,
                      current_probes=consumers, meter_probes=meter_probes, source_hashes=used,
                      checkpoint_times_s=checkpoints,
                      frozen_source_manifest='frozen-sources/manifest.json',
                      fixture_boundaries=['external reset/POR at 2 us, not the real cold-start POR',
                                          'diode loads enabled on all consumer ports; reserved LC output disabled',
                                          'unused ATB nodes terminate through 1 Gohm fixture loads',
                                          'host supply site: 1 ohm board shunt, 80 mA host load, declared 1 ohm ring tie'])
    (out/'experiment.json').write_text(json.dumps(experiment, indent=2)+'\n')
    return experiment


def assess(out, experiment):
    wave = np.loadtxt(out/'wave.txt', skiprows=1)
    assert np.isfinite(wave).all() and wave[-1, 0] >= experiment['stop']*(1-1e-8), 'Incomplete waveform'
    time_axis = wave[:, 0]
    columns = {name: index+1 for index, name in enumerate(experiment['voltage_probes'])}
    current_start = len(columns)+1
    node_bindings = {int(k): v for k, v in experiment['node_bindings'].items()}
    def value(name, when):
        return float(np.interp(when, time_axis, wave[:, columns[name]]))
    reads = []
    for read in experiment['reads']:
        levels = np.interp(read['sample_times'], time_axis, wave[:, columns['MISO']])
        assert np.all((levels <= 1) | (levels >= 2.3)), 'Indeterminate SPI'
        actual = 0
        for level in levels:
            actual = (actual << 1) | int(level >= 2.3)
        assert actual == read['expected'], ('SPI', read['address'], actual, read['expected'])
        reads.append(dict(address=read['address'], value=actual))
    normal = experiment['normal_at']
    assert 1.20 <= value('VBG', normal) <= 1.23, 'Bandgap out of nominal window'
    currents = {}
    for index, consumer in enumerate(experiment['current_probes']):
        sample = float(np.interp(normal, time_axis, wave[:, current_start+index]))
        currents[consumer] = sample
        assert abs(sample) < 1e-9 if consumer == 'lc_vco_reserved' else 9e-6 <= sample <= 11e-6, (consumer, sample)
    observed = []
    for observation in experiment['observations']:
        code, when = observation['code'], observation['time_s']
        source = node_bindings[code]
        expected = 0 if source == 'VSS' else value(source, when)
        actual = value('ATB1', when)
        error = abs(actual-expected)
        assert error <= .005, (code, source, actual, expected)
        observed.append(dict(code=code, net=source, pad_v=actual, source_v=expected, error_v=error, time_s=when))
    by_code = {row['code']: row for row in observed}
    if 5 in by_code and 6 in by_code:
        # The two supply taps must be distinguishable through the ATB: each
        # matches its own node within 5 mV and they differ by > 4x that.
        separation = abs(by_code[5]['pad_v']-by_code[6]['pad_v'])
        assert separation > 4*.005, ('core/host supply taps not distinguishable', separation)
    if 2 in by_code:
        assert 0.97 <= by_code[2]['pad_v'] <= 1.05, ('VREF0 out of window', by_code[2])
        assert abs(by_code[2]['pad_v']-value('VBG', by_code[2]['time_s'])*5/6) <= .01, 'VREF0 is not 5/6 VBG'
    if 3 in by_code:
        half = value('VDD', by_code[3]['time_s'])/2
        assert abs(by_code[3]['pad_v']-half) <= .02*half, ('VCM is not VDD/2', by_code[3], half)
    forced = experiment['forced_at']
    if forced is not None:
        assert abs(value('VBG', forced)-1.2) <= .01, 'VBG force failed'
        assert abs(value('ATB1', forced)-value('VBG', forced)) <= .005, 'Forced VBG not observable'
    # Use the independent auditor for current plateaus and full-window checks.
    from audit_core_bias_observation import audit
    independent = audit(out, 'wave.txt', out/'core-bias-audit.json')
    assert independent['status'] == 'pass'
    result = dict(status='pass', scope='SPI-controlled extracted core reference and ATB assembly with physical island switches',
                  spi_reads=reads, nominal_vbg_v=value('VBG', normal), nominal_bias_currents_a=currents,
                  observations=observed, forced_vbg_v=value('VBG', forced) if forced is not None else None,
                  idac1_smu=experiment.get('idac1_smu', False),
                  current_observations=[row for row in independent['completed_checks'] if row['check'] == 'IDAC1 SMU current'],
                  frozen_source_manifest=experiment.get('frozen_source_manifest'),
                  excluded=['full-chip source bindings and physical placement/routing', 'real cold-start POR',
                            'actual payload consumer macros', 'PVT, mismatch and external board qualification'],
                  source_hashes={**experiment['source_hashes'], **experiment['bridge']['source_hashes']},
                  artifact_hashes={name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name in
                                   ['pt_chip.spice', 'experiment.json', 'wave.txt', 'ngspice.log']})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['source_hashes', 'artifact_hashes']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/core-bias-observation')
    parser.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    parser.add_argument('--island-pex', type=Path, default=ROOT/'scratch/island-support-20261108-075605')
    parser.add_argument('--ngspice-source', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--reuse-build', action='store_true')
    parser.add_argument('--reuse-bridge', action='store_true')
    parser.add_argument('--idac1-smu', action='store_true', help='Measure spare IDAC1 through ATB code 57 into a 1 V SMU')
    parser.add_argument('--assess-only', action='store_true', help='Re-assess an existing completed wave.txt/ngspice.log without simulating')
    parser.add_argument('--timeout', type=float, default=21600)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.assess_only:
        experiment = json.loads((out/'experiment.json').read_text())
        assert experiment.get('idac1_smu', False) == args.idac1_smu, 'Different observation mode'
        text = (out/'ngspice.log').read_text()
        assert not any(error in text for error in ['Timestep too small', 'simulation(s) aborted', 'impossible delay', 'time is behind vtime'])
        assess(out, experiment)
        sys.exit(0)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    if args.reuse_build:
        experiment = json.loads((out/'experiment.json').read_text())
        assert experiment.get('idac1_smu', False) == args.idac1_smu, 'Different observation mode'
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in
                   {**experiment['source_hashes'], **experiment['bridge']['source_hashes']}.items()), 'Stale build'
    else:
        experiment = build(out, args.pdk.resolve(), args.island_pex.resolve(), args.ngspice_source.resolve(),
                           args.reuse_bridge, args.idac1_smu)
    if not args.build_only:
        (out/'wave.txt').unlink(missing_ok=True)
        started = time.monotonic()
        with (out/'ngspice.log').open('w') as log:
            with subprocess.Popen([str(args.ngspice_source.resolve()/'src/ngspice'), '-b', 'pt_chip.spice'],
                                  cwd=out, stdout=log, stderr=subprocess.STDOUT,
                                  env={**os.environ, 'OMP_NUM_THREADS': '1'}) as process:
                from audit_chip_bringup import record
                record(out, process.pid)
                try:
                    returncode = process.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise
                assert returncode == 0, ('ngspice failed', returncode)
        text = (out/'ngspice.log').read_text()
        assert not any(error in text for error in ['Timestep too small', 'simulation(s) aborted', 'impossible delay', 'time is behind vtime'])
        assess(out, experiment)
