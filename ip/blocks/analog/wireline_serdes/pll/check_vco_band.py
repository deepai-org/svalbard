#!/usr/bin/env python3
"""Bind physical VCO-band closure to its exact electrical evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--band-pex", type=Path, required=True)
    parser.add_argument("--selector-drc", type=Path, required=True)
    parser.add_argument("--selector-lvs", type=Path, required=True)
    parser.add_argument("--selector-pex", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    physical = json.loads(args.physical.read_text())
    simulation = json.loads(args.simulation.read_text())
    selector_drc = args.selector_drc.read_text()
    selector_lvs = args.selector_lvs.read_text()
    selector_pex = args.selector_pex.read_text()
    drc_match = re.search(r"\[INFO\] COUNT:\s*(\d+)", selector_drc)
    band_hash, selector_hash = digest(args.band_pex), digest(args.selector_pex)
    selector = {
        "drc_error_count": int(drc_match.group(1)) if drc_match else -1,
        "lvs_unique": selector_lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", selector_pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", selector_pex, re.MULTILINE)),
        "pex_sha256": selector_hash,
    }
    identities = {
        "physical_to_band_pex": physical.get("pex_sha256") == band_hash,
        "simulation_to_band_pex": simulation.get("band_pex_sha256") == band_hash,
        "simulation_to_selector_pex": simulation.get("selector_pex_sha256") == selector_hash,
    }
    passed = (
        physical.get("result") == "pass"
        and simulation.get("result") == "pass"
        and selector["drc_error_count"] == 0
        and selector["lvs_unique"]
        and selector["pex_resistor_count"] >= 300
        and selector["pex_capacitor_count"] >= 100
        and all(identities.values())
    )
    result = {
        "schema_version": 1,
        "claim": "physical_vco_band_bound_to_full_rc_electrical_evidence",
        "physical": physical,
        "simulation": simulation,
        "selector_load": selector,
        "pex_identity": identities,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO band closure: physical={physical.get('result')}; "
          f"simulation={simulation.get('result')}; identity={all(identities.values())}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
