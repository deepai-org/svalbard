#!/usr/bin/env python3
"""Live SPI -> extracted core bias of one chip -> its ATB tree -> provider pads (PT_CHIP=rf|wired, required).

Per chip: integration/core_bias.py build(read, chip) gives pt_core_bias_<chip>; integration/chips/<chip>/chip.conn
(parsed with integration/chips/check_top.py) gives every net: the core-bias pin bindings, the island switches, and
the chip's ATB leaves / group switches / pad switches / provider pads with the nets they tap. The deck is built
from those bindings, so an ATB code reads whatever net the conn puts on its leaf. The real pt_digital_macro
(PT_CHIP parameter) drives the core-bias controls through the c_* ports the conn binds them to, the island
enables and the ATB selects, over SPI through the provider host pads.

Normal run: all islands of the chip on, nominal reference programming, then every ATB1 code of the chip whose
leaf taps a net this fixture drives (core-bias outputs, island rails, supplies, consumer bias nets) is selected in
turn and the ATB1 pad must equal that net within 5 mV; VREF0 = 5/6 VBG, VCM = VDD/2, the bandgap window and every
consumer bank output 10 uA +/-10 % into its diode load; core and host supply taps (codes 5, 6) must be
distinguishable; finally VBG is forced through ATB0 after its source is disabled and sensed on ATB1.
--idac1-smu: spare IDAC1 through ATB1 code 57 into a 1 V SMU, codes 0/4/8/0.
The independent auditor (audit_core_bias_observation.py) re-derives the SPI expectations from the specification.
Every failed assertion is collected and reported (status fail); none stops the others.
Negative controls (--negative <kind>, must FAIL; they observe only the codes they need): `swap` exchanges the nets
of two ATB1 leaves in the deck (expectations stay the conn's), `enable` ties one consumer's bank enable off.

Declared fixture boundaries: every consumer enable tied on (LOAD_EN) with a diode load per bank output; nets of
blocks that are not in the fixture end in 1 Gohm; external reset/POR at 2 us (not the cold-start POR); per-island
block capacitance and a 1 mA load as in check_chip_power.py.
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

PROJECT, ROOT = power.PROJECT, power.ROOT
sys.path.insert(0, str(PROJECT/'integration'))
import core_bias  # noqa: E402

LEAF_PEX = {'atb_leaf_s': 'atb_leaf_s', 'atb_leaf_f': 'atb_leaf_f', 'atb_grp': 'atb_grp', 'atb_pad': 'atb_pad'}


def observable_codes(model, core_nets, driven):
    """ATB1 codes this fixture can observe on this chip, in code order, and the reason for every other ATB1 leaf."""
    nodes = {n['code']: n for n in json.loads((PROJECT/'spec/debug-controls.json').read_text())['atb_nodes']}
    codes, skipped = [], {}
    for name, i in model['inst'].items():
        m = re.fullmatch(r'atb1_leaf(\d+)', name)
        if not m:
            continue
        code, net = int(m.group(1)), i['pins']['NODE'][1]
        node = nodes[code]
        if not node.get('hardware', True):
            skipped[code] = 'hardware=false (dead code, leaf tied on purpose)'
        elif node['island'] and node['island'] not in model['groups']:
            skipped[code] = f'node island {node["island"]} is not on this chip: the leaf can never close'
        elif code == 57:
            skipped[code] = 'IDAC1 current source: measured by --idac1-smu'
        elif net not in driven:
            skipped[code] = f'{net}: driven by a block outside this fixture'
        else:
            codes.append(code)
    return sorted(codes), skipped


def sequence(model, codes, idac1_smu=False, negative=None):
    import pt_regmap
    spi = power.Spi(start=10e-6)
    regs = power.Registers(spi, model['chip'])
    groups = model['groups']
    spi.read(0, pt_regmap.ID_VALUE)
    spi.read(8, pt_regmap.ABI_VERSION)
    spi.read(9, pt_regmap.MAP_HASH)
    regs.write(**{f'debug.island_power.{g}': 1 for g in groups})
    regs.commit()
    spi.time += 20e-6
    on = sum(1 << b for b in groups.values())
    spi.read(0x0a, on | (on << 8))
    normal = {'core.biasgen.ena': 1, 'core.biasgen.ref_sel_vbg': 1, 'core.biasgen.ref_sel_coarse': 1,
              'core.biasgen.ref_sel_fine': 0, 'core.refchain.bgap_ena': 1,
              'core.refchain.bgap_trim': 8}
    normal.update({f: 1 for f in pt_regmap.FIELD_BY_NAME
                   if f.startswith('core.refchain.dist_en_') and not pt_regmap.FIELD_BY_NAME[f].get('absent')})
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
        return dict(spi=spi, reads=spi.reads, normal_at=normal_at, observations=[], current_observations=measurements,
                    forced_at=None, idac1_smu=True, stop=spi.time+5e-6)
    observations = []
    for code in codes:
        regs.write(**{'debug.atb.atb1': code})
        regs.commit()
        spi.time += 8e-6
        observations.append(dict(code=code, time_s=spi.time))
        regs.write(**{'debug.atb.atb1': 0})
        regs.commit()
        spi.time += 100e-9
    # VBG force is legal only after its on-chip source is disabled (commit rule).
    regs.write(**{'core.refchain.bgap_ena': 0, 'debug.atb.atb0': 55, 'debug.atb.atb1': 55})
    regs.commit()
    spi.time += 30e-6
    forced_at = spi.time
    spi.read(5, 0)
    return dict(spi=spi, reads=spi.reads, normal_at=normal_at, observations=observations, forced_at=forced_at,
                stop=spi.time+5e-6)


def build(out, pdk, island_pex, ng, chip, reuse_bridge=False, idac1_smu=False, negative=None):
    used = {}
    def read(path):
        path = Path(path).resolve()
        used[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text()
    model = power.chip_model(chip)
    read(model['conn'])
    core = core_bias.build(read, chip)
    for path in [core_bias.__file__, __file__, power.__file__, PROJECT/'verification/audit_core_bias_observation.py',
                 PROJECT/'verification/audit_chip_bringup.py', PROJECT/'spec/register-map.json', PROJECT/'spec/chips.json',
                 PROJECT/'spec/debug-controls.json',
                 PROJECT/'rtl/gen/pt_regmap.py']:
        read(path)
    graph = power.chip_connectivity(read(PROJECT/f'integration/chips/{chip}/generated/pt_chip.sv'), chip)
    inst = model['inst']
    failures = []
    # ---- core bias: the conn binds every pin of the generator's top
    cb = inst['core_bias']
    assert cb['master'] == core['top'], f'conn core_bias master {cb["master"]} != {core["top"]}'
    conn_pins = {k: v[1] for k, v in cb['pins'].items()}
    assert set(conn_pins) == set(core['pins']), f'core_bias pins differ: {set(conn_pins) ^ set(core["pins"])}'
    for code, pin in core['observation_bindings'].items():
        leaf = inst.get(f'atb1_leaf{code}')
        if leaf is None or leaf['pins']['NODE'][1] != conn_pins[pin]:
            failures.append(f'ATB code {code}: core_bias {pin} -> {conn_pins[pin]}, conn leaf atb1_leaf{code} '
                            f'-> {leaf and leaf["pins"]["NODE"][1]}')
    consumers = [name for group in core['consumers'].values() for name in group]
    library = read(pdk/'gf180mcu_fd_io.spice')
    # ---- macro boundary: c_* ports of the core-bias controls, island enables, ATB selects (projected bits)
    c_ports = sorted({re.sub(r'\[\d+\]$', '', net) for pin, net in conn_pins.items() if pin.startswith('C_')})
    atb_cells = {n: i for n, i in inst.items() if i['master'] in LEAF_PEX}
    macro_out = {net for kind, net in inst['digital']['pins'].values() if kind == '>'}
    # A select made outside the macro (pt_wired atb0_leaf22: the fallback control's FORCE_SELECTED) has no driver in
    # this fixture: that leaf is held open (declared boundary).
    held_open = sorted(n for n, i in atb_cells.items() if i['pins']['SEL'][1] not in macro_out)
    projected = {}
    for n, i in sorted(atb_cells.items()):
        sel = i['pins']['SEL'][1]
        if n in held_open:
            continue
        m = re.fullmatch(r'(\w+)\[(\d+)\]', sel)
        projected[node(sel)] = (m[1], int(m[2]), 1) if m else (sel, 0, 1)
    selected = ['spi_miso', 'spi_miso_oe', 'island_en', 'island_on']+c_ports
    bits = sorted({i['bit'] for i in model['islands']})
    pg_pins = [p for p in model['digital'] if p.startswith('s_pg_') and model['digital'][p] != 'VSS']
    if reuse_bridge:
        bridge = json.loads((out/'bridge/ports.json').read_text())
        assert bridge['projections'] == {k: list(v) for k, v in projected.items()}, 'Changed projection interface'
        assert bridge['parameters'] == {'PT_CHIP': model['chip_id']}, 'bridge built for another chip'
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in bridge['source_hashes'].items()), 'Stale bridge'
    else:
        bridge = compile_bridge(sorted((PROJECT/'rtl').glob('*.sv')), 'pt_digital_macro', out/'bridge', ng,
                                includes=[PROJECT/'rtl'], parameters={'PT_CHIP': model['chip_id']},
                                expose_outputs=selected, projections=projected,
                                expose_inputs=['reset_n_pad', 'por_n', 'spi_sclk', 'spi_cs_n', 'spi_mosi']+pg_pins)
        shutil.rmtree(out/'bridge/obj')
    # ---- nets the fixture drives (what an ATB leaf may observe)
    driven = {'VDD', 'VSS'} | {i['rail'] for i in model['islands']}
    driven |= {net for pin, net in conn_pins.items()
               if net != '-' and not pin.startswith(('C_', 'EN_', 'ON_', 'VDD', 'VSS', 'RAIL_'))}
    codes, skipped = observable_codes(model, conn_pins, driven)
    leaf_net = {int(n[len('atb1_leaf'):]): i['pins']['NODE'][1] for n, i in atb_cells.items() if n.startswith('atb1_leaf')}
    swapped = None
    if negative == 'swap':
        # the deck exchanges the nets of two leaves (master bias / core supply); expectations stay the conn's
        swapped = (codes[0], next(c for c in codes if leaf_net[c] == 'VDD'))
        codes = list(swapped)
    elif negative == 'enable':
        codes = codes[:1]
    plan = sequence(model, codes, idac1_smu, negative)
    spi = plan.pop('spi')
    bindings = {code: leaf_net[code] for code in codes}
    if idac1_smu:
        bindings[57] = leaf_net[57]
    # ---- deck
    switches = {}
    for i in model['islands']:
        if i['master'] not in switches:
            switches[i['master']] = power.compact_parallel_fets(read(island_pex/f'pex/{i["master"]}/{i["master"]}.pex.spice'))
    cells = {c: read(island_pex/'pexd'/c/f'{c}.pex.spice') for c in sorted({i['master'] for i in atb_cells.values()})}
    model_root = ng/'src/xspice/icm'
    (out/'.spiceinit').write_text('set ngbehavior=hs\n'+
        '\n'.join(f'codemodel {model_root}/{name}/{name}.cm' for name in ['analog', 'digital'])+'\n')
    deck = [f'* Live SPI-controlled extracted core bias / ATB assembly of pt_{chip}', f'.include {pdk}/ngspice/design.ngspice']
    deck += [f'.lib {pdk}/ngspice/sm141064.ngspice {section}' for section in
             ['typical', 'res_typical', 'diode_typical', 'mimcap_typical', 'moscap_typical', 'bjt_typical']]
    deck += ['.temp 27', library, core['text'], *switches.values(), *cells.values(),
             '.model to_logic adc_bridge(in_low=1.0 in_high=2.3)', '.model zero d_pulldown',
             '.model to_voltage dac_bridge(out_low=0 out_high=1 out_undef=0.5 input_load=0 t_rise=1e-10 t_fall=1e-10)',
             f'.model macro d_cosim(simulation="{bridge["library"]}" delay=1e-9 queue_size=4096)']
    host = []
    for label, pad, output, kind in [('reset', 'RESET_N', 'RESET_Y', 'in_c'), ('clock', 'SCLK', 'CLK_Y', 'bi_24t'),
                                      ('select', 'CS_N', 'CS_Y', 'bi_24t'), ('data', 'MOSI', 'MOSI_Y', 'bi_24t')]:
        connect = dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD=pad, PU='VSS',
                       PD='VDD' if label == 'reset' else 'VSS', Y=output)
        if kind == 'bi_24t':
            connect.update(A='VSS', CS='VSS', SL='VSS', OE='VSS', IE='VDD')
        host.append(power.instance('X'+label, 'gf180mcu_fd_io__'+kind, library, connect))
    host.append(power.instance('Xmiso', 'gf180mcu_fd_io__bi_t', library,
                dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD='MISO', PU='VSS', PD='VSS', Y='UNUSED',
                     A='MISO_A', CS='VSS', SL='VSS', OE='MISO_OE', IE='VSS', PDRV0='VSS', PDRV1='VDD')))
    deck += ['.subckt pt_host_physical VDD VSS RESET_N SCLK CS_N MOSI MISO RESET_Y CLK_Y CS_Y MOSI_Y MISO_A MISO_OE',
             *host, '.ends pt_host_physical']
    body, ext = [], {}       # ext: fixture-internal net -> chip-level port of pt_analog_physical
    def a_net(net):          # macro output (or a bit of it) as an analog node
        return 'A_'+power.node(net)
    for i in model['islands']:
        name = i['island']
        pg = f'PG_{name}' if i['pg'] != '-' else f'PG_{power.node(i["instance"])}'
        body.append(power.instance(f'X{power.node(i["instance"])}', f'{i["master"]}_pex', switches[i['master']],
                    dict(VDD='VDD', VSS='VSS', VISL=i['rail'], EN=a_net(f'island_en[{i["bit"]}]'),
                         ISO=f'ISO_{power.node(i["instance"])}', PG=pg)))
    for name in dict.fromkeys(i['island'] for i in model['islands']):
        group = next(i['group'] for i in model['islands'] if i['island'] == name)
        body += [f'Cdecap_{name} RAIL_{name} VSS {power.PG_GROUP_DECAP[group]}', f'Rload_{name} RAIL_{name} VSS 3300']
    connect = {}
    for pin, net in conn_pins.items():
        if pin.startswith('C_'):
            connect[pin] = a_net(net)
        elif pin.startswith('ON_'):
            connect[pin] = a_net(net)
        elif pin.startswith('EN_'):
            connect[pin] = 'VSS' if negative == 'enable' and pin == 'EN_'+consumers[0] else 'LOAD_EN'
        else:
            connect[pin] = net if net != '-' else f'NC_{pin}'
    body.append(power.instance('Xcore_bias', core['top'], core['text'], connect))
    leaf_nodes = set()
    for n, i in atb_cells.items():
        pins = {k: v[1] for k, v in i['pins'].items()}
        if i['master'].startswith('atb_leaf'):
            code = int(re.search(r'leaf(\d+)$', n).group(1))
            if swapped and n.startswith('atb1') and code in swapped:
                pins['NODE'] = bindings[swapped[1] if code == swapped[0] else swapped[0]]
            leaf_nodes.add(pins['NODE'])
        pins['SEL'] = 'VSS' if n in held_open else a_net(pins['SEL'])
        body.append(power.instance(f'X{n}', f'{i["master"]}_flat', cells[i['master']], pins))
    for n, i in inst.items():
        if i['master'] == 'atb_provider_pad':
            pins = {k: v[1] for k, v in i['pins'].items()}
            body.append(power.instance(f'X{n}', 'gf180mcu_fd_io__asig_5p0', library, pins))
    unbound = sorted(net for net in leaf_nodes if net not in driven)
    body += [f'Runbound_{power.node(net)} {net} VSS 1g' for net in unbound]
    bias_nets = {name: conn_pins['BIAS_'+name] for name in consumers}
    controls = sorted({connect[p] for p in connect if p.startswith(('C_', 'ON_'))} |
                      {a_net(i['pins']['SEL'][1]) for n, i in atb_cells.items() if n not in held_open} |
                      {a_net(f'island_en[{b}]') for b in bits})
    analog_pins = ['VDD', 'VSS', 'ATB0', 'ATB1', 'LOAD_EN', *controls, *[f'PG_{i["island"]}' for i in model['islands'] if i['pg'] != '-'],
                   *bias_nets.values()]
    deck += ['.subckt pt_analog_physical '+' '.join(analog_pins), *body, '.ends pt_analog_physical']
    chip_pins = ['VDD', 'VSS', 'RESET_N', 'SCLK', 'CS_N', 'MOSI', 'MISO', 'ATB0', 'ATB1', 'POR_N', 'LOAD_EN', *bias_nets.values()]
    deck += ['.subckt pt_chip '+' '.join(chip_pins),
             'Xhost VDD VSS RESET_N SCLK CS_N MOSI MISO RESET_Y CLK_Y CS_Y MOSI_Y A_spi_miso A_spi_miso_oe pt_host_physical',
             'Azero D_ZERO zero']
    inputs = {pin: '0' for pin in bridge['inputs']}
    inputs.update(reset_n_pad='RESET_Y', por_n='POR_N', spi_sclk='CLK_Y', spi_cs_n='CS_Y', spi_mosi='MOSI_Y')
    for pin in pg_pins:
        inputs[pin] = 'PG_'+model['digital'][pin][5:]
    for index, (pin, source) in enumerate(inputs.items()):
        if source != '0':
            deck.append(f'Ain{index} [{source}] [I_{power.node(pin)}] to_logic')
    deck.append('Adigital ['+' '.join('I_'+power.node(pin) if source != '0' else 'D_ZERO' for pin, source in inputs.items())+
                '] ['+' '.join('O_'+power.node(pin) for pin in bridge['outputs'])+'] NULL macro')
    for index, pin in enumerate(bridge['outputs']):
        deck += [f'Aout{index} [O_{power.node(pin)}] [U_{power.node(pin)}] to_voltage',
                 f'Bscale{index} A_{power.node(pin)} VSS V=V(U_{power.node(pin)})*V(VDD,VSS)']
    missing = [c for c in controls if c[2:] not in {power.node(p) for p in bridge['outputs']}]
    assert not missing, f'macro boundary lacks {missing}'
    analog_connect = {pin: pin for pin in analog_pins}
    deck += [power.instance('Xanalog', 'pt_analog_physical', '\n'.join(deck), analog_connect), '.ends pt_chip']
    deck += ['VBOARD BOARD 0 PWL(0 0 1u 3.3)', 'RBOND BOARD BOND 0.0225', 'LBOND BOND VDD 2n',
             'RDAMP BOND VDD 2', 'CCORE VDD 0 50p', 'BBACKGROUND VDD 0 I=0.13*min(max(V(VDD)/3.3,0),1)',
             'BHOSTLOAD VDD 0 I=0.08*min(max(V(VDD)/3.3,0),1)',
             # Declared fixture boundary, distinct from the real 40-ms POR.
             'VRESET RESET_N 0 PWL(0 0 2u 0 2.000002u 3.3)', 'VPOR POR_N 0 PWL(0 0 2u 0 2.000002u 3.3)',
             '.model host_switch sw(Ron=1 Roff=1e12 Vt=3.2 Vh=0.05)', *spi.sources(),
             'RMISO MISO 0 1g', 'CMISO MISO 0 5p', 'RMETER ATB1 0 1g', 'CMETER ATB1 0 10p',
             'VFORCE FORCE_BOARD 0 PWL(0 0 3u 0 3.00001u 1.2)', 'RFORCE FORCE_BOARD ATB0 100']
    if idac1_smu:
        # A real current measurement loads the sense pad at its compliance voltage.
        deck += ['VSMU SMU_BOARD 0 1', 'RSMU SMU_BOARD ATB1 10']
    chip_connect = {pin: pin for pin in chip_pins}
    chip_connect.update(VSS='0', LOAD_EN='VDD')
    deck.append(power.instance('Xchip', 'pt_chip', '\n'.join(deck), chip_connect))
    for name, net in bias_nets.items():
        deck += [f'Vload_{name} {net} DIODE_{name} 0', f'Xload_{name} DIODE_{name} DIODE_{name} 0 0 nfet_03v3 w=4u l=1u']
    sources = {'VDD': 'VDD', 'MISO': 'MISO', 'ATB1': 'ATB1', 'ATB0': 'ATB0'}
    for net in sorted(set(bindings.values()) | {conn_pins['VBG'], conn_pins['VREF0'], conn_pins['VCM']}):
        if net not in sources and net != 'VSS':
            sources[net] = net if net in chip_pins else 'Xchip.Xanalog.'+net
    sources['VBG'] = sources[conn_pins['VBG']]
    meter_probes = {'ATB1_SMU': 'VSMU'} if idac1_smu else {}
    probes = (['v('+n+')' for n in sources.values()]+[f'i(Vload_{name})' for name in consumers]
              +[f'i({name})' for name in meter_probes.values()])
    last = (plan['current_observations'] if idac1_smu else plan['observations'])[-1]['time_s']
    checkpoints = sorted({50e-6, plan['normal_at'], last})
    deck += ['.options klu reltol=1e-3 abstol=1e-13 method=gear rshunt=1e12 cshunt=1e-17', '.control',
             'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16', 'save '+' '.join(probes)]
    deck += [f'stop when time = {when:.16g}' for when in checkpoints]
    deck.append(f'tran 20n {plan["stop"]:.16g} 0 1u')
    for index, when in enumerate(checkpoints):
        # stop/resume keeps the transient state; complete prefixes survive a wall-clock timeout.
        deck += [f'wrdata checkpoint-{index}.txt '+' '.join(probes), 'resume']
    deck += ['wrdata wave.txt '+' '.join(probes), 'quit', '.endc', '.end']
    (out/'pt_chip.spice').write_text('\n'.join(deck)+'\n')
    for path in (pdk/'ngspice').glob('*'):
        if path.is_file():
            used[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    frozen = {}
    for name, digest in {**used, **bridge['source_hashes']}.items():
        original = Path(name)
        assert hashlib.sha256(original.read_bytes()).hexdigest() == digest, 'Source changed during build: '+name
        copy = out/'frozen-sources'/original.relative_to('/')
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, copy)
        frozen[name] = dict(path=str(copy.relative_to(out)), sha256=digest)
    (out/'frozen-sources/manifest.json').write_text(json.dumps(frozen, indent=2)+'\n')
    experiment = dict(**plan, chip=chip, negative=negative, swapped_leaves=swapped, bridge=bridge,
                      parent_connectivity=graph, build_failures=failures,
                      core={k: v for k, v in core.items() if k != 'text'},
                      node_bindings=bindings, not_observed=skipped, unbound_node_nets=unbound, voltage_probes=sources,
                      current_probes=consumers, meter_probes=meter_probes, source_hashes=used,
                      checkpoint_times_s=checkpoints, frozen_source_manifest='frozen-sources/manifest.json',
                      fixture_boundaries=['external reset/POR at 2 us, not the real cold-start POR',
                                          'every consumer enable tied on (LOAD_EN), diode load on every bank output',
                                          'nets of blocks outside the fixture terminate through 1 Gohm',
                                          'per-island block capacitance and 1 mA load (check_chip_power.py)',
                                          'one supply net VDD as in the conn; 80 mA host load on it',
                                          f'ATB cells with a select made outside the macro held open: {held_open}'])
    (out/'experiment.json').write_text(json.dumps(experiment, indent=2)+'\n')
    return experiment


def node(name):
    return power.node(name)


def assess(out, experiment):
    wave = np.loadtxt(out/'wave.txt', skiprows=1)
    assert np.isfinite(wave).all() and wave[-1, 0] >= experiment['stop']*(1-1e-8), 'Incomplete waveform'
    t = wave[:, 0]
    columns = {name: index+1 for index, name in enumerate(experiment['voltage_probes'])}
    current_start = len(columns)+1
    bindings = {int(k): v for k, v in experiment['node_bindings'].items()}
    failures = list(experiment['build_failures'])
    def require(ok, message):
        if not ok:
            failures.append(message)
    def value(name, when):
        return float(np.interp(when, t, wave[:, columns[name]]))
    reads = []
    for read in experiment['reads']:
        levels = np.interp(read['sample_times'], t, wave[:, columns['MISO']])
        actual = 0
        for level in levels:
            actual = (actual << 1) | int(level >= 2.3)
        require(np.all((levels <= 1) | (levels >= 2.3)), f'indeterminate SPI read 0x{read["address"]:02x}')
        require(actual == read['expected'], f'SPI 0x{read["address"]:02x} = 0x{actual:04x}, expected 0x{read["expected"]:04x}')
        reads.append(dict(address=read['address'], value=actual, expected=read['expected']))
    normal = experiment['normal_at']
    vbg = value('VBG', normal)
    require(1.20 <= vbg <= 1.23, f'bandgap {vbg:.4f} V outside 1.20-1.23 V')
    currents = {}
    for index, consumer in enumerate(experiment['current_probes']):
        sample = float(np.interp(normal, t, wave[:, current_start+index]))
        currents[consumer] = sample
        require(9e-6 <= sample <= 11e-6, f'{consumer} bank output {sample*1e6:.2f} uA outside 10 uA +/-10 %')
    observed = []
    for observation in experiment['observations']:
        code, when = observation['code'], observation['time_s']
        source = bindings[code]
        expected = 0 if source == 'VSS' else value(source, when)
        actual = value('ATB1', when)
        error = abs(actual-expected)
        require(error <= .005, f'ATB code {code} ({source}): pad {actual:.4f} V, net {expected:.4f} V')
        observed.append(dict(code=code, net=source, pad_v=actual, source_v=expected, error_v=error, time_s=when))
    by_code = {row['code']: row for row in observed}
    if 5 in by_code and 6 in by_code:
        separation = abs(by_code[5]['pad_v']-by_code[6]['pad_v'])
        require(separation > 4*.005 and by_code[5]['net'] != by_code[6]['net'],
                f'core / host supply taps (codes 5, 6) not distinguishable: both on {by_code[5]["net"]}/{by_code[6]["net"]}, '
                f'{separation*1e3:.1f} mV apart')
    if 2 in by_code:
        require(0.97 <= by_code[2]['pad_v'] <= 1.05, f'VREF0 {by_code[2]["pad_v"]:.4f} V out of window')
        require(abs(by_code[2]['pad_v']-value('VBG', by_code[2]['time_s'])*5/6) <= .01, 'VREF0 is not 5/6 VBG')
    if 3 in by_code:
        half = value('VDD', by_code[3]['time_s'])/2
        require(abs(by_code[3]['pad_v']-half) <= .02*half, f'VCM {by_code[3]["pad_v"]:.4f} V is not VDD/2 ({half:.4f})')
    forced = experiment['forced_at']
    if forced is not None:
        require(abs(value('VBG', forced)-1.2) <= .01, 'VBG force failed')
        require(abs(value('ATB1', forced)-value('VBG', forced)) <= .005, 'forced VBG not observable')
    from audit_core_bias_observation import audit
    try:
        independent = audit(out, 'wave.txt', out/'core-bias-audit.json')
        require(independent['status'] == 'pass', 'independent audit did not pass')
    except AssertionError as error:
        independent = dict(status='fail', error=repr(error), completed_checks=[])
        failures.append(f'independent audit: {error!r}')
    result = dict(chip=experiment['chip'], status='fail' if failures else 'pass', failures=failures,
                  negative=experiment.get('negative'),
                  scope=f'pt_{experiment["chip"]}: SPI-controlled extracted core bias and the chip ATB tree of the conn',
                  spi_reads=reads, nominal_vbg_v=vbg, nominal_bias_currents_a=currents, observations=observed,
                  not_observed=experiment['not_observed'],
                  forced_vbg_v=value('VBG', forced) if forced is not None else None,
                  idac1_smu=experiment.get('idac1_smu', False),
                  current_observations=[row for row in independent['completed_checks'] if row.get('check') == 'IDAC1 SMU current'],
                  frozen_source_manifest=experiment.get('frozen_source_manifest'),
                  excluded=['physical placement/routing of the core bias and ATB tree', 'real cold-start POR',
                            'actual payload consumer macros', 'PVT, mismatch and external board qualification'],
                  source_hashes={**experiment['source_hashes'], **experiment['bridge']['source_hashes']},
                  artifact_hashes={name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name in
                                   ['pt_chip.spice', 'experiment.json', 'wave.txt', 'ngspice.log']})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k in ['chip', 'status', 'failures', 'nominal_vbg_v', 'idac1_smu']}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir', type=Path, help='default scratch/core-bias-observation-<chip> (-idac1 with --idac1-smu)')
    parser.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    parser.add_argument('--island-pex', type=Path, default=ROOT/'scratch/island-support-20261108-075605')
    parser.add_argument('--ngspice-source', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--reuse-build', action='store_true')
    parser.add_argument('--reuse-bridge', action='store_true')
    parser.add_argument('--idac1-smu', action='store_true', help='Measure spare IDAC1 through ATB code 57 into a 1 V SMU')
    parser.add_argument('--negative', choices=('swap', 'enable'),
                        help='negative control (must FAIL; observes only the codes it needs)')
    parser.add_argument('--assess-only', action='store_true', help='Re-assess an existing completed wave.txt/ngspice.log')
    parser.add_argument('--timeout', type=float, default=21600)
    args = parser.parse_args()
    chip = os.environ['PT_CHIP']
    out = (args.output_dir or ROOT/f'scratch/core-bias-observation-{chip}{"-idac1" if args.idac1_smu else ""}').resolve()
    out.mkdir(parents=True, exist_ok=True)
    errors = ['Timestep too small', 'simulation(s) aborted', 'impossible delay', 'time is behind vtime']
    if args.assess_only:
        experiment = json.loads((out/'experiment.json').read_text())
        assert experiment.get('idac1_smu', False) == args.idac1_smu, 'Different observation mode'
        assert not any(error in (out/'ngspice.log').read_text() for error in errors)
        sys.exit(0 if assess(out, experiment)['status'] == 'pass' else 1)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    if args.reuse_build:
        experiment = json.loads((out/'experiment.json').read_text())
        assert experiment.get('idac1_smu', False) == args.idac1_smu, 'Different observation mode'
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in
                   {**experiment['source_hashes'], **experiment['bridge']['source_hashes']}.items()), 'Stale build'
    else:
        experiment = build(out, args.pdk.resolve(), args.island_pex.resolve(), args.ngspice_source.resolve(), chip,
                           args.reuse_bridge, args.idac1_smu, args.negative)
    if args.build_only:
        print(json.dumps(dict(chip=chip, codes=[o['code'] for o in experiment['observations']],
                              not_observed=experiment['not_observed'], build_failures=experiment['build_failures'],
                              stop_s=experiment['stop']), indent=2))
        sys.exit(0)
    (out/'wave.txt').unlink(missing_ok=True)
    started = time.monotonic()
    with (out/'ngspice.log').open('w') as log:
        with subprocess.Popen([str(args.ngspice_source.resolve()/'src/ngspice'), '-b', 'pt_chip.spice'], cwd=out,
                              stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'OMP_NUM_THREADS': '1'}) as process:
            from audit_chip_bringup import record
            record(out, process.pid)
            try:
                returncode = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            assert returncode == 0, ('ngspice failed', returncode)
    assert not any(error in (out/'ngspice.log').read_text() for error in errors)
    for checkpoint in out.glob('checkpoint-*.txt'):
        checkpoint.unlink()          # prefixes of wave.txt; keep the output dir small
    result = assess(out, experiment)
    result['analog_runtime_s'] = time.monotonic()-started
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    sys.exit(0 if result['status'] == 'pass' else 1)
