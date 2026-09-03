#!/usr/bin/env python3
"""Compile candidate RTL once and run the frozen ISA corpus through pin-level JTAG."""

from __future__ import annotations

import argparse
import json
import lzma
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path("/app/input_files") if Path("/app/input_files/spec").is_dir() else ROOT / "environment/input_files"
TESTS = Path("/tests") if Path("/tests/assets").is_dir() else ROOT / "tests"


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def image_stem(source: str, spec: dict) -> str:
    if source.startswith("tests/"):
        return PurePosixPath(source).stem
    if not source.startswith("catalog:"):
        raise ValueError(f"unknown source identity: {source}")
    operation = source.removeprefix("catalog:")
    for opcode_text, family in spec["vector"]["families"].items():
        prefix = family["name"] + "."
        if operation.startswith(prefix):
            function = operation.removeprefix(prefix)
            matches = [int(index) for index, name in family["funcs"].items() if name == function]
            if len(matches) != 1:
                raise ValueError(f"cannot map vector case: {source}")
            return f"vector-f{int(opcode_text, 0) & 0xf:x}-{matches[0]:02d}"
    return "typed-" + operation.replace(".", "-")


def write_case_manifest(path: Path, limit: int | None) -> int:
    report = json.loads((TESTS / "assets/isa_conformance_report.json").read_text())
    spec = json.loads((INPUT / "spec/isa_spec.json").read_text())
    cases = report["cases"][:limit]
    lines = ["# name\tstem\tattempted\ttransport\texit\tr3\tr4\tr5\tr6\tmem0\tdata0\terrno"]
    for row in cases:
        outcome = row["architectural_result"]
        values = [
            row["source"], image_stem(row["source"], spec), row["attempted_words"],
            outcome["result_transport"], outcome.get("exit", 0), outcome.get("r3", 0),
            outcome.get("r4", 0), outcome.get("r5", 0), outcome.get("env_page", 0),
            outcome.get("mem0", 0), outcome.get("data0", 0),
            outcome.get("errno", 0),
        ]
        lines.append("\t".join(map(str, values)))
    path.write_text("\n".join(lines) + "\n")
    return len(cases)


def materialize_emulator(work: Path) -> Path:
    executable = INPUT / "oracle/lnp64-emulator-aarch64"
    if executable.is_file():
        return executable
    archive = executable.with_suffix(".xz")
    if not archive.is_file():
        raise SystemExit("frozen LNP64 emulator is missing")
    local = work / "lnp64-emulator"
    with lzma.open(archive, "rb") as source:
        local.write_bytes(source.read())
    local.chmod(0o500)
    return local


def append_smp_case(case_file: Path, images: Path, work: Path) -> None:
    emulator = materialize_emulator(work)
    source = TESTS / "assets/smp_smoke.s"
    subprocess.run(
        [str(emulator), "asm-flat-exec", str(source), "-o", str(images / "smp-smoke.hex"),
         "--data-hex", str(images / "smp-smoke.data.hex")],
        check=True,
    )
    # Fifteen children plus the boot thread synchronize through futexes and
    # atomically produce data[0] == 15. Register values are parent snapshots.
    with case_file.open("a") as stream:
        stream.write("directed:smp-4x4\tsmp-smoke\t10000\texit\t0\t15\t15\t256\t15\t0\t15\t0\n")


def candidate_rtl(candidate: Path) -> list[Path]:
    rtl = candidate / "rtl"
    package = rtl / "lnp64_soc_pkg.sv"
    top = rtl / "lnp64_soc.sv"
    if not package.is_file() or not top.is_file():
        raise SystemExit("candidate is missing the required RTL files")
    others = sorted(path for path in rtl.glob("*.sv") if path not in {package, top})
    return [package, *others, top]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--include-smp", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.case_limit is not None and args.case_limit < 1:
        raise SystemExit("--case-limit must be positive")

    with tempfile.TemporaryDirectory(prefix="lnp64-isa-") as temporary:
        work = Path(temporary)
        images = work / "images"
        images.mkdir()
        archive = INPUT / "tests/all_instruction_images.tar.xz"
        with lzma.open(archive, "rb") as compressed, tarfile.open(fileobj=compressed, mode="r|") as tar:
            for member in tar:
                if not member.isfile() or not safe_member(member.name):
                    if not safe_member(member.name):
                        raise SystemExit("unsafe member in ISA image archive")
                    continue
                source = tar.extractfile(member)
                if source is None:
                    raise SystemExit(f"cannot read archive member {member.name}")
                (images / PurePosixPath(member.name).name).write_bytes(source.read())

        case_file = work / "cases.tsv"
        case_count = write_case_manifest(case_file, args.case_limit)
        if args.include_smp:
            append_smp_case(case_file, images, work)
            case_count += 1
        stems = {
            line.split("\t")[1] for line in case_file.read_text().splitlines()
            if line and not line.startswith("#")
        }
        missing = sorted(stem for stem in stems if not (images / f"{stem}.hex").is_file()
                         or not (images / f"{stem}.data.hex").is_file())
        if missing:
            raise SystemExit(f"ISA case/image mapping is incomplete: {missing[:3]}")
        if args.check_only:
            print(f"ISA adapter inputs: PASS ({case_count} cases)")
            return

        obj = work / "obj"
        command = [
            "verilator", "--cc", "--exe", "--build", "-j", str(min(16, os.cpu_count() or 1)),
            "--top-module", "lnp64_soc", "--Mdir", str(obj), "--timing", "--timescale", "1ns/1ps",
            "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD", "-Wno-WIDTH",
            *map(str, candidate_rtl(args.candidate)),
            str(INPUT / "memory/lnp64_sram_macros.sv"),
            str(TESTS / "gating/lnp64_jtag_isa.cpp"),
        ]
        build = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if build.returncode:
            print(build.stdout, end="")
            raise SystemExit("candidate failed Verilator compilation")
        run = subprocess.run(
            [str(obj / "Vlnp64_soc"), str(case_file), str(images)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        print(run.stdout, end="")
        if run.returncode:
            raise SystemExit(run.returncode)
        print(f"ISA adapter: PASS ({case_count} cases)")


if __name__ == "__main__":
    main()
