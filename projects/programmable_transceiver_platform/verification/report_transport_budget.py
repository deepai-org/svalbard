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
    host = (PROJECT/'rtl/pt_host_link.sv').read_text()
    assert 'pt_quad_link_tx #(.CW(WIRE_IN_A)) frame_tx' in core and 'pt_quad_link_rx frame_rx' in core
    assert 'pt_sample_pack packer' in core and 'pt_sample_unpack unpacker' in core
    assert 'pt_d2h_gearbox gearbox' in host and 'pt_h2d_gearbox h2d' in host and 'pt_host_divider divider' in host
    header = re.search(r'module pt_core #\(parameter\s+([^)]*)\)', core)[1]
    parameters = {name: int(value) for name, value in re.findall(r'(\w+)=(\d+)', header)}
    word_hz = 312.5e6
    payload_bps = word_hz*10*59/64
    data = dict(status='budget_only_not_timing_or_service_signoff',
                primary_payload_words=59, frame_words=64, host_word_bits=10,
                primary_owner='digital.transport_config.payload_iq: 0 wire, 1 I/Q',
                host_word_clock_mhz=word_hz/1e6, pad_ddr_clock_mhz=word_hz/2e6, core_clock_mhz=word_hz/4e6,
                core_word_bits=40, wired_boundary=dict(bits=40, clock='line/40', mhz_at_2g5=62.5),
                raw_host_bps=word_hz*10, payload_ceiling_bps=payload_bps,
                reduced_rate_div2_payload_ceiling_bps=payload_bps/2,
                iq_framing_ceiling_complex_samples_s={str(width): payload_bps/width for width in (16, 24)},
                functional_qualified_rates=dict(wired_bps=2.5e9, iq_complex_samples_s=40e6,
                                                iq_complex_samples_s_at_div2=40e6),
                selected_storage=dict(shared_ingress_quads=parameters['WIRE_IN_DEPTH'],
                                      shared_egress_quads=parameters['EGRESS_DEPTH'], bits_per_entry=40,
                                      host_h2d_quads=8, wired_start_quads=parameters['WIRE_START'],
                                      rf_start_quads=parameters['RF_START'],
                                      owner_change='disable and flush before changing stopped-clock owner'),
                required_work=['close routed timing at the specified host/line/sample rates',
                               'qualify pad/board timing, clock tolerance and bounded interruptions',
                               'verify final state count and physical footprint'],
                source_hashes={str(p): sha(p) for p in
                               [Path(__file__).resolve(), PROJECT/'rtl/pt_core.sv', PROJECT/'rtl/pt_host_link.sv',
                                PROJECT/'rtl/pt_quad_link.sv', PROJECT/'rtl/pt_quad_gearbox.sv',
                                PROJECT/'spec/streaming-transport-v2.md', *proofs]})
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(data, indent=2)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/transport-budget')
    report(parser.parse_args().output_dir.resolve())
