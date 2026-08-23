#!/usr/bin/env python3
"""Validate combined exact-PEX lane stress across representative PVT."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--case", action="append", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
documents = [json.loads(path.read_text()) for path in args.case]
observed = [(document.get("cases") or [{}])[0] for document in documents]
environments = [tuple(document.get("environment", ())) for document in documents]
pex = [document.get("pex_sha256") for document in documents]
physical = [document.get("physical_sha256") for document in documents]
sources = [document.get("source_sha256") for document in documents]
expected_ids = {"tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive"}
expected_restorer_bias = {
    "tt": 1.3, "ff_cold": 1.3, "ff_hot": 1.2,
    "ss_hot": 1.4, "ss_passive": 1.3,
}


def same_contract(document: dict) -> bool:
    stimulus = document.get("stimulus", {})
    channel = document.get("channel_stress", {})
    supply = document.get("supply_stress", {})
    controls = document.get("controls", {})
    return (
        stimulus.get("pattern") == "prbs7"
        and stimulus.get("bit_count") == 40
        and stimulus.get("scored_pair_count") == 16
        and stimulus.get("tx_clock_jitter_peak_s") == 30e-12
        and stimulus.get("tx_clock_duty") == 0.47
        and channel.get("series_resistance_ohm_per_leg") == 6.0
        and channel.get("differential_shunt_capacitance_f") == 1e-12
        and supply.get("vdd_ripple_peak_v") == 20e-3
        and supply.get("vdd_ripple_frequency_hz") == 100e6
        and controls.get("restorer_mode") == "data"
        and controls.get("sampler_phase_deg") == 78.75
    )


valid = (
    len(documents) == 5 and len(set(environments)) == 5
    and {document.get("case_id") for document in documents} == expected_ids
    and all(document.get("result") == "pass" for document in documents)
    and all(same_contract(document) for document in documents)
    and all(document.get("controls", {}).get("restorer_bias_v")
            == expected_restorer_bias[document.get("case_id")]
            for document in documents)
    and all(identity == pex[0] for identity in pex[1:])
    and all(identity == physical[0] for identity in physical[1:])
    and all(identity == sources[0] for identity in sources[1:])
)


def minimum(stage: str) -> float:
    return min(min(case.get(f"minimum_{stage}_even_v", 0.0),
                   case.get(f"minimum_{stage}_odd_v", 0.0))
               for case in observed)


result = {
    "schema_version": 1,
    "claim": "combined_pvt_channel_timing_supply_extracted_lane_stress",
    "environment_count": len(documents),
    "passing_environment_count": sum(document.get("result") == "pass"
                                      for document in documents),
    "stimulus": documents[0].get("stimulus") if documents else None,
    "channel_stress": documents[0].get("channel_stress") if documents else None,
    "supply_stress": documents[0].get("supply_stress") if documents else None,
    "minimum_tx_margin_v": minimum("tx"),
    "minimum_pin_margin_v": minimum("pin"),
    "minimum_rx_margin_v": minimum("rx"),
    "minimum_restored_margin_v": minimum("restored"),
    "minimum_frontend_margin_v": minimum("frontend"),
    "minimum_capture_margin_v": minimum("capture"),
    "minimum_supply_current_a": min(case.get("supply_current_a", 0.0)
                                    for case in observed),
    "maximum_supply_current_a": max(case.get("supply_current_a", 0.0)
                                    for case in observed),
    "pex_sha256": pex[0] if pex else None,
    "physical_sha256": physical[0] if physical else None,
    "source_sha256": sources[0] if sources else None,
    "cases": [
        {
            "case_id": document.get("case_id"),
            "environment": document.get("environment"),
            "controls": document.get("controls"),
            "observed_case": (document.get("cases") or [None])[0],
            "result": document.get("result"),
            "evidence_sha256": sha256(path),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane combined stress PVT: {result['passing_environment_count']}/"
      f"{len(documents)} pass")
if not valid:
    raise SystemExit(1)
