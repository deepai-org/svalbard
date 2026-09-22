"""Locate timestep sensitivity without relaxing reproduction or convergence gates."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import numpy as np

HERE = Path(__file__).resolve().parent
# Reuse terminal, artifact, prepared-deck and source provenance checks freshly.
with contextlib.redirect_stdout(io.StringIO()):
    checked = runpy.run_path(str(HERE/'check_sar_balance_refinement.py'))
assert 'fine' in checked, 'Both terminal refinement results are required'
P = checked['P']

def at(data, node, t):
    h, a, _ = data
    return np.interp(t, a[:, 0], a[:, h.index('v('+node+')')])

def difference(first, second, node, t):
    if node == 'differential':
        return difference(first, second, 'hp', t)-difference(first, second, 'hn', t)
    return at(second, node, t)-at(first, node, t)

# Sign and peak-location controls independent of transistor data.
t = np.array([0., 1., 2.])
a = (['time','v(hp)','v(hn)'], np.array([[0,0,0],[1,0,0],[2,0,0]]), {})
b = (a[0], np.array([[0,0,0],[1,2,1],[2,0,0]]), {})
assert np.array_equal(difference(a,b,'differential',t), [0,1,0])
assert difference(a,b,'differential',.5) == .5

rows = []
for label in ('baseline', 'instrumented'):
    coarse, fine = checked['coarse'][label], checked['fine'][label]
    grid = np.unique(np.r_[coarse[1][:,0], fine[1][:,0]])
    grid = grid[(grid>=70e-9)&(grid<=209e-9)]
    steps = []
    for hold in (70,120,170):
        for j in range(8):
            start = (hold+5*j)*1e-9
            pre = start+.5e-9  # Start of external comparator clock rising ramp.
            aperture = np.unique(np.r_[start+.3e-9,pre,
                grid[(grid>start+.3e-9)&(grid<pre)]])
            old = float(at(coarse,'hp',pre)-at(coarse,'hn',pre))
            new = float(at(fine,'hp',pre)-at(fine,'hn',pre))
            steps.append(dict(hold_ns=hold, bit=7-j, preclock_time_ns=pre*1e9,
                coarse_preclock_residue_v=old, fine_preclock_residue_v=new,
                preclock_residue_change_v=new-old,
                preclock_sign_matches=bool((old<=0)==(new<=0)),
                maximum_preclock_200ps_difference_v=float(max(abs(difference(coarse,fine,'differential',aperture))))))
    # Scheduled PWL boundaries from this fixture: compare labels, not an assumed
    # internal switching time. These offsets do not identify a device mechanism.
    boundaries = [(hold+5*j+offset, name) for hold in (70,120,170)
                  for j in range(8) for offset,name in
                  ((.5,'CLK rise start'),(.6,'CLK rise end'),
                   (2.5,'UPDATE rise start'),(2.6,'UPDATE rise end'),
                   (3.4,'CLK fall start'),(3.5,'CLK fall end / UPDATE fall start'),
                   (3.6,'UPDATE fall end'))]
    peaks = {}
    for node in ('hp','hn','vh','vl','differential'):
        delta = difference(coarse,fine,node,grid)
        index = int(np.argmax(abs(delta)))
        when = float(grid[index]*1e9)
        boundary,name = min(boundaries,key=lambda item: abs(item[0]-when))
        peaks[node] = dict(time_ns=when, signed_fine_minus_coarse_v=float(delta[index]),
            nearest_external_boundary=name, boundary_ns=boundary, offset_ps=(when-boundary)*1000)
    rows.append(dict(circuit=label, peaks=peaks, decisions=steps,
        maximum_preclock_residue_change_v=max(abs(s['preclock_residue_change_v']) for s in steps),
        minimum_fine_preclock_margin_v=min(abs(s['fine_preclock_residue_v']) for s in steps)))
report = dict(results=rows, numerical_convergence_established=False,
    source_report_sha256=hashlib.sha256((P/'evidence/sar-balance-refinement.json').read_bytes()).hexdigest(),
    analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    waveform_hashes=checked['out']['waveform_hashes'],
    limitations=['One refinement and linear interpolation do not establish numerical convergence.',
      'Preclock 200ps window is a diagnostic, not the physical comparator aperture.',
      'External PWL boundaries are not measured internal switching events.',
      'Matching sampled signs does not bound offset, kickback, noise or metastability.'])
(P/'evidence/sar-refinement-localization.json').write_text(json.dumps(report,indent=2)+'\n')
for row in rows:
    print(row['circuit'], 'peak',row['peaks']['differential'],
          'preclock change',row['maximum_preclock_residue_change_v'],
          'minimum fine margin',row['minimum_fine_preclock_margin_v'])
