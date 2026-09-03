#!/usr/bin/env python3
"""Validate the directed sixteen-thread image against the frozen emulator."""

import json
import lzma
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path("/app/input_files") if Path("/app/input_files/oracle").is_dir() else ROOT / "environment/input_files"
TESTS = Path("/tests") if Path("/tests/assets").is_dir() else ROOT / "tests"


def record(output: str, prefix: str):
    return json.loads(next(line.removeprefix(prefix) for line in output.splitlines() if line.startswith(prefix)))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lnp64-smp-oracle-") as temporary:
        work = Path(temporary)
        emulator = INPUT / "oracle/lnp64-emulator-aarch64"
        if not emulator.is_file():
            emulator = work / "lnp64-emulator"
            with lzma.open(INPUT / "oracle/lnp64-emulator-aarch64.xz", "rb") as source:
                emulator.write_bytes(source.read())
            emulator.chmod(0o500)
        text, data = work / "smp.hex", work / "smp.data.hex"
        subprocess.run([str(emulator), "asm-flat-exec", str(TESTS / "assets/smp_smoke.s"),
                        "-o", str(text), "--data-hex", str(data)], check=True)
        for profile in ("soc", "bare", "hosted-dev"):
            run = subprocess.run([str(emulator), "run-flat-exec", "--profile", profile,
                                  str(text), "--data-hex", str(data)],
                                 check=True, capture_output=True, text=True)
            final = record(run.stdout, "EMULATOR_FINAL ")
            retired = record(run.stdout, "EMULATOR_RETIRE ")
            assert final["exit"] == 0 and final["data0"] == 15
            assert (final["r3"], final["r4"], final["r5"], final["env_page"]) == (15, 15, 256, 15)
            assert len({row["tid"] for row in retired}) == 16
    print("SMP oracle: PASS (16 threads, 3 profiles)")


if __name__ == "__main__":
    main()
