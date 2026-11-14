#!/usr/bin/env python3
"""Assembled cold-start/SPI/island/observation/WTX_EXT bring-up verification.

--route-only checks the same physical data route with explicitly preset
control voltages, before running the full live-SPI experiment. It cannot close
the bring-up goal. A payload is checked only at the phase/latency learned from
a distinct training word, never by aligning against the payload itself.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np

import check_chip_power as power
from cosim_bridge import compile_bridge

sys.path.insert(0, str(power.PROJECT/'integration'))
import wtx_fallback as route
sys.path.insert(0, str(power.PROJECT/'rtl/gen'))
import pt_regmap as regmap


def prbs(seed, count):
    bits = []
    for _ in range(count):
        bits.append(seed & 1)
        seed = ((seed << 1) | (((seed >> 6) ^ (seed >> 5)) & 1)) & 127
    return bits


def projections():
    register_map = json.loads((power.PROJECT/'spec/register-map.json').read_text())
    fields = {f['name']: f for f in register_map['fields']}
    result = {}
    for alias, name in [('tx_branch', 'txpad.config.branch'), ('tmds_code', 'wiredtx.config.current_code'),
                        ('wtx_ext', 'debug.wtx_ext.enable'), ('tx_state', 'wiredtx.state.state'),
                        ('tx_idle', 'wiredtx.idle.idle'), ('tx_stage', 'consolidation.wiredtx_stage.stage')]:
        f = fields[name]
        result[alias] = (f['bus']+'_cfg', f['bus_lsb'], f.get('bus_bits', f['bits']))
    result.update(force_wire=('atb0_sw', 21, 1), force_group=('atb0_grp', 0, 1))
    return result


class Registers:
    def __init__(self, spi):
        self.spi = spi
        m = json.loads((power.PROJECT/'spec/register-map.json').read_text())
        self.fields = {f['name']: f for f in m['fields']}
        self.registers = {r['addr']: r for r in m['registers']}
        self.values = {f['name']: f['default'] for f in m['fields']}
        self.active = dict(self.values)
    def write(self, **values):
        addresses = set()
        for name, value in values.items():
            field = self.fields[name]
            low = field['minimum'] if field['minimum'] is not None else 0
            high = field['maximum'] if field['maximum'] is not None else (1 << field['bits'])-1
            assert low <= value <= high, name
            if field['allowed'] is not None:
                assert value in field['allowed'], name
            self.values[name] = value
            addresses.update(c['addr'] for c in field['chunks'])
        for address in sorted(addresses):
            value = 0
            for name, lsb, width, reg_lsb in self.registers[address]['chunks']:
                value |= ((self.values[name] >> lsb) & ((1 << width)-1)) << reg_lsb
            self.spi.write(address, value)
    def commit(self):
        code = regmap.commit_code(self.values, self.active, False)
        assert code == 0, f'Invalid bench configuration: commit error {code}'
        self.spi.write(6, 1)
        self.active = dict(self.values)


def sequence(island_pex, local=False):
    spi = power.Spi()
    regs = Registers(spi)
    spi.read(0, 0x5356)
    regs.write(**{'debug.island_power.wired': 1, 'debug.dbg_obs.sel0': 4})
    regs.commit()
    spi.time += 20e-6
    observed_at = spi.time
    spi.read(0x0a, 0x0101)
    # The debug island is tested after the wired island is individually on.
    regs.write(**{'debug.island_power.debug': 1})
    regs.commit()
    spi.time += 20e-6
    spi.read(0x0a, 0x2121)
    peer_start = spi.time
    regs.write(**{'debug.atb.atb0': 22, 'wiredtx.config.current_code': 125,
                  'txpad.config.branch': 2, 'debug.wtx_ext.enable': 1,
                  'wiredtx.state.state': 2, 'wiredtx.idle.idle': 0,
                  'consolidation.wiredtx_stage.stage': 1,
                  'debug.wdbg_obs.select': 18})
    # Check all shadow writes while the receiver is still disabled. The final
    # atomic commit must then take effect for the physical route to pass data.
    spi.read(0x05, 0)
    regs.commit()
    # Bias is within tolerance by 0.2 us in the physical activation fixture.
    # Reserve 0.5 us for that transient, then retain the full 1 us settled-bias
    # measurement window. An AC-coupled receiver has undefined no-signal data;
    # qualify it with the balanced preamble rather than a long quiet wait.
    spi.time += 1.5e-6
    for name in ['core.biasgen.ena']+['core.refchain.dist_en_'+i for i in ('rf', 'conv', 'pll', 'wire', 'debug')]:
        assert regs.values[name] == 0, 'external bias force requires the master/root route off'
    data_start = spi.time
    rate = .5e9
    preamble = [k & 1 for k in range(128)]
    training, payload = prbs(0x53, 64), prbs(0x6d, 64)
    bits = preamble+training+payload+[k & 1 for k in range(16)]
    data_end = data_start+len(bits)/rate
    # Leave the selected route running. Shutdown and brownout are separate
    # safety cases; the control-only check covers switch discharge.
    # End after the balanced guard; a quiet AC-coupled input is undefined.
    stop = data_end+20e-9
    if local:
        peer_start, data_start = 10e-6, 20e-6
        data_end = data_start+len(bits)/rate
        stop = data_end+20e-9
    return dict(spi=spi, observed_at=observed_at, stop=stop,
                live_post_commit_settle_s=1.5e-6,
                cfg_error_read_stage='all_shadow_writes_complete_before_final_atomic_commit',
                island_pex=str(island_pex), data_start=data_start, data_end=data_end,
                data_rate=rate, data_bits=bits, preamble_bits=len(preamble),
                training_bits=training, payload_bits=payload, peer_start=peer_start)


def build_local(out, pdk, experiment):
    """Use precisely the emitted pt_analog_physical in a preset-state fixture."""
    text = (out/'pt_chip.spice').read_text()
    definitions = text[:text.index('.subckt pt_chip ')]
    analog_pins = power.ports(definitions, 'pt_analog_physical')
    connections = {p: p for p in analog_pins}
    connections.update(VDD='VDD', VSS='0', POR_N='POR_UNUSED', RX_ENABLE='VDD', EXT_ENABLE='VDD',
                       BRANCH0='0', BRANCH1='VDD', STATE0='0', STATE1='VDD', IDLE='0', STAGE_TMDS='VDD',
                       FORCE_LEAF='VDD', FORCE_GROUP='VDD', FORCE_PAD='VDD')
    for name in ('wired', 'rf', 'pll', 'conv', 'debug'):
        connections[f'EN_{name}'] = 'VDD' if name in ('wired', 'debug') else '0'
    for k in range(8):
        connections[f'CODE{k}'] = 'VDD' if (125 >> k) & 1 else '0'
    probes = ['v(VDD)', 'v(BOARD_P,BOARD_N)', 'v(WIRE_TX_P,WIRE_TX_N)', 'v(PG_wired)',
              'v(PG_debug)', 'v(RAIL_wired)', 'v(RAIL_debug)', 'v(Xroute.DX)',
              'v(Xroute.DX_WIRED)', 'v(Xroute.EN_MAIN)', 'v(Xroute.MAIN_BIAS)',
              'v(Xroute.PRESENT_CORE)', 'i(v.Xroute.Vbias_measure)', 'v(ATB0)',
              'v(Xroute.TRK_WIRE)', 'v(EXT_DATA_OBS)']
    saved = []
    for probe in probes:
        match = re.fullmatch(r'v\(([^,]+),([^,]+)\)', probe)
        saved.extend([f'v({name})' for name in match.groups()] if match else [probe])
    d = [definitions, 'VDD VDD 0 3.3',
         power.instance('Xroute', 'pt_analog_physical', definitions, connections),
         *route.board(experiment),
         '.options klu reltol=1e-3 method=gear rshunt=1e12 cshunt=1e-17',
         '.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
         'save '+' '.join(saved), f'tran 1n {experiment["stop"]:.15g} 0 10n',
         'wrdata route-wave.txt '+' '.join(probes), 'quit', '.endc', '.end']
    (out/'route.spice').write_text('\n'.join(d)+'\n')


def train_and_check(wave, data_col, experiment):
    t, differential = wave[:, 0], wave[:, data_col]
    ui = 1/experiment['data_rate']
    start = experiment['data_start']
    training = np.array(experiment['training_bits'])
    payload = np.array(experiment['payload_bits'])
    preamble = experiment['preamble_bits']
    candidates = []
    for delay in np.arange(0, 16, 1/8)*ui:
        ts = start+(preamble+np.arange(len(training))+.5)*ui+delay
        levels = np.interp(ts, t, differential)
        errors = int(np.count_nonzero((levels > 0) != training))
        margin = float(np.min(levels*(2*training-1)))
        if errors == 0:
            candidates.append((margin, float(delay)))
    assert candidates, 'no latency/phase trained on the distinct training word'
    training_margin, delay = max(candidates)
    ts = start+(preamble+len(training)+np.arange(len(payload))+.5)*ui+delay
    assert ts[-1] <= t[-1], 'transient ended before the delayed payload'
    levels = np.interp(ts, t, differential)
    errors = int(np.count_nonzero((levels > 0) != payload))
    margin = float(np.min(levels*(2*payload-1)))
    assert errors == 0, f'fallback payload errors: {errors}/{len(payload)}'
    assert margin >= .25, f'fallback differential sample margin {margin} V < 0.25 V'
    return dict(payload_bits=len(payload), errors=errors, data_rate_bps=experiment['data_rate'],
                trained_delay_s=delay, training_margin_v=training_margin, payload_margin_v=margin,
                phase_selection='distinct 64-bit training word only; payload phase is fixed')


def bias_stats(wave, column, experiment):
    start, end = experiment['data_start']-1e-6, experiment['data_start']
    selected = (wave[:, 0] > start) & (wave[:, 0] < end)
    ts = np.r_[start, wave[selected, 0], end]
    current = np.interp(ts, wave[:, 0], wave[:, column])
    mean = float(np.trapezoid(current, ts)/(end-start))
    assert 9e-6 <= mean <= 11e-6, f'settled bias current {mean} A outside 10 uA +/-10%'
    data = (wave[:, 0] >= end) & (wave[:, 0] <= experiment['data_end'])
    return dict(settled_mean_a=mean, data_min_a=float(np.min(wave[data, column])),
                data_max_a=float(np.max(wave[data, column])))


def assess_local(out, experiment):
    w = np.loadtxt(out/'route-wave.txt', skiprows=1)
    assert np.isfinite(w).all() and w[-1, 0] >= experiment['stop']*(1-1e-8), 'incomplete route simulation'
    selection = (w[:, 0] >= experiment['data_start']) & (w[:, 0] <= experiment['data_end'])
    assert np.min(w[selection, 4:8]) >= 3.15, 'island rail or power-good invalid during data'
    return dict(status='pass', goal_complete=False, scope='preset_control_physical_WTX_EXT_route_only',
                data=train_and_check(w, 2, experiment),
                bias=bias_stats(w, 13, experiment),
                excluded=['cold-start/SPI-controlled enable and observation', 'physical glue layout',
                          'PVT, mismatch, BER qualification and complete chip signoff'])


def assess_full(out, experiment):
    w = np.loadtxt(out/'wave.txt', skiprows=1)
    assert np.isfinite(w).all() and w[-1, 0] >= experiment['stop']*(1-1e-8), 'incomplete assembled transient'
    checks = []
    for rd in experiment['reads']:
        levels = np.interp(rd['sample_times'], w[:, 0], w[:, 2])
        assert np.all((levels <= 1) | (levels >= 2.3)), 'indeterminate SPI output levels'
        value = 0
        for v in levels:
            value = (value << 1) | int(v >= 2.3)
        checks.append(dict(address=rd['address'], expected=rd['expected'], actual=value))
    assert all(r['expected'] == r['actual'] for r in checks), checks
    assert np.interp(experiment['observed_at'], w[:, 0], w[:, 3]) > 2.3, 'wired PG not visible at debug pad'
    startup = (w[:, 0] > 1e-6) & (w[:, 0] < .049)
    assert np.max(w[startup, 5:15:2]) < .35, 'island rail powered before SPI enable'
    assert np.max(w[startup, 23]) < .3, 'TX driver enabled during startup'
    # RF, PLL and converter islands remain off while wired and debug are on.
    assert np.max(w[:, [7, 9, 11]]) < .35, 'nonselected island powered'
    running = w[:, 0] > .049
    assert np.min(w[running, 1]) >= 3.15 and np.max(w[running, 1]) <= 3.35, 'ring outside operating window'
    # Original power probes occupy columns 1..16; extension adds the raw pads.
    data_wave = np.column_stack([w[:, 0], w[:, 27]-w[:, 28]])
    data = train_and_check(data_wave, 1, experiment)
    por = np.nonzero(w[:, 4] > 2.3)[0]
    assert len(por), 'POR never released'
    return dict(status='pass', goal_complete=False, scope='assembled_nominal_cold_start_SPI_islands_debug_WTX_EXT',
                spi_reads=checks, por_release_s=float(w[por[0], 0]), data=data,
                bias=bias_stats(w, 29, experiment),
                excluded=['physical glue layout, complete chip placement/DRC/LVS',
                          'inactive payload macro loading', 'PVT, mismatch and statistical BER',
                          'board supervisor is a declared external model'])


def preflight(out, ng, deck):
    """Check all probes in a separate operating-point process before a long run."""
    source = (out/deck).read_text()
    source, count = re.subn(r'^tran .*$', 'op', source, flags=re.M)
    assert count == 1, 'expected one transient command'
    match = re.search(r'^wrdata \S+ (.*)$', source, re.M)
    assert match, 'missing waveform export'
    columns = len(match.group(1).split())+1
    source = re.sub(r'^wrdata \S+ ', 'wrdata preflight-probes.txt ', source, flags=re.M)
    (out/'preflight.spice').write_text(source)
    probe = out/'preflight-probes.txt'
    probe.unlink(missing_ok=True)
    with (out/'preflight.log').open('w') as log:
        subprocess.run([str(ng/'src/ngspice'), '-b', 'preflight.spice'], cwd=out,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
                       env={**os.environ, 'OMP_NUM_THREADS': '1'})
    text = (out/'preflight.log').read_text()
    assert not re.search(r'(?im)^error|undefined parameter|simulation\(s\) aborted', text), 'probe preflight failed'
    assert probe.exists(), 'probe export failed'
    values = np.atleast_2d(np.loadtxt(probe, skiprows=1))
    assert values.shape[1] == columns and np.isfinite(values).all(), 'probe schema/nonfinite values'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, default=power.ROOT/'scratch/chip-fallback-live')
    p.add_argument('--ngspice-source', type=Path, default=power.ROOT/'scratch/pad-ngspice47/ngspice-47')
    p.add_argument('--pdk', type=Path, default=power.ROOT/'scratch/transceiver-pad-pdk')
    p.add_argument('--island-pex', type=Path, default=power.ROOT/'scratch/island-support-20261108-075605')
    p.add_argument('--reuse-bridge', action='store_true')
    p.add_argument('--build-only', action='store_true')
    p.add_argument('--route-only', action='store_true')
    p.add_argument('--timeout', type=float, default=7200)
    args = p.parse_args()
    out, ng = args.output_dir.resolve(), args.ngspice_source.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out/('route-report.json' if args.route_only else 'report.json')
    report_path.write_text('{"status":"incomplete","goal_complete":false}\n')
    selected = ['spi_miso', 'spi_miso_oe', 'island_en', 'island_on', 'dbg_obs0', 'dbg_obs0_oe',
                'rx_en_wtx_ext', 'wdbg_obs', 'wdbg_obs_oe', 'atb0_en']
    projected = projections()
    if args.reuse_bridge:
        bridge = json.loads((out/'bridge/ports.json').read_text())
        assert bridge.get('projections') == {k: list(v) for k, v in projected.items()}, 'stale projected interface'
        for path, digest in bridge['source_hashes'].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, f'stale bridge: {path}'
    else:
        bridge = compile_bridge(sorted((power.PROJECT/'rtl').glob('*.sv')), 'pt_digital_macro',
                                out/'bridge', ng, includes=[power.PROJECT/'rtl'], expose_outputs=selected,
                                projections=projected)
    from check_moscap_charge import check as check_moscap
    check_moscap(out/'moscap-validation', args.pdk.resolve(), ng/'src/ngspice')
    experiment = power.build(out, bridge, args.pdk.resolve(), args.island_pex.resolve(), extension=route.extension,
                             sequence=lambda: sequence(args.island_pex.resolve(), args.route_only),
                             charge_moscap=True)
    experiment['moscap_validation_sha256'] = hashlib.sha256((out/'moscap-validation/report.json').read_bytes()).hexdigest()
    for path in [Path(__file__).resolve(), Path(route.__file__).resolve(),
                 Path(__file__).with_name('check_moscap_charge.py'), power.PROJECT/'spec/register-map.json']:
        experiment['source_hashes'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'experiment.json').write_text(json.dumps(experiment, indent=2)+'\n')
    if args.route_only:
        build_local(out, args.pdk.resolve(), experiment)
    if args.build_only:
        print(f'Built {out}'); return
    models = ng/'src/xspice/icm'
    (out/'.spiceinit').write_text('set ngbehavior=hs\n'+
        '\n'.join(f'codemodel {models}/{name}/{name}.cm' for name in ('analog', 'digital'))+'\n')
    waveform = out/('route-wave.txt' if args.route_only else 'wave.txt')
    waveform.unlink(missing_ok=True)
    log_path = out/('route.log' if args.route_only else 'ngspice.log')
    preflight(out, ng, 'route.spice' if args.route_only else 'pt_chip.spice')
    started = time.monotonic()
    with log_path.open('w') as log:
        subprocess.run([str(ng/'src/ngspice'), '-b', 'route.spice' if args.route_only else 'pt_chip.spice'],
                       cwd=out, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=args.timeout,
                       env={**os.environ, 'OMP_NUM_THREADS': '1'})
    log_text = log_path.read_text()
    for error in ('impossible delay', 'time is behind vtime', 'simulation(s) aborted', 'Timestep too small'):
        assert error not in log_text, error
    report = (assess_local if args.route_only else assess_full)(out, experiment)
    report.update(experiment=experiment, bridge=bridge, runtime_s=time.monotonic()-started,
                  deck_sha256=hashlib.sha256((out/('route.spice' if args.route_only else 'pt_chip.spice')).read_bytes()).hexdigest())
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'scope', 'data')}, indent=2))


if __name__ == '__main__':
    main()
