#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ALLOWED = {".sv", ".json"}
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 256
FORBIDDEN_RTL = (
    (re.compile(r"\b(?:bind|force|release|deassign)\b", re.IGNORECASE), "simulation override"),
    (re.compile(r"\b(?:import|export)\s+['\"]DPI(?:-C)?['\"]", re.IGNORECASE), "DPI"),
    (re.compile(r"\$(?:system|fopen|fclose|fread|fwrite|fscanf|readmem[bh]|writemem[bh]|"
                r"test\$plusargs|value\$plusargs)\b", re.IGNORECASE), "external data access"),
    (re.compile(r"\$(?:display|write|strobe|monitor|finish|stop|fatal|error|warning|info|"
                r"dumpfile|dumpvars)\b", re.IGNORECASE), "simulation control"),
    (re.compile(r"`include\s+['\"](?:/|\.\./)"), "path-escape include"),
    (re.compile(r"`ifn?def\s+(?:VERILATOR|IVERILOG|__ICARUS__|SYNTHESIS|YOSYS)\b",
                re.IGNORECASE), "tool-dependent RTL"),
    (re.compile(r"\(\*[^*]*(?:blackbox|whitebox)[^*]*\*\)", re.IGNORECASE),
     "fake implementation attribute"),
)
FORBIDDEN_RAW = re.compile(r"(?:translate_off|synthesis\s+off)", re.IGNORECASE)
LOCAL_ROOT = Path(__file__).resolve().parents[2]
INPUT = Path("/app/input_files") if Path("/app/input_files/integration").is_dir() else LOCAL_ROOT / "environment/input_files"


def mask_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", text)


def check(root: Path) -> list[str]:
    errors: list[str] = []
    required = [root / "rtl/lnp64_soc_pkg.sv", root / "rtl/lnp64_soc.sv", root / "integration/soc_manifest.json"]
    for path in required:
        if not path.is_file():
            errors.append(f"missing {path.relative_to(root)}")
    total = 0
    files = [path for path in root.rglob("*") if not path.is_dir()]
    if len(files) > MAX_FILES:
        errors.append(f"candidate exceeds {MAX_FILES} files")
    for path in files:
        if path.is_symlink():
            errors.append(f"symlink forbidden: {path.relative_to(root)}")
        elif path.is_file():
            total += path.stat().st_size
            if path.suffix not in ALLOWED:
                errors.append(f"file type forbidden: {path.relative_to(root)}")
            elif path.suffix == ".sv":
                try:
                    text = path.read_text()
                except (OSError, UnicodeDecodeError):
                    errors.append(f"RTL is not UTF-8 text: {path.relative_to(root)}")
                    continue
                if "\x00" in text:
                    errors.append(f"RTL contains NUL: {path.relative_to(root)}")
                if FORBIDDEN_RAW.search(text):
                    errors.append(f"synthesis-exclusion pragma forbidden: {path.relative_to(root)}")
                code = mask_comments(text)
                for pattern, label in FORBIDDEN_RTL:
                    if pattern.search(code):
                        errors.append(f"{label} forbidden: {path.relative_to(root)}")
                        break
        else:
            errors.append(f"non-regular file forbidden: {path.relative_to(root)}")
    if total > MAX_BYTES:
        errors.append("candidate exceeds 64 MiB")
    package = root / "rtl/lnp64_soc_pkg.sv"
    reference_package = INPUT / "rtl/lnp64_soc_pkg.sv"
    if package.is_file() and reference_package.is_file():
        try:
            if package.read_bytes() != reference_package.read_bytes():
                errors.append("rtl/lnp64_soc_pkg.sv must match the frozen interface package")
        except OSError:
            errors.append("cannot read rtl/lnp64_soc_pkg.sv")
    manifest = root / "integration/soc_manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text())
            if not isinstance(data, dict):
                errors.append("manifest must be a JSON object")
            else:
                for field, expected in (
                    ("cores", 4), ("contexts_per_core", 4), ("vlen_bits", 512),
                    ("core_clock_hz", 200000000), ("sram_clock_max_hz", 50000000),
                ):
                    if data.get(field) != expected:
                        errors.append(f"manifest {field} must equal {expected}")
                reference = INPUT / "integration/soc_manifest.json"
                if reference.is_file():
                    expected_manifest = json.loads(reference.read_text())
                    identity_fields = (
                        "top", "isa_revision", "isa_spec_sha256", "source_lock_sha256",
                        "soc_profile_sha256", "platform_devices_sha256", "pdk_lock_sha256", "boot_spec_sha256",
                        "sram_contract_sha256", "pdk", "approved_blackboxes",
                    )
                    for field in identity_fields:
                        if data.get(field) != expected_manifest[field]:
                            errors.append(f"manifest {field} does not match the frozen contract")
        except (OSError, json.JSONDecodeError):
            errors.append("manifest is invalid JSON")
    return errors


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: candidate_safety.py OUTPUT")
    failures = check(Path(sys.argv[1]))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        raise SystemExit(1)
    print("candidate safety: PASS")
