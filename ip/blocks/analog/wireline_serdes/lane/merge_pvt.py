#!/usr/bin/env python3
"""Merge fail-closed representative extracted lane environments."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--case", action="append", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--serial-rate-gbd", type=float, choices=(1.25, 2.5), default=1.25)
parser.add_argument("--allow-fail", action="store_true")
args = parser.parse_args()
serial_rate_hz = args.serial_rate_gbd * 1e9
documents = [json.loads(path.read_text()) for path in args.case]
environments = [tuple(document.get("environment", ())) for document in documents]
valid = (
    len(documents) == 5
    and len(set(environments)) == 5
    and all(document.get("result") == "pass" for document in documents)
    and all(document.get("extraction") == "full_rc_leaves" for document in documents)
    and all(document.get("serial_rate_hz") == serial_rate_hz for document in documents)
)
result = {
    "schema_version": 1,
    "claim": ("representative_pvt_externally_clocked_1p25_gbd_tx_to_sampler"
              if args.serial_rate_gbd == 1.25 else
              "representative_pvt_externally_clocked_2p5_gts_tx_to_sampler"),
    "environment_count": len(documents),
    "passing_environment_count": sum(document.get("result") == "pass" for document in documents),
    "cases": [
        {
            "environment": document.get("environment"),
            "controls": document.get("controls"),
            "selected_case": ({
                key: document["selected_case"].get(key)
                for key in (
                    "id", "phase_deg", "selected_latency_ui",
                    "minimum_signed_tx_v", "minimum_signed_pin_v",
                    "selected_rx_contract_window", "minimum_signed_restored_v",
                    "minimum_signed_sample_v", "rx_common_mode_v",
                    "tx_common_mode_v", "amplifier_common_mode_v",
                    "restorer_common_mode_v", "supply_current_a", "result",
                )
            } if document.get("selected_case") else None),
            "evidence_sha256": sha256(path),
            "result": document.get("result"),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane representative PVT: {result['passing_environment_count']}/{len(documents)} pass")
if not valid and not args.allow_fail:
    raise SystemExit(1)
