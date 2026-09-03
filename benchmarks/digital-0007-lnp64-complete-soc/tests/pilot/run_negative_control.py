#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MINI = ROOT / "solution/mini_candidate"


def check_safety_mutations() -> None:
    snippets = (
        'initial $readmemh("/tests/answer.hex", memory);',
        'initial begin $display("PCIE_ROOT_PASS\\nPCIE_SOC_PASS"); $finish; end',
        '`ifdef VERILATOR\nwire simulation_only = 1\'b1;\n`endif',
        '// synthesis translate_off\nwire simulation_only = 1\'b1;\n// synthesis translate_on',
    )
    with tempfile.TemporaryDirectory(prefix="lnp64-safety-") as temporary:
        candidate = Path(temporary) / "candidate"
        for snippet in snippets:
            shutil.copytree(MINI, candidate)
            (candidate / "rtl/attack.sv").write_text(f"module attack; {snippet} endmodule\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "tests/gating/candidate_safety.py"), str(candidate)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                raise SystemExit("candidate safety accepted a simulator-dependent mutation")
            shutil.rmtree(candidate)
        shutil.copytree(MINI, candidate)
        package = candidate / "rtl/lnp64_soc_pkg.sv"
        package.write_text(package.read_text().replace("VLEN = 512", "VLEN = 256"))
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/gating/candidate_safety.py"), str(candidate)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            raise SystemExit("candidate safety accepted a modified interface package")


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "tests/gating/candidate_safety.py"), str(MINI)], check=True)
    check_safety_mutations()
    subprocess.run(
        [sys.executable, str(ROOT / "environment/input_files/test_visible/run_visible.py")],
        check=True,
        env={**os.environ, "OUTPUT": str(MINI)},
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests/gating/run_boot_adapter.py"), str(MINI)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0 or "UART invalid-image gate: PASS" not in result.stdout:
        print(result.stdout, end="")
        raise SystemExit("invalid-image boundary fixture did not pass its intended contract")
    jtag = subprocess.run(
        [sys.executable, str(ROOT / "tests/gating/run_jtag_adapter.py"), str(MINI)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if jtag.returncode != 0 or "JTAG architectural adapter: PASS" not in jtag.stdout:
        print(jtag.stdout, end="")
        raise SystemExit("JTAG boundary fixture did not pass its intended positive contract")
    platform = subprocess.run(
        [sys.executable, str(ROOT / "tests/gating/run_platform_adapter.py"), str(MINI)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if platform.returncode != 0 or "UART boot and SDRAM integration: PASS" not in platform.stdout:
        print(platform.stdout, end="")
        raise SystemExit("platform boundary fixture did not pass its intended positive contract")
    sdhc = subprocess.run(
        [sys.executable, str(ROOT / "tests/gating/run_sdhc_adapter.py"), str(MINI)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if sdhc.returncode == 0 or "valid SDHC image did not boot" not in sdhc.stdout:
        print(sdhc.stdout, end="")
        raise SystemExit("negative control was not rejected by the SDHC boot test")
    isa = subprocess.run(
        [sys.executable, str(ROOT / "tests/gating/run_isa_adapter.py"), str(MINI), "--case-limit", "1"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if isa.returncode == 0 or "stop cause" not in isa.stdout:
        print(isa.stdout, end="")
        raise SystemExit("negative control was not rejected by the ISA oracle")
    print("mini candidate: boundary fixtures PASS; ISA and SDHC gates REJECTED as intended")


if __name__ == "__main__":
    main()
