#!/usr/bin/env python3
"""Measure candidate-specific internal nodes in the integrated event PEX."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import run_event_capture_schematic as runner
import run_hclk_window_probe as base


NODES = ("hsn", "estate", "lc0b", "lc1", "lc2b", "lstate", "sib", "sdrv")
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    controls = {item["id"]: item for item in runner.CONTROLS}
    environments = {item["id"]: item for item in base.CONTRACT["environments"]}
    cases = []
    for environment_id, control_id in (
        ("tt", "sense1_interval0_epoch0"),
        ("ss_hot", "sense1_interval0_epoch0"),
    ):
        environment, control = environments[environment_id], controls[control_id]
        deck_text = runner.compile_deck(
            args.pex, None, args.capture, environment, control,
            combined_pex=True,
        )
        measures = []
        for phase in ("e", "o"):
            for node in NODES:
                hierarchical = f"xsource.DBG_{phase.upper()}_{node.upper()}"
                measures.extend([
                    f"meas tran probe_{phase}_{node}_high max v({hierarchical}) from=8n to=12.8n",
                    f"meas tran probe_{phase}_{node}_low min v({hierarchical}) from=8n to=12.8n",
                ])
        deck_text = deck_text.replace(
            ".endc\n.end", "\n".join(measures) + "\n.endc\n.end")
        stem = f"{environment_id}_{control_id}"
        deck, log = args.work / f"{stem}.spice", args.work / f"{stem}.log"
        deck.write_text(deck_text)
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=300, check=False,
            )
        observed = {
            key: float(value) for key, value in MEASURE.findall(log.read_text())
            if key.startswith("probe_")
        }
        expected = 2 * 2 * len(NODES)
        cases.append({
            "case_id": stem,
            "complete": run.returncode == 0 and len(observed) == expected,
            "returncode": run.returncode,
            "observed": observed,
        })
    result = {
        "schema_version": 1,
        "claim": "capture_integrated_state_full_rc_internal_diagnostic",
        "scope": "diagnostic only; candidate-specific internal full-RC nodes",
        "nodes": list(NODES),
        "cases": cases,
        "result": "pass" if all(case["complete"] for case in cases) else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "complete_cases": sum(case["complete"] for case in cases)}))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
