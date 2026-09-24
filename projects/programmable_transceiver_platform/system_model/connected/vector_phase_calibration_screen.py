"""Managed loaded calibration, multiple DAC events and stopped charge."""
import json
from chip_model import P
from phase_loaded_calibration_screen import run_calibration
from vector_loaded_tx import VectorPhaseLoadedTxChip

def main():
    report=run_calibration(VectorPhaseLoadedTxChip)
    baseline=json.loads((P/'evidence/connected-phase-loaded-calibration.json').read_text())
    for key in ('probe_powers','correction','dac_updates','phase_substeps','phase_events'):
        assert report[key]==baseline[key],key
    for key in ('before_stop_pad_magnitude','after_stop_pad_magnitude','max_phase_residual'):
        assert abs(report[key]-baseline[key])<1e-12,key
    report['scalar_comparison']='Matching saved scalar codes, coefficients, event counts and pad endpoints'
    (P/'evidence/connected-vector-phase-loaded-calibration.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
