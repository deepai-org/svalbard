#!/usr/bin/env python3
"""Run candidate-dependent functional and GF180 release gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

LOCAL_ROOT = Path(__file__).resolve().parents[1]
TESTS = Path("/tests") if Path("/tests/gating").is_dir() else LOCAL_ROOT / "tests"
REWARD = json.loads((TESTS / "assets/tiered_reward.json").read_text())


def candidate_digest(root: Path) -> str:
    value = hashlib.sha256()
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            value.update(path.relative_to(root).as_posix().encode() + b"\0")
            value.update(path.read_bytes())
    return value.hexdigest()


def run_gate(name: str, command: list[str], log: Path, timeout: int) -> bool:
    try:
        with (log / f"{name}.log").open("w") as stream:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        (log / f"{name}.log").write_text(f"{type(exc).__name__}: {exc}\n")
        return False


def quality(physical: dict) -> float:
    try:
        fmax = float(physical["estimated_fmax_mhz"])
        area = float(physical["area_um2"]) / 1_000_000.0
        power = float(physical["power_w"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    if not all(math.isfinite(value) and value > 0 for value in (fmax, area, power)):
        return 0.0
    levels = {
        "fmax": min(fmax / REWARD["normalization"]["fmax"]["full_credit"], 1.0),
        "area": min(REWARD["normalization"]["area"]["full_credit"] / area, 1.0),
        "power": min(REWARD["normalization"]["power"]["full_credit"] / max(power, 1e-12), 1.0),
    }
    return sum(REWARD["quality_weights"][name] * value for name, value in levels.items())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    candidate, log = args.candidate.resolve(), args.log.resolve()
    log.mkdir(parents=True, exist_ok=True)

    gates = {
        "candidate_safety": False,
        "jtag_4x4": False,
        "isa_engine_smp": False,
        "uart_invalid_boot": False,
        "uart_sdram": False,
        "sdhc": False,
        "pcie_iommu": False,
        "gf180_physical": False,
    }
    commands = [
        ("candidate_safety", [sys.executable, str(TESTS / "gating/candidate_safety.py"), str(candidate)], 60),
        ("jtag_4x4", [sys.executable, str(TESTS / "gating/run_jtag_adapter.py"), str(candidate)], 600),
        ("isa_engine_smp", [sys.executable, str(TESTS / "gating/run_isa_adapter.py"),
                            str(candidate), "--include-smp"], 28_800),
        ("uart_invalid_boot", [sys.executable, str(TESTS / "gating/run_boot_adapter.py"), str(candidate)], 600),
        ("uart_sdram", [sys.executable, str(TESTS / "gating/run_platform_adapter.py"), str(candidate)], 3_600),
        ("sdhc", [sys.executable, str(TESTS / "gating/run_sdhc_adapter.py"), str(candidate)], 3_600),
        ("pcie_iommu", [sys.executable, str(TESTS / "gating/run_pcie_adapter.py"), str(candidate)], 3_600),
    ]
    proceed = True
    for name, command, timeout in commands:
        if proceed:
            gates[name] = run_gate(name, command, log, timeout)
            proceed = gates[name]
        else:
            (log / f"{name}.log").write_text("SKIP: an earlier hard gate failed\n")

    physical: dict = {}
    if proceed:
        work = log / "physical"
        gates["gf180_physical"] = run_gate(
            "gf180_physical",
            [sys.executable, str(TESTS / "physical/run_gf180.py"), str(candidate),
             "--work", str(work), "--jobs", str(min(16, max(1, os.cpu_count() or 1)))],
            log, 43_200,
        )
        try:
            physical = json.loads((work / "physical_evidence.json").read_text())
        except (OSError, json.JSONDecodeError):
            physical = {}
    else:
        (log / "gf180_physical.log").write_text("SKIP: a functional hard gate failed\n")

    functional_names = [name for name in gates if name != "gf180_physical"]
    functional_level = sum(gates[name] for name in functional_names) / len(functional_names)
    eligible = all(gates.values())
    evidence = {
        "schema_version": 1,
        "benchmark": "circuitbench-digital/6045-lnp64-complete-soc",
        "candidate_sha256": candidate_digest(candidate),
        "hard_gates": gates,
        "eligible": eligible,
        "criteria": {
            "R1": functional_level,
            "R2": 1.0 if gates["gf180_physical"] else 0.0,
            "R3": quality(physical),
        },
        "physical": physical,
        "return_code": 0 if eligible else 1,
    }
    (log / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))
    raise SystemExit(evidence["return_code"])


if __name__ == "__main__":
    main()
