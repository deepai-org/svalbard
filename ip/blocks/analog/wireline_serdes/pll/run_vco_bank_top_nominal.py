#!/usr/bin/env python3
"""Run the first exact-PEX selected-bank startup/selection qualification."""
from __future__ import annotations

import argparse
import concurrent.futures
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
    "startup_time", "period_early", "period_late", "diff_high", "diff_low",
    "output_cm", "supply_current", "reference_power_avg",
)
CANDIDATES = (
    (13, 20, 1.50, 1.35),
    (14, 20, 1.50, 1.35),
    (14, 21, 1.50, 1.35),
    (15, 20, 1.50, 1.35),
    (15, 21, 1.50, 1.35),
    (16, 21, 1.50, 1.35),
    (16, 22, 1.50, 1.35),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def bit_sources(prefix: str, code_a: int, code_b: int, vdd: float) -> list[str]:
    lines = []
    for channel, code in (("A", code_a), ("B", code_b)):
        for bit in range(4, -1, -1):
            value = (code >> bit) & 1
            for suffix, inverted in (("", False), ("B", True)):
                high = value ^ inverted
                node = f"{prefix}_{channel}{bit}{suffix}"
                lines.append(
                    f"V{node} {node} 0 PWL(0 0 500p {vdd if high else 0:.3f})"
                )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "vco_bank_top_nominal_tb.spice.in"
    pattern = re.compile(
        rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )

    def run_candidate(candidate: tuple[int, int, float, float]) -> dict[str, object]:
        main_code, regen_code, selector_active, selector_buffer = candidate
        case_id = (
            f"m{main_code:02d}_r{regen_code:02d}_"
            f"sa{selector_active:.2f}_sb{selector_buffer:.2f}"
        ).replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        sources = (
            bit_sources("F", main_code, regen_code, 3.3)
            + bit_sources("G", 0, 0, 3.3)
        )
        deck.write_text(instantiate(template_path.read_text(), {
            "PEX_PATH": str(args.pex),
            "DUT_CODE_PORTS": " ".join(CODE_PORTS),
            "BIT_SOURCES": "\n".join(sources),
            "SEL_ACTIVE_V": f"{selector_active:.2f}",
            "SEL_BUFFER_V": f"{selector_buffer:.2f}",
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=300, check=False,
            )
        observed = {
            name: float(value) for name, value in pattern.findall(log.read_text())
        }
        complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
        early = observed.get("period_early", 0.0)
        late = observed.get("period_late", 0.0)
        frequency = 1.0 / late if late > 0 else 0.0
        drift = abs(late - early) / late if late > 0 and early > 0 else 1.0
        passed = (
            complete
            and 1.225e9 <= frequency <= 1.275e9
            and drift <= 0.01
            and observed["startup_time"] <= 8e-9
            and observed["diff_high"] >= 0.15
            and observed["diff_low"] <= -0.15
            and 0.5 <= observed["output_cm"] <= 3.1
            and observed["supply_current"] <= 0.035
            and observed["reference_power_avg"] <= 0.003
        )
        return {
            "id": case_id,
            "selected_codes": {"main": main_code, "regen": regen_code},
            "selector_bias_v": {
                "selected": selector_active,
                "unselected": 0.0,
                "buffer": selector_buffer,
            },
            "complete": complete,
            "observed": observed,
            "frequency_hz": frequency,
            "period_drift_fraction": drift,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(run_candidate, CANDIDATES))
    passing = [case for case in cases if case["result"] == "pass"]
    selected = min(
        passing, key=lambda case: abs(float(case["frequency_hz"]) - 1.25e9)
    ) if passing else None
    passed = selected is not None
    result = {
        "schema_version": 1,
        "claim": "nominal_realizable_code_selected_vco_bank_parent_pex",
        "bias_reference_v": 2.0,
        "environment": ["typical", "res_typical", 3.3, 27],
        "selected_member": "split_fast",
        "candidate_count": len(cases),
        "passing_candidate_count": len(passing),
        "selected_candidate": selected,
        "inactive_member_codes": {"main": 0, "regen": 0},
        "initial_condition": "none",
        "transient_uic": False,
        "cases": cases,
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
        f"selected bank nominal search: {len(passing)}/{len(cases)}; "
        f"selected={selected['id'] if selected else 'none'}; "
        f"result={result['result']}"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
