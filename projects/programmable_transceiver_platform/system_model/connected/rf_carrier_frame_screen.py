"""Independent frame-equivalence checks of the loaded network and detector."""
import copy,json,math
import numpy as np
from chip_model import P
from rf_loaded_detector import LoadedDetector

def main():
    rows=[]
    f0=2.412e9
    for f1,phase in ((2.437e9,.7),(2.387e9,-1.2),(2.412e9,2.1)):
        original=LoadedDetector()
        original.network.voltage=original.network.steady(.2+.1j)
        original.detector.value=.012
        changed=copy.deepcopy(original)
        energy=changed.network.energy();power=changed.detector.value
        rotation=changed.network.reframe(f1,phase)
        assert abs(changed.network.energy()-energy)<1e-27
        assert changed.detector.value==power
        source=[(.15+.03j,0j),(.05-.01j,-1e8+2j*math.pi*4e6)]
        delta=2*math.pi*(f1-f0)
        duration=2e-9
        original.advance(duration,source)
        changed.advance(duration,[(a*rotation,p-1j*delta) for a,p in source])
        expected=original.network.voltage*rotation*np.exp(-1j*delta*duration)
        error=float(max(abs(changed.network.voltage-expected)))
        detector_error=abs(original.detector.value-changed.detector.value)
        assert error<1e-12 and detector_error<1e-12
        # Omitting the coefficient/rate transform must be observably wrong.
        wrong=LoadedDetector();wrong.network.voltage=wrong.network.steady(.2+.1j)
        wrong.network.reframe(f1,phase);wrong.advance(duration,source)
        wrong_error=float(max(abs(wrong.network.voltage-expected)))
        assert wrong_error>1e-3
        rows.append(dict(new_carrier_hz=f1,phase_delta_rad=phase,
            voltage_equivalence_error=error,detector_equivalence_error=detector_error,
            untransformed_source_error=wrong_error))
    r=dict(status='passed',cases=rows,limitations=[
        'Coordinate transform only; physical oscillator retuning and phase-noise interpolation remain separate.',
        'Caller owns frame phase and must transform every source term consistently.',
        'Managed LoadedTxChip remains fixed2412MHz until oscillator trajectory integration is verified.'])
    (P/'evidence/connected-rf-carrier-frame.json').write_text(json.dumps(r,indent=2)+'\n');print(rows)

if __name__=='__main__':main()
