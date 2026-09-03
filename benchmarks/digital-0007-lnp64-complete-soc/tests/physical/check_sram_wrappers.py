#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/physical/lnp64_sram_macros_physical.sv"
CONTRACT = json.loads((ROOT / "environment/input_files/memory/sram_macros.json").read_text())
LEAF = "gf180mcu_fd_ip_sram__sram512x8m8wm1"


def count_leaves(top: str) -> int:
    with tempfile.TemporaryDirectory(prefix="lnp64-sram-") as temp:
        netlist = Path(temp) / "netlist.json"
        script = (f"read_verilog -sv {SOURCE}; hierarchy -check -top {top}; "
                  f"proc; flatten; opt_clean; write_json {netlist}")
        subprocess.run(["yosys", "-q", "-p", script], check=True)
        design = json.loads(netlist.read_text())
    return sum(cell["type"] == LEAF for cell in design["modules"][top]["cells"].values())


def main() -> None:
    for module, row in CONTRACT["modules"].items():
        assert count_leaves(module) == row["leaf_instances"]
        geometry = row["physical_geometry"]
        assert geometry["columns"] * geometry["rows"] == row["leaf_instances"]
        expected = geometry["columns"] * geometry["rows"] * 431.86 * 484.88
        assert abs(geometry["leaf_outline_area_total_um2"] - expected) < 0.01
    print("physical SRAM wrappers: PASS (64 and 128 GF180 leaves)")


if __name__ == "__main__":
    main()
