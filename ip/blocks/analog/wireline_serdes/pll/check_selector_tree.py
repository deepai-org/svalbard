#!/usr/bin/env python3
"""Combine selector-tree physical and extracted switching evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    physical = json.loads(args.physical.read_text())
    simulation = json.loads(args.simulation.read_text())
    same_pex = physical.get("pex_sha256") == simulation.get("pex_sha256")
    passed = (physical.get("result") == "pass" and simulation.get("result") == "pass"
              and same_pex)
    result = {"schema_version": 1, "claim": "physical_twelve_band_selector_tree",
              "physical": physical, "extracted_switching": simulation,
              "pex_identity_match": same_pex,
              "result": "pass" if passed else "fail"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"selector tree combined: physical={physical.get('result')}; "
          f"simulation={simulation.get('result')}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
