#!/usr/bin/env python3
"""Sweep the dual capture stage over representative PVT and timing."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

EVEN_BITS = (1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0)
ODD_BITS = (0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1)
SAMPLE_INDICES = tuple(range(2, 12))
ENVIRONMENTS = (
    ("typical", 3.30, 27),
    ("ff", 2.97, -40), ("ff", 2.97, 125),
    ("ff", 3.63, -40), ("ff", 3.63, 125),
    ("ss", 2.97, -40), ("ss", 2.97, 125),
    ("ss", 3.63, -40), ("ss", 3.63, 125),
)
DATA_READY_PS = (680, 700)
CAPTURE_CLOSE_PS = (950, 1000)
LOADS_FF = (10, 50)
OUTPUT_SETTLE_PS = 300
SCALAR = re.compile(
    r"^((?:even|odd)_(?:q|qb)_\d+|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def data_pwl(bits: tuple[int, ...], vdd: float, ready_ps: int) -> str:
    interval, edge = 800e-12, 20e-12
    points = [(0.0, bits[0] * vdd)]
    previous = bits[0]
    for index, bit in enumerate(bits[1:], start=1):
        if bit == previous:
            continue
        end = index * interval + ready_ps * 1e-12
        points.extend(((end - edge, previous * vdd), (end, bit * vdd)))
        previous = bit
    points.append(((len(bits) + 1) * interval, previous * vdd))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--output-settle-ps", type=int, default=OUTPUT_SETTLE_PS)
    parser.add_argument("--capture-close-ps", type=int, action="append")
    parser.add_argument("--smoke", action="store_true",
                        help="run 700 ps ready and 50 fF at the contract closes")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    if not 100 <= args.output_settle_ps <= 450:
        parser.error("--output-settle-ps must be between 100 and 450")
    if args.capture_close_ps and any(not 820 <= value <= 1000
                                     for value in args.capture_close_ps):
        parser.error("--capture-close-ps must be between 820 and 1000")
    args.work.mkdir(parents=True, exist_ok=True)
    source = args.pex if args.pex else args.source / "deserializer.spice"
    template = (args.source / "capture_tb.spice.in").read_text()
    dut_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    expected_scalars = 4 * len(SAMPLE_INDICES) + 1
    specifications = []
    ready_values = (700,) if args.smoke else DATA_READY_PS
    close_values = CAPTURE_CLOSE_PS
    if args.capture_close_ps:
        close_values = tuple(dict.fromkeys(args.capture_close_ps))
    if max(close_values) + args.output_settle_ps > 1380:
        parser.error("capture close plus output settle must not exceed 1380 ps")
    load_values = (50,) if args.smoke else LOADS_FF
    for mos, vdd, temp in ENVIRONMENTS:
        for ready_ps in ready_values:
            for close_ps in close_values:
                for load_ff in load_values:
                    case_id = (f"{mos}_{vdd:.2f}_{temp:+d}_ready{ready_ps}_"
                               f"close{close_ps}_load{load_ff}")
                    case_id = case_id.replace("+", "p").replace("-", "m").replace(".", "p")
                    sample_delay = close_ps + args.output_settle_ps
                    measures = []
                    for index in SAMPLE_INDICES:
                        time = index * 800e-12 + sample_delay * 1e-12
                        for lane in ("even", "odd"):
                            measures.append(
                                f"meas tran {lane}_q_{index} find v({lane.upper()}_Q) at={time:.12g}")
                            measures.append(
                                f"meas tran {lane}_qb_{index} find v({lane.upper()}_QB) at={time:.12g}")
                    values = {
                        "DUT_SHA256": dut_sha256, "DUT_PATH": str(source),
                        "DUT_SUBCKT": ("deserializer_1to2_pex" if args.pex
                                        else "deserializer_1to2"),
                        "MOS_CORNER": mos, "TEMP_C": str(temp), "VDD_V": f"{vdd:.2f}",
                        "EVEN_PWL": data_pwl(EVEN_BITS, vdd, ready_ps),
                        "EVENB_PWL": data_pwl(tuple(1 - bit for bit in EVEN_BITS),
                                               vdd, ready_ps),
                        "ODD_PWL": data_pwl(ODD_BITS, vdd, ready_ps),
                        "ODDB_PWL": data_pwl(tuple(1 - bit for bit in ODD_BITS),
                                              vdd, ready_ps),
                        "CAPTURE_WIDTH": f"{close_ps - 620}p",
                        "LOAD_F": f"{load_ff}f",
                        "TSTOP": f"{len(EVEN_BITS) * 800e-12:.12g}",
                        "MEASURES": "\n".join(measures),
                    }
                    specifications.append((case_id, mos, vdd, temp, ready_ps,
                                           close_ps, load_ff, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, mos, vdd, temp, ready_ps, close_ps, load_ff, values = specification
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())})
                    == expected_scalars)
        return_code = 0
        if not reusable:
            deck.write_text(deck_text)
            with log.open("w") as output:
                try:
                    run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                         stderr=subprocess.STDOUT, timeout=args.timeout_s,
                                         check=False)
                    return_code = run.returncode
                except subprocess.TimeoutExpired:
                    return_code = 124
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        margins = []
        for index in SAMPLE_INDICES:
            for lane, bits in (("even", EVEN_BITS), ("odd", ODD_BITS)):
                q = observed.get(f"{lane}_q_{index}", 0.0)
                qb = observed.get(f"{lane}_qb_{index}", 0.0)
                high, low = (q, qb) if bits[index] else (qb, q)
                margins.extend((high - 0.8 * vdd, 0.2 * vdd - low))
        complete = return_code == 0 and len(observed) == expected_scalars
        margin = min(margins)
        passed = (complete and margin >= 0
                  and 1e-5 <= observed.get("supply_current", 0.0) <= 0.010)
        return {
            "id": case_id, "environment": [mos, vdd, temp],
            "data_ready_s": ready_ps * 1e-12,
            "capture_close_s": close_ps * 1e-12, "load_ff": load_ff,
            "setup_s": (close_ps - ready_ps) * 1e-12,
            "complete": complete, "logic_margin_v": margin,
            "supply_current_a": observed.get("supply_current"),
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    keys = sorted({(tuple(case["environment"]), case["data_ready_s"], case["load_ff"])
                   for case in cases})
    for environment, ready_s, load_ff in keys:
        members = [case for case in cases
                   if tuple(case["environment"]) == environment
                   and case["data_ready_s"] == ready_s and case["load_ff"] == load_ff]
        passing = [case for case in members if case["result"] == "pass"]
        groups.append({
            "environment": list(environment), "data_ready_s": ready_s,
            "load_ff": load_ff, "case_count": len(members),
            "passing_case_count": len(passing),
            "passing_capture_close_s": [case["capture_close_s"] for case in passing],
            "result": "pass" if passing else "fail",
        })
    complete_count = sum(case["complete"] for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    result = {
        "schema_version": 1, "dut_sha256": dut_sha256,
        "mode": "smoke" if args.smoke else "matrix",
        "output_settle_s": args.output_settle_ps * 1e-12,
        "result": "pass" if complete_count == len(cases)
                  and passing_groups == len(groups) else "fail",
        "case_count": len(cases), "complete_case_count": complete_count,
        "group_count": len(groups), "passing_group_count": passing_groups,
        "cases": cases, "groups": groups,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"deserializer capture: {complete_count}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} timing groups pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
