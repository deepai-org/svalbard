#!/usr/bin/env python3
"""Screen physically selectable full-state HCLK WRITE-window candidates."""

import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEMPLATE = (ROOT / "hclk_window.spice.in").read_text()
WORK = Path("/work/cases")
OUTPUT = Path("/work/hclk-window-result.json")
MEASURE = re.compile(
    r"^(\w+)\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
    re.MULTILINE,
)
ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27),
    ("ff_cold", "ff", 3.63, -40),
    ("ff_hot", "ff", 2.97, 125),
    ("ss_hot", "ss", 2.97, 125),
    ("ss_cold", "ss", 3.63, -40),
)
# The extra stage is deliberately swept broadly.  Every option is an actual
# two-inverter CMOS delay rather than a simulator timing parameter.  A
# candidate earns promotion only if each PVT environment has a valid code.
EXTRA_STAGES = (
    ("x1", "2u", "1u", 1, 1),
    ("x2", "4u", "2u", 2, 2),
    ("x4", "8u", "4u", 4, 4),
    ("x8", "8u", "4u", 8, 8),
)
REQUIRED = {
    "hclk_fall", "write_rise", "write_fall", "write_high", "write_low",
    "win_rise", "win_fall", "wpn_fall", "wpn_rise", "wpn_high", "wpn_low",
    "supply_current",
}


def cyclic_delta(later: float, earlier: float) -> float:
    """Return the positive same-event separation at the 800-ps unit interval."""
    delta = later - earlier
    while delta < 0:
        delta += 800e-12
    while delta >= 800e-12:
        delta -= 800e-12
    return delta


def run_case(spec: tuple[str, str, str, float, int, int, int, int]) -> dict:
    stage, environment, corner, vdd, temperature, code, multiplier, ignored = spec
    del multiplier, ignored
    extra = next(item for item in EXTRA_STAGES if item[0] == stage)
    _, extra_w, extra_n, extra_mp, extra_mn = extra
    replacement = {
        "MOS_CORNER": corner,
        "TEMP_C": str(temperature),
        "VDD_V": f"{vdd:.6f}",
        "VMID": f"{vdd / 2:.6f}",
        "SEL_V": f"{vdd if code else 0:.6f}",
        "EXTRA_W": extra_w,
        "EXTRA_N": extra_n,
        "EXTRA_MP": str(extra_mp),
        "EXTRA_MN": str(extra_mn),
    }
    text = TEMPLATE
    for key, value in replacement.items():
        text = text.replace(f"@{key}@", value)
    stem = f"{stage}_{environment}_sel{code}"
    deck = WORK / f"{stem}.spice"
    log = WORK / f"{stem}.log"
    deck.write_text(text)
    try:
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=240, check=False,
            )
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    complete = returncode == 0 and REQUIRED <= observed.keys()
    # The first edge after the fixed measurement window can belong to either
    # side of a periodic pulse.  Normalizing by the known UI pairs the next
    # matching edge without assuming which side happens first.
    width = cyclic_delta(observed.get("write_fall", 0), observed.get("write_rise", 0))
    window_width = cyclic_delta(observed.get("win_fall", 0), observed.get("win_rise", 0))
    wpn_width = cyclic_delta(observed.get("wpn_rise", 0), observed.get("wpn_fall", 0))
    delay = cyclic_delta(observed.get("write_rise", 0), observed.get("hclk_fall", 0))
    passed = (
        complete
        and 100e-12 <= width <= 220e-12
        and 80e-12 <= delay <= 650e-12
        and observed["write_high"] >= vdd - 0.25
        and observed["write_low"] <= 0.25
        and observed["wpn_high"] >= vdd - 0.25
        and observed["wpn_low"] <= 0.25
        and 0 < observed["supply_current"] <= 0.075
    )
    return {
        "case_id": stem,
        "extra_stage": stage,
        "environment": [corner, vdd, temperature],
        "code": code,
        "complete": complete,
        "write_width_s": width,
        "detector_window_width_s": window_width,
        "wpn_low_width_s": wpn_width,
        "write_delay_from_hclk_fall_s": delay,
        "observed": observed,
        "result": "pass" if passed else "fail",
    }


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    specs = [
        (stage, name, corner, vdd, temperature, code, 0, 0)
        for stage, *_ in EXTRA_STAGES
        for name, corner, vdd, temperature in ENVIRONMENTS
        for code in (0, 1)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        cases = list(executor.map(run_case, specs))
    coverage = {}
    for name, corner, vdd, temperature in ENVIRONMENTS:
        coverage[name] = [
            {"extra_stage": case["extra_stage"], "code": case["code"]}
            for case in cases
            if case["environment"] == [corner, vdd, temperature]
            and case["result"] == "pass"
        ]
    result = {
        "schema_version": 1,
        "claim": "selectable_full_swing_hclk_write_window_necessary_screen",
        "scope": (
            "schematic necessary condition only: full-swing HCLK input through "
            "a one-bit restored selector, local window detector, and 650-fF "
            "WRITE load"
        ),
        "not_a_claim": [
            "complete_pcie_pulse_generator",
            "physical_layout_or_pex",
            "pcie_capture_or_cdr_closure",
            "calibration_algorithm_or_silicon_yield",
        ],
        "source_sha256": hashlib.sha256((ROOT / "hclk_window.spice.in").read_bytes()).hexdigest(),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "environment_coverage": coverage,
        "cases": cases,
    }
    result["result"] = "pass" if all(coverage.values()) else "fail"
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"], "coverage": coverage}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
