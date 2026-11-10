#!/usr/bin/env python3
"""Report the selected dense transport budget from fresh functional evidence.

This is an admission budget. Physical timing, board service, clock tolerance
and bounded host interruptions require their own qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
PROOFS = ['dense-transport', 'dense-service', 'dense-pair', 'dense-pair-link',
          'pair-gearbox', 'dense-rf-service', 'dense-rf-burst',
          'sync-fifo-depth', 'shared-egress-lifecycle']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report(out):
    proofs = [ROOT/'scratch'/name/'report.json' for name in PROOFS]
    for path in proofs:
        proof = json.loads(path.read_text())
        assert proof['status'] == 'pass', f'Functional evidence missing: {path}'
        assert all(sha(p) == h for p, h in proof['source_hashes'].items()), f'Stale evidence: {path}'
    core = (PROJECT/'rtl/pt_core.sv').read_text()
    paired = (PROJECT/'rtl/pt_core_pair.sv').read_text()
    assert 'pt_core_pair paired_core' in core
    assert 'pt_dense_pair_link_tx frame_tx' in paired and 'pt_dense_pair_link_rx frame_rx' in paired
    assert 'pt_pair_gearbox #(.PACK(1)) packer' in paired and 'pt_pair_gearbox #(.PACK(0)) unpacker' in paired
    header = re.search(r'#\(parameter\s+([^)]*)\)', paired)[1]
    parameters = {name: int(value) for name, value in re.findall(r'(\w+)=(\d+)', header)}
    clock_hz = 312.5e6
    payload_bps = clock_hz*10*59/64
    data = dict(status='budget_only_not_timing_or_service_signoff',
                primary_payload_words=59, frame_words=64, host_word_bits=10,
                primary_owner='digital.transport_config.payload_iq: 0 wire, 1 I/Q',
                host_word_clock_mhz=clock_hz/1e6, paired_engine_clock_mhz=clock_hz/2e6,
                raw_host_bps=clock_hz*10, payload_ceiling_bps=payload_bps,
                iq_framing_ceiling_complex_samples_s={str(width): payload_bps/width for width in (16, 24)},
                functional_qualified_rates=dict(wired_bps=2.5e9, iq_complex_samples_s=40e6),
                selected_storage=dict(wired_ingress_pairs=64, rf_ingress_samples=1 << parameters['RF_IN_A'],
                                      shared_egress_entries=1 << parameters['EGRESS_A'], shared_egress_bits_per_entry=24,
                                      iq_tx_pairs=parameters['IQ_TX_DEPTH'], iq_rx_pairs=parameters['IQ_RX_DEPTH'],
                                      owner_change='disable and flush before changing stopped-clock owner'),
                required_work=['close routed timing at the specified host/line/sample rates',
                               'qualify pad/board timing, clock tolerance and bounded interruptions',
                               'verify final state count and physical footprint'],
                source_hashes={str(p): sha(p) for p in
                               [Path(__file__).resolve(), PROJECT/'rtl/pt_core.sv',
                                PROJECT/'rtl/pt_core_pair.sv', PROJECT/'rtl/pt_pair_gearbox.sv',
                                PROJECT/'spec/streaming-transport-v2.md', *proofs]})
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(data, indent=2)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/transport-budget')
    report(parser.parse_args().output_dir.resolve())
