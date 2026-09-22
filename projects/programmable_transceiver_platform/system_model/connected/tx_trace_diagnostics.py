"""Offline phase diagnostics from preserved TX observations; no circuit rerun."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from rf_quality_screen import quality

def analyze(path):
 with np.load(path) as z:
    t=z['time_s'];x=z['ideal_tx'];y=z['actual_tx'];ip=z['ideal_rotation'];ap=z['actual_rotation']
 dt=float(np.median(np.diff(t)))
 if not np.allclose(np.diff(t),dt,atol=1e-15,rtol=0):raise ValueError('Nonuniform recorded trace')
 phase=np.unwrap(np.angle(ap*np.conjugate(ip)))
 n=len(t)//4;relative=t-t[0];weights=abs(x[:n])**2
 # Training-only fitted frequency drift; diagnostic, never used by the gate.
 design=np.column_stack((np.ones(n),relative[:n]*1e6))
 fit=np.linalg.lstsq(design*np.sqrt(weights[:,None]),phase[:n]*np.sqrt(weights),rcond=None)[0]
 cfo=float(fit[1]*1e6/(2*np.pi));predicted=fit[0]+fit[1]*relative*1e6
 centered=phase-float(np.mean(phase));psd=abs(np.fft.rfft(centered*np.hanning(len(t))))**2
 f=np.fft.rfftfreq(len(t),dt);indices=np.argsort(psd[1:])[-5:][::-1]+1
 train_gain=np.vdot(x[:n],y[:n])/np.vdot(x[:n],x[:n])
 validation_gain=np.vdot(x[n:],y[n:])/np.vdot(x[n:],x[n:])
 bias=abs(validation_gain-train_gain)/abs(train_gain)
 residual=np.sqrt(np.sum(abs(y[n:]-validation_gain*x[n:])**2)/np.sum(abs(x[n:])**2))/abs(train_gain)
 gate=quality(x.tolist(),y.tolist())
 assert abs(bias*bias+residual*residual-gate['corrected_relative_rms']**2)<1e-12
 return dict(training_to_validation_gain_shift_relative_rms=float(bias),
    within_validation_residual_relative_rms=float(residual),
    decomposition_scope='Orthogonal diagnostic using a held-out oracle gain; not a permitted calibration or qualification substitution.',trace=str(path),trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    observations=len(t),phase_span_rad=float(np.ptp(phase)),phase_rms_about_mean_rad=float(np.std(phase)),
    training_fitted_frequency_offset_hz=cfo,heldout_phase_rms_after_training_linear_fit_rad=float(np.sqrt(np.mean((phase[n:]-predicted[n:])**2))),
    dominant_phase_bins_hz=[float(f[i]) for i in indices],
    uncorrected_gate=quality(x.tolist(),y.tolist()),
    frequency_fit_diagnostic=quality(x.tolist(),(y*np.exp(-2j*np.pi*cfo*relative)).tolist()),
    scope='Offline diagnostics only. Fitted frequency correction does not change the qualification gate; FFT bins are finite-record features, not identified device noise sources.')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('trace',type=Path);parser.add_argument('--output',type=Path,required=True)
 a=parser.parse_args();a.output.write_text(json.dumps(analyze(a.trace),indent=2)+'\n')
