#!/usr/bin/env python3
"""Reduce the generic LibreLane flow to strict compact evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import sys


def fail(message: str) -> None:
    raise SystemExit(f"digital-pnr-smoke: {message}")


if len(sys.argv) != 9:
    fail("usage: check_results.py METRICS FINAL_DIR WARNING_LOG GATE_LOG DFT_LOG DFT_NETLIST SCAN_LOG OUTPUT_JSON")

(
    metrics_path,
    final_dir,
    warning_log,
    gate_log,
    dft_log,
    dft_netlist,
    scan_log,
    output_path,
) = map(Path, sys.argv[1:])
metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

required_zero = [
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
]
for key in required_zero:
    if key not in metrics or metrics[key] != 0:
        fail(f"required zero metric {key} is {metrics.get(key)!r}")

corners = [
    f"{interconnect}_{pvt}"
    for interconnect in ("nom", "min", "max")
    for pvt in ("tt_025C_5v00", "ss_125C_4v50", "ff_n40C_5v50")
]
for corner in corners:
    for prefix in ("timing__setup_vio__count", "timing__hold_vio__count"):
        key = f"{prefix}__corner:{corner}"
        if key not in metrics or metrics[key] != 0:
            fail(f"timing metric {key} is {metrics.get(key)!r}")

if "powered gate simulation: PASS" not in gate_log.read_text(encoding="utf-8"):
    fail("powered gate-level simulation did not report PASS")

dft_text = dft_netlist.read_text(encoding="utf-8")
if dft_text.count("gf180mcu_fd_sc_mcu7t5v0__sdffq_1") != 4:
    fail("OpenROAD did not replace all four flops with scan-capable cells")
if "gf180mcu_fd_sc_mcu7t5v0__dffq_1" in dft_text:
    fail("ordinary flop remains after scan replacement")
dft_log_text = dft_log.read_text(encoding="utf-8")
if "Scan chain 'chain_0'" not in dft_log_text:
    fail("OpenROAD did not report the requested single scan chain")
if "Number of chains: 1" not in dft_log_text or "has 4 cells (4 bits)" not in dft_log_text:
    fail("OpenROAD DFT plan does not contain exactly one four-bit chain")
for port in ("scan_enable_0", "scan_in_0", "scan_out_0"):
    if f" {port};" not in dft_text:
        fail(f"stitched scan netlist lacks port {port}")
if "stitched scan simulation: PASS" not in scan_log.read_text(encoding="utf-8"):
    fail("stitched scan chain did not pass structural gate simulation")

allowed_warning_markers = {
    "duplicate timing library": "STA-1140",
    "floating optimization nets": "RSZ-0020",
    "unsupported public-PDK enclosure": "DRT-0349",
    "missing package source locations": "VSRC_LOC_FILES",
    "unqualified wire-length threshold": "Threshold for Threshold-surpassing",
    "public-PDK pad-site metadata": "ODB-0186",
    "PDN minimum-distance override": "Overriding minimum distance",
}
warning_lines = [
    line.strip()
    for line in warning_log.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
warning_counts = {name: 0 for name in allowed_warning_markers}
unknown_warnings = []
for line in warning_lines:
    matches = [name for name, marker in allowed_warning_markers.items() if marker in line]
    if not matches:
        unknown_warnings.append(line)
    for name in matches:
        warning_counts[name] += 1
if unknown_warnings:
    fail("unexpected warning(s): " + " | ".join(unknown_warnings[:5]))

artifacts = {
    "gds": final_dir / "gds/counter.gds",
    "klayout_gds": final_dir / "klayout_gds/counter.klayout.gds",
    "powered_netlist": final_dir / "pnl/counter.pnl.v",
    "nominal_spef": final_dir / "spef/nom/counter.nom.spef",
    "spice": final_dir / "spice/counter.spice",
    "scan_stitched_netlist": dft_netlist,
}
artifact_hashes = {}
for name, path in artifacts.items():
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"required final artifact is absent or empty: {path}")
    artifact_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()

result = {
    "schema_version": 1,
    "result": "pass_with_limitations",
    "start_time_utc": os.environ["RUN_START_UTC"],
    "end_time_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "final_flow_step_index": 76,
    "timing_corners_checked": corners,
    "checks": {
        "lint_synthesis_and_unmapped_cells": "pass",
        "powered_gate_level_simulation": "pass",
        "scan_cell_replacement_and_single_chain_stitching": "pass",
        "multi_corner_setup_and_hold": "pass",
        "routing_drc_and_antenna": "pass",
        "power_grid_connectivity": "pass",
        "magic_and_klayout_drc": "pass",
        "magic_klayout_xor": "pass",
        "netgen_lvs": "pass",
    },
    "observed": {
        "standard_cell_instances": metrics["design__instance__count__stdcell"],
        "die_area_um2": metrics["design__die__area"],
        "route_wirelength_um": metrics["route__wirelength"],
        "worst_setup_slack_ns": metrics["timing__setup__ws"],
        "worst_hold_slack_ns": metrics["timing__hold__ws"],
        "allowlisted_warning_counts": warning_counts,
    },
    "artifact_hashes": artifact_hashes,
    "limitations": [
        "generic four-bit counter core canary only",
        "public embedded PDK snapshot is not provider accepted or fabrication qualified",
        "pad timing libraries and pad integration are intentionally excluded",
        "IR drop has no qualified package or VSRC location model",
        "OpenROAD reports unsupported LEF58 enclosure constructs from the public PDK",
        "OpenROAD repair reports two floating optimization nets; final disconnected-pin metrics are zero",
        "scan replacement and one-chain stitching were probed after the ordinary core flow; the scan-inserted netlist was not physically re-closed",
        "no DFT coverage/ATPG, equivalence, SDF timing simulation, or project RTL was exercised",
    ],
}
output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("digital-pnr-smoke: metrics and final artifacts PASS")
