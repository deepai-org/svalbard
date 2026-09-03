#!/usr/bin/env python3
"""Emit the fail-closed initial tier ledger.

The concrete DUT adapters are intentionally not fabricated without a DUT.  This
entry point prevents a benchmark scaffold from being mistaken for passing
evidence while preserving the exact tier interface future adapters must fill.
"""

from __future__ import annotations

import json


def main() -> int:
    result = {
        "schema_version": 1,
        "benchmark": "circuitbench-mixed-signal/0001-complete-gigabit-ethernet-port",
        "candidate_passage_claimed": False,
        "tiers": {
            "T1_mac": {"score": 0.0, "state": "candidate_adapter_required"},
            "T2_pcs": {"score": 0.0, "state": "candidate_adapter_required"},
            "T3_mapped_digital": {"score": 0.0, "state": "candidate_adapter_required"},
            "T4_analog_ideal_clock": {"score": 0.0, "state": "candidate_adapter_required"},
            "T5_integrated_clocking": {"score": 0.0, "state": "candidate_adapter_required"},
            "T6_extracted_phy": {"score": 0.0, "state": "candidate_adapter_required"},
            "T7_complete_port": {"score": 0.0, "state": "candidate_adapter_required"}
        },
        "reason": "No working solution was requested or supplied; test scenarios and oracle qualification are separate from DUT passage."
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
