"""Measure plateau and edge-associated compensation in long-acquisition diagnostic."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/sar-long-acquisition.json';e=json.loads(E.read_text());assert e['completed'];p=R/'scratch/transceiver-sar-long-acquisition/baseline.dat';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(p)==e['waveform_sha256']
with p.open() as f:h=f.readline().lower().split()
a=np.loadtxt(p,skiprows=1);t=a[:,0];assert np.isfinite(a).all()
drive=a[:,h.index('v(ip)')]-a[:,h.index('v(in)')];held=a[:,h.index('v(hp)')]-a[:,h.index('v(hn)')];tt=np.r_[88e-9,t[(t>88e-9)&(t<90e-9)],90e-9]
pre=float(np.interp(90e-9,t,held)-.4);post=float(np.interp(90.5e-9,t,held)-.4)
out=dict(completed=True,source_sha256=sha(E),window_ns=[88,90],driver_peak_to_peak_v=float(np.ptp(np.interp(tt,t,drive))),held_peak_to_peak_v=float(np.ptp(np.interp(tt,t,held))),pre_edge_held_error_v=pre,first_clock_held_error_v=post,edge_to_clock_change_v=post-pre,limitations=['One input polarity and ideal references, deliberately extended acquisition.','Near-flat2ns observation is evidence of a plateau, not mathematical proof of DC convergence.','Sampling/command-mask changes coexist; cancellation is not uniquely attributed to charge injection.','No deliberate calibration or robust cancellation mechanism is implemented.'])
(P/'evidence/acquisition-cancellation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
