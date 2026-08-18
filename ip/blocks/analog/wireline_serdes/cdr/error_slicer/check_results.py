#!/usr/bin/env python3
"""Enforce error-slicer schematic, extracted, physical, and speed evidence."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

def main() -> None:
    parser=argparse.ArgumentParser()
    for name in ("schematic","extracted","drc","lvs","pex","gds","render","output"):
        parser.add_argument(f"--{name}",required=True,type=Path)
    args=parser.parse_args(); schematic=json.loads(args.schematic.read_text()); extracted=json.loads(args.extracted.read_text())
    pex_text=args.pex.read_text(); resistors=len(re.findall(r"^R\d+\s",pex_text,re.MULTILINE)); capacitors=len(re.findall(r"^C\d+\s",pex_text,re.MULTILINE))
    checks={
        "schematic.calibrated_pvt": schematic.get("result")=="pass" and schematic.get("case_count")==972 and schematic.get("passing_group_count")==9,
        "extracted.calibrated_pvt": extracted.get("result")=="pass" and extracted.get("case_count")==972 and extracted.get("passing_group_count")==9,
        "extracted.interior_trim": all(group.get("selected_is_interior") for group in extracted["groups"]),
        "extracted.speed_below_300ps": max(group["selected_worst_assert_delay_s"] for group in extracted["groups"]) <= 0.30e-9,
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": ".subckt cml_error_slicer_pex" in pex_text and "extresist threshold=0 mOhm" in pex_text and resistors>=150 and capacitors>=80,
        "layout.rendered": args.render.stat().st_size>=10_000,
    }
    selected=[]
    for group in extracted["groups"]:
        selected.extend(case for case in extracted["cases"] if case["environment"]==group["environment"] and case["main_bias_v"]==group["selected_main_bias_v"] and case["threshold_bias_v"]==group["selected_threshold_bias_v"])
    result={
        "schema_version":1,"result":"pass" if all(checks.values()) else "fail",
        "qualification":"experimental pre-silicon GF180 public-model evidence only",
        "checks":checks,"layout_sha256":hashlib.sha256(args.gds.read_bytes()).hexdigest(),
        "pex":{"mode":"full_rc_coupled","resistor_count":resistors,"capacitor_count":capacitors,"sha256":hashlib.sha256(args.pex.read_bytes()).hexdigest()},
        "observed":{
            "selected_main_bias_v":[min(c["main_bias_v"] for c in selected),max(c["main_bias_v"] for c in selected)],
            "selected_threshold_bias_v":[min(c["threshold_bias_v"] for c in selected),max(c["threshold_bias_v"] for c in selected)],
            "minimum_asserted_output_v":min(c["minimum_asserted_output_v"] for c in selected),
            "maximum_dead_zone_output_v":max(c["maximum_dead_zone_output_v"] for c in selected),
            "worst_assert_delay_ps":max(c["worst_assert_delay_s"] for c in selected)*1e12,
        },
    }
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    if result["result"]!="pass": raise SystemExit("error-slicer checks failed: "+", ".join(k for k,v in checks.items() if not v))
    print("cml_error_slicer schematic/layout/PEX checks: PASS")
if __name__=="__main__": main()
