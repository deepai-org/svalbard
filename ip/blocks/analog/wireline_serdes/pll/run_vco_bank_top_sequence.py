#!/usr/bin/env python3
"""Verify parent-PEX nonoverlap handoff and old-VCO DAC shutdown."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))

from analog_evidence import sha256_file  # noqa: E402

CODE_PORTS = tuple(
    f"{prefix}_{channel}{bit}{suffix}"
    for prefix in ("F", "G")
    for channel in ("A", "B")
    for bit in range(4, -1, -1)
    for suffix in ("", "B")
)
MEASUREMENTS = (
    "before_period", "before_high", "before_low", "release_peak", "gap_peak",
    "gap_current", "after_period", "after_high", "after_low", "current_dual",
    "current_gain_only",
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def bits(prefix: str, code_a: int, code_b: int, *, shut_down: bool) -> list[str]:
    lines = []
    for channel, code in (("A", code_a), ("B", code_b)):
        for bit in range(4, -1, -1):
            value = (code >> bit) & 1
            for suffix, inverted in (("", False), ("B", True)):
                initial = value ^ inverted
                final = inverted if shut_down else initial
                node = f"{prefix}_{channel}{bit}{suffix}"
                if shut_down:
                    source = (
                        f"PWL(0 0 500p {3.3 * initial:.3f} 25n "
                        f"{3.3 * initial:.3f} 25.1n {3.3 * final:.3f})"
                    )
                else:
                    source = f"PWL(0 0 500p {3.3 * initial:.3f})"
                lines.append(f"V{node} {node} 0 {source}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "vco_bank_top_sequence_tb.spice.in"
    deck, log = args.work / "sequence.spice", args.work / "sequence.log"
    bit_sources = bits("F", 15, 20, shut_down=True) + bits(
        "G", 22, 22, shut_down=False
    )
    deck.write_text(instantiate(template_path.read_text(), {
        "PEX_PATH": str(args.pex), "DUT_CODE_PORTS": " ".join(CODE_PORTS),
        "BIT_SOURCES": "\n".join(bit_sources),
    }))
    with log.open("w") as output:
        run = subprocess.run(
            ["ngspice", "-b", str(deck)], stdout=output,
            stderr=subprocess.STDOUT, timeout=600, check=False,
        )
    pattern = re.compile(
        rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )
    observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
    complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
    before_frequency = 1 / observed.get("before_period", 0.0) \
        if observed.get("before_period", 0.0) > 0 else 0.0
    after_frequency = 1 / observed.get("after_period", 0.0) \
        if observed.get("after_period", 0.0) > 0 else 0.0
    current_reduction = observed.get("current_dual", 0.0) - observed.get(
        "current_gain_only", 0.0
    )
    gap_current_reduction = observed.get("current_dual", 0.0) - observed.get(
        "gap_current", 0.0
    )
    passed = (
        complete and 1.225e9 <= before_frequency <= 1.275e9
        and 1.10e9 <= after_frequency <= 1.40e9
        and observed["before_high"] >= 0.15 and observed["before_low"] <= -0.15
        and observed["after_high"] >= 0.15 and observed["after_low"] <= -0.15
        and observed["gap_peak"] <= 0.05
        and gap_current_reduction >= 0.001
        and current_reduction >= 0.001
        and observed["current_gain_only"] <= 0.025
    )
    result = {
        "schema_version": 1,
        "claim": "selected_bank_parent_break_before_make_and_old_vco_shutdown",
        "bias_reference_v": 2.0,
        "environment": ["typical", "res_typical", 3.3, 27],
        "fast_codes_before_shutdown": {"main": 15, "regen": 20},
        "gain_codes": {"main": 22, "regen": 22},
        "nonoverlap_interval_s": [20.1e-9, 22.0e-9],
        "old_vco_shutdown_time_s": 25.1e-9,
        "initial_condition": "none", "transient_uic": False,
        "observed": observed,
        "before_frequency_hz": before_frequency,
        "after_frequency_hz": after_frequency,
        "current_reduction_a": current_reduction,
        "gap_current_reduction_a": gap_current_reduction,
        "pex_sha256": sha256_file(args.pex),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "testbench_source_sha256": sha256_file(template_path),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"selected bank sequence: before={before_frequency / 1e9:.4f}GHz; "
        f"after={after_frequency / 1e9:.4f}GHz; gap={observed.get('gap_peak', 0):.4f}V; "
        f"result={result['result']}"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
