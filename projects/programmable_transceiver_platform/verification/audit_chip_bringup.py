#!/usr/bin/env python3
"""Audit the nominal assembled bring-up milestone of pt_wired from its actual waveform (PT_CHIP=wired).

The milestone moves data through the WTX_EXT -> WIRE_TX fallback route, which exists on pt_wired only: on pt_rf
this audit does not apply and says so. The producer is check_chip_fallback.py (output scratch/chip-fallback-live):
it must have passed on the current RTL and conn, or this audit fails at its first assertion. Waveform columns are
read by name (check_chip_power.build: experiment['columns']); the payload rails are the wired enable group's
islands of the conn.

Record the running simulator/library/deck identities with --record-runtime PID.
After the producer finishes, check source freshness, parent connectivity and
each milestone requirement. This is not a tapeout/PVT/BER signoff.
"""
import argparse
import os
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

import check_chip_fallback as fallback
import check_chip_power as power


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identities(out, executable):
    bridge = json.loads((out/'bridge/ports.json').read_text())
    cm = Path(executable).resolve().parent/'xspice/icm'
    files = [out/'pt_chip.spice', out/'experiment.json', out/'bridge/ports.json',
             out/'.spiceinit', Path(bridge['library']), Path(executable),
             cm/'analog/analog.cm', cm/'digital/digital.cm']
    return {str(p.resolve()): sha(p) for p in files}


def record(out, pid):
    proc = Path('/proc')/str(pid)
    assert (proc/'comm').read_text().strip() == 'ngspice', 'PID is not ngspice'
    assert (proc/'cwd').resolve() == out, 'simulator is using another output directory'
    executable = (proc/'exe').resolve()
    command = (proc/'cmdline').read_bytes().split(b'\0')
    assert b'pt_chip.spice' in command, 'simulator is running another deck'
    result = dict(pid=pid, process_start_ticks=(proc/'stat').read_text().split(') ', 1)[1].split()[19],
                  executable=str(executable), recorded_at=datetime.now(timezone.utc).isoformat(),
                  artifact_hashes=identities(out, executable))
    target = out/'runtime-snapshot.json'
    if target.exists():
        old = json.loads(target.read_text())
        assert old['artifact_hashes'] == result['artifact_hashes'], 'runtime artifacts changed'
        assert old['process_start_ticks'] == result['process_start_ticks'] and old['pid'] == pid, 'different run'
    else:
        target.write_text(json.dumps(result, indent=2)+'\n')
    print(f'Verified live simulator PID {pid}; runtime identities recorded in {target}')


COLUMNS_FROM_EXTENSION = dict(tx_p='extra0', tx_n='extra1', tx_enable='extra6', board_p='extra10', board_n='extra11',
                              bias_current='extra12')     # integration/wtx_fallback.py extension probe order


def audit(out):
    chip = os.environ['PT_CHIP']
    if chip != 'wired':
        print(f'audit_chip_bringup: not applicable to pt_{chip} (no WTX_EXT -> WIRE_TX fallback route); nothing audited')
        return
    report = json.loads((out/'report.json').read_text())
    assert report['status'] == 'pass', 'combined producer has not passed'
    experiment = json.loads((out/'experiment.json').read_text())
    bridge = json.loads((out/'bridge/ports.json').read_text())
    assert report['experiment'] == experiment and report['bridge'] == bridge, 'report/input mismatch'
    sources = {**experiment['source_hashes'], **bridge['source_hashes']}
    changed = [p for p, h in sources.items() if sha(p) != h]
    assert not changed, f'stale evidence: {changed}'
    if experiment.get('moscap_realization') == 'analytical_charge_integral':
        validation_path = out/'moscap-validation/report.json'
        assert sha(validation_path) == experiment['moscap_validation_sha256'], 'MOSCAP validation changed'
        validation = json.loads(validation_path.read_text())
        assert validation['status'] == 'pass', 'MOSCAP realization not validated'
        assert all(sha(p) == h for p, h in validation['source_hashes'].items()), 'stale MOSCAP validation'
    snapshot = json.loads((out/'runtime-snapshot.json').read_text())
    assert identities(out, snapshot['executable']) == snapshot['artifact_hashes'], 'runtime artifact changed'
    assert sha(out/'pt_chip.spice') == report['deck_sha256'], 'reported deck changed'
    parent = power.chip_connectivity((power.PROJECT/f'integration/chips/{chip}/generated/pt_chip.sv').read_text(), chip)
    assert parent == experiment['parent_connectivity'], 'parent hierarchy differs'
    assert bridge['projections'] == {k: list(v) for k, v in fallback.projections().items()}, 'control projection changed'
    w = np.loadtxt(out/'wave.txt', skiprows=1)
    names = experiment['columns']
    assert w.ndim == 2 and w.shape[1] == len(names)+1 and np.isfinite(w).all(), 'waveform schema/nonfinite values'
    col = {name: k+1 for k, name in enumerate(names)}
    col.update({k: col[v] for k, v in COLUMNS_FROM_EXTENSION.items()})
    payload = [i['island'] for i in experiment['islands'] if i['group'] == 'wired' and i['pg'] != '-']
    others = [i['island'] for i in experiment['islands'] if i['group'] not in ('wired', 'debug') and i['pg'] != '-']
    debug = [i['island'] for i in experiment['islands'] if i['group'] == 'debug' and i['pg'] != '-']
    wired_bit = next(i['bit'] for i in experiment['islands'] if i['group'] == 'wired')
    t = w[:, 0]
    assert np.all(np.diff(t) >= 0) and t[-1] >= experiment['stop']*(1-1e-8), 'incomplete transient'
    def at(column, when):
        return float(np.interp(when, t, w[:, column]))
    startup = (t > 1e-6) & (t < .049)
    for island in payload+others+debug:
        assert np.max(w[startup, col['RAIL_'+island]]) < .35, f'{island} rail powered during startup'
    assert np.max(w[startup, col['tx_enable']]) < .3, 'TX enabled during startup'
    assert np.min(w[:, col['VDD']]) >= -.3 and np.max(w[:, col['VDD']]) <= 3.63, 'ring exceeded safety voltage bounds'
    operating = t > .049
    assert np.min(w[operating, col['VDD']]) >= 3.15 and np.max(w[operating, col['VDD']]) <= 3.35, 'ring left functional window'
    for island in others:
        assert np.max(w[:, col['RAIL_'+island]]) < .35, 'nonselected island powered'
    for name in ('tx_p', 'tx_n', 'board_p', 'board_n'):
        assert np.min(w[:, col[name]]) >= -.3 and np.max(w[:, col[name]]) <= 3.63, 'TX pad/board voltage out of bounds'
    released = (w[:, col['POR_N']] > 2.3) & (w[:, col['VDD']] >= 3.15)
    rises = np.nonzero(np.diff(released.astype(int)) == 1)[0]+1
    assert len(rises) == 1, 'POR release missing or not clean'
    por_time = float(t[rises[0]])
    assert .001 < por_time < .050, 'POR release outside the bring-up interval'
    spi = []
    for read in experiment['reads']:
        levels = np.interp(read['sample_times'], t, w[:, col['MISO']])
        assert np.all((levels <= 1) | (levels >= 2.3)), 'indeterminate SPI data'
        actual = 0
        for value in levels:
            actual = (actual << 1) | int(value >= 2.3)
        assert actual == read['expected'], f'SPI 0x{read["address"]:02x} mismatch'
        spi.append((read['address'], actual))
    assert {(0, 0x5356), (0x0a, 0x0101), (0x0a, 0x2121), (5, 0)} <= set(spi), 'missing required SPI observations'
    observed = experiment['observed_at']
    for island in payload:
        assert at(col['RAIL_'+island], observed) >= 3.15 and at(col['PG_'+island], observed) > 2.3, f'{island} rail/PG invalid at observation'
    assert at(col[f'EN_{wired_bit}'], observed) > 2.3 and at(col[f'ON_{wired_bit}'], observed) > 2.3, 'wired enable/effective-on missing'
    assert at(col['DBG_OBS0'], observed) > 2.3 and np.max(w[startup, col['DBG_OBS0']]) < 1, 'debug pad observation missing'
    data_interval = (t >= experiment['data_start']) & (t <= experiment['data_end'])
    assert np.any(data_interval), 'no samples cover active data'
    for island in payload+debug:
        assert np.min(w[data_interval, col['RAIL_'+island]]) >= 3.15, 'selected island rail invalid during data'
        assert np.min(w[data_interval, col['PG_'+island]]) > 2.3, 'power-good missing during data'
    for name in (f'EN_{wired_bit}', f'ON_{wired_bit}', 'tx_enable'):
        assert np.min(w[data_interval, col[name]]) > 2.3, 'effective-on or TX enable missing during data'
    delay = report['data']['trained_delay_s']
    assert 0 <= delay < 16/experiment['data_rate'], 'training delay out of bounds'
    assert experiment['training_bits'] != experiment['payload_bits'], 'training and payload not distinct'
    ui, start = 1/experiment['data_rate'], experiment['data_start']
    differential = w[:, col['board_p']]-w[:, col['board_n']]
    margins = {}
    offset = experiment['preamble_bits']
    for label in ('training_bits', 'payload_bits'):
        bits = np.array(experiment[label])
        assert set(bits.tolist()) == {0, 1}, f'{label} must exercise both data levels'
        times = start+(offset+np.arange(len(bits))+.5)*ui+delay
        assert times[-1] <= t[-1], 'waveform does not cover the delayed word'
        values = np.interp(times, t, differential)
        assert np.array_equal(values > 0, bits.astype(bool)), f'{label} does not match'
        margins[label] = float(np.min(values*(2*bits-1)))
        assert margins[label] >= .25, f'{label} has insufficient differential margin'
        offset += len(bits)
    bias = fallback.bias_stats(w, col['bias_current'], experiment)
    result = dict(status='pass', milestone_met=True,
                  evidence_class='nominal_mixed_level_simulation_RTL_and_extracted_analog',
                  requirements={
                      'power_up_safely': dict(por_release_s=por_time, startup_islands_off=True,
                                             startup_tx_disabled=True, ring_max_v=float(np.max(w[:, col['VDD']]))),
                      'read_SPI': dict(id='0x5356', reads_verified=len(spi)),
                      'enable_one_island': dict(first_status='0x0101', second_status='0x2121'),
                      'observe_it': dict(spi_power_good_verified=True, debug_pad_v=at(col['DBG_OBS0'], observed)),
                      'move_data_through_one_fallback': dict(route='WTX_EXT -> receiver -> selector/bias -> TMDS output pad -> board',
                                                            rate_bps=experiment['data_rate'], payload_bits=len(experiment['payload_bits']),
                                                            errors=0, minimum_sample_margin_v=margins['payload_bits']),
                      'assembled_hierarchy': dict(parent_source=experiment['assembly_source'], connectivity_verified=True)},
                  bias=bias, source_files_verified=len(sources), runtime_artifacts_verified=True,
                  excluded=report['excluded'],
                  producer_report_sha256=sha(out/'report.json'), waveform_sha256=sha(out/'wave.txt'),
                  auditor_sha256=sha(__file__))
    (out/'milestone-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, default=power.ROOT/'scratch/chip-fallback-live', help='check_chip_fallback.py output')
    p.add_argument('--record-runtime', type=int, metavar='PID')
    args = p.parse_args()
    out = args.output_dir.resolve()
    if args.record_runtime:
        record(out, args.record_runtime)
    else:
        audit(out)


if __name__ == '__main__':
    main()
