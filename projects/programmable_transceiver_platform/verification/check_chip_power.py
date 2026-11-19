#!/usr/bin/env python3
"""Live mixed-level power-up of one chip (PT_CHIP=rf|wired, required): real POR, extracted island switches, real
control RTL, provider host / debug pads.

Everything chip-specific comes from integration/chips/<chip>/chip.conn (parsed with integration/chips/check_top.py):
the island switches (master, EN bit, rail, PG pin), the enable groups (spec/chips.json) and the macro pins. The
generated top integration/chips/<chip>/generated/pt_chip.sv is audited against the conn for the instances this
bench depends on (digital macro, host pads, debug pads). The macro (pt_digital_macro with its PT_CHIP parameter)
runs through Verilator / XSPICE d_cosim.

Sequence: board ramp, board reset supervisor and the real POR; read ID / ABI / island status over SPI; enable the
chip's payload group (pt_rf: rf = rf_rx + rf_tx + lod + lo; pt_wired: wired = wired_rx + wired_cap + wired_tx) with
its power-good on DBG_OBS0; read the island status; disable it and read the status again.
Asserted: SPI reads, every rail off before the SPI enable, the payload group's rails and power-goods valid while on,
power-good at the debug pad, every other island off throughout, the payload rails discharged after the disable,
the supply ring in its window, POR release. Negative control (--negative <kind>, must FAIL): `group` expects the
other enable group, `pg_obs` observes a power-good that stays low, `rail` swaps one payload switch's EN to another
group. Fixture boundaries (declared, not extracted): per-island block capacitance and a 1 mA resistive load, 130 mA
always-on background, bond loop, board supervisor.

Helpers used by other scripts (keep): ports, instance, node, compact_parallel_fets, Spi, Registers, chip_model,
chip_connectivity, PROJECT, ROOT.
"""
import argparse
from collections import Counter
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

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'integration/chips'))
sys.path.insert(0, str(PROJECT/'rtl/gen'))


def node(name):
    return re.sub(r'\W', '_', name).rstrip('_')


def compact_parallel_fets(text):
    """Combine only identical parallel PDK FET instances; retain every capacitor.

    Each match has the same four nodes, model and ALL geometry parameters.
    PDK subcircuit multiplier m scales its entire device, including junctions.
    Independent internal nodes or an existing multiplier prevent combining.
    """
    text = re.sub(r'\n\+\s*', ' ', text)
    lines = text.splitlines()
    keys = []
    for line in lines:
        words = line.split()
        eligible = (len(words) > 6 and words[0].lower().startswith('x') and
                    words[5] in ('nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0')
                    and not any(w.lower().startswith('m=') for w in words[6:]))
        keys.append(' '.join(words[1:]) if eligible else None)
    # Counts reset for each subcircuit: identical local node names in different
    # cells must never result in devices moving between cells.
    output = []
    section = []
    def flush():
        counts = Counter(k for _, k in section if k is not None)
        seen = set()
        for line, key in section:
            if key is None:
                output.append(line)
            elif key not in seen:
                output.append(line+(f' m={counts[key]}' if counts[key] > 1 else ''))
                seen.add(key)
        section.clear()
    for line, key in zip(lines, keys):
        if line.lower().startswith(('.subckt', '.ends')):
            flush()
            output.append(line)
        else:
            section.append((line, key))
    flush()
    return '\n'.join(output)+'\n'


def ports(text, cell):
    text = re.sub(r'\n\+\s*', ' ', text)
    return next(line.split()[2:] for line in text.splitlines()
                if line.lower().startswith('.subckt '+cell.lower()+' '))


def instance(label, cell, text, connections):
    pins = ports(text, cell)
    if set(pins) != set(connections):
        raise ValueError(f'{cell} pin mismatch: {set(pins)^set(connections)}')
    return f'{label} '+ ' '.join(connections[p] for p in pins)+' '+cell


# ---------------------------------------------------------------- chip description (from the conn)

PG_GROUP_DECAP = dict(wired=150e-12, rf=200e-12, pll=250e-12, conv=250e-12, debug=100e-12)   # per island, declared
PAYLOAD = dict(rf='rf', wired='wired')        # the enable group this bench switches on, per chip


def chip_model(chip):
    """Islands, groups and macro pins of one chip from its conn (check_top loaders)."""
    import check_top
    conn_path = Path(check_top.HERE)/chip/'chip.conn'
    inst, _, _, err = check_top.parse(check_top.read_conn(str(conn_path)))
    assert not err, err
    spec = check_top.CHIPS[chip]
    groups = spec['enable_groups']
    islands = []
    for name, i in inst.items():
        if not i['master'].startswith('isw_'):
            continue
        pins = {k: v[1] for k, v in i['pins'].items()}
        bit = int(re.fullmatch(r'island_en\[(\d+)\]', pins['EN']).group(1))
        island = re.fullmatch(r'RAIL_(\w+)', pins['VISL']).group(1)
        group = check_top.GROUP_NAME[bit]
        assert island in spec['islands'] and groups.get(group) == bit, f'{name}: island {island} / group bit {bit} not on {chip}'
        assert pins['PG'] in ('s_pg_'+island, '-'), f'{name}: PG -> {pins["PG"]}'
        islands.append(dict(instance=name, master=i['master'], island=island, group=group, bit=bit,
                            rail=pins['VISL'], pg=pins['PG'], iso=pins['ISO']))
    # one island may have several switches in parallel (same rail and EN); exactly one reports its power-good
    assert sorted({i['island'] for i in islands}) == sorted(spec['islands']), 'island switches != spec/chips.json islands'
    for island in spec['islands']:
        mine = [i for i in islands if i['island'] == island]
        assert sum(i['pg'] != '-' for i in mine) == 1 and len({i['bit'] for i in mine}) == 1, f'{island}: switch PG/EN'
    digital = {k: v[1] for k, v in inst['digital']['pins'].items()}
    return dict(chip=chip, chip_id=spec['chip_id'], groups=groups, islands=islands, digital=digital, inst=inst,
                conn=str(conn_path))


def chip_connectivity(source, chip):
    """Audit the generated pt_chip.sv against the conn for the macro, host and debug pad instances: every conn pin
    binding must resolve (through the generated alias assigns) to the same chip net. Returns {instance: {pin: net}}."""
    model = chip_model(chip)
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    parent = {}
    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x
    def union(a, b):
        parent[find(a)] = find(b)
    const = {"1'b0": 'VSS', "1'b1": 'VDD'}
    for a, b in re.findall(r"\bassign\s+([\w\[\]]+)\s*=\s*([\w\[\]']+)\s*;", source):
        union(a, const.get(b, b))
    graph = {}
    for label in ('digital', 'host', 'debug_pads'):
        m = re.search(r'\b(\w+)\s*(?:#\s*\(.*?\)\s*)?'+label+r'\s*\((.*?)\);', source, re.S)
        assert m and m.group(1) == model['inst'][label]['master'], f'pt_chip.sv: instance {label} missing or wrong master'
        bound = dict(re.findall(r'\.(\w+)\(([^()]*)\)', m.group(2)))
        graph[label] = {}
        for pin, (kind, net) in model['inst'][label]['pins'].items():
            if net == '-' or kind == '~':       # supply / pad pins: the generator renames them (VDD_CORE, ...)
                continue
            base, bit = (pin[:-1].split('[') + [None])[:2] if '[' in pin else (pin, None)
            assert base in bound, f'pt_chip.sv {label}: pin {base} unbound'
            expr = bound[base].strip()
            token = f'{expr}[{bit}]' if bit is not None and '[' not in expr else expr
            assert find(const.get(token, token)) == find(net), f'pt_chip.sv {label}.{pin} = {token}, conn says {net}'
            graph[label][pin] = net
    if chip == 'rf' or chip == 'wired':
        m = re.search(r'pt_digital_macro\s*#\s*\(\s*\.PT_CHIP\((\d+)\)\s*\)\s*digital', source)
        assert m and int(m.group(1)) == model['chip_id'], 'pt_chip.sv: macro PT_CHIP parameter != spec/chips.json chip_id'
    return graph


# ---------------------------------------------------------------- SPI stimulus

class Spi:
    def __init__(self, start=.050):
        self.time = start
        self.points = {'SCLK': [(0, 0)], 'CS_N': [(0, 3.3)], 'MOSI': [(0, 0)]}
        self.reads = []
    def set(self, name, value):
        points = self.points[name]
        if points[-1][1] != value:
            points.extend([(self.time, points[-1][1]), (self.time+2e-9, value)])
    def transfer(self, command, address, value=0, expected=None):
        tx = (command << 24) | (address << 16) | value
        self.set('CS_N', 0)
        self.time += .05e-6
        samples = []
        for i in range(31, -1, -1):
            self.set('MOSI', 3.3*((tx >> i) & 1))
            self.time += .05e-6
            self.set('SCLK', 3.3)
            self.time += .05e-6
            if i < 16:
                samples.append(self.time-.01e-6)
            self.set('SCLK', 0)
        self.time += .05e-6
        self.set('CS_N', 3.3)
        self.time += .05e-6
        if expected is not None:
            self.reads.append({'address': address, 'expected': expected, 'sample_times': samples})
    def write(self, a, d):
        self.transfer(0x80, a, d)
    def read(self, a, expected):
        self.transfer(0, a, expected=expected)
    def sources(self):
        sources = []
        for name, pts in self.points.items():
            sources += [f'V{name} SRC_{name} 0 PWL('+ ' '.join(f'{t:.15g} {v:g}' for t, v in pts)+')',
                        f'Shost_{name} SRC_{name} {name} VDD 0 host_switch']
        return sources


class Registers:
    """Shadow register writes and commits of one chip (rtl/gen/pt_regmap.py in the chip's view)."""
    def __init__(self, spi, chip):
        import pt_regmap
        self.regmap = pt_regmap
        pt_regmap.chip_view(chip)
        self.spi = spi
        self.values = pt_regmap.reset_config()
        self.active = dict(self.values)
    def write(self, **values):
        addresses = set()
        for name, value in values.items():
            field = self.regmap.FIELD_BY_NAME[name]
            assert not field.get('absent'), f'{name} is not on this chip'
            self.values[name] = value
            addresses.update(c['addr'] for c in field['chunks'])
        for address in sorted(addresses):
            value = 0
            for name, lsb, width, reg_lsb in self.regmap.REGISTER_BY_ADDR[address]['chunks']:
                value |= ((self.values[name] >> lsb) & ((1 << width)-1)) << reg_lsb
            self.spi.write(address, value)
    def commit(self):
        code = self.regmap.commit_code(self.values, self.active, False)
        assert code == 0, f'Invalid bench configuration: commit error {code}'
        self.spi.write(6, 1)
        self.active = dict(self.values)


def control_sequence(model, negative=None):
    import pt_regmap
    spi = Spi()
    regs = Registers(spi, model['chip'])
    group = PAYLOAD[model['chip']]
    bit = model['groups'][group]
    obs = json.loads((PROJECT/'spec/debug-controls.json').read_text())['obs_status']
    expect_bit = bit
    if negative == 'group':
        expect_bit = next(b for g, b in model['groups'].items() if g != group)
    observe = group
    if negative == 'pg_obs':
        observe = next(g for g in model['groups'] if g != group)
    spi.read(0, pt_regmap.ID_VALUE)
    spi.read(8, pt_regmap.ABI_VERSION)
    spi.read(0x0a, 0)
    regs.write(**{f'debug.island_power.{group}': 1, 'debug.dbg_obs.sel0': 4+obs.index('island_pgood_'+observe)})
    regs.commit()
    spi.time += 20e-6
    spi.read(0x0a, (1 << expect_bit) | (1 << (8+expect_bit)))
    observed_at = spi.time+1e-6
    spi.time += 5e-6
    spi.read(0x05, 0)
    regs.write(**{f'debug.island_power.{group}': 0})
    regs.commit()
    spi.time += 20e-6
    spi.read(0x0a, 0)
    return dict(spi=spi, observed_at=observed_at, stop=spi.time+10e-6, payload_group=group,
                disabled_at=observed_at+5e-6)


# ---------------------------------------------------------------- deck

def build(out, bridge, pdk, island_pex, chip, *, extension=None, sequence=None, charge_moscap=False, negative=None):
    used = []
    def read(path):
        path = Path(path).resolve()
        used.append(path)
        return path.read_text()
    model = chip_model(chip)
    read(model['conn'])
    top_path = PROJECT/f'integration/chips/{chip}/generated/pt_chip.sv'
    parent_graph = chip_connectivity(read(top_path), chip)
    library = read(pdk/'gf180mcu_fd_io.spice')
    por = read(PROJECT/'analog/core_support/por/netlist/layout/gf180mcu_ocd_ip__por.spice')
    support = {}
    for isl in model['islands']:
        cell = isl['master']
        if cell not in support:
            support[cell] = compact_parallel_fets(read(island_pex/f'pex/{cell}/{cell}.pex.spice'))
    islands = [dict(i) for i in model['islands']]
    if negative == 'rail':
        # one payload switch takes its EN from another group: the payload rails are then not all on
        victim = next(i for i in islands if i['group'] == PAYLOAD[chip])
        victim['bit'] = next(b for g, b in model['groups'].items() if g != PAYLOAD[chip])
    scenario = (sequence or control_sequence)(model, negative)
    spi = scenario.pop('spi')
    observed_at, stop = scenario['observed_at'], scenario['stop']
    extra = extension(read, support, pdk, library, scenario) if extension else {}
    digital_inputs, digital_outputs = bridge['inputs'], bridge['outputs']
    inputs = {n: '0' for n in digital_inputs}
    inputs.update(reset_n_pad='RESET_Y', por_n='POR_N', spi_sclk='SCLK_Y', spi_cs_n='CS_Y', spi_mosi='MOSI_Y')
    for pin in [p for p in digital_inputs if p.startswith('s_pg_')]:
        net = model['digital'][pin]
        if net == 'VSS':
            continue
        isl = next(i for i in islands if i['pg'] == net)      # the switch that reports this island's power-good
        inputs[pin] = 'PG_'+isl['island']
    inputs.update(extra.get('inputs', {}))
    bits = sorted({i['bit'] for i in model['islands']})
    wanted = ['spi_miso', 'spi_miso_oe', 'dbg_obs0', 'dbg_obs0_oe']
    wanted += [f'island_en[{b}]' for b in bits]+[f'island_on[{b}]' for b in bits]
    wanted += extra.get('outputs', [])
    for name in wanted:
        if name not in digital_outputs:
            raise ValueError(f'Compiled digital macro is missing {name}')
    d = [f'* Mixed-level power-up of pt_{chip}: real POR, extracted island switches, real control RTL',
         f'.include {pdk}/ngspice/design.ngspice']
    d += [f'.lib {pdk}/ngspice/sm141064.ngspice {c}' for c in ('typical', 'res_typical', 'diode_typical', 'mimcap_typical')]
    if charge_moscap:
        from moscap_charge import overlay
        read(Path(__file__).with_name('moscap_charge.py'))
        d.append(overlay(pdk))
    else:
        d.append(f'.lib {pdk}/ngspice/sm141064.ngspice moscap_typical')
    d += ['.temp 27', library, por, *support.values(),
          '.model to_logic adc_bridge(in_low=1.0 in_high=2.3)',
          '.model constant_zero d_pulldown',
          '.model to_voltage dac_bridge(out_low=0 out_high=1 out_undef=0.5 input_load=0 t_rise=1e-10 t_fall=1e-10)',
          f'.model macro d_cosim(simulation="{bridge["library"]}" delay=1e-9 queue_size=4096)']
    d += extra.get('models', [])
    d += ['.subckt pt_host_physical VDD VSS RESET_N SCLK CS_N MOSI MISO RESET_Y SCLK_Y CS_Y MOSI_Y MISO_A MISO_OE']
    for name, pad, y, cell in [('reset', 'RESET_N', 'RESET_Y', 'in_c'), ('clock', 'SCLK', 'SCLK_Y', 'bi_24t'),
                               ('select', 'CS_N', 'CS_Y', 'bi_24t'), ('data', 'MOSI', 'MOSI_Y', 'bi_24t')]:
        conn = dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD=pad,
                    PU='VSS', PD='VDD' if name == 'reset' else 'VSS', Y=y)
        if cell == 'bi_24t':
            conn.update(A='VSS', CS='VSS', SL='VSS', OE='VSS', IE='VDD')
        d.append(instance('X'+name, 'gf180mcu_fd_io__'+cell, library, conn))
    d.append(instance('Xreturn', 'gf180mcu_fd_io__bi_t', library,
                      dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD='MISO', PU='VSS', PD='VSS', Y='UNUSED',
                           A='MISO_A', CS='VSS', SL='VSS', OE='MISO_OE', IE='VSS', PDRV0='VSS', PDRV1='VDD')))
    d += ['.ends pt_host_physical',
          '.subckt pt_debug_physical VDD VSS A OE PAD',
          instance('Xobserve', 'gf180mcu_fd_io__bi_24t', library,
                   dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD='PAD', PU='VSS', PD='VSS', Y='UNUSED', A='A',
                        CS='VSS', SL='VSS', OE='OE', IE='VSS')),
          '.ends pt_debug_physical']
    analog_pins = ['VDD', 'VSS', 'POR_N']+[f'EN_{b}' for b in bits]
    names = list(dict.fromkeys(i['island'] for i in islands))
    analog_pins += [f'{p}_{n}' for n in names for p in ('PG', 'RAIL')]
    analog_pins += extra.get('analog_pins', [])
    d += ['.subckt pt_analog_physical '+' '.join(analog_pins),
          instance('Xpor', 'gf180mcu_ocd_ip__por', por,
                   dict(vdd3v3='VDD', ena='VDD', por_unbuf='POR_U', vss='VSS', porb='POR_N', por='POR')),
          'CPOR_N POR_N VSS 1p', 'CPOR POR VSS 1p']
    decaps = {}
    for i in islands:
        name = i['island']
        pg = f'PG_{name}' if i['pg'] != '-' else f'PG_{node(i["instance"])}'
        d.append(instance(f'X{node(i["instance"])}', f'{i["master"]}_pex', support[i['master']],
                          dict(VDD='VDD', VSS='VSS', VISL=f'RAIL_{name}', EN=f'EN_{i["bit"]}',
                               ISO=f'ISO_{node(i["instance"])}', PG=pg)))
        if name not in decaps:
            decaps[name] = PG_GROUP_DECAP[i['group']]
            d += [f'Cdecap_{name} RAIL_{name} VSS {decaps[name]}', f'Rload_{name} RAIL_{name} VSS 3300']
    d += extra.get('analog_body', [])
    chip_extra_pins = extra.get('chip_pins', [])
    d += ['.ends pt_analog_physical',
          '.subckt pt_chip VDD VSS RESET_N SCLK CS_N MOSI MISO DBG_OBS0 '+' '.join(chip_extra_pins),
          'Xhost VDD VSS RESET_N SCLK CS_N MOSI MISO RESET_Y SCLK_Y CS_Y MOSI_Y A_spi_miso A_spi_miso_oe pt_host_physical',
          'Azero D_ZERO constant_zero']
    for k, (port, source) in enumerate(inputs.items()):
        if source != '0':
            d.append(f'Ain{k} [{source}] [I_{node(port)}] to_logic')
    d.append('Adigital ['+' '.join('I_'+node(n) if inputs[n] != '0' else 'D_ZERO' for n in digital_inputs)+'] ['+
             ' '.join('O_'+node(n) for n in digital_outputs)+'] NULL macro')
    for k, n in enumerate(wanted):
        d += [f'Aout{k} [O_{node(n)}] [U_{node(n)}] to_voltage', f'Bscale{k} A_{node(n)} VSS V=V(U_{node(n)})*V(VDD,VSS)']
    nets = ['VDD', 'VSS', 'POR_N']+[f'A_island_en_{b}' for b in bits]
    nets += [f'{p}_{n}' for n in names for p in ('PG', 'RAIL')]
    nets += extra.get('analog_connections', [])
    d += ['Xanalog '+' '.join(nets)+' pt_analog_physical',
          'Xdebug_pads VDD VSS A_dbg_obs0 A_dbg_obs0_oe DBG_OBS0 pt_debug_physical']
    d += extra.get('chip_body', [])
    d += ['.ends pt_chip']
    global_decap = extra.get('global_decap_f', 1e-9)
    bond_loop_r = extra.get('bond_loop_r_ohm', .0125)
    probes = {'VDD': 'v(VDD)', 'MISO': 'v(MISO)', 'DBG_OBS0': 'v(DBG_OBS0)', 'POR_N': 'v(Xchip.POR_N)'}
    for i in [i for i in islands if i['pg'] != '-']:
        probes['RAIL_'+i['island']] = f'v(Xchip.RAIL_{i["island"]})'
        probes['PG_'+i['island']] = f'v(Xchip.PG_{i["island"]})'
    for b in bits:
        probes[f'EN_{b}'] = f'v(Xchip.A_island_en_{b})'
        probes[f'ON_{b}'] = f'v(Xchip.A_island_on_{b})'
    for k, p in enumerate(extra.get('probes', [])):
        probes[f'extra{k}'] = p
    d += ['VBOARD BOARD 0 PWL(0 0 1u 3.3)', f'RBOND BOARD BOND {bond_loop_r:.12g}',
          'LBOND BOND VDD 2n', 'RDAMP BOND VDD 2', f'CGLOBAL VDD 0 {global_decap:.12g}',
          'BBACKGROUND VDD 0 I=0.13*min(max(V(VDD)/3.3,0),1)',
          # Board reset-supervisor boundary: holds reset for 1 ms, reasserts below 3.15 V, releasing above 3.25 V.
          '.model board_switch sw(Ron=1 Roff=1e12 Vt=0.5 Vh=0)',
          '.model host_switch sw(Ron=1 Roff=1e12 Vt=3.2 Vh=0.05)',
          '.model undervoltage sw(Ron=1e12 Roff=1 Vt=3.2 Vh=0.05)',
          'Vhold HOLD 0 PWL(0 1 1m 1 1.00001m 0)',
          'Sreset_hold RESET_N 0 HOLD 0 board_switch',
          'Sreset_uv RESET_N 0 VDD 0 undervoltage', 'Rreset_pullup VDD RESET_N 4700',
          *spi.sources(), 'RMISO MISO 0 1g', 'CMISO MISO 0 5p', 'RDBG DBG_OBS0 0 1g', 'CDBG DBG_OBS0 0 5p',
          'Xchip VDD 0 RESET_N SCLK CS_N MOSI MISO DBG_OBS0 '+' '.join(chip_extra_pins)+' pt_chip',
          *extra.get('bench_body', []),
          '.options klu reltol=1e-3 method=gear rshunt=1e12 cshunt=1e-17',
          '.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
          'save '+' '.join(probes.values()), f'tran 1u {stop:.15g} 0 200u',
          'wrdata wave.txt '+' '.join(probes.values()), 'quit', '.endc', '.end']
    (out/'pt_chip.spice').write_text('\n'.join(d)+'\n')
    used += list((pdk/'ngspice').glob('*.ngspice'))+list((pdk/'ngspice').glob('*.spice'))
    used += [Path(__file__).resolve()]
    return dict(chip=chip, reads=spi.reads, **scenario, negative=negative, columns=list(probes),
                islands=[{k: v for k, v in i.items()} for i in islands], island_decap_f=decaps,
                moscap_realization='analytical_charge_integral' if charge_moscap else 'native_nonlinear_capacitance',
                assembly_source=str(top_path.relative_to(ROOT)), parent_connectivity=parent_graph,
                board_assumptions=dict(supervisor_release_v=3.25, supervisor_assert_v=3.15, startup_hold_s=.001,
                                       spi_hz=10e6, payload_clocks='stopped', background_load_ma=130,
                                       island_load_ohm=3300, bond_loop_r_ohm=bond_loop_r, global_decap_f=global_decap),
                source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in used})


def assess(out, experiment):
    wave = np.loadtxt(out/'wave.txt', skiprows=1)
    assert wave.shape[1] == len(experiment['columns'])+1, 'waveform schema'
    col = {name: k+1 for k, name in enumerate(experiment['columns'])}
    t = wave[:, 0]
    assert np.all(np.isfinite(wave)), 'nonfinite analog results'
    assert t[-1] >= experiment['stop']*(1-1e-8), 'transient did not finish'
    assert np.all(np.diff(t) >= 0), 'nonmonotone transient output'
    def v(name, when):
        return float(np.interp(when, t, wave[:, col[name]]))
    failures = []
    def require(ok, message):
        if not ok:
            failures.append(message)
    reads = []
    for rd in experiment['reads']:
        levels = [v('MISO', s) for s in rd['sample_times']]
        value = 0
        for level in levels:
            value = (value << 1) | (level >= 2.3)
        reads.append(dict(address=rd['address'], actual=value, expected=rd['expected'],
                          defined=not any(1.0 < x < 2.3 for x in levels)))
        require(reads[-1]['defined'], f'SPI read 0x{rd["address"]:02x} has undefined voltage levels')
        require(value == rd['expected'], f'SPI read 0x{rd["address"]:02x} = 0x{value:04x}, expected 0x{rd["expected"]:04x}')
    observed = experiment['observed_at']
    require(v('DBG_OBS0', observed) > 2.3, 'payload power-good did not reach DBG_OBS0')
    startup = (t > 1e-6) & (t < .049)
    running = t > .049
    require(np.min(wave[running, col['VDD']]) >= 3.15 and np.max(wave[running, col['VDD']]) <= 3.35,
            'ring outside functional envelope')
    payload = experiment['payload_group']
    rails = {}
    for i in [i for i in experiment['islands'] if i['pg'] != '-']:
        name = i['island']
        rail = wave[:, col['RAIL_'+name]]
        rails[name] = dict(group=i['group'], startup_max_v=float(np.max(rail[startup])), at_observation_v=v('RAIL_'+name, observed),
                           pg_at_observation_v=v('PG_'+name, observed), at_stop_v=v('RAIL_'+name, experiment['stop']))
        require(rails[name]['startup_max_v'] < .35, f'{name} rail powered before the SPI enable')
        if i['group'] == payload:
            require(rails[name]['at_observation_v'] >= 3.15, f'{name} rail {rails[name]["at_observation_v"]:.3f} V < 3.15 V while enabled')
            require(rails[name]['pg_at_observation_v'] > 2.3, f'{name} power-good low while enabled')
            require(rails[name]['at_stop_v'] < .3, f'{name} rail did not discharge after the disable')
        else:
            require(float(np.max(rail)) < .35, f'nonselected island {name} powered')
    por = np.nonzero((wave[:, col['POR_N']] > 2.3) & (t > 1e-6))[0]
    require(len(por) > 0, 'physical POR did not release')
    return dict(status='fail' if failures else 'pass', failures=failures, chip=experiment['chip'], goal_complete=False,
                spi_reads=reads, por_release_s=float(t[por[0]]) if len(por) else None,
                dbg_obs0_v=v('DBG_OBS0', observed), rails=rails,
                scope=f'pt_{experiment["chip"]}: live POR, extracted island switches of the conn, SPI status and '
                      'debug pad with the real control RTL',
                excluded=['inactive payload circuit loading (1 mA resistive fixture load per island)',
                          'core-boundary isolation-clamp loading and fault behavior',
                          'full-chip physical routing/DRC/LVS', 'corner and mismatch coverage',
                          'physical implementation of the board reset supervisor'],
                **{k: v_ for k, v_ in experiment.items() if k not in ('reads', 'chip')})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir', type=Path, help='default scratch/chip-power-<chip>')
    parser.add_argument('--ngspice-source', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47')
    parser.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    parser.add_argument('--island-pex', type=Path, default=ROOT/'scratch/island-support-20261108-075605')
    parser.add_argument('--reuse-bridge', action='store_true')
    parser.add_argument('--negative', choices=('group', 'pg_obs', 'rail'), help='negative control (must FAIL)')
    parser.add_argument('--timeout', type=float, default=7200, help='maximum analog simulation wall time in seconds')
    args = parser.parse_args()
    chip = os.environ['PT_CHIP']
    out = (args.output_dir or ROOT/f'scratch/chip-power-{chip}').resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    (out/'wave.txt').unlink(missing_ok=True)
    ng = args.ngspice_source.resolve()
    model = chip_model(chip)
    from cosim_bridge import compile_bridge
    if args.reuse_bridge:
        bridge = json.loads((out/'bridge/ports.json').read_text())
        for p, h in bridge['source_hashes'].items():
            assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h, f'stale bridge: {p}'
        assert bridge['parameters'] == {'PT_CHIP': model['chip_id']}, 'bridge built for another chip'
    else:
        bridge = compile_bridge(sorted((PROJECT/'rtl').glob('*.sv')), 'pt_digital_macro', out/'bridge', ng,
                                includes=[PROJECT/'rtl'], parameters={'PT_CHIP': model['chip_id']},
                                expose_outputs=['spi_miso', 'spi_miso_oe', 'island_en', 'island_on', 'dbg_obs0', 'dbg_obs0_oe'],
                                expose_inputs=['reset_n_pad', 'por_n', 'spi_sclk', 'spi_cs_n', 'spi_mosi']+
                                              [p for p in model['digital'] if p.startswith('s_pg_')])
        shutil.rmtree(out/'bridge/obj')        # digital.so is self-contained; keep the output dir small
    experiment = build(out, bridge, args.pdk.resolve(), args.island_pex.resolve(), chip, negative=args.negative)
    (out/'experiment.json').write_text(json.dumps(experiment, indent=2)+'\n')
    models = ng/'src/xspice/icm'
    (out/'.spiceinit').write_text('set ngbehavior=hs\n'+
        '\n'.join(f'codemodel {models}/{name}/{name}.cm' for name in ('analog', 'digital'))+'\n')
    started = time.monotonic()
    with (out/'ngspice.log').open('w') as log:
        subprocess.run([str(ng/'src/ngspice'), '-b', 'pt_chip.spice'], cwd=out, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=args.timeout, env={**os.environ, 'OMP_NUM_THREADS': '1'})
    text = (out/'ngspice.log').read_text()
    for error in ('impossible delay', 'time is behind vtime', 'simulation(s) aborted', 'Timestep too small'):
        if error in text:
            raise RuntimeError(f'Invalid mixed simulation: {error}')
    report = assess(out, experiment)
    report['bridge_parameters'] = bridge.get('parameters')
    report['bridge_source_hashes'] = bridge['source_hashes']
    report['ngspice_sha256'] = hashlib.sha256((ng/'src/ngspice').read_bytes()).hexdigest()
    report['analog_runtime_s'] = time.monotonic()-started
    report['wave_sha256'] = hashlib.sha256((out/'wave.txt').read_bytes()).hexdigest()
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    subprocess.run(['gzip', '-f', str(out/'wave.txt')], check=True)     # keep the output dir small
    print(json.dumps({k: report[k] for k in ('chip', 'status', 'failures', 'por_release_s', 'dbg_obs0_v', 'analog_runtime_s')}, indent=2))
    if report['status'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
