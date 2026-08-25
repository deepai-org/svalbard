#!/usr/bin/env python3
"""Screen the calibrated dual-edge pulse generator over PVT and delay bias."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(
    r"^(\w+)\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
    re.MULTILINE)
REQUIRED = {
    "clk_rise", "es_rise", "es_fall", "ew_rise", "ew_fall",
    "os_rise", "os_fall", "ow_rise", "ow_fall", "es_high", "es_low",
    "ew_high", "ew_low", "eb_high", "supply_current", "ob_high",
}
ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27),
    ("ff_cold", "ff", 3.63, -40),
    ("ff_hot", "ff", 2.97, 125),
    ("ss_hot", "ss", 2.97, 125),
    ("ss_cold", "ss", 3.63, -40),
)


parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--work", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--pex", type=Path)
parser.add_argument("--pex-resistance-scale", type=float, default=1.0)
parser.add_argument("--pex-capacitance-scale", type=float, default=1.0)
parser.add_argument(
    "--pex-resistance-net-scale", action="append", default=[],
    metavar="NET=SCALE",
    help="multiply extracted resistors wholly inside a named net")
parser.add_argument("--environment", action="append")
parser.add_argument("--fraction", action="append", type=float)
parser.add_argument("--tap-code", action="append",
                    help="realized sense,start,end profile, for example 2,8,9")
args = parser.parse_args()
if args.pex_resistance_scale < 0 or args.pex_capacitance_scale < 0:
    parser.error("PEX scales must be nonnegative")
net_resistance_scales = {}
for encoded in args.pex_resistance_net_scale:
    try:
        net, scale_text = encoded.rsplit("=", 1)
        scale = float(scale_text)
    except ValueError:
        parser.error(f"invalid resistance-net scale: {encoded}")
    if not net or scale < 0:
        parser.error(f"invalid resistance-net scale: {encoded}")
    net_resistance_scales[net] = scale
args.work.mkdir(parents=True, exist_ok=True)
template = (args.source / "clock_pulse_generator_tb.spice.in").read_text()
if not args.pex:
    schematic_debug = {
        "D08": "D08", "D09": "D09", "WSTART_SEL": "WSTART_SEL",
        "WEND_SEL": "WEND_SEL", "WST": "WST", "WET": "WET",
        "WCOREB": "WCOREB",
        "WB0": "WB0", "WB1": "WB1", "WB2": "WB2", "WB3": "WB3",
        "P06G": "P06_G", "P06S": "P06S", "P09S": "P09S",
        "P09M": "P09M", "P10M": "P10M",
        "WMID": "WMID", "WMIDB": "WMIDB",
        "SSEL": "SSEL", "CT": "CT", "ST": "ST", "CTD": "CTD",
        "STD": "STD", "SN0": "SN0", "SND": "SND",
        "SB0": "SB0", "SB1": "SB1",
        "PCLK": "PCLK", "P08": "P08", "D08": "D08",
        "CTSEL": "CTSEL",
        "CTB0": "XCT.B0", "CTB1": "XCT.B1", "CTB2": "XCT.B2",
        "STB0": "XST.B0", "STB1": "XST.B1", "STB2": "XST.B2",
        "WSTB1": "XWST.B1", "WETB1": "XWET.B1",
    }
    for phase, instance in (("E", "XE"), ("O", "XO")):
        for label in sorted(schematic_debug, key=len, reverse=True):
            node = schematic_debug[label]
            template = template.replace(f"XDUT.DBG_{phase}_{label}",
                                        f"XDUT.{instance}.{node}")
    template = template.replace("* @DEBUG_BEGIN@\n", "")
    template = template.replace("* @DEBUG_END@\n", "")
cases = []
dut_path = args.pex or args.source / "clock_pulse_generator.spice"
if args.pex and (args.pex_resistance_scale != 1.0
                 or args.pex_capacitance_scale != 1.0
                 or net_resistance_scales):
    scaled_lines = []
    parasitic = re.compile(
        r"^([RC]\S+)\s+(\S+)\s+(\S+)\s+([-+0-9.eE]+)"
        r"(meg|[tgkmunpf])?(\s*)$",
        re.IGNORECASE)
    for line in args.pex.read_text().splitlines():
        match = parasitic.match(line)
        if match:
            scale = (args.pex_resistance_scale if line.startswith("R")
                     else args.pex_capacitance_scale)
            if line.startswith("R"):
                for net, net_scale in net_resistance_scales.items():
                    inside = lambda node: node == net or node.startswith(net + ".")
                    if inside(match.group(2)) and inside(match.group(3)):
                        scale *= net_scale
            line = (f"{match.group(1)} {match.group(2)} {match.group(3)} "
                    f"{float(match.group(4)) * scale:.12g}"
                    + (match.group(5) or "") + match.group(6))
        scaled_lines.append(line)
    dut_path = args.work / "scaled-clock-pulse-generator.pex.spice"
    dut_path.write_text("\n".join(scaled_lines) + "\n")
selected_environments = tuple(
    env for env in ENVIRONMENTS
    if not args.environment or env[0] in args.environment)
fractions = tuple(args.fraction) if args.fraction else (0.70,)
tap_codes = []
profiles = {
    (0, 10, 11): 0,
    (1, 8, 9): 1,
    (0, 8, 9): 2,
    (2, 8, 9): 3,
}
for encoded in args.tap_code or ("0,10,11", "1,8,9", "0,8,9", "2,8,9"):
    try:
        sense_tap, write_start_tap, write_end_tap = (
            int(part) for part in encoded.split(","))
    except (TypeError, ValueError):
        parser.error(f"invalid tap code: {encoded}")
    if (sense_tap, write_start_tap, write_end_tap) not in profiles:
        parser.error(f"tap code is not a realized profile: {encoded}")
    tap_codes.append((sense_tap, write_start_tap, write_end_tap))
for sense_tap, write_start_tap, write_end_tap in tap_codes:
    code = f"s{sense_tap:02d}_w{write_start_tap:02d}_{write_end_tap:02d}"
    profile = profiles[(sense_tap, write_start_tap, write_end_tap)]
    for env_name, corner, vdd, temperature in selected_environments:
      for fraction in fractions:
        values = {
            "MOS_CORNER": corner,
            "TEMP_C": str(temperature),
            "VDD_V": f"{vdd:.6f}",
            "VMID": f"{vdd / 2:.6f}",
            "DUT_PATH": str(dut_path),
            "DUT_SUBCKT": "clock_pulse_generator_pex" if args.pex
                           else "clock_pulse_generator",
            **{f"SEL{index}_V": f"{vdd if index == profile else 0:.6f}"
               for index in range(4)},
        }
        text = template
        for key, value in values.items():
            text = text.replace(f"@{key}@", value)
        stem = f"{env_name}_{code}_{round(fraction * 100):02d}"
        deck = args.work / f"{stem}.spice"
        log = args.work / f"{stem}.log"
        deck.write_text(text)
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=240,
                                 check=False)
        observed = {key: float(value)
                    for key, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and REQUIRED <= observed.keys()
        def cycle_delta(later: str, earlier: str) -> float:
            delta = observed.get(later, 0) - observed.get(earlier, 0)
            while delta < 0:
                delta += 800e-12
            while delta >= 800e-12:
                delta -= 800e-12
            return delta

        es_width = cycle_delta("es_fall", "es_rise")
        ew_width = cycle_delta("ew_fall", "ew_rise")
        os_width = cycle_delta("os_fall", "os_rise")
        ow_width = cycle_delta("ow_fall", "ow_rise")
        write_delay = cycle_delta("ew_rise", "es_rise")
        odd_spacing = cycle_delta("os_rise", "es_rise")
        dead_time = cycle_delta("ew_rise", "es_fall")
        passed = (complete
                  and 450e-12 <= es_width <= 650e-12
                  and 100e-12 <= ew_width <= 220e-12
                  and 450e-12 <= os_width <= 650e-12
                  and 100e-12 <= ow_width <= 220e-12
                  and 500e-12 <= write_delay <= 700e-12
                  and 350e-12 <= odd_spacing <= 450e-12
                  and 0 <= dead_time <= 150e-12
                  and observed["es_high"] >= vdd - 0.25
                  and observed["ew_high"] >= vdd - 0.25
                  and observed["es_low"] <= 0.25
                  and observed["ew_low"] <= 0.25
                  and observed["os_high"] >= vdd - 0.25
                  and observed["ow_high"] >= vdd - 0.25
                  and observed["os_low"] <= 0.25
                  and observed["ow_low"] <= 0.25
                  and observed["eb_high"] >= vdd - 0.25
                  and observed["ob_high"] >= vdd - 0.25
                  and 0 < observed["supply_current"] <= 0.075)
        cases.append({
            "case_id": stem,
            "environment": [corner, vdd, temperature],
            "control_fraction": fraction,
            "tap_code": [sense_tap, write_start_tap, write_end_tap],
            "complete": complete,
            "sense_width_s": es_width,
            "write_width_s": ew_width,
            "odd_sense_width_s": os_width,
            "odd_write_width_s": ow_width,
            "write_delay_s": write_delay,
            "odd_spacing_s": odd_spacing,
            "dead_time_s": dead_time,
            "observed": observed,
            "result": "pass" if passed else "fail",
        })

coverage = {}
for env_name, corner, vdd, temperature in selected_environments:
    selected = [case for case in cases
                if case["environment"] == [corner, vdd, temperature]
                and case["result"] == "pass"]
    coverage[env_name] = [case["tap_code"] for case in selected]
result = {
    "schema_version": 1,
    "claim": ("calibrated_dual_edge_sense_write_pulse_full_rc"
              if args.pex else
              "calibrated_dual_edge_sense_write_pulse_schematic"),
    "case_count": len(cases),
    "passing_case_count": sum(case["result"] == "pass" for case in cases),
    "environment_coverage": coverage,
    "cases": cases,
}
if args.pex:
    result["pex_sha256"] = hashlib.sha256(args.pex.read_bytes()).hexdigest()
result["result"] = "pass" if all(coverage.values()) else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": result["result"], "coverage": coverage},
                 sort_keys=True))
if result["result"] != "pass":
    raise SystemExit(1)
