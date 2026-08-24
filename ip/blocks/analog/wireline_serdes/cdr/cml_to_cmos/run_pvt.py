#!/usr/bin/env python3
"""Verify the clocked CML-to-CMOS sense amplifier across PVT."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
from pathlib import Path

from run_nominal import (BITS, SAMPLE_DELAYS_S,
                         SAMPLE_INDICES, SCALAR, instantiate, pwl)

MOS_CORNERS = ("typical", "ff", "ss")
SUPPLIES_V = (2.97, 3.30, 3.63)
TEMPERATURES_C = (-40, 27, 125)
COMMON_MODE_FRACTIONS = (0.60, 0.70, 0.80)
DIFFERENTIAL_INPUTS_V = (0.10, 0.20, 0.40)
LOADS_FF = (10, 25, 50)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--dut", type=Path,
                        help="alternate schematic with a cml_to_cmos subcircuit")
    parser.add_argument("--eval-width-ps", type=int, default=575)
    parser.add_argument("--regen-delay-ps", type=int, default=10,
                        help="regeneration enable delay after sense-clock rise")
    parser.add_argument("--capture-delay-ps", type=int, default=200,
                        help="capture enable delay after sense-clock rise")
    parser.add_argument("--capture-width-ps", type=int, default=320)
    parser.add_argument("--pipeline-latency-ui", type=int, choices=(0, 1), default=0)
    parser.add_argument("--boost-policy",
                        choices=("common-mode", "calibrated", "slow-corner",
                                 "slow-low-hot", "always", "never"),
                        default="common-mode")
    parser.add_argument("--boost-fraction", type=float, default=1.0,
                        help="enabled boost high level as a fraction of VDD")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout-s", type=int, default=90,
                        help="per-case ngspice timeout")
    parser.add_argument("--sample-delay-ps", action="append", type=int,
                        help="sample delay from decision-UI start; repeat for a grid")
    parser.add_argument("--case", action="append", default=[],
                        help="run only an exact case ID (repeatable)")
    parser.add_argument("--waveform-dir", type=Path,
                        help="write internal-node waveforms for selected cases")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    if not 0.0 < args.boost_fraction <= 1.0:
        parser.error("--boost-fraction must be in (0, 1]")
    if not 100 <= args.eval_width_ps <= 650:
        parser.error("--eval-width-ps must be between 100 and 650")
    if not 10 <= args.regen_delay_ps <= args.eval_width_ps - 100:
        parser.error("--regen-delay-ps must leave at least 100 ps regeneration time")
    if args.capture_delay_ps < args.regen_delay_ps + 50:
        parser.error("--capture-delay-ps must follow regeneration by at least 50 ps")
    if args.capture_width_ps < 50:
        parser.error("--capture-width-ps must be at least 50 ps")
    if args.capture_delay_ps + args.capture_width_ps > 700:
        parser.error("capture fall must complete at least 10 ps before the next UI")
    sample_delays_s = (tuple(delay * 1e-12 for delay in args.sample_delay_ps)
                       if args.sample_delay_ps else SAMPLE_DELAYS_S)
    if (len(set(sample_delays_s)) != len(sample_delays_s)
            or any(delay <= 0 or delay >= 1500e-12 for delay in sample_delays_s)):
        parser.error("sample delays must be unique and between 0 and 1500 ps")
    sample_delays_s = tuple(sorted(sample_delays_s))
    args.work.mkdir(parents=True, exist_ok=True)
    if args.waveform_dir:
        args.waveform_dir.mkdir(parents=True, exist_ok=True)
    source_dir = (args.source / "cml_to_cmos" if
                  (args.source / "cml_to_cmos").is_dir() else args.source)
    template = (source_dir / "transient_tb.spice.in").read_text()
    if args.pex and args.dut:
        parser.error("select either --pex or --dut")
    dut_path = args.pex or args.dut or source_dir / "cml_to_cmos.spice"
    dut_sha256 = hashlib.sha256(dut_path.read_bytes()).hexdigest()
    interval, edge = 800e-12, 20e-12
    measures = []
    for index in SAMPLE_INDICES:
        for delay in sample_delays_s:
            sample_time = index * interval + delay
            delay_ps = round(delay / 1e-12)
            measures.append(f"meas tran outP_{index}_{delay_ps} find v(OUTP) "
                            f"at={sample_time:.12g}")
            measures.append(f"meas tran outN_{index}_{delay_ps} find v(OUTN) "
                            f"at={sample_time:.12g}")
    expected_scalars = 2 * len(SAMPLE_INDICES) * len(sample_delays_s) + 1
    specifications = []
    for mos in MOS_CORNERS:
        for vdd in SUPPLIES_V:
            for temperature in TEMPERATURES_C:
                for common_mode_fraction in COMMON_MODE_FRACTIONS:
                    common_mode = vdd * common_mode_fraction
                    for differential_input in DIFFERENTIAL_INPUTS_V:
                        for load_ff in LOADS_FF:
                            peak = differential_input / 2
                            case_id = (
                                f"{mos}_{vdd:.2f}_{temperature:+d}_cm{common_mode_fraction:.2f}_"
                                f"in{differential_input:.2f}_load{load_ff}"
                            ).replace("+", "p").replace("-", "m").replace(".", "p")
                            boost_enabled = {
                                "common-mode": common_mode_fraction <= 0.70,
                                "calibrated": (mos == "ss"
                                               and common_mode_fraction <= 0.70),
                                "slow-corner": mos == "ss",
                                "slow-low-hot": (mos == "ss" and vdd <= 3.0
                                                 and temperature >= 100),
                                "always": True,
                                "never": False,
                            }[args.boost_policy]
                            values = {
                                "MOS_CORNER": mos, "TEMP_C": str(temperature),
                                "DUT_SHA256": dut_sha256,
                                "DUT_INCLUDE": f".include {dut_path}",
                                "DUT_SUBCKT": ("cml_to_cmos_pex" if args.pex else
                                                "cml_to_cmos"),
                                "EVAL_WIDTH_S": f"{args.eval_width_ps}p",
                                "BOOST_CLOCK": (f"PULSE(0 {vdd * args.boost_fraction:.6g} 50p 20p 20p "
                                                f"{args.eval_width_ps}p 800p)"
                                                if boost_enabled else "0"),
                                "REGEN_DELAY_S": f"{50 + args.regen_delay_ps}p",
                                "REGEN_WIDTH_S": f"{args.eval_width_ps - args.regen_delay_ps}p",
                                "CAPTURE_DELAY_S": f"{50 + args.capture_delay_ps}p",
                                "CAPTURE_WIDTH_S": f"{args.capture_width_ps}p",
                                "VDD_V": f"{vdd:.2f}",
                                "INP_PWL": pwl(True, common_mode, peak, interval, edge),
                                "INN_PWL": pwl(False, common_mode, peak, interval, edge),
                                "CLOAD_F": f"{load_ff}f",
                                "TSTOP_S": f"{len(BITS) * interval:.12g}",
                                "MEASURES": "\n".join(measures),
                                "WAVEFORM_COMMAND": (
                                    "wrdata " + str(args.waveform_dir / f"{case_id}.dat") +
                                    " time v(xdut.xp) v(xdut.xn)"
                                    " v(sense_clk) v(regen_clk) v(regen_clkb)"
                                    " v(capture_clk) v(capture_clkb)"
                                    " v(outp) v(outn) v(xdut.h) v(xdut.hb)"
                                    " v(xdut.dp) v(xdut.dn)"
                                    " v(xdut.nip) v(xdut.nin) v(xdut.ntail)"
                                    if args.waveform_dir else
                                    "* waveform capture disabled"
                                ),
                            }
                            environment = (mos, vdd, temperature, common_mode_fraction)
                            specifications.append((case_id, environment,
                                                   differential_input, load_ff, values))
    if args.case:
        requested = set(args.case)
        specifications = [item for item in specifications if item[0] in requested]
        missing = requested - {item[0] for item in specifications}
        if missing:
            parser.error(f"unknown --case value(s): {', '.join(sorted(missing))}")

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, environment, differential_input, load_ff, values = specification
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())})
                    == expected_scalars)
        if reusable:
            return_code = 0
        else:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT,
                                     timeout=args.timeout_s, check=False)
            return_code = run.returncode
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        vdd = float(environment[1])
        margins_by_delay = {round(delay / 1e-12): [] for delay in sample_delays_s}
        for index in SAMPLE_INDICES:
            expected = BITS[index - args.pipeline_latency_ui]
            for delay in sample_delays_s:
                delay_ps = round(delay / 1e-12)
                high = observed.get(
                    f"outp_{index}_{delay_ps}" if expected
                    else f"outn_{index}_{delay_ps}", 0.0)
                low = observed.get(
                    f"outn_{index}_{delay_ps}" if expected
                    else f"outp_{index}_{delay_ps}", vdd)
                margins_by_delay[delay_ps].extend((high - 0.8 * vdd, 0.2 * vdd - low))
        complete = return_code == 0 and len(observed) == expected_scalars
        early_margin = min(margins_by_delay[min(margins_by_delay)])
        qualified_margin = min(margins_by_delay[max(margins_by_delay)])
        passed = (complete and qualified_margin >= 0.0
                  and 0.00001 <= observed["supply_current"] <= 0.020)
        return {"id": case_id, "environment": list(environment),
                "differential_input_v": differential_input, "load_ff": load_ff,
                "tail_boost_enabled": {
                    "common-mode": float(environment[3]) <= 0.70,
                    "calibrated": (environment[0] == "ss"
                                   and float(environment[3]) <= 0.70),
                    "slow-corner": environment[0] == "ss",
                    "slow-low-hot": (environment[0] == "ss"
                                      and float(environment[1]) <= 3.0
                                      and int(environment[2]) >= 100),
                    "always": True,
                    "never": False,
                }[args.boost_policy],
                "role": "contract" if differential_input >= 0.20 else "stress",
                "complete": complete,
                "early_logic_margin_v": early_margin,
                "qualified_logic_margin_v": qualified_margin,
                "logic_margin_by_delay_v": {
                    str(delay_ps): min(margins)
                    for delay_ps, margins in margins_by_delay.items()
                },
                "qualified_delay_s": max(sample_delays_s), "observed": observed,
                "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    delay_summary = []
    for delay in sample_delays_s:
        delay_ps = round(delay / 1e-12)
        members = [(case, case["logic_margin_by_delay_v"][str(delay_ps)])
                   for case in cases]
        contract = [margin for case, margin in members
                    if case["role"] == "contract"]
        delay_summary.append({
            "delay_s": delay,
            "minimum_contract_logic_margin_v": min(contract, default=None),
            "passing_contract_case_count": sum(margin >= 0 for margin in contract),
            "contract_case_count": len(contract),
            "passing_case_count": sum(margin >= 0 for _, margin in members),
            "case_count": len(members),
        })
    groups = []
    environments = sorted({tuple(case["environment"]) for case in cases})
    for environment in environments:
        members = [case for case in cases if tuple(case["environment"]) == environment]
        contract = [case for case in members if case["role"] == "contract"]
        stress = [case for case in members if case["role"] == "stress"]
        groups.append({"environment": list(environment), "case_count": len(members),
                       "passing_case_count": sum(case["result"] == "pass"
                                                 for case in members),
                       "contract_case_count": len(contract),
                       "passing_contract_case_count": sum(
                           case["result"] == "pass" for case in contract),
                       "stress_case_count": len(stress),
                       "passing_stress_case_count": sum(
                           case["result"] == "pass" for case in stress),
                       "minimum_qualified_logic_margin_v": min(
                           case["qualified_logic_margin_v"] for case in members),
                       "minimum_contract_logic_margin_v": min(
                           (case["qualified_logic_margin_v"] for case in contract),
                           default=None),
                       "result": "pass" if contract and all(
                           case["result"] == "pass" for case in contract) else "fail"})
    complete_count = sum(case["complete"] for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    passed = complete_count == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "dut_sha256": dut_sha256,
              "boost_policy": args.boost_policy,
              "boost_fraction": args.boost_fraction,
              "pipeline_latency_ui": args.pipeline_latency_ui,
              "sample_delays_s": sample_delays_s,
              "delay_summary": delay_summary,
              "result": "pass" if passed else "fail",
              "case_count": len(cases), "complete_case_count": complete_count,
              "contract_case_count": sum(case["role"] == "contract" for case in cases),
              "passing_contract_case_count": sum(
                  case["role"] == "contract" and case["result"] == "pass"
                  for case in cases),
              "stress_case_count": sum(case["role"] == "stress" for case in cases),
              "passing_stress_case_count": sum(
                  case["role"] == "stress" and case["result"] == "pass"
                  for case in cases),
              "group_count": len(groups), "passing_group_count": passing_groups,
              "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cml_to_cmos PVT: {complete_count}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} environments pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
