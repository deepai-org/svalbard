"""Compare vector convolution with scalar, quadrature and ADC lifecycle."""
import json,time
import numpy as np
from scipy.integrate import quad
from chip_model import P
from tx_power_detector import PowerDetector
from vector_power_detector import VectorPowerDetector

def main():
    rng=np.random.default_rng(420)
    errors=[];large=None
    for count in (1,4,16,74):
        for dt in (0.,1e-12,1e-9,200e-9,2e-6):
            terms=list(zip((rng.normal(size=count)+1j*rng.normal(size=count))*.02/count,
                -rng.uniform(0,1e9,count)+1j*rng.uniform(-2e9,2e9,count)))
            if count==74:large=terms
            a=PowerDetector();b=VectorPowerDetector();a.value=b.value=.003
            a.advance(dt,terms);b.advance(dt,terms)
            error=abs(a.value-b.value);assert error<1e-13;errors.append(error)
            a.request();b.request();assert a.pending==b.pending
            a.abort();b.abort();assert a.pending is b.pending is None and a.epoch==b.epoch
    # Coincident pole and nearby cancellation cases, independently integrated.
    for shift in (0.,1e-5,-1e-5):
        b=VectorPowerDetector();dt=100e-9;rate=-b.pole/2+shift
        terms=[(.2+0j,complex(rate))];b.advance(dt,terms)
        expected=quad(lambda t:b.pole*np.exp(-b.pole*(dt-t))*.04*np.exp(2*rate*t),0,dt,epsabs=1e-14)[0]
        assert abs(b.value-expected)<1e-12
    from tx_dac_correction_screen import make
    from tx_output_terms import output_terms
    from tx_output_candidate import PARAMETERS
    from rf_loaded_detector import LoadedDetector,voltage_terms
    tx=make(12);tx.apply_sample(.15+.1j,0.)
    load=LoadedDetector();fast=VectorPowerDetector();physical_errors=[]
    for i in range(100):
        source=output_terms(tx.transmit_terms(),**PARAMETERS)
        terms=voltage_terms(load.network,source)
        end=(i+1)*1e-9
        fast.advance(end,[(complex(v[2]),complex(rate)) for v,rate in terms])
        load.advance(end,source);tx.advance(end)
        physical_errors.append(abs(fast.value-load.detector.value))
        assert physical_errors[-1]<1e-12
    timing={}
    for cls in (PowerDetector,VectorPowerDetector):
        durations=[]
        for repeat in range(3):
            detector=cls();start=time.perf_counter()
            for i in range(100):detector.advance((i+1)*1e-9,large)
            durations.append(time.perf_counter()-start)
        timing[cls.__name__]=float(np.median(durations))
    report=dict(status='passed',max_scalar_difference=max(errors),cases=len(errors),reconstruction_steps=100,max_reconstruction_difference=max(physical_errors),
        median_100_step_seconds=timing,local_speed_ratio=timing['PowerDetector']/timing['VectorPowerDetector'],
        limitations=['Local convolution benchmark, not end-to-end speedup; no timestep or model simplification.',
        'Floating summation order differs; whole-chain regression required before default replacement.'])
    (P/'evidence/connected-vector-power-detector.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
