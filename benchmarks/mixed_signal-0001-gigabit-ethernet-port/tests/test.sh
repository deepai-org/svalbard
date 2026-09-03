#!/bin/bash
set -euo pipefail

bench_root=$(cd "$(dirname "$0")/.." && pwd)
make -C "$bench_root" selftest

if [ -d /app/output ]; then
  python3 "$bench_root/environment/input_files/test_visible/run_visible.py" --output /app/output
else
  echo "candidate tests: SKIP (/app/output is absent; no DUT passage claimed)"
fi

python3 "$bench_root/tests/graded/verifier_plan.py"
