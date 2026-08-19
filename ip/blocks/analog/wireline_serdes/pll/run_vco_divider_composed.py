#!/usr/bin/env python3
"""Qualify the exact routed VCO parent directly loaded by the exact divider."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))
from analog_evidence import environment_index, sha256_file  # noqa: E402

CODE_PORTS = tuple(
    f"{prefix}_{channel}{bit}{suffix}"
    for prefix in ("F", "G") for channel in ("A", "B")
    for bit in range(4, -1, -1) for suffix in ("", "B")
)
BASE_DIVIDER_BIASES_V = (0.8, 0.9, 1.0)
SLOW_DIVIDER_BIASES_V = (0.8, 0.9, 1.0, 1.1, 1.2)
BASE_SELECTOR_BIASES_V = (1.35,)
SLOW_SELECTOR_BIASES_V = (1.35, 1.50, 1.65, 1.80)
MEASUREMENTS = (
    "vco_startup", "vco_period", "vco_high", "vco_low", "div_startup",
    "div_period_early", "div_period_late", "div_high_time", "div_high",
    "div_low", "div_output_cm", "vco_current", "div_current",
    "reference_power_avg",
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def bit_sources(prefix: str, code_a: int, code_b: int, vdd: float) -> list[str]:
    lines = []
    for channel, code in (("A", code_a), ("B", code_b)):
        for bit in range(4, -1, -1):
            value = (code >> bit) & 1
            for suffix, inverted in (("", False), ("B", True)):
                node = f"{prefix}_{channel}{bit}{suffix}"
                high = value ^ inverted
                lines.append(f"V{node} {node} 0 PWL(0 0 500p {vdd if high else 0:.3f})")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--vco-pex", type=Path, required=True)
    parser.add_argument("--divider-pex", type=Path, required=True)
    parser.add_argument("--vco-baseline", type=Path, required=True)
    parser.add_argument("--divider-physical", type=Path, required=True)
    parser.add_argument("--clock-width-screen", action="store_true")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "vco_divider_composed_tb.spice.in"
    template = template_path.read_text()
    baseline = json.loads(args.vco_baseline.read_text())
    divider_physical = json.loads(args.divider_physical.read_text())
    vco_hash, divider_hash = sha256_file(args.vco_pex), sha256_file(args.divider_pex)
    if baseline.get("result") != "pass" or baseline.get("pex_sha256") != vco_hash:
        raise SystemExit("VCO baseline is not a pass for the supplied exact PEX")
    if divider_physical.get("result") != "pass" or divider_physical.get("pex_sha256") != divider_hash:
        raise SystemExit("divider physical evidence is not a pass for the supplied exact PEX")
    cases_by_id = {case["id"]: case for case in baseline["cases"]}
    selected = [cases_by_id[item["selected_case_id"]] for item in baseline["calibration"]]
    divider_variants = [(8.0, args.divider_pex)]
    if args.clock_width_screen:
        base_pex = args.divider_pex.read_text()
        divider_variants = []
        device = re.compile(r"^X\S+.*\bw=8u l=0\.28u$", re.MULTILINE)
        number = re.compile(r"\b(ad|pd|as|ps)=([0-9.]+)([pu])")
        for width in (12.0, 16.0, 24.0):
            ratio = width / 8.0
            def scale_device(match: re.Match[str]) -> str:
                line = number.sub(
                    lambda item: f"{item.group(1)}={float(item.group(2)) * ratio:.6g}{item.group(3)}",
                    match.group(0),
                )
                return line.replace("w=8u l=0.28u", f"w={width:g}u l=0.28u")
            variant_path = args.work / f"divider-clock-w{width:g}.pex.spice"
            variant_path.write_text(device.sub(scale_device, base_pex))
            if len(device.findall(base_pex)) != 8:
                raise SystemExit("expected exactly eight extracted 8 um clock devices")
            divider_variants.append((width, variant_path))
    specs = []
    for case in selected:
        slow = case["environment"][0] == "ss"
        if args.clock_width_screen and not slow:
            continue
        divider_biases = (0.9, 1.1) if args.clock_width_screen else (
            SLOW_DIVIDER_BIASES_V if slow else BASE_DIVIDER_BIASES_V
        )
        selector_biases = BASE_SELECTOR_BIASES_V if args.clock_width_screen else (
            SLOW_SELECTOR_BIASES_V if slow else BASE_SELECTOR_BIASES_V
        )
        specs.extend((case, divider_bias, selector_bias, width, divider_path)
                     for divider_bias in divider_biases for selector_bias in selector_biases
                     for width, divider_path in divider_variants)
    pattern = re.compile(rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE)

    def simulate(spec: tuple[dict[str, object], float, float, float, Path]) -> dict[str, object]:
        base, bias, selector_bias, clock_width, divider_path = spec
        mos, resistor, supply, temperature = base["environment"]
        member = str(base["selected_member"])
        main, regen = (int(base["selected_codes"][key]) for key in ("main", "regen"))
        case_id = f"{base['id']}_db{bias:.1f}_sb{selector_bias:.2f}_cw{clock_width:g}".replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        fast_codes = (main, regen) if member == "fast" else (0, 0)
        gain_codes = (main, regen) if member == "gain" else (0, 0)
        sources = bit_sources("F", *fast_codes, float(supply)) + bit_sources("G", *gain_codes, float(supply))
        pulse = f"PULSE(0 {float(supply):.2f} 1n 20p 20p 250p 100n)"
        select = "PWL(0 0 3n 0 3.1n 1.50)"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.2f}",
            "VBIAS_V": f"{bias:.2f}", "VCO_PEX_PATH": str(args.vco_pex),
            "SEL_BUF_V": f"{selector_bias:.2f}",
            "DIVIDER_PEX_PATH": str(divider_path),
            "DUT_CODE_PORTS": " ".join(CODE_PORTS), "BIT_SOURCES": "\n".join(sources),
            "FAST_KICKP_SOURCE": pulse if member == "fast" else "0",
            "FAST_KICKN_SOURCE": "0", "GAIN_KICKP_SOURCE": pulse if member == "gain" else "0",
            "GAIN_KICKN_SOURCE": "0", "SEL_A_SOURCE": select if member == "fast" else "0",
            "SEL_B_SOURCE": select if member == "gain" else "0",
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=600, check=False)
        observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
        vco_period, div_period = observed.get("vco_period", 0.0), observed.get("div_period_late", 0.0)
        vco_frequency = 1 / vco_period if vco_period > 0 else 0.0
        div_frequency = 1 / div_period if div_period > 0 else 0.0
        ratio_error = abs(2 * div_frequency / vco_frequency - 1) if vco_frequency > 0 else 1.0
        drift = abs(div_period - observed.get("div_period_early", 0.0)) / div_period if div_period > 0 else 1.0
        duty = abs(observed.get("div_high_time", 0.0)) / div_period if div_period > 0 else 0.0
        loading_shift = abs(vco_frequency / float(base["frequency_hz"]) - 1)
        passed = (
            complete and 1.20e9 <= vco_frequency <= 1.30e9 and loading_shift <= 0.05
            and observed["vco_startup"] <= 8e-9 and observed["vco_high"] >= 0.15
            and observed["vco_low"] <= -0.15 and ratio_error <= 0.005 and drift <= 0.01
            and 0.45 <= duty <= 0.55 and observed["div_startup"] <= 10e-9
            and observed["div_high"] >= 0.15 and observed["div_low"] <= -0.15
            and 0.4 <= observed["div_output_cm"] <= float(supply)
            and observed["vco_current"] <= 0.035 and observed["div_current"] <= 0.025
            and observed["reference_power_avg"] <= 0.003
        )
        return {
            "id": case_id, "environment": base["environment"], "selected_member": member,
            "selected_codes": base["selected_codes"], "divider_bias_v": bias,
            "selector_buffer_bias_v": selector_bias,
            "candidate_clock_width_um": clock_width,
            "baseline_vco_frequency_hz": base["frequency_hz"], "complete": complete,
            "observed": observed, "vco_frequency_hz": vco_frequency,
            "divider_frequency_hz": div_frequency, "divide_ratio_error_fraction": ratio_error,
            "divider_period_drift_fraction": drift, "divider_duty_cycle": duty,
            "vco_loading_frequency_shift_fraction": loading_shift,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))
    calibration = []
    for base in selected:
        members = [case for case in cases if case["environment"] == base["environment"]]
        passing = [case for case in members if case["result"] == "pass"]
        choice = min(passing, key=lambda case: (
            abs(case["selector_buffer_bias_v"] - 1.35),
            abs(case["divider_bias_v"] - 0.9),
            case["observed"]["vco_current"] + case["observed"]["div_current"],
            case["candidate_clock_width_um"],
        )) if passing else None
        calibration.append({
            "environment": base["environment"], "candidate_count": len(members),
            "passing_candidate_count": len(passing), "selected_case_id": choice["id"] if choice else None,
            "selected_divider_bias_v": choice["divider_bias_v"] if choice else None,
            "selected_selector_buffer_bias_v": choice["selector_buffer_bias_v"] if choice else None,
            "selected_candidate_clock_width_um": choice["candidate_clock_width_um"] if choice else None,
            "result": "pass" if choice else "fail",
        })
    environment_index(calibration)
    required_environments = 2 if args.clock_width_screen else 5
    passed = len(calibration) == required_environments and all(item["result"] == "pass" for item in calibration)
    result = {
        "schema_version": 1, "claim": (
            "retained_rc_vco_divider_clock_width_candidate_screen"
            if args.clock_width_screen else "exact_pex_vco_bank_to_static_cml_divider_composition"
        ),
        "physical_qualification": not args.clock_width_screen,
        "case_count": len(cases), "passing_case_count": sum(c["result"] == "pass" for c in cases),
        "passing_environment_count": sum(c["result"] == "pass" for c in calibration),
        "calibration": calibration, "cases": cases, "vco_pex_sha256": vco_hash,
        "divider_pex_sha256": divider_hash, "vco_baseline_sha256": sha256_file(args.vco_baseline),
        "divider_physical_sha256": sha256_file(args.divider_physical),
        "testbench_source_sha256": sha256_file(template_path),
        "simulation_source_sha256": sha256_file(Path(__file__)), "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO/divider composed: {result['passing_case_count']}/{result['case_count']} cases; "
          f"{result['passing_environment_count']}/5 env")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
