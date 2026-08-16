#!/usr/bin/env bash
set -euo pipefail

export PATH="/foss/tools/yosys/bin:$PATH"
cp /src/counter.sv /src/counter_tb.sv /src/counter.sby /work/
cd /work

verible-verilog-lint counter.sv counter_tb.sv
slang --lint-only --quiet counter.sv counter_tb.sv
iverilog -g2012 -s counter_tb -o counter_sim counter.sv counter_tb.sv
vvp -n counter_sim | tee simulation.log
grep -qx 'digital simulation: PASS' simulation.log
verilator --lint-only --timing --top-module counter_tb counter.sv counter_tb.sv
yosys -q -p 'read_verilog -sv counter.sv; synth -top counter; check' -o counter.json
sby --sequential -f counter.sby > symbiyosys.log 2>&1

python3 - <<'PY'
import json
from pathlib import Path
import re

for task in ("counter_prove", "counter_cover"):
    status = (Path(task) / "status").read_text(encoding="utf-8").split()
    if not status or status[0] != "PASS":
        raise SystemExit(f"{task} status is {status!r}, expected 'PASS'")

formal_log = Path("symbiyosys.log").read_text(encoding="utf-8")
cover_match = re.search(r"Reached cover statement in step ([0-9]+)", formal_log)
if cover_match is None or int(cover_match.group(1)) != 17:
    raise SystemExit("formal cover did not reach the post-reset wrap at step 17")

result = {
    "schema_version": 1,
    "result": "pass",
    "checks": [
        "verible_lint",
        "slang_lint",
        "iverilog_simulation",
        "verilator_lint",
        "yosys_synthesis",
        "symbiyosys_yices_prove",
        "symbiyosys_yices_cover"
    ],
    "formal_solver": "Yices 2.7.0",
    "formal_cover_step": 17,
    "limitations": [
        "generic counter canary only",
        "Boolector and Z3 remain required and missing",
        "no PDK, standard-cell library, STA, or physical implementation was exercised"
    ]
}
Path("result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo 'digital formal proof: PASS; post-reset cover reached at step 17'
echo 'digital toolchain smoke: PASS'
