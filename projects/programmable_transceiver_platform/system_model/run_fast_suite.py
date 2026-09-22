"""Run inexpensive architecture screens; success does not qualify silicon."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SCREENS = [
    'check_filter_analytic.py', 'check_envelope_convergence.py',
    'fast_screen.py', 'host_screen.py', 'mode_screen.py',
    'queue_screen.py', 'host_supply_screen.py', 'wired_screen.py',
    'clock_tracking_screen.py', 'measured_lo_screen.py', 'trace_conversion_screen.py',
]

# Coverage describes what is executed, not a physical acceptance gate.
COVERAGE = {
    'rf_rx_tx': 'Complex-envelope gain, filtering, clipping, I/Q imbalance and quantization; mostly hypothetical parameters.',
    'wired': 'Channel sampling and idealized transition-driven timing recovery; no transistor CDR qualification.',
    'transport': 'Contract rates, static slots and finite event queues; no electrical GPIO timing qualification.',
    'coexistence': 'Hypothetical shared-supply sensitivity; no extracted die/package network.',
    'measured_conversion': 'Finite recorded LO disturbance sampled by an ideal quantizer; not a calibrated complete RF chain.',
}


def main():
    started = time.perf_counter()
    results = []
    for name in SCREENS:
        path = HERE / name
        before = time.perf_counter()
        result = subprocess.run([sys.executable, str(path)], cwd=HERE.parents[1],
                                capture_output=True, text=True)
        results.append(dict(script=name, returncode=result.returncode,
                            seconds=time.perf_counter() - before,
                            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            stdout=result.stdout, stderr=result.stderr))
        print(f'{name}: {"PASS" if result.returncode == 0 else "FAIL"} '
              f'({results[-1]["seconds"]:.2f}s)', flush=True)
    passed = all(row['returncode'] == 0 for row in results)
    report = dict(status='screens_completed' if passed else 'screen_execution_failed',
                  silicon_qualified=False, seconds=time.perf_counter() - started,
                  coverage=COVERAGE,
                  workflow='spec/fast-feasibility-workflow.md',
                  limitations=['Execution success checks model controls, not physical requirements.',
                               'These are partially connected screens, not a complete chip simulation.',
                               'Measured LO screen requires existing transistor replay evidence.'],
                  results=results)
    (HERE.parent / 'evidence/fast-suite.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
