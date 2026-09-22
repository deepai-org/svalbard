"""Postprocess saved held-out failure without changing its gain fit or gate."""
import json,hashlib
import numpy as np
from chip_model import P

def main():
    path=P/'evidence/connected-guarded-limited-pad-quality-mode1-traces.npz'
    z=np.load(path);x=z['ideal_pad'];y=z['actual_pad'];t=z['time_s'];split=len(x)//4
    g=np.vdot(x[:split],y[:split])/np.vdot(x[:split],x[:split])
    a=g*x[split:];b=y[split:];den=float(np.sum(abs(a)**2))
    radial=float(np.sum((abs(b)-abs(a))**2))/den
    # Exact decomposition, defined even where either waveform is zero.
    angular=float(np.sum(2*(abs(a)*abs(b)-np.real(np.conj(a)*b))))/den
    total=float(np.sum(abs(b-a)**2))/den
    assert abs(radial+angular-total)<1e-12
    report=dict(status='diagnostic_only',trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        validation_samples=len(a),total_relative_rms=float(np.sqrt(total)),
        radial_relative_rms=float(np.sqrt(radial)),angular_relative_rms=float(np.sqrt(max(0,angular))),
        radial_fraction_of_squared_error=radial/total,angular_fraction_of_squared_error=angular/total,
        validation_duration_s=float(t[-1]-t[split]),
        limitations=['Exact radial/angular error identity using original first-quarter complex gain; no refit on validation.',
        'Angular error includes any phase-changing impairment, not solely PLL noise. Radial error does not identify a unique circuit cause.',
        'Diagnostic decomposition does not change or replace the failed 10 percent TX gate.'])
    (P/'evidence/guarded-mode1-tx-error-decomposition.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
