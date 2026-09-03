#!/usr/bin/env python3
"""Validate the frozen ISA denominator, reference report, and image archive."""

from __future__ import annotations

import hashlib
import json
import lzma
import tarfile
from pathlib import Path, PurePosixPath

LOCAL_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path("/tests") if Path("/tests/assets").is_dir() else LOCAL_ROOT / "tests"
INPUT = Path("/app/input_files") if Path("/app/input_files/spec").is_dir() else LOCAL_ROOT / "environment/input_files"
CONTRACT = INPUT / "contract"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def denominator(spec: dict) -> tuple[int, int]:
    dark = {"cap.weaken", "cap.upgrade", "window.faultable"}
    typed = {name for name, row in spec["typed_operation_schemas"].items() if "encoding" in row}
    typed_opcodes = {number(spec["typed_operation_schemas"][name]["encoding"]["opcode"]) for name in typed}
    amo_opcode = number(spec["opcode_map"]["opcodes"]["amo"])
    vector_opcodes = {number(opcode) for opcode in spec["vector"]["families"]}
    primary = sum(
        number(opcode) not in typed_opcodes | vector_opcodes | {amo_opcode}
        for opcode in spec["opcode_map"]["opcodes"].values()
    )
    total = len(typed) + len(spec["amo_funcs"]["assigned"]) + sum(
        len(family["funcs"]) for family in spec["vector"]["families"].values()
    ) + primary
    return total - len(dark), len(dark)


def main() -> None:
    lock = json.loads((CONTRACT / "source_lock.json").read_text())
    paths = {
        "lnp64_isa_sha256": INPUT / "spec/lnp64_isa.md",
        "isa_spec_sha256": INPUT / "spec/isa_spec.json",
        "reference_report_sha256": TEST_ROOT / "assets/isa_conformance_report.json",
        "image_archive_sha256": INPUT / "tests/all_instruction_images.tar.xz",
        "source_archive_sha256": INPUT / "tests/all_instruction_sources.tar.xz",
        "emulator_archive_sha256": INPUT / "oracle/lnp64-emulator-aarch64.xz",
    }
    for field, path in paths.items():
        assert sha256(path) == lock[field], f"{field} mismatch"
    emulator = lzma.decompress(paths["emulator_archive_sha256"].read_bytes())
    assert hashlib.sha256(emulator).hexdigest() == lock["emulator_sha256"]

    spec = json.loads(paths["isa_spec_sha256"].read_text())
    assert denominator(spec) == (619, 3)
    assert spec["rights_bits"]["21"] == "STATE"
    assert spec["rights_bits"]["23"] == "INSPECT"
    assert spec["rights_bits"]["reserved"] == "[31:24] reserved-zero"
    assert lock["isa_spec_upstream_sha256"] != lock["isa_spec_sha256"]
    report = json.loads(paths["reference_report_sha256"].read_text())
    assert report["denominator"] == {"supported": 619, "assigned_dark": 3, "total_assigned": 622}
    assert report["coverage"] == {
        "supported": 619, "assigned_dark": 3, "missing_supported": 0,
        "unexpected": 0, "outcome_failures": 0, "semantically_asserted": 619,
        "semantic_missing": 0, "semantic_failures": 0,
    }
    assert report["launch_profiles"] == ["soc", "bare", "hosted-dev"]
    assert report["profile_reports_identical"] is True
    assert all("mem_checksum" not in row.get("architectural_result", {}) for row in report["cases"])
    assert "removed the legacy mem_checksum" in lock["reference_report_normalization"]

    archive = paths["image_archive_sha256"]
    digest = hashlib.sha256()
    with tarfile.open(archive, "r:xz") as tar:
        assert all(safe_member(member.name) for member in tar.getmembers())
        members = sorted(
            (m for m in tar.getmembers() if m.isfile() and m.name.endswith((".hex", ".data.hex"))),
            key=lambda member: Path(member.name).name,
        )
        for member in members:
            name = Path(member.name).name
            data = tar.extractfile(member).read()
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
    expected = report["shared_image_set"]
    assert len(members) == expected["count"] == 918
    names = {Path(member.name).name for member in members}
    programs = {name.removesuffix(".hex") for name in names if not name.endswith(".data.hex")}
    data_images = {name.removesuffix(".data.hex") for name in names if name.endswith(".data.hex")}
    assert programs == data_images and len(programs) == 459
    assert digest.hexdigest() == expected["sha256"]

    with tarfile.open(paths["source_archive_sha256"], "r:xz") as tar:
        assert all(safe_member(member.name) for member in tar.getmembers())
        sources = [member for member in tar.getmembers() if member.isfile()]
        assert len(sources) == 27 and all(member.name.endswith(".s") for member in sources)
    print("ISA bundle: PASS (619 active, 3 assigned-dark, 459 program/data pairs)")


if __name__ == "__main__":
    main()
