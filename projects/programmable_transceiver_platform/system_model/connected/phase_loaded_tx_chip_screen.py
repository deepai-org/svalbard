"""Managed advance ordering smoke test with actual LO and loaded RF states."""
import json
import numpy as np
from chip_model import P
from phase_loaded_tx_chip import PhaseLoadedTxChip
from oscillator_noise import FrequencyNoise

def main():
    rows=[];traces=[]
    for step in (1e-9,.25e-9):
        c=PhaseLoadedTxChip(phase_step_s=step,watchdog_s=1e-3)
        c.rf_pll.set_noise(0,FrequencyNoise.seeded(20000,seed=830))
        c.advance(20e-9)
        # Direct probe injection isolates analog event ordering, not admission.
        c._probe(c.time,.15+.1j)
        values=[]
        for t in np.linspace(25e-9,100e-9,16):
            c.advance(float(t))
            assert c.tx.time==c.loaded_tx.network.time==c.tx_detector.time==c.time
            assert c.rf_pll.time==c.time
            values.append(c.pad_envelope())
        traces.append(np.array(values))
        rows.append(dict(step_s=step,substeps=c.phase_steps,pump_boundaries=c.phase_events,
            max_phase_residual=c.phase_residual,detector_power=c.tx_detector.value,
            final_clock_phase=c.rf_pll.output_phase_cycles))
    difference=float(max(abs(traces[0]-traces[1])))
    assert difference<1e-7
    assert abs(rows[0]['final_clock_phase']-rows[1]['final_clock_phase'])<1e-10
    r=dict(status='passed',cases=rows,max_pad_difference=difference,limitations=[
        'Startup trajectory with direct diagnostic probe; not managed calibration or full traffic quality.',
        'Fixed2412MHz network frame; carrier retarget guard still applies.',
        'Actual autonomous noisy LO drives the network; physical driver supply feedback remains absent.',
        'Finite step comparison, not universal interpolation-error bound.'])
    (P/'evidence/connected-phase-loaded-tx-chip.json').write_text(json.dumps(r,indent=2)+'\n');print(r)

if __name__=='__main__':main()
