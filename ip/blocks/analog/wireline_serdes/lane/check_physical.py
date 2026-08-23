#!/usr/bin/env python3
"""Bind fresh leaf geometry checks to the extracted lane composition."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
for cell in ("termination", "rx", "sampler"):
    for view in ("drc", "lvs", "pex"):
        parser.add_argument(f"--{cell}-{view}", required=True, type=Path)
    parser.add_argument(f"--{cell}-simulation-pex", type=Path)
parser.add_argument("--release-physical", type=Path)
parser.add_argument("--lane", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--serial-rate-gbd", type=float, choices=(1.25, 2.5), default=1.25)
args = parser.parse_args()

cells = {}
simulation_hashes = {}
for cell in ("termination", "rx", "sampler"):
    drc_path = getattr(args, f"{cell}_drc")
    lvs_path = getattr(args, f"{cell}_lvs")
    pex_path = getattr(args, f"{cell}_pex")
    simulation_pex_path = getattr(args, f"{cell}_simulation_pex") or pex_path
    drc_text = drc_path.read_text()
    lvs_text = lvs_path.read_text()
    pex_text = pex_path.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc_text)
    cells[cell] = {
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": lvs_text.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE)),
        "pex_sha256": sha256(pex_path),
        "simulation_pex_sha256": sha256(simulation_pex_path),
    }
    simulation_hashes[cell] = sha256(simulation_pex_path)

lane = json.loads(args.lane.read_text())
hashes = lane.get("source_hashes", {})
identity = {
    "termination": hashes.get("termination_pex") == simulation_hashes["termination"],
    "rx": hashes.get("rx_pex") == simulation_hashes["rx"],
    "sampler": hashes.get("sampler_pex") == simulation_hashes["sampler"],
}
release_identity = {}
release_physical_sha256 = None
if args.release_physical is not None:
    release = json.loads(args.release_physical.read_text())
    release_physical_sha256 = sha256(args.release_physical)
    release_identity = {
        name: release.get("cells", {}).get(name, {}).get("pex_sha256") == digest
        for name, digest in simulation_hashes.items()
    }
    release_identity["lane_record"] = hashes.get("base_physical") == release_physical_sha256
    release_identity["result"] = release.get("result") == "pass"
physical_pass = all(
    item["drc_error_count"] == 0 and item["lvs_unique"]
    and item["pex_resistor_count"] > 0 and item["pex_capacitor_count"] > 0
    for item in cells.values()
)
passed = physical_pass and all(identity.values()) and all(release_identity.values()) \
    and lane.get("result") == "pass" \
    and lane.get("extraction") == "full_rc_leaves"
result = {
    "schema_version": 1,
    "claim": ("physical_externally_clocked_1p25_gbd_tx_to_sampler_composition"
              if args.serial_rate_gbd == 1.25 else
              "physical_externally_clocked_2p5_gts_tx_to_sampler_composition"),
    "cells": cells,
    "lane_pex_identity": identity,
    "release_physical_identity": release_identity,
    "release_physical_sha256": release_physical_sha256,
    "lane_evidence_sha256": sha256(args.lane),
    "result": "pass" if passed else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane physical: {result['result']}; "
      + ", ".join(f"{name}={item['drc_error_count']}DRC/{item['lvs_unique']}LVS/"
                  f"{item['pex_resistor_count']}R/{item['pex_capacitor_count']}C"
                  for name, item in cells.items()))
if not passed:
    raise SystemExit(1)
