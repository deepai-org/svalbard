"""Native-pad 8 pF screen; host thresholds, assumed aperture, no host timing proof."""
import hashlib
import json
from pathlib import Path
import numpy as np
from run_gpio_transient import run_case, crossing, stimulus, START, UI, N

work = Path('/work')
results = []
for pattern in ('alternating', 'prbs7'):
    result = run_case(work, 'typical', 3.3, 25, 8, pattern)
    t, a, k, d, c, ivd, ivc = np.loadtxt(work/result['case']/'wave.txt', skiprows=1).T
    edges_in = crossing(t, k, 1.65)
    edges_out = crossing(t, c, 1.65)
    bits, _ = stimulus(pattern, 3.3)
    if len(edges_out) < sum(x < START+(N-4)*UI for x in edges_in):
        raise ValueError('missing clock edge')
    margins = []
    for ti, to in zip(edges_in, edges_out):
        sample = int(np.floor((ti-START)/UI))
        if not 8 <= sample < N-4:
            continue
        lo, hi = to-.2e-9, to+.2e-9
        # Include every recorded interior point, plus interpolated boundaries.
        values = np.concatenate((np.interp([lo, hi], t, d), d[(t > lo) & (t < hi)]))
        margins.append(float(min(values-2.0) if bits[sample] else min(.8-values)))
    if len(margins) != 20:
        raise ValueError('unexpected sample count')
    result['host_threshold_screen'] = {
        'vil_max_v': .8, 'vih_min_v': 2.0,
        'clock_reference_v': 1.65, 'assumed_aperture_ns': .4,
        'minimum_margin_v': min(margins), 'failures': sum(m < 0 for m in margins),
        'sampled_bits': len(margins), 'qualified': False}
    results.append(result)
report = {'scope': 'nominal native-pad 8 pF load screen, not FPGA electrical/timing qualification',
          'source_url': 'https://docs.amd.com/v/u/en-US/ds181_Artix_7_Data_Sheet',
          'source_revision': 'DS181 v1.27.1, July 3 2024',
          'source_pdf_sha256': '3f0cb482d645e217ae834e9370c1320300abb85a8046287250f9a48856aed070',
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'native_runner_sha256': hashlib.sha256(Path(__file__).with_name('run_gpio_transient.py').read_bytes()).hexdigest(),
          'results': results,
          'limitations': ['8 pF covers specified FPGA die capacitance only, no package/PCB.',
                         'Assumed aperture is not Artix pin setup/hold closure.',
                         'Only nominal GF180 process, 3.3 V and 25 C; ideal supplies.',
                         'No H2D, SSO, extracted routing, host implementation or interoperability proof.']}
(work/'artix-load.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
