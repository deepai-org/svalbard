#!/usr/bin/env python3
"""Compactly validate the full-RC composed phase-error front end."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def pex_record(path: Path, subckt: str, minimum_r: int, minimum_c: int) -> dict:
    text = path.read_text()
    resistors = len(re.findall(r"^R\d+\s", text, re.MULTILINE))
    capacitors = len(re.findall(r"^C\d+\s", text, re.MULTILINE))
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "resistor_count": resistors, "capacitor_count": capacitors,
            "valid": (f".subckt {subckt}" in text
                      and "extresist threshold=0 mOhm" in text
                      and resistors >= minimum_r and capacitors >= minimum_c)}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("result", "calibration", "error-calibration", "sampler-pex",
                 "detector-pex", "error-pex", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    calibration = json.loads(args.calibration.read_text())
    error_calibration = json.loads(args.error_calibration.read_text())
    pex = {
        "sampler": pex_record(args.sampler_pex, "cdr_sampler_pex", 400, 150),
        "detector": pex_record(args.detector_pex, "cml_alexander_boundary_pex", 400, 150),
        "error_combiner": pex_record(args.error_pex, "cml_phase_error_filter_pex", 300, 100),
    }
    checks = {
        "calibration.valid": (calibration.get("result") == "pass"
                              and len(calibration.get("selected_settings", [])) == 9
                              and calibration.get("phase_search_case_count") == 252
                              and calibration.get("sampler_recalibration_case_count") == 420
                              and len(calibration.get("recalibrated_environments", [])) == 3),
        "error_calibration.valid": (error_calibration.get("result") == "pass"
                                    and error_calibration.get("case_count") == 108
                                    and error_calibration.get("complete_case_count") == 108
                                    and error_calibration.get("passing_group_count") == 9),
        "composition.all_complete": (result.get("case_count") == 36
                                     and result.get("complete_case_count") == 36),
        "composition.all_environments_calibrate": (result.get("result") == "pass"
                                                    and result.get("group_count") == 9
                                                    and result.get("passing_group_count") == 9),
        "composition.full_rc": result.get("mode") == "full_rc_composed",
        "composition.error_bias_calibrated": result.get("error_bias_calibrated") is True,
        "pex.all_full_rc": all(record["valid"] for record in pex.values()),
    }
    selected = []
    for group in result["groups"]:
        selected.extend(case for case in result["cases"]
                        if case["environment"] == group["environment"]
                        and case["sampler_bias_v"] == group["selected"]["sampler_bias_v"]
                        and case["edge_phase_deg"] == group["selected"]["edge_phase_deg"]
                        and case["error_bias_v"] == group["selected"]["error_bias_v"])
    summary = {
        "schema_version": 1, "result": "pass" if all(checks.values()) else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "calibration_sha256": hashlib.sha256(args.calibration.read_bytes()).hexdigest(),
        "error_calibration_sha256": hashlib.sha256(
            args.error_calibration.read_bytes()).hexdigest(),
        "composition_sha256": hashlib.sha256(args.result.read_bytes()).hexdigest(),
        "pex": pex,
        "observed": {
            "selected_error_bias_v": [min(case["error_bias_v"] for case in selected),
                                      max(case["error_bias_v"] for case in selected)],
            "selected_minimum_signed_error_v": min(case["minimum_signed_error_v"]
                                                    for case in selected),
            "selected_supply_current_a": [min(case["observed"]["supply_current"]
                                               for case in selected),
                                          max(case["observed"]["supply_current"]
                                               for case in selected)],
            "selected_output_common_mode_v": [min(case["observed"]["output_cm_avg"]
                                                   for case in selected),
                                              max(case["observed"]["output_cm_avg"]
                                                   for case in selected)],
        },
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if summary["result"] != "pass":
        raise SystemExit("composed full-RC checks failed: "
                         + ", ".join(name for name, value in checks.items() if not value))
    print("full-RC sampler/detector/error-combiner composition: PASS")


if __name__ == "__main__":
    main()
