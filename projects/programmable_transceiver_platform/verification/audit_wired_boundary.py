#!/usr/bin/env python3
"""Inventory exact existing wired evidence; does not rerun electrical simulation."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SERDES = ROOT / 'ip/blocks/analog/wireline_serdes'
PROJECT = ROOT / 'projects/programmable_transceiver_platform'
checker = SERDES / 'lane/check_rx_capture_evidence.py'
checked = subprocess.run(['python3', str(checker)], capture_output=True, text=True)
if checked.returncode:
    raise SystemExit(checked.stdout + checked.stderr)
paths = [checker, SERDES / 'lane/lane_tb.spice.in',
         SERDES / 'lane/run_capture_stress_case.py',
         SERDES / 'pulse_bridge_lane/pulse_bridge_regenerative_sustained_result.json']
rows = []
for corner in ('tt', 'ff_cold', 'ff_hot', 'ss_hot', 'ss_passive'):
    path = SERDES / f'lane/extracted_capture_2p5_rx_capture_{corner}_result.json'
    paths.append(path)
    data = json.loads(path.read_text())
    rows.append(dict(environment=corner, result=data['result'],
                     scored_serial_bits=2*data['stimulus']['scored_pair_count'],
                     current_a=data['selected_case']['supply_current_a'],
                     controls=data['controls']))
pulse = json.loads(paths[3].read_text())
report = dict(
    status='integration_incomplete',
    evidence_kind='existing_evidence_integrity_check_and_scope_audit_not_new_simulation',
    routed_capture_checker_output=checked.stdout.strip(),
    routed_capture_cases=rows,
    routed_capture_total_scored_bits=sum(r['scored_serial_bits'] for r in rows),
    real_pulse_generator=dict(result=pulse['result'],
                             passing_cases=pulse['passing_case_count'],
                             total_cases=pulse['case_count'], boundary=pulse['boundary'],
                             integrity_scope='record hash only; physical flow not rerun in this audit'),
    missing_joint_evidence=[
        'Changing serial data through real pulse generation and capture circuitry',
        'Autonomous recovered clock with acquisition and frequency-offset tracking',
        'Serial-to-host word assembly with demonstrated timing and sustained transfer',
        'Selected pad/ESD/package/channel and complete clock/bias supply loading',
        'Noise, mismatch, jitter tolerance and statistically meaningful error-rate evidence'],
    next_experiment='At TT 3.3 V 27 C, replace static data in the actual pulse/bridge consumer screen with changing data and score each interleave; retain upstream ideal clock as an explicit remaining boundary.',
    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
out = PROJECT / 'evidence/wired-boundary-audit.json'
out.write_text(json.dumps(report, indent=2) + '\n')
print(checked.stdout.strip())
print(f"Recorded {report['routed_capture_total_scored_bits']} scored bits across five environments; no BER qualification.")
print(out)
