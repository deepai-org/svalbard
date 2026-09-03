#!/usr/bin/env python3
"""Deterministic safety and identity gates for a candidate directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parents[2]
PDK_LOCK = BENCH_ROOT / "pdk.lock.json"
BENCHMARK_PROFILE = BENCH_ROOT / "benchmark_profile.json"
ALLOWED_ROOTS = {"rtl", "analog", "integration", "layout"}
ALLOWED_SUFFIXES = {".sv", ".svh", ".v", ".vh", ".spice", ".cir", ".json", ".gds"}
REQUIRED = {
    "rtl/gigabit_ethernet_port_pkg.sv",
    "rtl/gigabit_ethernet_port.sv",
    "analog/gigabit_ethernet_phy.spice",
    "integration/port_manifest.json",
}
FORBIDDEN_TEXT = (
    re.compile(r"\$system\b", re.IGNORECASE),
    re.compile(r"\bDPI-C\b", re.IGNORECASE),
    re.compile(r"(?:^|\s)\.include\s+[\"']?/", re.IGNORECASE | re.MULTILINE),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(output: Path) -> dict[str, object]:
    errors: list[str] = []
    if not output.is_dir() or output.is_symlink():
        return {"passed": False, "errors": ["output must be a real directory"]}

    files = [path for path in output.rglob("*") if not path.is_dir()]
    if len(files) > 512:
        errors.append("candidate contains more than 512 files")
    total = 0
    relative_files: set[str] = set()
    for path in files:
        rel = path.relative_to(output)
        relative_files.add(rel.as_posix())
        if path.is_symlink() or not path.is_file():
            errors.append(f"non-regular candidate file: {rel}")
            continue
        if not rel.parts or rel.parts[0] not in ALLOWED_ROOTS:
            errors.append(f"file outside allowed candidate roots: {rel}")
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            errors.append(f"unsupported candidate suffix: {rel}")
        total += path.stat().st_size
        if path.suffix.lower() != ".gds":
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                errors.append(f"non-UTF-8 text candidate file: {rel}")
                continue
            if "\x00" in text or any(pattern.search(text) for pattern in FORBIDDEN_TEXT):
                errors.append(f"forbidden construct in: {rel}")
    if total > 256 * 1024 * 1024:
        errors.append("candidate exceeds 256 MiB package limit")

    for missing in sorted(REQUIRED - relative_files):
        errors.append(f"missing required file: {missing}")

    manifest_path = output / "integration/port_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append("integration manifest is not valid JSON")
        else:
            expected_hash = sha256(PDK_LOCK)
            expected = {
                "schema_version": 1,
                "top_rtl": "gigabit_ethernet_port",
                "phy_subckt": "gigabit_ethernet_phy",
                "line_rate_baud": 1_250_000_000,
                "pdk": "GF180MCU/gf180mcuD",
                "pdk_lock_sha256": expected_hash,
                "benchmark_profile_sha256": sha256(BENCHMARK_PROFILE),
                "claim_limit": "benchmark simulation contract only; not standards compliance",
            }
            for key, value in expected.items():
                if manifest.get(key) != value:
                    errors.append(f"manifest identity mismatch: {key}")

    return {
        "passed": not errors,
        "complete_physical_submission": "layout/gigabit_ethernet_port.gds" in relative_files,
        "file_count": len(files),
        "total_bytes": total,
        "errors": errors,
    }


def selftest() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        result = validate(root)
        assert not result["passed"] and len(result["errors"]) == len(REQUIRED)
        (root / "rtl").mkdir()
        unsafe = root / "rtl/unsafe.sv"
        unsafe.write_text("initial $system(\"bad\");\n", encoding="utf-8")
        result = validate(root)
        assert any("forbidden construct" in error for error in result["errors"])
    print("candidate safety self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if args.output is None:
        parser.error("--output is required unless --selftest is used")
    result = validate(args.output.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
