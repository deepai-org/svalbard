"""Measure load bias coverage before choosing independent device-sweep points."""
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import numpy as np

P = Path(__file__).resolve().parents[1]
R = P.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        shared = runpy.run_path(str(P/'verification/check_sar_balance_refinement.py'))
    rows = []
    hashes = {}
    sources = None
    for name in ('reference-bias-observation', 'reference-charge-validation'):
        header, data, result = shared['load'](name)
        assert sources is None or sources == result['sources_before']
        sources = result['sources_before']
        hashes[name] = result['artifacts_sha256']['.dat']
        t = data[:,0]
        # Explicit endpoints, not just whichever adaptive steps happen to land.
        grid = np.r_[70e-9,t[(t>70e-9)&(t<209e-9)],209e-9]
        for rail, drain, gate in [('xhigh','vh','rbn'),('xlow','vl','rbp')]:
            row = dict(stimulus=name, rail=rail, interval_s=[70e-9,209e-9])
            for port,node in [('drain',drain),('gate',gate)]:
                trace = data[:,header.index('v('+node+')')]
                values = np.interp(grid,t,trace)
                row[port] = dict(minimum_v=float(min(values)), maximum_v=float(max(values)),
                    minimum_time_s=float(grid[np.argmin(values)]),
                    maximum_time_s=float(grid[np.argmax(values)]),
                    full_run_minimum_v=float(min(trace)),full_run_maximum_v=float(max(trace)))
            rows.append(row)
    sweep = []
    for rail in ('xhigh','xlow'):
        group = [row for row in rows if row['rail']==rail]
        item = dict(rail=rail)
        for port,step in [('drain',.01),('gate',.001)]:
            low = min(row[port]['minimum_v'] for row in group)
            high = max(row[port]['maximum_v'] for row in group)
            # At least one grid increment outside both observed extrema.
            bounds = [step*(math.floor(low/step)-1),step*(math.ceil(high/step)+1)]
            assert bounds[0] < low <= high < bounds[1]
            item[port+'_bounds_v'] = bounds
        sweep.append(item)
    report = dict(rows=rows, proposed_independent_sweep=sweep, waveform_hashes=hashes,
        source_hashes={Path(__file__).name:sha(Path(__file__)),
                       'check_sar_balance_refinement.py':sha(P/'verification/check_sar_balance_refinement.py')},
        physical_qualification=False, limitations=[
            'Envelope covers two simulated stimuli at one corner and temperature, not all code histories.',
            'Proposed sweep rectangle includes unobserved drain/gate combinations as conservative coverage.',
            'Rounded bounds include guard margins, not a process, mismatch or package uncertainty bound.',
            'Operating interval excludes startup; full-run extrema are reported separately.'])
    (P/'evidence/reference-load-bias-envelope.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(sweep,indent=2))

if __name__ == '__main__':
    main()
