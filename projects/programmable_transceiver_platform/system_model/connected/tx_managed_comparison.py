"""Compare terminal matched-preparation correction and bypass experiments."""
import hashlib,json
import numpy as np
from chip_model import P

def main():
    root=P/'evidence';names=['connected-managed-tx-quality-mode1','connected-managed-tx-uncorrected-mode1']
    reports=[json.loads((root/(n+'.json')).read_text()) for n in names]
    assert all(r['status'] in ('passed','failed') and len(r['cases'])==1 for r in reports)
    cases=[r['cases'][0] for r in reports]
    traces=[np.load(root/c['traces']) for c in cases]
    assert np.array_equal(traces[0]['time_s'],traces[1]['time_s'])
    assert np.array_equal(traces[0]['ideal_tx'],traces[1]['ideal_tx'])
    for field in ('experiment','host_delay_s','host_warmup','rf_bandwidth_hz','rf_fast_fraction'):
        assert cases[0][field]==cases[1][field],field
    calibrations=[c['traffic']['reference_metrics']['tx_calibration'] for c in cases]
    assert calibrations[0]['probe_powers']==calibrations[1]['probe_powers']
    assert calibrations[0]['candidate']==calibrations[1]['candidate']
    rotations=[t['actual_rotation'] for t in traces]
    delta=np.angle(rotations[0]*rotations[1].conjugate())
    r=dict(status='compared',matched_times=True,matched_ideal=True,matched_calibration=True,
        actual_carrier_rotations_equal=bool(np.array_equal(*rotations)),
        carrier_difference_rms_rad=float(np.sqrt(np.mean(delta**2))),
        corrected_tx_error=cases[0]['quality']['corrected_relative_rms'],
        bypass_tx_error=cases[1]['quality']['corrected_relative_rms'],
        source_reports={n:hashlib.sha256((root/(n+'.json')).read_bytes()).hexdigest() for n in names},
        scope='Same preparation and independent input; any correction-induced analog/supply changes remain part of the live result.')
    (root/'connected-managed-tx-comparison.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
if __name__=='__main__':main()
