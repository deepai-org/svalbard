#!/usr/bin/env python3
"""Build the checked-in golden DCO layout from its structural GF180 netlist."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
TOP = "dco4"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "solution/golden_output/layout/dco4.gds")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    work = args.work.resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    source = (ROOT / "solution/source/dco4.v").resolve()
    config = {
        "meta": {"version": 3, "flow": "Classic"},
        "DESIGN_NAME": TOP,
        "VERILOG_FILES": [str(source)],
        "STD_CELL_LIBRARY": "gf180mcu_fd_sc_mcu7t5v0",
        "SYNTH_ELABORATE_ONLY": True,
        "SYNTH_CHECKS_ALLOW_TRISTATE": True,
        "ERROR_ON_SYNTH_CHECKS": False,
        "SETUP_VIOLATION_CORNERS": [],
        "TIMING_VIOLATION_CORNERS": [],
        "SYNTH_DIRECT_WIRE_BUFFERING": False,
        "SYNTH_SPLITNETS": False,
        "RSZ_DONT_TOUCH_RX": "^X",
        "DESIGN_REPAIR_BUFFER_INPUT_PORTS": False,
        "DESIGN_REPAIR_BUFFER_OUTPUT_PORTS": False,
        "DESIGN_REPAIR_TIE_FANOUT": False,
        "PL_RESIZER_SETUP_BUFFERING": False,
        "PL_RESIZER_SETUP_BUFFER_REMOVAL": False,
        "GRT_RESIZER_SETUP_BUFFERING": False,
        "GRT_RESIZER_SETUP_BUFFER_REMOVAL": False,
        "VDD_NETS": ["VDD"],
        "GND_NETS": ["VSS"],
        "FP_SIZING": "relative",
        "FP_CORE_UTIL": 25,
        "PL_TARGET_DENSITY_PCT": 30,
        "GRT_ALLOW_CONGESTION": True,
        "DRT_THREADS": max(1, min(args.jobs, 16)),
        "RT_MAX_LAYER": "Metal5",
        "DRT_ANTENNA_REPAIR_ITERS": 4,
    }
    cfg = work / "config.json"
    cfg.write_text(json.dumps(config, indent=2) + "\n")
    env = os.environ.copy()
    env["PATH"] = "/foss/tools/bin:/foss/tools/klayout:" + env.get("PATH", "")
    command = [
        "librelane", "--manual-pdk", "--pdk-root", env.get("PDK_ROOT", "/foss/pdks"),
        "-p", "gf180mcuD", "-s", "gf180mcu_fd_sc_mcu7t5v0", "-j", str(args.jobs),
        "--condensed", "--hide-progress-bar",
        "--skip", "OpenROAD.RepairDesignPostGPL",
        "--skip", "OpenROAD.ResizerTimingPostCTS",
        "--skip", "OpenROAD.ResizerTimingPostGRT",
        "--skip", "Checker.SetupViolations",
        "--run-tag", "golden", str(cfg),
    ]
    with (work / "librelane.log").open("w") as log:
        result = subprocess.run(command, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print("\n".join((work / "librelane.log").read_text(errors="replace").splitlines()[-120:]))
        raise SystemExit("LibreLane failed")
    gds = work / "runs/golden/final/gds/dco4.gds"
    if not gds.is_file():
        raise SystemExit("LibreLane produced no final GDS")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gds, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
