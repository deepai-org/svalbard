#!/usr/bin/env bash
set -euo pipefail

export PATH="/solvers/usr/bin:/foss/tools/yosys/bin:$PATH"
export LD_LIBRARY_PATH="/solvers/usr/lib/aarch64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
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

tasks = (
    "counter_prove_yices",
    "counter_prove_boolector",
    "counter_prove_z3",
    "counter_cover_yices",
    "counter_cover_boolector",
    "counter_cover_z3",
)
for task in tasks:
    status = (Path(task) / "status").read_text(encoding="utf-8").split()
    if not status or status[0] != "PASS":
        raise SystemExit(f"{task} status is {status!r}, expected 'PASS'")

formal_log = Path("symbiyosys.log").read_text(encoding="utf-8")
cover_steps = [int(step) for step in re.findall(r"Reached cover statement in step ([0-9]+)", formal_log)]
if cover_steps != [17, 17, 17]:
    raise SystemExit(f"formal covers did not all reach the post-reset wrap at step 17: {cover_steps}")

result = {
    "schema_version": 1,
    "result": "pass",
    "checks": [
        "verible_lint",
        "slang_lint",
        "iverilog_simulation",
        "verilator_lint",
        "yosys_synthesis",
        "symbiyosys_yices_prove_and_cover",
        "symbiyosys_boolector_prove_and_cover",
        "symbiyosys_z3_prove_and_cover"
    ],
    "formal_solvers": ["Yices 2.7.0", "Boolector 3.2.4", "Z3 4.8.12"],
    "formal_cover_steps": {"yices": 17, "boolector": 17, "z3": 17},
    "limitations": [
        "generic counter canary only",
        "no PDK, standard-cell library, STA, or physical implementation was exercised"
    ]
}
Path("result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo 'digital formal proof: PASS with Yices, Boolector, and Z3; covers reached at step 17'
echo 'digital toolchain smoke: PASS'
