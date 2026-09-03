#!/usr/bin/env python3
"""Public structural checks; functional adapters activate when a DUT exists."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parents[3]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()

    run([sys.executable, str(BENCH_ROOT / "tests/reference/test_ethernet_oracle.py")])
    run([sys.executable, str(BENCH_ROOT / "tests/reference/test_analog_metrics.py")])
    run([sys.executable, str(BENCH_ROOT / "tests/coverage/audit_coverage.py")])
    run([
        sys.executable,
        str(BENCH_ROOT / "tests/gating/candidate_safety.py"),
        "--output",
        str(output),
    ])

    compiler = shutil.which("iverilog")
    if compiler is None:
        raise RuntimeError("iverilog is required for the public RTL interface check")
    build = output / ".visible-smoke.vvp"
    try:
        run([
            compiler,
            "-g2012",
            "-s",
            "tb_gigabit_ethernet_port_smoke",
            "-o",
            str(build),
            str(output / "rtl/gigabit_ethernet_port_pkg.sv"),
            str(output / "rtl/gigabit_ethernet_port.sv"),
            str(Path(__file__).resolve().parent / "tb_gigabit_ethernet_port_smoke.sv"),
        ])
        run(["vvp", str(build)])
    finally:
        build.unlink(missing_ok=True)

    result = {
        "schema_version": 1,
        "candidate_structural_checks": "passed",
        "functional_candidate_tests": "visible_digital_loopback_smoke_passed",
        "analog_candidate_tests": "adapter_pending_candidate",
        "candidate_passage_claimed": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
