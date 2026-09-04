#!/usr/bin/env python3
from pathlib import Path
import argparse,json,re

PINS=["EN","CTRL0","CTRL1","CTRL2","CTRL3","OUT","VDD","VSS"]
ap=argparse.ArgumentParser();ap.add_argument("candidate",type=Path);ap.add_argument("--require-gds",action="store_true");a=ap.parse_args()
spice=a.candidate/"analog/dco4.spice";manifest=a.candidate/"integration/dco4.json";gds=a.candidate/"layout/dco4.gds"
if json.loads(manifest.read_text())!={"top":"dco4","pins":PINS,"supply_v":3.3}:raise SystemExit("manifest mismatch")
if not re.search(r"(?im)^\.subckt\s+dco4\s+"+r"\s+".join(PINS)+r"\s*$",spice.read_text()):raise SystemExit("SPICE signature mismatch")
if a.require_gds and (not gds.is_file() or gds.stat().st_size<1024):raise SystemExit("GDS missing or empty")
print("INTERFACE_PASS")
