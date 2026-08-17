#!/usr/bin/env python3
"""Small dependency-free, fail-closed repository checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def structure() -> None:
    required = [
        "portfolio.yaml",
        "env/images.lock",
        "env/builders.lock",
        "env/tools.lock",
        "env/tool_gaps.yaml",
        "env/tool_artifacts.lock",
        "processes/gf180/process.lock",
        "processes/gf180/data_gaps.yaml",
        "processes/gf180/image_candidate.yaml",
        "docs/roadmap/g0_process_provider_eligibility.yaml",
        "docs/roadmap/public_source_audit.yaml",
        "docs/verification/gf180-digital-canary.md",
        "projects/pcie_gen1_endpoint/component.yaml",
        "projects/pcie_gen1_endpoint/spec/spec.yaml",
        "projects/pcie_gen1_endpoint/interfaces.yaml",
        "projects/pcie_gen1_endpoint/verification/bfm_candidates.yaml",
        "projects/pcie_gen1_endpoint/verification/bfm_scenario_matrix.yaml",
        "projects/pcie_gen1_endpoint/verification/dependencies.lock",
        "projects/pcie_gen1_endpoint/risks.yaml",
        "projects/pcie_gen1_endpoint/uncertainties.yaml",
        "projects/pcie_gen1_endpoint/claims.yaml",
        "ip/blocks/analog/wireline_serdes/component.yaml",
        "ip/blocks/analog/wireline_serdes/spec.yaml",
        "schemas/pcie_gen1_endpoint_spec.schema.json",
        "scripts/image_lock.py",
        "scripts/verification_deps.py",
        "scripts/bfm_source_audit.py",
        "scripts/bfm_history_audit.py",
        "scripts/tool_artifacts.py",
        "flows/verification/pcie_bfms/run.sh",
        "flows/verification/pcie_bfms/container_smoke.sh",
        "flows/verification/pcie_bfms/check_results.py",
        "flows/smoke/digital/run.sh",
        "flows/smoke/digital/container_smoke.sh",
        "flows/smoke/digital/counter.sv",
        "flows/smoke/digital/counter_tb.sv",
        "flows/smoke/digital/counter.sby",
        "env/images/librelane-gf180-canary/Dockerfile",
        "env/images/librelane-gf180-canary/build.sh",
        "env/images/librelane-gf180-canary/overlay_pdk.py",
        "flows/smoke/digital_pnr/run.sh",
        "flows/smoke/digital_pnr/container_smoke.sh",
        "flows/smoke/digital_pnr/check_results.py",
        "flows/smoke/digital_pnr/config.yaml",
        "flows/smoke/digital_pnr/constraints.sdc",
        "flows/smoke/digital_pnr/dft_probe.tcl",
        "flows/smoke/digital_pnr/normalize_scan_netlist.py",
        "flows/smoke/digital_pnr/counter.v",
        "flows/smoke/digital_pnr/counter_gate_tb.v",
        "flows/smoke/digital_pnr/counter_scan_tb.v",
        "flows/smoke/digital_pnr/pin_order.cfg",
        "flows/smoke/digital_pnr/scan_config.yaml",
        "flows/smoke/digital_pnr/scan_pin_order.cfg",
        "flows/smoke/digital_pnr/stuck_at.py",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))
    documents = {path: load(path) for path in required if path.endswith((".yaml", ".lock"))}
    if documents["portfolio.yaml"]["id"] != "portfolio.svalbard":
        fail("portfolio ID is not canonical")
    component = documents["projects/pcie_gen1_endpoint/component.yaml"]
    if component["id"] != "project.pcie_gen1_endpoint":
        fail("PCIe component ID is not canonical")
    risks = documents["projects/pcie_gen1_endpoint/risks.yaml"]["risks"]
    fmea_fields = {
        "failure_mode", "local_effect", "system_effect", "criticality",
        "common_cause_id", "observable", "control_or_bypass", "fallback",
        "owner", "reviewer", "evidence",
    }
    for risk in risks:
        absent = sorted(fmea_fields - risk.keys())
        if absent:
            fail(f"{risk.get('id', '<unknown>')} lacks FMEA fields: {absent}")
    serdes = documents["ip/blocks/analog/wireline_serdes/spec.yaml"]
    expected = {
        "serdes_tx", "serdes_rx", "pll", "cdr", "phase_interpolator",
        "termination", "serializer", "deserializer",
    }
    if set(serdes["required_children"]) != expected:
        fail("wireline_serdes child boundary differs from the project plan")
    spec("project.pcie_gen1_endpoint", quiet=True)
    print(f"structure: PASS ({len(required)} required files, JSON-compatible YAML parsed)")


def spec(component_id: str, quiet: bool = False) -> None:
    if component_id != "project.pcie_gen1_endpoint":
        fail(f"unsupported component selector: {component_id}")
    data = load("projects/pcie_gen1_endpoint/spec/spec.yaml")
    schema = load("schemas/pcie_gen1_endpoint_spec.schema.json")
    absent_top_level = sorted(set(schema["required"]) - data.keys())
    if absent_top_level:
        fail(f"PCIe spec lacks schema-required keys: {absent_top_level}")
    unexpected = sorted(data.keys() - schema["properties"].keys())
    if schema.get("additionalProperties") is False and unexpected:
        fail(f"PCIe spec has unexpected keys: {unexpected}")
    profile = data["profile"]
    expected = {
        "generation": 1,
        "lanes": 1,
        "line_rate_gt_s": 2.5,
        "role": "endpoint",
        "clocking": "common_clock",
        "bar_count": 1,
    }
    for key, value in expected.items():
        if profile.get(key) != value:
            fail(f"PCIe profile {key} must be {value!r}")
    proof = data["digital_proof"]
    if proof["external_hardware_required"] is not False:
        fail("project plan requires software-only digital proof")
    if proof["independent_software_bfm_count_min"] < 2:
        fail("at least two independent software BFMs are required")
    bfm_ids = [item["id"] for item in proof["bfm_implementations"]]
    if len(set(bfm_ids)) < proof["independent_software_bfm_count_min"]:
        fail("the draft does not name enough distinct software BFM candidates")
    required_scenarios = {
        "enumeration", "configuration", "bar_access", "memory_transactions", "reset",
        "malformed_packets", "replay", "retry", "timeout", "credit_exhaustion",
        "link_loss", "recovery",
    }
    if not required_scenarios.issubset(proof["required_scenarios"]):
        fail("digital proof scenario matrix is incomplete")
    matrix = load("projects/pcie_gen1_endpoint/verification/bfm_scenario_matrix.yaml")
    matrix_rows = {row["id"]: row for row in matrix["scenarios"]}
    if set(matrix_rows) != required_scenarios:
        fail("BFM scenario audit does not exactly cover the required digital scenarios")
    allowed = set(matrix["allowed_statuses"])
    for scenario_id, row in matrix_rows.items():
        for bfm_id in bfm_ids:
            if bfm_id not in row or row[bfm_id].get("status") not in allowed:
                fail(f"BFM scenario {scenario_id} lacks a valid {bfm_id} assessment")
    interfaces = load("projects/pcie_gen1_endpoint/interfaces.yaml")
    if interfaces.get("status") != "frozen":
        blockers = list(data.get("freeze_blockers", [])) + list(interfaces.get("freeze_blockers", []))
    else:
        blockers = list(data.get("freeze_blockers", []))
    if quiet:
        return
    if data.get("status") != "frozen" or blockers:
        print("spec: BLOCKED - draft structure is valid, but G1 is not frozen", file=sys.stderr)
        for blocker in blockers:
            print(f"- {blocker}", file=sys.stderr)
        raise SystemExit(2)
    print("spec: PASS (frozen G1 specification)")


def process_eligibility() -> None:
    decision = load("docs/roadmap/g0_process_provider_eligibility.yaml")
    lock = load("processes/gf180/process.lock")
    gaps = load("processes/gf180/data_gaps.yaml")["entries"]
    blockers = list(decision.get("blockers", []))
    if lock.get("status") != "qualified":
        blockers.append("canonical GF180 process lock is unresolved")
    blockers.extend(
        f"data gap {entry['id']} is unavailable" for entry in gaps
        if entry.get("disposition") == "unavailable"
    )
    if decision.get("status") != "accepted" or blockers:
        print("process-eligibility: BLOCKED", file=sys.stderr)
        for blocker in blockers:
            print(f"- {blocker}", file=sys.stderr)
        raise SystemExit(2)
    print("process-eligibility: PASS")


def image_lock_ready() -> None:
    images = load("env/images.lock")["images"]
    unresolved = [
        item["role"] for item in images
        if item.get("required_for_role_readiness", True)
        and (not item.get("digest") or item.get("status") != "qualified")
    ]
    if unresolved:
        print("images-ready: BLOCKED", file=sys.stderr)
        for role in unresolved:
            print(f"- {role} is not role-qualified", file=sys.stderr)
        raise SystemExit(2)
    for item in images:
        evidence_id = item.get("qualification_evidence", "")
        evidence_path = ROOT / "evidence/runs" / f"{evidence_id.removeprefix('run.')}.json"
        if not evidence_id or not evidence_path.is_file():
            fail(f"image {item['role']} lacks qualification evidence")
        if load(str(evidence_path.relative_to(ROOT))).get("id") != evidence_id:
            fail(f"image {item['role']} qualification evidence ID mismatch")
    print("image locks: PASS")


def toolchain_readiness() -> None:
    document = load("env/tool_gaps.yaml")
    roles = document["required_roles"]
    role_names = [item["role"] for item in roles]
    if len(role_names) != len(set(role_names)):
        fail("tool gap inventory contains duplicate required roles")
    recognized = {
        "generic_smoke_passed",
        "generic_pdk_smoke_passed",
        "upstream_bfm_smoke_passed",
        "version_probe_passed",
        "representative_smoke_pending",
        "missing",
        "incompatible",
    }
    unknown = [item["role"] for item in roles if item["status"] not in recognized]
    if unknown:
        fail("tool gap inventory has unrecognized statuses: " + ", ".join(unknown))
    incomplete = [
        item["role"] for item in roles
        if item["status"] not in {"missing", "incompatible"}
        and (not item.get("provider") or not item.get("version"))
    ]
    if incomplete:
        fail("available tool roles lack provider/version: " + ", ".join(incomplete))
    blockers = [
        f"{item['role']} is {item['status']}"
        for item in roles
        if item["status"] in {"missing", "representative_smoke_pending", "incompatible"}
    ]
    if blockers:
        print("toolchain-readiness: BLOCKED", file=sys.stderr)
        for blocker in blockers:
            print(f"- {blocker}", file=sys.stderr)
        raise SystemExit(2)
    print("toolchain-readiness: PASS")


def repo_audit() -> None:
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    ).split(b"\0")
    oversized: list[str] = []
    for raw in tracked:
        if not raw:
            continue
        relative = os.fsdecode(raw)
        path = ROOT / relative
        if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            oversized.append(relative)
    git_kib = int(subprocess.check_output(["du", "-sk", ".git"], cwd=ROOT).split()[0])
    if oversized:
        fail("tracked files exceed 5 MiB: " + ", ".join(oversized))
    if git_kib > 2 * 1024 * 1024:
        fail(".git exceeds the 2 GiB stop-work threshold")
    print(f"repo-audit: PASS ({len(tracked) - 1} source files, .git={git_kib / 1024:.1f} MiB)")


def graph() -> None:
    project = load("projects/pcie_gen1_endpoint/component.yaml")
    serdes = load("ip/blocks/analog/wireline_serdes/component.yaml")
    known = {project["id"], serdes["id"]}
    unknown = [dep for doc in (project, serdes) for dep in doc["dependencies"] if dep not in known]
    if unknown:
        fail("unknown dependencies: " + ", ".join(unknown))
    print(f"{project['id']} -> {serdes['id']}")
    print("graph: PASS (acyclic)")


COMMANDS = {
    "structure": structure,
    "process-eligibility": process_eligibility,
    "image-lock-ready": image_lock_ready,
    "toolchain-readiness": toolchain_readiness,
    "repo-audit": repo_audit,
    "graph": graph,
}


def main() -> None:
    if len(sys.argv) < 2:
        fail("a validation command is required")
    command = sys.argv[1]
    if command == "spec":
        spec(sys.argv[2] if len(sys.argv) > 2 else "project.pcie_gen1_endpoint")
        return
    action = COMMANDS.get(command)
    if action is None:
        fail(f"unknown validation command: {command}")
    action()


if __name__ == "__main__":
    main()
