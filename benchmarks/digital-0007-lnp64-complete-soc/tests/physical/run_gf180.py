#!/usr/bin/env python3
"""Prepare and run the frozen candidate-dependent GF180MCU implementation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

LOCAL_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path("/tests") if Path("/tests/physical").is_dir() else LOCAL_ROOT / "tests"
INPUT = Path("/app/input_files") if Path("/app/input_files/contract").is_dir() else LOCAL_ROOT / "environment/input_files"
LEAF = "gf180mcu_fd_ip_sram__sram512x8m8wm1"
CORNER = "nom_ss_125C_4v50"


def candidate_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def rtl_files(candidate: Path) -> list[Path]:
    package = candidate / "rtl/lnp64_soc_pkg.sv"
    top = candidate / "rtl/lnp64_soc.sv"
    if not package.is_file() or not top.is_file():
        raise SystemExit("candidate is missing required RTL")
    rest = sorted(path for path in (candidate / "rtl").glob("*.sv") if path not in {package, top})
    return [package, *rest, top]


def run_checked(command: list[str], *, cwd: Path, log: Path | None = None) -> None:
    if log is None:
        subprocess.run(command, cwd=cwd, check=True)
        return
    with log.open("w") as stream:
        process = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
    if process.returncode:
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-80:])
        raise SystemExit(f"command failed ({process.returncode}): {' '.join(command)}\n{tail}")


def elaborate(candidate_rtl: list[Path], work: Path) -> list[str]:
    wrapper = TEST_ROOT / "physical/lnp64_sram_macros_physical.sv"
    script = work / "elaborate.ys"
    lines = [f"read_verilog -sv {path}" for path in [*candidate_rtl, wrapper]]
    # Flattening establishes the exact macro instance names without lowering
    # processes or inferred memories. The real synthesis pass remains the
    # authority for all logic transformations.
    lines += [
        "hierarchy -check -top lnp64_soc",
        "flatten",
        "proc",
        "check -assert",
        "select -assert-none t:$dlatch",
        f"select -write leaf_cells.txt t:{LEAF}",
    ]
    script.write_text("\n".join(lines) + "\n")
    run_checked(["yosys", "-q", "-s", str(script)], cwd=work, log=work / "elaborate.log")
    prefix = "lnp64_soc/"
    leaves = []
    for line in (work / "leaf_cells.txt").read_text().splitlines():
        if not line.startswith(prefix):
            raise SystemExit(f"unexpected SRAM selection path: {line}")
        leaves.append(line.removeprefix(prefix))
    return sorted(leaves)


def macro_layout(leaves: list[str]) -> tuple[dict, list[float] | None, list[float] | None]:
    if not leaves:
        return {}, None, None
    leaf_width, leaf_height = 431.86, 484.88
    gap, margin = 50.0, 100.0
    columns = max(1, math.ceil(math.sqrt(len(leaves) * leaf_height / leaf_width)))
    rows = math.ceil(len(leaves) / columns)
    occupied_width = columns * leaf_width + (columns - 1) * gap
    occupied_height = rows * leaf_height + (rows - 1) * gap
    # SRAMs occupy the lower-left portion. Generous contiguous space remains
    # above and to the right for logic, repair buffers, and routing; die area is
    # not an eligibility constraint in this benchmark.
    die_width = math.ceil((occupied_width + 2 * margin) * 1.75)
    die_height = math.ceil((occupied_height + 2 * margin) * 1.75)
    instances = {}
    for index, name in enumerate(leaves):
        column, row = index % columns, index // columns
        instances[name] = {
            "location": [margin + column * (leaf_width + gap), margin + row * (leaf_height + gap)],
            "orientation": "N",
        }
    die = [0.0, 0.0, float(die_width), float(die_height)]
    core = [20.0, 20.0, float(die_width - 20), float(die_height - 20)]
    return instances, die, core


def make_config(candidate_rtl: list[Path], leaves: list[str], work: Path) -> Path:
    wrapper = TEST_ROOT / "physical/lnp64_sram_macros_physical.sv"
    sdc = work / "lnp64_soc.sdc"
    constraints = (INPUT / "constraints/lnp64_soc.sdc").read_text()
    if leaves:
        constraints += "\n" + (TEST_ROOT / "physical/sram_clocks.sdc").read_text()
    sdc.write_text(constraints)

    instances, die, core = macro_layout(leaves)
    config: dict[str, object] = {
        "meta": {"version": 3, "flow": "Classic"},
        "DESIGN_NAME": "lnp64_soc",
        "VERILOG_FILES": [str(path.resolve()) for path in [*candidate_rtl, wrapper]],
        "STD_CELL_LIBRARY": "gf180mcu_fd_sc_mcu9t5v0",
        "CLOCK_PORT": "clk_200_i",
        "CLOCK_PERIOD": 5.0,
        "PNR_SDC_FILE": str(sdc),
        "SIGNOFF_SDC_FILE": str(sdc),
        "FALLBACK_SDC": str(sdc),
        "DEFAULT_CORNER": CORNER,
        "STA_CORNERS": [CORNER],
        "SYNTH_STRATEGY": "DELAY 0",
        "PL_TARGET_DENSITY_PCT": 40,
        "PL_MAX_DISPLACEMENT_X": 800,
        "PL_MAX_DISPLACEMENT_Y": 500,
        "GRT_ALLOW_CONGESTION": True,
        "RT_MAX_LAYER": "Metal5",
        "DRT_ANTENNA_REPAIR_ITERS": 4,
        "PDN_CFG": str((TEST_ROOT / "physical/pdn_macros.tcl").resolve()),
    }
    if leaves:
        config.update({"FP_SIZING": "absolute", "DIE_AREA": die, "CORE_AREA": core})
        config["MACROS"] = {
            LEAF: {
                "gds": ["pdk_dir::libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram512x8m8wm1.gds"],
                "lef": ["pdk_dir::libs.ref/gf180mcu_fd_ip_sram/lef/gf180mcu_fd_ip_sram__sram512x8m8wm1.lef"],
                "vh": ["pdk_dir::libs.ref/gf180mcu_fd_ip_sram/verilog/gf180mcu_fd_ip_sram__sram512x8m8wm1__blackbox.v"],
                "lib": {"*_ss_125C_4v50": [f"pdk_dir::libs.ref/gf180mcu_fd_ip_sram/lib/{LEAF}__ss_125C_4v50.lib"]},
                "instances": instances,
            }
        }
    else:
        config.update({"FP_SIZING": "relative", "FP_CORE_UTIL": 40})
    path = work / "config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def parse_result(work: Path, digest: str, macro_count: int, mapped_smoke_passed: bool) -> dict:
    final = work / "runs/candidate/final"
    metrics_path = final / "metrics.json"
    if not metrics_path.is_file():
        raise SystemExit("LibreLane did not produce final metrics")
    metrics = json.loads(metrics_path.read_text())
    required_views = [final / "def/lnp64_soc.def", final / "odb/lnp64_soc.odb", final / "nl/lnp64_soc.nl.v"]
    route_complete = all(path.is_file() and path.stat().st_size for path in required_views)
    wns = float(metrics.get(f"timing__setup__wns__corner:{CORNER}", float("-inf")))
    setup_count = int(metrics.get(f"timing__setup_vio__count__corner:{CORNER}", -1))
    route_drc = int(metrics.get("route__drc_errors", -1))
    standard_cell_area = float(metrics.get("design__instance__area__stdcell", float("nan")))
    macro_area = float(metrics.get("design__instance__area__macros", float("nan")))
    area = standard_cell_area + macro_area
    power = float(metrics.get("power__total", float("nan")))
    critical_period = 5.0 - wns
    evidence = {
        "schema_version": 1,
        "candidate_digest": digest,
        "pdk": "GF180MCU/gf180mcuD",
        "standard_cell_library": "gf180mcu_fd_sc_mcu9t5v0",
        "corner": CORNER,
        "sram_leaf_instances": macro_count,
        "route_complete": route_complete,
        "route_drc_errors": route_drc,
        "mapped_smoke_passed": mapped_smoke_passed,
        "setup_wns_ns": wns,
        "setup_violation_count": setup_count,
        "area_um2": area,
        "power_w": power,
        "estimated_fmax_mhz": 1000.0 / critical_period if critical_period > 0 else 0.0,
    }
    evidence["eligible"] = (
        route_complete and route_drc == 0 and mapped_smoke_passed
        and setup_count == 0 and wns >= 0.0
        and math.isfinite(wns) and math.isfinite(area) and area > 0.0
        and math.isfinite(power) and power > 0.0
    )
    (work / "physical_evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=min(16, max(1, os.cpu_count() or 1)))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    work = args.work.resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    files = rtl_files(candidate)
    leaves = elaborate(files, work)
    config = make_config(files, leaves, work)
    digest = candidate_digest(candidate)
    preparation = {"candidate_digest": digest, "sram_leaf_instances": len(leaves), "config": str(config)}
    (work / "preparation.json").write_text(json.dumps(preparation, indent=2, sort_keys=True) + "\n")
    if args.prepare_only:
        print(f"GF180 preparation: PASS ({len(leaves)} SRAM leaves)")
        return
    command = [
        "librelane", "--manual-pdk", "--pdk-root", os.environ.get("PDK_ROOT", "/foss/pdks"),
        "-p", "gf180mcuD", "-s", "gf180mcu_fd_sc_mcu9t5v0", "-j", str(args.jobs),
        "--condensed", "--hide-progress-bar", "--to", "OpenROAD.STAPostPNR",
        "--run-tag", "candidate", str(config),
    ]
    run_checked(command, cwd=work, log=work / "librelane.log")
    mapped_log = work / "mapped_smoke.log"
    mapped_netlist = work / "runs/candidate/06-yosys-synthesis/lnp64_soc.nl.v"
    mapped = subprocess.run(
        [sys.executable, str(TEST_ROOT / "physical/run_mapped_smoke.py"),
         str(mapped_netlist)],
        cwd=work, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    mapped_log.write_text(mapped.stdout)
    evidence = parse_result(work, digest, len(leaves), mapped.returncode == 0)
    print(json.dumps(evidence, sort_keys=True))
    if not evidence["eligible"]:
        raise SystemExit("GF180 physical eligibility: FAIL")
    print("GF180 physical eligibility: PASS")


if __name__ == "__main__":
    main()
