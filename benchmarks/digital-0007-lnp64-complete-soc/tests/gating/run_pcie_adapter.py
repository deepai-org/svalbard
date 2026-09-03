#!/usr/bin/env python3
"""Run PCIe Gen1 PIPE, BAR/MSI, bidirectional DMA, and IOMMU-revocation tests."""

from __future__ import annotations

import argparse
import contextlib
import lzma
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path("/app/input_files") if Path("/app/input_files/spec").is_dir() else ROOT / "environment/input_files"
TESTS = Path("/tests") if Path("/tests/gating").is_dir() else ROOT / "tests"
PCIE_REVISION = "b82b2ff3a047f742354c9607dea34b9b97bf108c"
VPROC_REVISION = "ae80e5b5cb43d4e9f82f9d45aa3b614e053f9df4"


def source_root(environment: str, installed: str) -> Path:
    value = os.environ.get(environment)
    choices = [Path(value)] if value else []
    choices.append(Path(installed))
    for choice in choices:
        if choice.is_dir():
            return choice.resolve()
    raise SystemExit(f"missing pinned public dependency {environment}")


def verify_revision(root: Path, expected: str) -> None:
    marker = root / ".benchmark-revision"
    if marker.is_file():
        actual = marker.read_text().strip()
    elif (root / ".git").exists():
        actual = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True).stdout.strip()
    else:
        raise SystemExit(f"dependency has no revision marker: {root}")
    if actual != expected:
        raise SystemExit(f"dependency revision mismatch: {root.name} {actual}")


def candidate_rtl(candidate: Path) -> list[Path]:
    rtl = candidate / "rtl"
    package, top = rtl / "lnp64_soc_pkg.sv", rtl / "lnp64_soc.sv"
    if not package.is_file() or not top.is_file():
        raise SystemExit("candidate is missing required RTL")
    return [package, *sorted(path for path in rtl.glob("*.sv") if path not in {package, top}), top]


def run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        print(completed.stdout, end="")
        raise SystemExit(f"command failed: {' '.join(command)}")


def materialize_emulator(work: Path) -> Path:
    emulator = INPUT / "oracle/lnp64-emulator-aarch64"
    if emulator.is_file():
        return emulator
    local = work / "lnp64-emulator"
    with lzma.open(emulator.with_suffix(".xz"), "rb") as source:
        local.write_bytes(source.read())
    local.chmod(0o500)
    return local


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path, nargs="?")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--oracle-selftest", action="store_true")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    if not (args.oracle_selftest or args.check_only) and args.candidate is None:
        parser.error("candidate is required unless a self-check mode is used")
    candidate = args.candidate.resolve() if args.candidate is not None else None

    pcievhost = source_root("PCIEVHOST_ROOT", "/opt/pcievhost")
    vproc = source_root("VPROC_ROOT", "/opt/vproc")
    verify_revision(pcievhost, PCIE_REVISION)
    verify_revision(vproc, VPROC_REVISION)
    required = [
        pcievhost / "src/pcieModelClass.h",
        pcievhost / "verilog/headers/pcie_vhost_map.v",
        pcievhost / "verilog/pcieVHost/pcieVHostPipex1.v",
        vproc / "f_VProc.v",
        TESTS / "gating/pcie_root.cpp",
        TESTS / "gating/tb_pcie_candidate.sv",
        TESTS / "gating/pcie_reference_endpoint.cpp",
        TESTS / "gating/tb_pcie_oracle.sv",
        TESTS / "assets/pcie_iommu_smoke.s",
    ]
    if any(not path.is_file() for path in required):
        raise SystemExit("PCIe verifier sources are incomplete")
    if args.check_only:
        print("PCIe adapter dependencies: PASS")
        return

    if args.work:
        work = args.work.resolve()
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        manager = contextlib.nullcontext(str(work))
    else:
        manager = tempfile.TemporaryDirectory(prefix="lnp64-pcie-")
    with manager as temporary:
        work = Path(temporary)

        pcie_library = pcievhost / "lib/libpcievhost.a"
        if not pcie_library.is_file():
            run(["make", "-f", "makefile.sysvlog", "ARCHFLAG=",
                 f"VPROC_TOP={vproc}"], cwd=pcievhost / "lib")

        vproc_obj = work / "vproc_obj"
        vproc_library = work / "libvproc.a"
        user_sources = "pcie_root.cpp pcie_reference_endpoint.cpp" if args.oracle_selftest else "pcie_root.cpp"
        nodes = "2" if args.oracle_selftest else "1"
        run([
            "make", "-f", "makefile.verilator", "ARCHFLAG=", f"MAX_NUM_VPROC={nodes}",
            f"USRFLAGS=-I{pcievhost / 'src'}", f"USRCDIR={TESTS / 'gating'}",
            f"USER_C={user_sources}", f"TESTDIR={work}", f"VOBJDIR={vproc_obj}",
            str(vproc_library),
        ], cwd=vproc / "test")

        obj = work / "obj"
        sources = [
            pcievhost / "verilog/lib/Serialiser.v",
            pcievhost / "verilog/lib/clkmux.v",
            pcievhost / "verilog/pcieVHost/pcieVHostPipex1.v",
            pcievhost / "verilog/pcieVHost/pcieVHost.v",
            vproc / "f_VProc.v",
        ]
        if args.oracle_selftest:
            sources.append(TESTS / "gating/tb_pcie_oracle.sv")
            simulation_args: list[str] = []
        else:
            assert candidate is not None
            emulator = materialize_emulator(work)
            image = work / "pcie_iommu.hex"
            data = work / "pcie_iommu.data.hex"
            run([str(emulator), "asm-flat-exec", str(TESTS / "assets/pcie_iommu_smoke.s"),
                 "-o", str(image), "--data-hex", str(data)], cwd=work)
            words = sum(1 for line in image.read_text().splitlines() if line.strip())
            sources += [*candidate_rtl(candidate), INPUT / "memory/lnp64_sram_macros.sv",
                        TESTS / "gating/tb_pcie_candidate.sv"]
            simulation_args = [f"+IMAGE={image}", f"+WORDS={words}"]
        verilator = [
            "verilator", "--binary", "-sv", "--timing", "--threads", "1",
            "-j", str(min(16, os.cpu_count() or 1)),
            "--top-module", "test", "--Mdir", str(obj), "--timescale", "1ns/1ps",
            "+define+VPROC_SV", f"+incdir+{pcievhost / 'verilog/testpipex1'}",
            f"+incdir+{pcievhost / 'verilog/headers'}", f"-I{vproc}",
            "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD", "-Wno-WIDTH",
            "-Wno-CASEINCOMPLETE", "-Wno-INITIALDLY", "-CFLAGS", "-std=c++20 -Wno-attributes",
            "-LDFLAGS", (f"-Wl,-E -lrt -rdynamic -Wl,-whole-archive {vproc_library} "
                           f"{pcie_library} -Wl,-no-whole-archive -ldl -lpthread"),
            *map(str, sources),
        ]
        run(verilator, cwd=work)
        simulation_environment = os.environ.copy()
        if args.oracle_selftest:
            simulation_environment["LNP64_PCIE_ORACLE_SELFTEST"] = "1"
        # pcievhost/VProc's two native model threads are deterministic when
        # co-scheduled on one CPU; unconstrained host scheduling exposes an
        # upstream shared-model race unrelated to candidate behavior.
        cpu = min(os.sched_getaffinity(0))
        transcript = work / "pcie-simulation.log"
        with transcript.open("w") as stream:
            simulation = subprocess.run(
                ["taskset", "-c", str(cpu), str(obj / "Vtest"), *simulation_args],
                cwd=work, text=True, stdout=stream, stderr=subprocess.STDOUT,
                timeout=3600, env=simulation_environment,
            )
        output = transcript.read_text(errors="replace")
        # Keep the useful verdict and nearby diagnostics; pcievhost's optional
        # protocol display can otherwise produce megabytes of transcript.
        expected = ["PCIE_ROOT_PASS", "PCIE_REFERENCE_ENDPOINT_PASS"] if args.oracle_selftest else ["PCIE_ROOT_PASS", "PCIE_SOC_PASS"]
        if simulation.returncode or any(marker not in output for marker in expected):
            print(f"simulation return code: {simulation.returncode}; output lines: {len(output.splitlines())}")
            for line in output.splitlines():
                if "PCIE_" in line:
                    print(line)
            print("\n".join(output.splitlines()[-300:]))
            raise SystemExit("PCIe protocol oracle: FAIL" if args.oracle_selftest else
                             "PCIe PIPE/DMA/IOMMU integration: FAIL")
        print("PCIe protocol oracle: PASS" if args.oracle_selftest else
              "PCIe PIPE/DMA/IOMMU integration: PASS")


if __name__ == "__main__":
    main()
