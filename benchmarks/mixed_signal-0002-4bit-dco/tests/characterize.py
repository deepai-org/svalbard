#!/usr/bin/env python3
"""Deterministic transistor-level characterization for a submitted dco4."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


PINS = ["EN", "CTRL0", "CTRL1", "CTRL2", "CTRL3", "OUT", "VDD", "VSS"]
POINTS = (("tt", "typical", 3.3, 25), ("ss", "ss", 3.0, 125), ("ff", "ff", 3.6, -40))


def parse_measures(log: str) -> dict[str, float]:
    return {
        key.lower(): float(value)
        for key, value in re.findall(r"(?m)^(\w+)\s*=\s*([-+0-9.eE]+)", log)
    }


def simulate(spice: Path, code: int, point: tuple[str, str, float, int], pdk: Path) -> dict[str, float]:
    name, model_corner, voltage, temp = point
    models = pdk / "libs.tech/ngspice/sm141064.ngspice"
    cells = pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice"
    controls = [voltage if code & (1 << bit) else 0.0 for bit in range(4)]
    with tempfile.TemporaryDirectory() as td_text:
        td = Path(td_text)
        deck, log = td / "test.spice", td / "ngspice.log"
        deck.write_text(f"""DCO characterization {name} code {code}
.param fnoicor=1 sw_stat_mismatch=0
.lib {models} {model_corner}
.include {cells}
.include {spice}
.temp {temp}
VVDD vdd 0 {voltage}
VEN en 0 PWL(0 0 20n 0 21n {voltage})
VC0 c0 0 {controls[0]}
VC1 c1 0 {controls[1]}
VC2 c2 0 {controls[2]}
VC3 c3 0 {controls[3]}
XU en c0 c1 c2 c3 out vdd 0 dco4
CLOAD out 0 20f
.option method=gear reltol=1e-3
.tran 5n 1u uic
.measure tran tstart WHEN v(out)={voltage/2} RISE=1
.measure tran tr3 WHEN v(out)={voltage/2} RISE=2
.measure tran tr8 WHEN v(out)={voltage/2} RISE=5
.measure tran thigh TRIG v(out) VAL={voltage/2} RISE=2 TARG v(out) VAL={voltage/2} FALL=2
.measure tran vmax MAX v(out) FROM=0.3u TO=1u
.measure tran vmin MIN v(out) FROM=0.3u TO=1u
.measure tran iavg AVG i(VVDD) FROM=0.3u TO=1u
.end
""")
        ngspice = shutil.which("ngspice") or "/foss/tools/bin/ngspice"
        env=os.environ.copy();env.update({"OMP_NUM_THREADS":"1","OMP_THREAD_LIMIT":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1"})
        result = subprocess.run([ngspice, "-b", "-o", log, deck], cwd=td,env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output = log.read_text(errors="replace")
        values = parse_measures(output)
        required = {"tstart", "tr3", "tr8", "thigh", "vmax", "vmin", "iavg"}
        if result.returncode or "Error:" in output or not required <= values.keys():
            raise RuntimeError(f"ngspice failed at {name} code {code}\n{output[-4000:]}")
        period = (values["tr8"] - values["tr3"]) / 3.0
        if period <= 0:
            raise RuntimeError(f"invalid period at {name} code {code}")
        return {
            "frequency_hz": 1.0 / period,
            "startup_s": values["tstart"],
            "duty": values["thigh"] / period,
            "vmax_v": values["vmax"],
            "vmin_v": values["vmin"],
            "power_w": abs(values["iavg"]) * voltage,
        }


def disabled(spice: Path, pdk: Path) -> dict[str, float]:
    models = pdk / "libs.tech/ngspice/sm141064.ngspice"
    cells = pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice"
    with tempfile.TemporaryDirectory() as td_text:
        td = Path(td_text); deck, log = td / "off.spice", td / "ngspice.log"
        deck.write_text(f"""DCO disabled test
.param fnoicor=1 sw_stat_mismatch=0
.lib {models} typical
.include {cells}
.include {spice}
VVDD vdd 0 3.3
VEN en 0 0
VC0 c0 0 3.3
VC1 c1 0 3.3
VC2 c2 0 3.3
VC3 c3 0 3.3
XU en c0 c1 c2 c3 out vdd 0 dco4
CLOAD out 0 20f
.tran 5n 1u uic
.measure tran vmax MAX v(out) FROM=0.5u TO=1u
.measure tran iavg AVG i(VVDD) FROM=0.5u TO=1u
.end
""")
        ngspice = shutil.which("ngspice") or "/foss/tools/bin/ngspice"
        env=os.environ.copy();env.update({"OMP_NUM_THREADS":"1","OMP_THREAD_LIMIT":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1"})
        result = subprocess.run([ngspice, "-b", "-o", log, deck], cwd=td,env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output = log.read_text(errors="replace"); values = parse_measures(output)
        if result.returncode or not {"vmax", "iavg"} <= values.keys():
            raise RuntimeError(f"disabled simulation failed\n{output[-4000:]}")
        return {"vmax_v": values["vmax"], "current_a": abs(values["iavg"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--tt-only", action="store_true")
    parser.add_argument("--pex-sample", action="store_true")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    spice = (args.candidate / "analog/dco4.spice").resolve()
    pdk = Path(os.environ.get("PDK_ROOT", "/foss/pdks")) / "gf180mcuD"
    if not spice.is_file() or not pdk.is_dir():
        raise SystemExit("candidate SPICE or GF180MCU PDK is missing")
    if spice.is_symlink() or spice.stat().st_size > 2_000_000:
        raise SystemExit("candidate SPICE is not a bounded regular file")
    if re.search(r"(?im)^\s*\.(control|shell|exec|include|lib)\b",spice.read_text(errors="replace")):
        raise SystemExit("candidate SPICE contains a prohibited directive")
    points = POINTS[:1] if args.tt_only else POINTS
    codes = (0, 7, 15) if args.pex_sample else tuple(range(16))
    if args.pex_sample and not args.tt_only:
        raise SystemExit("--pex-sample requires --tt-only")
    result: dict[str, object] = {"disabled": disabled(spice, pdk), "corners": {}}
    for point in points:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            measurements = list(pool.map(lambda code: simulate(spice, code, point, pdk), codes))
        result["corners"][point[0]] = measurements
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    off = result["disabled"]
    assert isinstance(off, dict)
    if off["vmax_v"] >= 0.1 or off["current_a"] >= 100e-6:
        raise SystemExit(f"disabled limits failed: {off}")
    for name, rows in result["corners"].items():
        frequencies = [row["frequency_hz"] for row in rows]
        low, high = ((5e6, 110e6) if name == "tt" else (1e6, 250e6))
        for code, row in zip(codes, rows):
            if not (low <= row["frequency_hz"] <= high and row["startup_s"] <= 5e-6):
                raise SystemExit(f"{name} code {code} frequency/startup failed: {row}")
            if not (0.40 <= row["duty"] <= 0.60 and row["vmin_v"] <= 0.1*POINTS[[p[0] for p in POINTS].index(name)][2]
                    and row["vmax_v"] >= 0.9*POINTS[[p[0] for p in POINTS].index(name)][2]):
                raise SystemExit(f"{name} code {code} output limits failed: {row}")
            if row["power_w"] >= 5e-3:
                raise SystemExit(f"{name} code {code} power failed: {row['power_w']}")
        span = max(frequencies) / min(frequencies) - 1.0
        if span < (3.0 if name == "tt" else 2.0):
            raise SystemExit(f"{name} tuning span failed: {span:.3f}")
        if not all(frequencies[i] > frequencies[i+1] for i in range(len(frequencies)-1)):
            raise SystemExit(f"{name} codes are not strictly decreasing")
        if name == "tt":
            bins = len({math.floor(f / 1e6) for f in frequencies})
            required_bins = 3 if args.pex_sample else 10
            if frequencies[0] < 50e6 or frequencies[-1] > 25e6 or bins < required_bins:
                raise SystemExit(f"TT code-0/resolution failed: {frequencies[0]}, {bins} bins")
    print("CHARACTERIZATION_PASS")


if __name__ == "__main__":
    main()
