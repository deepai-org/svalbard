#!/usr/bin/env python3
"""Compare Chain 1 smoke outputs with the pinned nominal golden result."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re

MEASURE = re.compile(
    r"^(vout_high_initial|vout_low|vout_high_final|t_phl|t_plh)\s*=\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
    re.MULTILINE,
)
DRC_COUNT = re.compile(r"\[INFO\] COUNT:\s*(\d+)")
LVS_RESULT = re.compile(r"Final result:\s*([^\r\n]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--prelayout", required=True, type=Path)
    parser.add_argument("--postlayout", required=True, type=Path)
    parser.add_argument("--drc", required=True, type=Path)
    parser.add_argument("--lvs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def measurements(path: Path) -> dict[str, float]:
    values = {name: float(value) for name, value in MEASURE.findall(path.read_text())}
    required = {"vout_high_initial", "vout_low", "vout_high_final", "t_phl", "t_plh"}
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"{path} lacks measurements: {missing}")
    return values


def compare(actual: float, rule: dict[str, float]) -> tuple[bool, float]:
    expected = float(rule["expected"])
    tolerance = max(
        float(rule.get("absolute_tolerance", 0.0)),
        abs(expected) * float(rule.get("relative_tolerance", 0.0)),
    )
    delta = abs(actual - expected)
    return math.isfinite(actual) and delta <= tolerance, delta


def main() -> None:
    args = parse_args()
    golden = json.loads(args.golden.read_text())
    observed = {
        "prelayout": measurements(args.prelayout),
        "postlayout": measurements(args.postlayout),
    }
    checks: list[dict[str, object]] = []

    for stage, expected_values in golden["measurements"].items():
        for name, rule in expected_values.items():
            passed, delta = compare(observed[stage][name], rule)
            checks.append(
                {
                    "check": f"{stage}.{name}",
                    "pass": passed,
                    "actual": observed[stage][name],
                    "expected": rule["expected"],
                    "absolute_delta": delta,
                }
            )

    drc_text = args.drc.read_text()
    drc_match = DRC_COUNT.search(drc_text)
    drc_count = int(drc_match.group(1)) if drc_match else None
    checks.append(
        {
            "check": "magic_drc_error_count",
            "pass": drc_count == golden["drc_error_count"],
            "actual": drc_count,
            "expected": golden["drc_error_count"],
        }
    )

    lvs_text = args.lvs.read_text()
    lvs_matches = LVS_RESULT.findall(lvs_text)
    lvs_result = lvs_matches[-1].strip() if lvs_matches else None
    checks.append(
        {
            "check": "netgen_lvs_result",
            "pass": lvs_result == golden["lvs_result"],
            "actual": lvs_result,
            "expected": golden["lvs_result"],
        }
    )

    passed = all(bool(check["pass"]) for check in checks)
    result = {
        "schema_version": 1,
        "result": "pass" if passed else "fail",
        "qualification": golden["qualification"],
        "image_digest": golden["image_digest"],
        "pdk": golden["pdk"],
        "observed": observed,
        "checks": checks,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        failures = [str(check["check"]) for check in checks if not check["pass"]]
        raise SystemExit("Chain 1 golden comparison failed: " + ", ".join(failures))

    print("Chain 1 golden comparison: PASS")


if __name__ == "__main__":
    main()
