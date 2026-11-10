#!/usr/bin/env python3
"""Live mixed-level bring-up: real POR/island/pad circuits and control RTL.

The generated SPICE pt_chip contains pt_host_physical, pt_analog_physical,
pt_debug_physical and the real pt_digital_macro via XSPICE/Verilator. Physical
ring placement, inactive payload macros and fallback data remain open.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np

from cosim_bridge import compile_bridge

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


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


def chip_connectivity(source):
    """Audit the parent hierarchy, rather than relying on repeated net names."""
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    graph = {}
    for module, label in [('pt_host_physical', 'host'), ('pt_analog_physical', 'analog'),
                          ('pt_debug_physical', 'debug_pads')]:
        declaration = re.search(r'\bmodule\s+'+module+r'\s*\((.*?)\);', source, re.S).group(1)
        pins = [re.search(r'(\w+)\s*$', p).group(1) for p in declaration.split(',')]
        actual = re.search(r'\b'+module+r'\s+'+label+r'\s*\((.*?)\);', source, re.S).group(1)
        nets = [p.strip() for p in actual.split(',')]
        assert len(pins) == len(nets), f'{label} positional pin mismatch'
        graph[label] = dict(zip(pins, nets))
    digital = re.search(r'pt_digital_macro\s+digital\((.*?)\);', source, re.S).group(1)
    graph['digital'] = dict(re.findall(r'\.(\w+)\(([^()]*)\)', digital))
    def joined(a, b):
        an, ap = a.split('.')
        bn, bp = b.split('.')
        assert graph[an][ap] == graph[bn][bp], f'parent connection changed: {a} -> {b}'
    for dp, hp in [('reset_n_pad', 'rst_n'), ('spi_sclk', 'sclk'), ('spi_cs_n', 'cs_n'),
                   ('spi_mosi', 'mosi'), ('spi_miso', 'miso'), ('spi_miso_oe', 'miso_oe')]:
        joined('digital.'+dp, 'host.'+hp)
    for pin in ['por_n', 'analog_cfg', 'debug_cfg', 'island_en', 'island_on',
                'island_pgood', 'wire_analog_status', 'rx_en_wtx_ext', 'atb0_sw', 'atb0_grp', 'atb0_en']:
        joined('digital.'+pin, 'analog.'+pin)
    for pin in ['dbg_obs0', 'dbg_obs0_oe', 'wdbg_obs', 'wdbg_obs_oe']:
        joined('digital.'+pin, 'debug_pads.'+pin)
    for pin in ['WTX_EXT_P', 'WTX_EXT_N', 'WIRE_TX_P', 'WIRE_TX_N', 'ATB0']:
        assert graph['analog'][pin] == pin, f'external analog pad connection changed: {pin}'
    for pin in ['DBG_OBS0', 'WDBG_OBS']:
        assert graph['debug_pads'][pin] == pin, f'external debug pad connection changed: {pin}'
    return graph


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


def control_sequence():
    spi = Spi()
    spi.read(0, 0x5356)
    spi.read(8, 2)
    spi.read(0x0a, 0)
    spi.write(0x40, 1)
    spi.write(6, 1)
    spi.time += 20e-6
    spi.read(0x0a, 0x0101)
    spi.write(0x4e, 4)
    spi.write(6, 1)
    observed_at = spi.time+1e-6
    spi.time += 5e-6
    spi.read(0x05, 0)
    spi.write(0x40, 0)
    spi.write(6, 1)
    spi.time += 20e-6
    spi.read(0x0a, 0)
    return dict(spi=spi, observed_at=observed_at, stop=spi.time+10e-6)


def build(out, bridge, pdk, island_pex, *, extension=None, sequence=control_sequence,
          charge_moscap=False):
    used = []
    def read(path):
        path = Path(path).resolve()
        used.append(path)
        return path.read_text()
    chip = read(PROJECT/'integration/pt_chip.sv')
    parent_graph = chip_connectivity(chip)
    digital = re.search(r'pt_digital_macro digital\((.*?)\);', chip, re.S).group(1)
    bindings = dict(re.findall(r'\.(\w+)\(([^()]*)\)', digital))
    for pin, net in dict(reset_n_pad='pad_rst_n', por_n='por_n', spi_sclk='sclk',
                         spi_cs_n='cs_n', spi_mosi='mosi', spi_miso='miso', spi_miso_oe='miso_oe',
                         island_pgood='island_pgood', island_en='island_en', island_on='island_on',
                         dbg_obs0='dbg_obs0', dbg_obs0_oe='dbg_obs0_oe').items():
        if bindings.get(pin) != net:
            raise ValueError(f'pt_chip digital connection changed: {pin}')
    library = read(pdk/'gf180mcu_fd_io.spice')
    por_path = PROJECT/'analog/core_support/por/netlist/layout/gf180mcu_ocd_ip__por.spice'
    por = read(por_path)
    support = {}
    for name in ('wired', 'rf', 'pll', 'conv', 'debug'):
        support[name] = compact_parallel_fets(read(island_pex/f'pex/isw_{name}/isw_{name}.pex.spice'))
    scenario = sequence()
    spi = scenario.pop('spi')
    observed_at, stop = scenario['observed_at'], scenario['stop']
    extra = extension(read, support, pdk, library, scenario) if extension else {}
    digital_inputs = bridge['inputs']
    digital_outputs = bridge['outputs']
    # These are the live connections used by the selected bring-up assembly.
    inputs = {n: '0' for n in digital_inputs}
    inputs.update(reset_n_pad='RESET_Y', por_n='POR_N', spi_sclk='SCLK_Y',
                  spi_cs_n='CS_Y', spi_mosi='MOSI_Y')
    bits = {'wired': 0, 'rf': 1, 'pll': 2, 'conv': 4, 'debug': 5}
    for name, bit in bits.items():
        inputs[f'island_pgood[{bit}]'] = f'PG_{name}'
    inputs.update(extra.get('inputs', {}))
    wanted = ['spi_miso', 'spi_miso_oe', 'dbg_obs0', 'dbg_obs0_oe']
    wanted += [f'island_en[{bit}]' for bit in bits.values()]
    wanted += [f'island_on[{bit}]' for bit in bits.values()]
    wanted += extra.get('outputs', [])
    for name in wanted:
        if name not in digital_outputs:
            raise ValueError(f'Compiled digital macro is missing {name}')
    d = ['* Mixed-level assembled bring-up; physical inactive payloads are not yet bound.',
         f'.include {pdk}/ngspice/design.ngspice']
    d += [f'.lib {pdk}/ngspice/sm141064.ngspice {c}' for c in
          ('typical', 'res_typical', 'diode_typical', 'mimcap_typical')]
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
    for name, pad, y, cell in [('reset','RESET_N','RESET_Y','in_c'),
                              ('clock','SCLK','SCLK_Y','bi_24t'),
                              ('select','CS_N','CS_Y','bi_24t'),
                              ('data','MOSI','MOSI_Y','bi_24t')]:
        conn = dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD=pad,
                    PU='VSS', PD='VDD' if name == 'reset' else 'VSS', Y=y)
        if cell == 'bi_24t':
            conn.update(A='VSS', CS='VSS', SL='VSS', OE='VSS', IE='VDD')
        d.append(instance('X'+name, 'gf180mcu_fd_io__'+cell, library, conn))
    d.append(instance('Xreturn', 'gf180mcu_fd_io__bi_t', library,
                     dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD='MISO',
                          PU='VSS', PD='VSS', Y='UNUSED', A='MISO_A', CS='VSS',
                          SL='VSS', OE='MISO_OE', IE='VSS', PDRV0='VSS', PDRV1='VDD')))
    d += ['.ends pt_host_physical',
          '.subckt pt_debug_physical VDD VSS A OE PAD',
          instance('Xobserve', 'gf180mcu_fd_io__bi_24t', library,
                   dict(DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS', PAD='PAD',
                        PU='VSS', PD='VSS', Y='UNUSED', A='A', CS='VSS',
                        SL='VSS', OE='OE', IE='VSS')),
          '.ends pt_debug_physical']
    analog_pins = ['VDD', 'VSS', 'POR_N']
    analog_pins += [f'{prefix}_{name}' for name in bits for prefix in ('EN', 'PG', 'RAIL')]
    analog_pins += extra.get('analog_pins', [])
    d += ['.subckt pt_analog_physical '+' '.join(analog_pins),
          instance('Xpor', 'gf180mcu_ocd_ip__por', por,
                   dict(vdd3v3='VDD', ena='VDD', por_unbuf='POR_U', vss='VSS', porb='POR_N', por='POR')),
          'CPOR_N POR_N VSS 1p', 'CPOR POR VSS 1p']
    decaps = dict(wired=150e-12, rf=200e-12, pll=250e-12, conv=250e-12, debug=100e-12)
    for name in bits:
        d += [instance(f'Xswitch_{name}', f'isw_{name}_pex', support[name],
                       dict(VDD='VDD', VSS='VSS', VISL=f'RAIL_{name}', EN=f'EN_{name}',
                            ISO=f'ISO_{name}', PG=f'PG_{name}')),
              f'Cdecap_{name} RAIL_{name} VSS {decaps[name]}',
              f'Rload_{name} RAIL_{name} VSS 3300']
    d += extra.get('analog_body', [])
    chip_extra_pins = extra.get('chip_pins', [])
    d += ['.ends pt_analog_physical',
          '.subckt pt_chip VDD VSS RESET_N SCLK CS_N MOSI MISO DBG_OBS0 '+ ' '.join(chip_extra_pins),
          'Xhost VDD VSS RESET_N SCLK CS_N MOSI MISO RESET_Y SCLK_Y CS_Y MOSI_Y A_spi_miso A_spi_miso_oe pt_host_physical']
    d.append('Azero D_ZERO constant_zero')
    for i, (port, source) in enumerate(inputs.items()):
        if source != '0':
            d.append(f'Ain{i} [{source}] [I_{node(port)}] to_logic')
    d.append('Adigital ['+' '.join('I_'+node(n) if inputs[n] != '0' else 'D_ZERO' for n in digital_inputs)+'] ['+
             ' '.join('O_'+node(n) for n in digital_outputs)+'] NULL macro')
    for i, n in enumerate(wanted):
        d += [f'Aout{i} [O_{node(n)}] [U_{node(n)}] to_voltage',
              f'Bscale{i} A_{node(n)} VSS V=V(U_{node(n)})*V(VDD,VSS)']
    nets = ['VDD', 'VSS', 'POR_N']
    nets += [v for name, bit in bits.items() for v in
             (f'A_island_en_{bit}', f'PG_{name}', f'RAIL_{name}')]
    nets += extra.get('analog_connections', [])
    d += ['Xanalog '+' '.join(nets)+' pt_analog_physical',
          'Xdebug_pads VDD VSS A_dbg_obs0 A_dbg_obs0_oe DBG_OBS0 pt_debug_physical']
    d += extra.get('chip_body', [])
    d += ['.ends pt_chip']
    global_decap = extra.get('global_decap_f', 1e-9)
    bond_loop_r = extra.get('bond_loop_r_ohm', .0125)
    d += ['VBOARD BOARD 0 PWL(0 0 1u 3.3)', f'RBOND BOARD BOND {bond_loop_r:.12g}',
          'LBOND BOND VDD 2n', 'RDAMP BOND VDD 2', f'CGLOBAL VDD 0 {global_decap:.12g}',
          'BBACKGROUND VDD 0 I=0.13*min(max(V(VDD)/3.3,0),1)',
          # Board reset-supervisor boundary: holds reset for 1 ms, reasserts
          # below 3.15 V, releasing above 3.25 V. Represents board B1.
          '.model board_switch sw(Ron=1 Roff=1e12 Vt=0.5 Vh=0)',
          '.model host_switch sw(Ron=1 Roff=1e12 Vt=3.2 Vh=0.05)',
          '.model undervoltage sw(Ron=1e12 Roff=1 Vt=3.2 Vh=0.05)',
          'Vhold HOLD 0 PWL(0 1 1m 1 1.00001m 0)',
          'Sreset_hold RESET_N 0 HOLD 0 board_switch',
          'Sreset_uv RESET_N 0 VDD 0 undervoltage', 'Rreset_pullup VDD RESET_N 4700',
          *spi.sources(), 'RMISO MISO 0 1g', 'CMISO MISO 0 5p',
          'RDBG DBG_OBS0 0 1g', 'CDBG DBG_OBS0 0 5p',
          'Xchip VDD 0 RESET_N SCLK CS_N MOSI MISO DBG_OBS0 '+ ' '.join(chip_extra_pins)+' pt_chip',
          *extra.get('bench_body', []),
          '.options klu reltol=1e-3 method=gear rshunt=1e12 cshunt=1e-17',
          '.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
          'save v(VDD) v(MISO) v(DBG_OBS0) v(Xchip.POR_N) '+
          ' '.join(f'v(Xchip.RAIL_{n}) v(Xchip.PG_{n})' for n in bits)+
          ' v(Xchip.A_island_en_0) v(Xchip.A_island_on_0) '+ ' '.join(extra.get('probes', [])),
          f'tran 1u {stop:.15g} 0 200u',
          'wrdata wave.txt v(VDD) v(MISO) v(DBG_OBS0) v(Xchip.POR_N) '+
          ' '.join(f'v(Xchip.RAIL_{n}) v(Xchip.PG_{n})' for n in bits)+
          ' v(Xchip.A_island_en_0) v(Xchip.A_island_on_0) '+ ' '.join(extra.get('probes', [])),
          'quit', '.endc', '.end']
    (out/'pt_chip.spice').write_text('\n'.join(d)+'\n')
    used += list((pdk/'ngspice').glob('*.ngspice'))+list((pdk/'ngspice').glob('*.spice'))
    used += [Path(__file__).resolve()]
    return dict(reads=spi.reads, **scenario,
                moscap_realization='analytical_charge_integral' if charge_moscap else 'native_nonlinear_capacitance',
                assembly_source='integration/pt_chip.sv', digital_bindings=bindings,
                parent_connectivity=parent_graph,
                board_assumptions=dict(supervisor_release_v=3.25, supervisor_assert_v=3.15,
                                       startup_hold_s=.001, spi_hz=10e6,
                                       payload_clocks='stopped', background_load_ma=130,
                                       bond_loop_r_ohm=bond_loop_r,
                                       global_decap_f=global_decap, island_decap_f=sum(decaps.values())),
                source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in used})


def assess(out, experiment):
    wave = np.loadtxt(out/'wave.txt', skiprows=1)
    time = wave[:, 0]
    assert np.all(np.isfinite(wave)), 'nonfinite analog results'
    assert time[-1] >= experiment['stop']*(1-1e-8), 'transient did not finish'
    assert np.all(np.diff(time) >= 0), 'nonmonotone transient output'
    def voltage(col, when):
        return float(np.interp(when, time, wave[:, col]))
    reads = []
    for rd in experiment['reads']:
        levels = [voltage(2, t) for t in rd['sample_times']]
        if any(1.0 < v < 2.3 for v in levels):
            raise AssertionError(f'SPI read 0x{rd["address"]:02x} has undefined voltage levels')
        value = 0
        for v in levels:
            value = (value << 1) | (v >= 2.3)
        reads.append(dict(address=rd['address'], actual=value, expected=rd['expected']))
    assert all(r['actual'] == r['expected'] for r in reads), reads
    assert voltage(3, experiment['observed_at']) > 2.3, 'power-good did not reach DBG_OBS0'
    startup = (time > 1e-6) & (time < .049)
    assert np.max(wave[startup, 5]) < .35, 'wired rail powered before SPI enable'
    running = time > .049
    assert np.min(wave[running, 1]) >= 3.15 and np.max(wave[running, 1]) <= 3.35, 'ring outside functional envelope'
    # Nonselected islands remain off throughout this experiment.
    for col in (7, 9, 11, 13):
        assert np.max(wave[:, col]) < .35, f'inactive island rail column {col} powered'
    assert voltage(5, experiment['stop']) < .3, 'wired rail did not discharge after disable'
    por = np.nonzero((wave[:, 4] > 2.3) & (time > 1e-6))[0]
    assert len(por), 'physical POR did not release'
    return dict(status='pass', goal_complete=False, spi_reads=reads,
                por_release_s=float(time[por[0]]),
                dbg_obs0_v=voltage(3, experiment['observed_at']),
                scope='live_POR_island_power_SPI_status_and_debug_pad_with_real_control_RTL',
                excluded=['fallback data path', 'inactive payload circuit loading',
                          'core-boundary isolation-clamp loading and fault behavior',
                          'full-chip physical routing/DRC/LVS', 'corner and mismatch coverage',
                          'physical implementation of the board reset supervisor'],
                **experiment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/chip-bringup')
    parser.add_argument('--ngspice-source', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47')
    parser.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    parser.add_argument('--island-pex', type=Path, default=ROOT/'scratch/island-support-20261108-075605')
    parser.add_argument('--reuse-bridge', action='store_true')
    parser.add_argument('--timeout', type=float, default=7200,
                        help='maximum analog simulation wall time in seconds')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    (out/'wave.txt').unlink(missing_ok=True)
    ng = args.ngspice_source.resolve()
    if args.reuse_bridge:
        bridge = json.loads((out/'bridge/ports.json').read_text())
        for p, h in bridge['source_hashes'].items():
            assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h, f'stale bridge: {p}'
    else:
        bridge = compile_bridge(sorted((PROJECT/'rtl').glob('*.sv')), 'pt_digital_macro',
                                out/'bridge', ng, includes=[PROJECT/'rtl'],
                                expose_outputs=['spi_miso', 'spi_miso_oe', 'island_en', 'island_on',
                                                'dbg_obs0', 'dbg_obs0_oe'])
    experiment = build(out, bridge, args.pdk.resolve(), args.island_pex.resolve())
    models = ng/'src/xspice/icm'
    (out/'.spiceinit').write_text('set ngbehavior=hs\n'+
        '\n'.join(f'codemodel {models}/{name}/{name}.cm' for name in ('analog', 'digital'))+'\n')
    started = time.monotonic()
    with (out/'ngspice.log').open('w') as log:
        subprocess.run([str(ng/'src/ngspice'), '-b', 'pt_chip.spice'], cwd=out,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=args.timeout,
                       env={**os.environ, 'OMP_NUM_THREADS': '1'})
    log = (out/'ngspice.log').read_text()
    for error in ('impossible delay', 'time is behind vtime', 'simulation(s) aborted', 'Timestep too small'):
        if error in log:
            raise RuntimeError(f'Invalid mixed simulation: {error}')
    report = assess(out, experiment)
    report['bridge'] = bridge
    report['ngspice_sha256'] = hashlib.sha256((ng/'src/ngspice').read_bytes()).hexdigest()
    report['analog_runtime_s'] = time.monotonic()-started
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'por_release_s', 'dbg_obs0_v', 'goal_complete')}, indent=2))


if __name__ == '__main__':
    main()
