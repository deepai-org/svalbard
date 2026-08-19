#!/usr/bin/env python3
"""Bind VCO-bias DAC electrical evidence to its checked physical artifacts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))

from analog_evidence import sha256_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dac-source", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--lvs", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--gds", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    simulation = json.loads(args.simulation.read_text())
    drc = args.drc.read_text()
    lvs = args.lvs.read_text()
    pex = args.pex.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    physical = {
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": sha256_file(args.pex),
        "gds_sha256": sha256_file(args.gds),
        "layout_image_sha256": sha256_file(args.render),
        "layout_image_bytes": args.render.stat().st_size,
    }
    identity = physical["pex_sha256"] == simulation["pex_sha256"]
    passed = (
        physical["drc_error_count"] == 0
        and physical["lvs_unique"]
        and physical["pex_resistor_count"] >= 600
        and physical["pex_capacitor_count"] >= 240
        and physical["layout_image_bytes"] >= 20_000
        and identity
        and simulation["result"] == "pass"
    )
    result = {
        "schema_version": 1,
        "claim": "physical_dual_5bit_vco_bias_dac",
        "physical": physical,
        "simulation_to_pex_identity": identity,
        "simulation": simulation,
        "dac_layout_source_sha256": sha256_file(args.dac_source / "layout.tcl"),
        "dac_schematic_source_sha256": sha256_file(
            args.dac_source / "phase_control_dac.spice"
        ),
        "checker_source_sha256": sha256_file(Path(__file__)),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"physical VCO bias DAC: drc={physical['drc_error_count']}; "
        f"lvs={physical['lvs_unique']}; identity={identity}; "
        f"electrical={simulation['result']}"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
