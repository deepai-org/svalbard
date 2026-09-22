"""Managed PLL feedback and shared conversion state survive array optimization."""
import json,time
import numpy as np
from chip_model import P
from managed_guarded_reference import ManagedGuardedReferenceChip
from managed_dense_reference import ManagedDenseReferenceChip

def run(cls):
    c=cls(adc_latency_s=30e-9,resistance=50.,load_capacitance=2e-12,dac_reference_load_capacitance=2e-12)
    start=time.perf_counter();c.advance(100e-9);c.bits=12
    c.convert_adc(.5+.2j);c.reference_dac(c.time,.6+.3j)
    c.advance(150e-9)
    d=c.loaded_tx.driver;r=c.adc_reference
    assert r is c.dac_reference is d.reference and d.detector is c.tx_detector
    assert r.time==d.time==c.rf_pll.time==c.time
    return np.r_[d.network.voltage.real,d.network.voltage.imag,d.rail_v,r.voltage,r.charge,
        c.tx_detector.value,c.tx_detector.readout_value,c.rf_pll.output_phase_cycles],time.perf_counter()-start

def main():
    a,ta=run(ManagedGuardedReferenceChip);b,tb=run(ManagedDenseReferenceChip)
    error=float(np.max(abs(a-b)));assert error<1e-10
    report=dict(status='passed',max_state_difference=error,baseline_s=ta,dense_s=tb,
        observed_speedup=ta/tb,limitations=['Short managed path only; full acquisition/payload equivalence remains.',
        'Wall-time ratio under concurrent load is indicative, not a benchmark guarantee.'])
    (P/'evidence/connected-managed-dense-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
