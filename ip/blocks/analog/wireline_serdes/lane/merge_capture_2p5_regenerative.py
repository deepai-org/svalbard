#!/usr/bin/env python3
"""Merge exact-PEX direct-regenerative capture environments."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--case", action="append", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
documents = [json.loads(path.read_text()) for path in args.case]
expected_ids = {"tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive"}
frontend_latencies = {"tt": 2, "ff_cold": 0, "ff_hot": 2,
                      "ss_hot": 2, "ss_passive": 2}
composition = "routed_termination_rx_dual_regenerative_sampler_capture_parent"
identity_fields = ("pex_sha256", "physical_sha256", "source_sha256")
complete = (
    len(documents) == 5
    and {document.get("case_id") for document in documents} == expected_ids
    and all(document.get("case_count") == 1
            and document.get("complete_case_count") == 1 for document in documents)
    and all(document.get("stimulus", {}).get("serial_rate_hz") == 2.5e9
            and document.get("stimulus", {}).get("pattern") == "prbs7"
            and document.get("stimulus", {}).get("bit_count") == 24
            and document.get("stimulus", {}).get("scored_pair_count") == 8
            for document in documents)
    and all(document.get("channel_stress", {}).get(
        "series_resistance_ohm_per_leg") == 6.0 for document in documents)
    and all(document.get("channel_stress", {}).get(
        "differential_shunt_capacitance_f") == 1e-12 for document in documents)
    and all(document.get("stimulus", {}).get(
        "tx_clock_jitter_peak_s") == 30e-12
        and document.get("stimulus", {}).get("tx_clock_duty") == 0.47
        for document in documents)
    and all(document.get("supply_stress", {}).get(
        "vdd_ripple_peak_v") == 20e-3
        and document.get("supply_stress", {}).get(
            "vdd_ripple_frequency_hz") == 100e6 for document in documents)
    and all(document.get("controls", {}).get("restorer_mode") == "none"
            and document.get("controls", {}).get("frontend_tail_boost") is True
            and document.get("controls", {}).get("capture_delay_ps") == 200
            and document.get("controls", {}).get("capture_width_ps") == 150
            and document.get("controls", {}).get("frontend_latency_ui")
            == frontend_latencies.get(document.get("case_id"))
            and document.get("controls", {}).get("frontend_write_latency_ui") == 2
            and document.get("controls", {}).get("capture_latency_ui") == 2
            for document in documents)
    and all(document.get("evidence_class") == "exact_pex"
            and document.get("physical_composition") == composition
            for document in documents)
    and all(document.get(field) == documents[0].get(field)
            for field in identity_fields for document in documents[1:])
)
keys = (
    "minimum_tx_even_v", "minimum_tx_odd_v", "minimum_pin_even_v",
    "minimum_pin_odd_v", "minimum_sampler_even_v", "minimum_sampler_odd_v",
    "minimum_frontend_even_v", "minimum_frontend_odd_v",
    "minimum_frontend_write_even_v", "minimum_frontend_write_odd_v",
    "minimum_capture_even_v", "minimum_capture_odd_v", "rx_common_mode_v",
    "amplifier_common_mode_v", "supply_current_a", "result",
)
result = {
    "schema_version": 1,
    "claim": "routed_regenerative_rx_capture_extracted_2p5_gts_combined_stress_pvt",
    "aggregate_source_sha256": digest(Path(__file__)),
    "physical_composition": composition,
    "case_count": len(documents),
    "passing_case_count": sum(document.get("result") == "pass"
                              for document in documents),
    "cases": [{
        "case_id": document.get("case_id"),
        "environment": document.get("environment"),
        "controls": document.get("controls"),
        "measurements": {key: document["cases"][0].get(key) for key in keys},
        "pex_sha256": document.get("pex_sha256"),
        "physical_sha256": document.get("physical_sha256"),
        "source_sha256": document.get("source_sha256"),
        "evidence_sha256": digest(path),
        "result": document.get("result"),
    } for path, document in zip(args.case, documents)],
    "result": ("pass" if complete and all(document.get("result") == "pass"
                                             for document in documents)
               else "fail"),
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"regenerative capture PVT: {result['passing_case_count']}/"
      f"{len(documents)} pass")
if not complete:
    raise SystemExit(1)
if result["result"] != "pass":
    raise SystemExit(1)
