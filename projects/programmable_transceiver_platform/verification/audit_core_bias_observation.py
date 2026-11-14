#!/usr/bin/env python3
"""Independently audit a complete core-bias waveform or an explicit prefix.

Source snapshots and live runtime identities establish which circuit ran.
A prefix reports completed checks separately and can never pass the campaign.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from audit_chip_bringup import identities

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

# IDAC1 bench plan, from the specification rather than the producer's setup
# (ATB sense of the spare biasgen IDAC1 into
# a 1 V SMU with SPI-commanded off/4/8/off steps; register-map.json:
# core.biasgen.idac1_source is a "spare 1 uA-unit source").
IDAC1_PLAN = dict(atb_node='idac1_source_ibias', bus_field='debug.atb.atb1',
                  code_field='core.biasgen.idac1_source', steps=(0, 4, 8, 0),
                  smu_v=1.0, lsb_a=1e-6, lsb_tolerance=.1, off_limit_a=10e-9,
                  settle_s=3e-6, guard_s=50e-9)
SPI_CMD_WRITE, COMMIT_ADDR, COMMIT_CMD = 0x80, 0x06, 0x0001


def pwl_sources(netlist):
    """Board SPI stimulus exactly as simulated: V<pin> SRC_<pin> 0 PWL(...)."""
    text = re.sub(r'\n\+', ' ', netlist)
    sources = {}
    for pin in ('SCLK', 'CS_N', 'MOSI'):
        m = re.search(rf'^V{pin} SRC_{pin} 0 PWL\(([^)]*)\)', text, re.M)
        assert m, f'No PWL source for {pin}'
        v = np.array([float(x) for x in m[1].split()]).reshape(-1, 2)
        assert np.all(np.diff(v[:, 0]) >= 0)
        sources[pin] = v
        # The source must actually drive the chip pin.
        assert re.search(rf'^Shost_{pin} SRC_{pin} {pin} ', text, re.M), f'{pin} source not connected'
    return sources


def decode_spi(sources):
    """Decode every 32-bit SPI frame (MSB first, MOSI sampled at SCLK rise)."""
    level = lambda pin, t: float(np.interp(t, sources[pin][:, 0], sources[pin][:, 1])) > 1.65
    clk = sources['SCLK']
    rises = [(clk[i, 0]+clk[i+1, 0])/2 for i in range(len(clk)-1) if clk[i, 1] < 1.65 <= clk[i+1, 1]]
    cs = sources['CS_N']
    falls = [(cs[i, 0]+cs[i+1, 0])/2 for i in range(len(cs)-1) if cs[i, 1] >= 1.65 > cs[i+1, 1]]
    ups = [(cs[i, 0]+cs[i+1, 0])/2 for i in range(len(cs)-1) if cs[i, 1] < 1.65 <= cs[i+1, 1]]
    assert len(falls) == len(ups) and all(a < b for a, b in zip(falls, ups))
    frames = []
    for start, end in zip(falls, ups):
        edges = [t for t in rises if start < t < end]
        assert len(edges) == 32, ('SPI frame length', start, len(edges))
        word = 0
        for t in edges:
            word = (word << 1) | int(level('MOSI', t))
        frames.append(dict(start=start, end=end, command=word >> 24, address=(word >> 16) & 0xFF, value=word & 0xFFFF))
    return frames


def field_value(field, registers):
    value = 0
    for chunk in field['chunks']:
        bits = (registers[chunk['addr']] >> chunk['reg_lsb']) & ((1 << chunk['width'])-1)
        value |= bits << chunk['field_lsb']
    return value


def audit_idac1(out, runtime, w, wave_path, regmap, controls, stop):
    """IDAC1 SMU audit; expected codes from IDAC1_PLAN, times from the SPI
    stimulus decoded out of the simulated deck. Nothing is read from
    experiment.json's measurement schedule."""
    plan = IDAC1_PLAN
    deck = (out/'pt_chip.spice').resolve()
    assert runtime['artifact_hashes'][str(deck)] == sha(deck), 'Simulated deck changed'
    nodes = [n for n in controls['atb_nodes'] if n['name'] == plan['atb_node']]
    assert len(nodes) == 1 and nodes[0].get('hardware', True)
    atb_code = nodes[0]['code']
    fields = {f['name']: f for f in regmap['fields']}
    assert '1 uA' in (fields[plan['code_field']]['meaning'] or ''), 'IDAC1 unit changed in register map'
    assert atb_code in fields[plan['bus_field']]['allowed']
    # Shadow/active register images: reset defaults, then every SPI write.
    shadow = {r['addr']: 0 for r in regmap['registers']}
    for f in regmap['fields']:
        for chunk in f['chunks']:
            shadow[chunk['addr']] |= ((f['default'] >> chunk['field_lsb']) & ((1 << chunk['width'])-1)) << chunk['reg_lsb']
    active = dict(shadow)
    commits = []
    frames = decode_spi(pwl_sources(deck.read_text()))
    for frame in frames:
        if not frame['command'] & SPI_CMD_WRITE:
            continue
        if frame['address'] == COMMIT_ADDR:
            if frame['value'] == COMMIT_CMD:
                active = dict(shadow)
                commits.append(dict(time=frame['end'], atb=field_value(fields[plan['bus_field']], active),
                                    code=field_value(fields[plan['code_field']], active)))
        elif frame['address'] in shadow:
            shadow[frame['address']] = frame['value']
    starts = [f['start'] for f in frames]
    selected = [c for c in commits if c['atb'] == atb_code]
    assert selected, 'ATB never selects the IDAC1 node'
    first = commits.index(selected[0])
    run = []
    for c in commits[first:]:
        if c['atb'] != atb_code:
            break
        run.append(c)
    # The selecting commit must connect the source switched off (no current
    # step through the closing switch); each later commit is one plan step.
    assert run[0]['code'] == 0, 'IDAC1 enabled when ATB selection closed'
    run = run[1:]
    steps = [c['code'] for c in run]
    assert steps == list(plan['steps']), ('Decoded IDAC1 schedule differs from plan', steps)
    header = wave_path.open().readline().split()
    column = {name: i for i, name in enumerate(header)}
    assert header[0] == 'time'
    smu, pad, src = column['i(VSMU)'], column['v(ATB1)'], column['v(Xchip.Xanalog.IDAC1)']
    t = w[:, 0]
    completed, pending, measured, decoded = [], [], {}, []
    for index, c in enumerate(run):
        begin = c['time']+plan['settle_s']
        later = [s for s in starts if s > c['time']]
        end = (later[0] if later else stop)-plan['guard_s']
        decoded.append(dict(code=c['code'], commit_s=c['time'], window_s=[begin, end]))
        if stop < end:
            pending.append(f'IDAC1 SMU step {index}, code {c["code"]}')
            continue
        assert end-begin >= 2e-6, 'Step window shorter than 2 us'
        # Solver samples inside the window plus the linear interpolant on a
        # 201-point grid spanning it (the solver takes long steps once settled).
        mask = (t >= begin) & (t <= end)
        grid = np.union1d(np.linspace(begin, end, 201), t[mask])
        trace = lambda col: np.interp(grid, t, w[:, col])
        values = trace(smu)
        code = c['code']
        if code:
            low, high = code*plan['lsb_a']*(1-plan['lsb_tolerance']), code*plan['lsb_a']*(1+plan['lsb_tolerance'])
            assert np.min(values) >= low and np.max(values) <= high, ('IDAC1', code, float(np.min(values)), float(np.max(values)))
        else:
            assert np.max(np.abs(values)) < plan['off_limit_a'], 'IDAC1 off leakage'
        assert np.max(np.abs(trace(pad)-plan['smu_v'])) <= .001, 'SMU compliance voltage'
        assert np.min(trace(src)) >= .9 and np.max(trace(src)) <= 1.5
        measured.setdefault(code, []).append(float(np.mean(values)))
        completed.append(dict(check='IDAC1 SMU current', code=code, atb_code=atb_code, window_s=[begin, end],
                              window_samples=int(mask.sum()), min_a=float(np.min(values)),
                              max_a=float(np.max(values)), mean_a=float(np.mean(values)),
                              settled_span_a=float(np.ptp(values))))
    if 4 in measured and 8 in measured:
        ratio = measured[8][0]/measured[4][0]
        assert 1.9 <= ratio <= 2.1, 'IDAC1 code ratio'
        completed.append(dict(check='IDAC1 code ratio 8/4', ratio=ratio))
    if len(measured.get(0, [])) == 2:
        completed.append(dict(check='IDAC1 off before and after', off_a=measured[0]))
    return dict(completed=completed, pending=pending, steps=[dict(code=d['code'], time_s=d['commit_s']) for d in decoded],
                windows=decoded, spi_frames=len(frames), commits=len(commits))


def audit(out, wave_name, destination):
    experiment = json.loads((out/'experiment.json').read_text())
    bridge = json.loads((out/'bridge/ports.json').read_text())
    assert bridge == experiment['bridge'], 'Bridge manifest changed'
    expected = {**experiment['source_hashes'], **bridge['source_hashes']}
    manifest_path = out/experiment['frozen_source_manifest']
    frozen = json.loads(manifest_path.read_text())
    assert set(frozen) == set(expected), 'Frozen source set differs'
    for source, info in frozen.items():
        assert info['sha256'] == expected[source] == sha(out/info['path']), source
    runtime = json.loads((out/'runtime-snapshot.json').read_text())
    assert identities(out, runtime['executable']) == runtime['artifact_hashes'], 'Runtime circuit changed'
    regmap_source = next(p for p in frozen if p.endswith('/spec/register-map.json'))
    regmap = json.loads((out/frozen[regmap_source]['path']).read_text())
    expected_spi = {0: 0x5356, 8: 2, 9: regmap['map_hash16'], 10: 0x3737, 5: 0}
    wave_path = out/wave_name
    before = wave_path.stat()
    w = np.loadtxt(wave_path, skiprows=1)
    assert wave_path.stat().st_mtime_ns == before.st_mtime_ns, 'Waveform is still being written'
    voltages = experiment['voltage_probes']
    columns = {name: index+1 for index, name in enumerate(voltages)}
    current_start = 1+len(voltages)
    meter_start = current_start+len(experiment['current_probes'])
    meters = list(experiment.get('meter_probes', {}))
    assert w.ndim == 2 and w.shape[1] == meter_start+len(meters)
    assert np.isfinite(w).all() and np.all(np.diff(w[:, 0]) >= 0)
    t = w[:, 0]
    stop = float(t[-1])
    def at(name, when):
        return float(np.interp(when, t, w[:, columns[name]]))
    def window(when, duration):
        # The adaptive solver and the schedule can round the same boundary
        # to adjacent floating-point values. Include that boundary sample;
        # this is far below a physical timestep and does not widen thresholds.
        rounding = 32*np.spacing(when)
        mask = (t >= when-duration-rounding) & (t <= when+rounding)
        assert mask.sum() >= 2, 'Insufficient waveform samples'
        return mask
    complete = stop >= experiment['stop']*(1-1e-8)
    completed, pending, reads = [], [], []
    for request in experiment['reads']:
        if max(request['sample_times']) > stop:
            pending.append('SPI read '+str(request['address']))
            continue
        want = expected_spi[request['address']]
        assert request['expected'] == want, 'Producer expectation differs from register contract'
        samples = np.interp(request['sample_times'], t, w[:, columns['MISO']])
        assert np.all((samples <= 1) | (samples >= 2.3)), 'Indeterminate physical MISO'
        actual = 0
        for sample in samples:
            actual = (actual << 1) | int(sample >= 2.3)
        assert actual == want, ('SPI', request['address'], actual, want)
        reads.append(dict(address=request['address'], value=actual))
    completed.append(dict(check='physical SPI reads', reads=reads))
    normal = experiment['normal_at']
    if stop >= normal:
        mask = window(normal, 5e-6)
        vbg = w[mask, columns['VBG']]
        assert np.min(vbg) >= 1.20 and np.max(vbg) <= 1.23, 'Normal VBG window failed'
        currents = {}
        for index, consumer in enumerate(experiment['current_probes']):
            values = w[mask, current_start+index]
            if consumer == 'lc_vco_reserved':
                assert np.max(np.abs(values)) < 1e-9
            else:
                assert np.min(values) >= 9e-6 and np.max(values) <= 11e-6, consumer
            currents[consumer] = dict(min_a=float(np.min(values)), max_a=float(np.max(values)))
        completed.append(dict(check='normal reference and bank currents over 5 us',
                              vbg_min_v=float(np.min(vbg)), vbg_max_v=float(np.max(vbg)), currents=currents))
    else:
        pending.append('normal reference and bank currents')
    bindings = {int(code): net for code, net in experiment['node_bindings'].items()}
    for observation in experiment['observations']:
        code, when = observation['code'], observation['time_s']
        if stop < when:
            pending.append('ATB code '+str(code))
            continue
        net = bindings[code]
        mask = window(when, 1e-6)
        source = 0 if net == 'VSS' else w[mask, columns[net]]
        error = float(np.max(np.abs(w[mask, columns['ATB1']]-source)))
        assert error <= .005, ('ATB', code, net, error)
        completed.append(dict(check='ATB sense', code=code, net=net, max_error_v=error,
                              source_v=0 if net == 'VSS' else at(net, when), pad_v=at('ATB1', when)))
    current_measurements = experiment.get('current_observations', [])
    if experiment.get('idac1_smu', False):
        frozen_path = lambda suffix: out/frozen[next(p for p in frozen if p.endswith(suffix))]['path']
        idac1 = audit_idac1(out, runtime, w, wave_path, regmap,
                            json.loads(frozen_path('/spec/debug-controls.json').read_text()), stop)
        completed += idac1['completed']
        pending += idac1['pending']
        # The producer's schedule is compared, never used.
        producer = [dict(code=r['code'], time_s=r['time_s']) for r in current_measurements]
        completed.append(dict(check='producer schedule consistency (informational)',
                              producer_steps=producer, decoded_steps=idac1['steps'],
                              producer_codes_agree=[r['code'] for r in producer] == [s['code'] for s in idac1['steps']]))
    else:
        assert not current_measurements and not meters, 'Unexpected current measurement schema'
    forced = experiment['forced_at']
    if forced is not None and stop >= forced:
        mask = window(experiment['forced_at'], 5e-6)
        assert np.max(np.abs(w[mask, columns['VBG']]-1.2)) <= .01, 'VBG force failed'
        assert np.max(np.abs(w[mask, columns['ATB1']]-w[mask, columns['VBG']])) <= .005
        completed.append(dict(check='VBG external force and sense over 5 us'))
    elif forced is not None:
        pending.append('VBG external force and sense')
    if not complete:
        pending.append('complete transient')
    assert not complete or not pending
    result = dict(status='pass' if complete else 'partial_diagnostic', waveform_stop_s=stop,
                  scope='exact frozen mixed-level core reference / bank / ATB fixture',
                  completed_checks=completed, pending_checks=pending,
                  current_sources_changed=[p for p, h in expected.items() if not Path(p).exists() or sha(p) != h],
                  fixture_boundaries=experiment['fixture_boundaries'],
                  artifact_hashes={name: sha(out/name) for name in
                                   ['experiment.json', 'runtime-snapshot.json', str(manifest_path.relative_to(out)), wave_name]},
                  auditor_sha256=sha(__file__))
    destination.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status=result['status'], waveform_stop_s=stop, completed_checks=len(completed),
                          spi_reads=reads, pending_checks=pending, report=str(destination)), indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/core-bias-observation-checkpointed')
    parser.add_argument('--wave', default='wave.txt')
    parser.add_argument('--report', default='core-bias-audit.json')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    audit(out, args.wave, out/args.report)
