#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ZERO_METRICS = (
    "flow__errors__count",
    "design__lint_error__count",
    "synthesis__check_error__count",
    "design__instance_unmapped__count",
    "design__critical_disconnected_pin__count",
    "design__disconnected_pin__count",
    "design__violations",
    "route__drc_errors",
    "route__antenna_violation__count",
    "design__power_grid_violation__count",
    "design__xor_difference__count",
    "magic__drc_error__count",
    "klayout__drc_error__count",
    "design__lvs_error__count",
    "design__lvs_device_difference__count",
    "design__lvs_net_difference__count",
    "design__lvs_property_fail__count",
    "design__lvs_unmatched_device__count",
    "design__lvs_unmatched_net__count",
    "design__lvs_unmatched_pin__count",
    "design__max_slew_violation__count",
    "design__max_cap_violation__count",
    "design__max_fanout_violation__count",
    "timing__setup_vio__count",
    "timing__hold_vio__count",
    "timing__unannotated_net__count",
)
CORNERS = tuple(
    f"{interconnect}_{pvt}"
    for interconnect in ("nom", "min", "max")
    for pvt in ("tt_025C_5v00", "ss_125C_4v50", "ff_n40C_5v50")
)
WARNING_MARKERS = {
    "lint": "Lint warnings found",
    "duplicate_lib": "STA-1140",
    "floating_net": "RSZ-0020",
    "lef58_enclosure": "DRT-0349",
    "missing_vsrc": "VSRC_LOC_FILES",
    "wire_length_threshold": "Threshold for Threshold-surpassing",
    "pad_site": "ODB-0186",
    "pdn_distance": "Overriding minimum distance",
}


def fail(message: str) -> None:
    raise SystemExit(f"digital-pnr-smoke: {message}")


def load_metrics(path: Path, label: str) -> dict:
    metrics = json.loads(path.read_text())
    for key in ZERO_METRICS:
        if metrics.get(key) != 0:
            fail(f"{label} metric {key}={metrics.get(key)!r}")
    for corner in CORNERS:
        for prefix in ("timing__setup_vio__count", "timing__hold_vio__count"):
            key = f"{prefix}__corner:{corner}"
            if metrics.get(key) != 0:
                fail(f"{label} metric {key}={metrics.get(key)!r}")
    return metrics


def warning_counts(path: Path, label: str) -> dict:
    counts = {key: 0 for key in WARNING_MARKERS}
    unknown = []
    for line in filter(None, map(str.strip, path.read_text().splitlines())):
        matches = [key for key, marker in WARNING_MARKERS.items() if marker in line]
        if not matches:
            unknown.append(line)
        for key in matches:
            counts[key] += 1
    if unknown:
        fail(f"{label} unexpected warnings: {' | '.join(unknown[:5])}")
    return counts


def digest(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"missing artifact {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(metrics: dict, warnings: dict) -> dict:
    return {
        "instances": metrics["design__instance__count__stdcell"],
        "die_area_um2": metrics["design__die__area"],
        "wirelength_um": metrics["route__wirelength"],
        "setup_slack_ns": metrics["timing__setup__ws"],
        "hold_slack_ns": metrics["timing__hold__ws"],
        "warnings": warnings,
    }


def independent_atpg(work: Path, netlist_hash: str) -> dict:
    bench = (work / "counter.atpg.bench").read_text()
    source_match = re.search(r"^# source_sha256=([0-9a-f]{64})$", bench, re.MULTILINE)
    if source_match is None or source_match.group(1) != netlist_hash:
        fail("ATPG model source identity")
    if bench.count(" = DFF(") != 4:
        fail("ATPG model scan-cell count")

    generation = (work / "quaigh-atpg.log").read_text()
    analysis_match = re.search(
        r"Analyzing network with (\d+) inputs, (\d+) outputs, (\d+) gates, "
        r"(\d+) possible faults, (\d+) unique faults",
        generation,
    )
    coverage_match = re.search(
        r"Kept (\d+) patterns, detecting (\d+)/(\d+) faults \(100\.00% coverage\)",
        generation,
    )
    if "Exposing flip-flops for a sequential network" not in generation:
        fail("ATPG did not expose the scan state")
    if analysis_match is None or coverage_match is None:
        fail("ATPG generation report")
    inputs, outputs, gates, possible, unique = map(int, analysis_match.groups())
    patterns, detected, covered = map(int, coverage_match.groups())
    if (
        inputs != 5
        or outputs != 9
        or gates < 12
        or possible < unique
        or unique < 16
        or detected != covered
        or covered != unique
        or patterns < 1
    ):
        fail("ATPG generation coverage")

    pattern_lines = []
    for line in (work / "quaigh-patterns.test").read_text().splitlines():
        if line.strip() and not line.startswith("*"):
            pattern_lines.append(line.strip())
    if len(pattern_lines) != patterns:
        fail("ATPG pattern count")
    for index, line in enumerate(pattern_lines, start=1):
        match = re.fullmatch(r"(\d+):\s+([01]+)", line)
        if match is None or int(match.group(1)) != index or len(match.group(2)) != inputs:
            fail("ATPG pattern format")

    report = (work / "quaigh-atpg-report.log").read_text()
    report_match = re.search(
        r"Analyzed (\d+) patterns, detecting (\d+)/(\d+) faults \(100\.00% coverage\)",
        report,
    )
    if "Exposing flip-flops for a sequential network" not in report or report_match is None:
        fail("ATPG simulation report")
    reported_patterns, reported_detected, reported_faults = map(int, report_match.groups())
    if (reported_patterns, reported_detected, reported_faults) != (patterns, unique, unique):
        fail("ATPG simulated coverage")
    return {
        "inputs": inputs,
        "outputs": outputs,
        "gates": gates,
        "possible_faults": possible,
        "unique_faults": unique,
        "patterns": patterns,
    }


if len(sys.argv) != 2:
    fail("usage: check_results.py OUTPUT_JSON")

work = Path("/work")
ordinary_run = work / "design/runs/CANARY"
scan_run = work / "scan_design/runs/SCAN"
ordinary_final = ordinary_run / "final"
scan_final = scan_run / "final"
ordinary_metrics = load_metrics(ordinary_final / "metrics.json", "ordinary")
scan_metrics = load_metrics(scan_final / "metrics.json", "scan")
ordinary_warnings = warning_counts(ordinary_run / "warning.log", "ordinary")
scan_warnings = warning_counts(scan_run / "warning.log", "scan")
faults = json.loads((work / "stuck-at.json").read_text())
if faults["detected"] != faults["faults"] or faults["faults"] < 16:
    fail("stuck-at coverage")
atpg = independent_atpg(work, faults["netlist_sha256"])
transitions = json.loads((work / "transition-fault.json").read_text())
if (
    transitions["detected"] != transitions["faults"]
    or transitions["faults"] != 2 * len(transitions["sites"])
    or transitions["sites"] != faults["sites"]
    or transitions["netlist_sha256"] != faults["netlist_sha256"]
    or transitions["pattern_ids"] != {"reset_assert": 16, "reset_deassert": 17}
    or any(not 0 <= pattern <= 17 for pattern in transitions["patterns"].values())
):
    fail("transition-fault coverage")
equivalence_log = (work / "scan-equivalence.log").read_text()
if "Equivalence successfully proven!" not in equivalence_log:
    fail("scan functional equivalence")

if "powered gate simulation: PASS" not in (work / "gate-simulation.log").read_text():
    fail("ordinary powered gate simulation")
if "stitched scan simulation: PASS" not in (work / "scan-simulation.log").read_text():
    fail("stitched scan simulation")
if "stitched scan simulation: PASS" not in (work / "scan-physical-simulation.log").read_text():
    fail("physical scan simulation")

dft_log = (work / "dft-probe.log").read_text()
dft_netlist = (work / "counter.scan-stitched.v").read_text()
if "Number of chains: 1" not in dft_log or "has 4 cells (4 bits)" not in dft_log:
    fail("DFT plan is not one four-bit chain")
if dft_netlist.count("gf180mcu_fd_sc_mcu7t5v0__sdffq_1") != 4:
    fail("DFT netlist scan-cell count")
if "gf180mcu_fd_sc_mcu7t5v0__dffq_1" in dft_netlist or " assign " in dft_netlist:
    fail("DFT netlist normalization")
for port in ("scan_enable_0", "scan_in_0", "scan_out_0"):
    if f" {port};" not in dft_netlist:
        fail(f"DFT netlist port {port}")

artifacts = {
    "ordinary_gds": ordinary_final / "gds/counter.gds",
    "ordinary_powered_netlist": ordinary_final / "pnl/counter.pnl.v",
    "ordinary_spef": ordinary_final / "spef/nom/counter.nom.spef",
    "ordinary_spice": ordinary_final / "spice/counter.spice",
    "scan_input_netlist": work / "counter.scan-stitched.v",
    "scan_gds": scan_final / "gds/counter.gds",
    "scan_powered_netlist": scan_final / "pnl/counter.pnl.v",
    "scan_spef": scan_final / "spef/nom/counter.nom.spef",
    "scan_spice": scan_final / "spice/counter.spice",
    "scan_equivalence": work / "scan-equivalence.log",
    "stuck_at": work / "stuck-at.json",
    "transition_fault": work / "transition-fault.json",
    "independent_atpg_model": work / "counter.atpg.bench",
    "independent_atpg_patterns": work / "quaigh-patterns.test",
    "independent_atpg_generation": work / "quaigh-atpg.log",
    "independent_atpg_simulation": work / "quaigh-atpg-report.log",
}
result = {
    "schema_version": 3,
    "result": "pass_with_limitations",
    "start_time_utc": os.environ["RUN_START_UTC"],
    "end_time_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "checks": {
        "ordinary_rtl_to_gds": "pass",
        "scan_insert": "pass",
        "scan_functional_equivalence": "pass",
        "scan_shift": "pass",
        "scan_rtl_to_gds": "pass",
        "stuck_at": "pass",
        "transition_fault": "pass",
        "independent_atpg": "pass",
    },
    "corners": list(CORNERS),
    "observed": {
        "scan_equivalence_points": 4,
        "ordinary": summary(ordinary_metrics, ordinary_warnings),
        "scan": summary(scan_metrics, scan_warnings),
        "stuck_at_faults": faults["faults"],
        "stuck_at_sites": len(faults["sites"]),
        "stuck_at_patterns": faults["patterns"],
        "transition_faults": transitions["faults"],
        "transition_patterns": transitions["patterns"],
        "independent_atpg": atpg,
    },
    "artifacts": {key: digest(path) for key, path in artifacts.items()},
    "limitations": [
        "generic_counter_only",
        "public_pdk_not_fabrication_qualified",
        "core_only_no_pads",
        "no_package_vsrc_model",
        "no_sdf_or_at_speed_transition_delay",
        "no_project_rtl",
    ],
}
Path(sys.argv[1]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print("digital-pnr-smoke: ordinary and scan physical flows PASS")
