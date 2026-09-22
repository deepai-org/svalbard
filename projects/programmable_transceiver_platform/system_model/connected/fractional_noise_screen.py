"""Narrow fractional-loop candidate with declared oscillator noise and conversion."""
import json
from chip_model import P
from fractional_rf_quality import run

def main():
    rows=[]
    for mode in (0,1):
        for target in (2412000000,2437000000):
            row=run(mode,target,350e3,rf_noise_rms_hz=20000)
            row.update(rf_noise_rms_hz=20000,wire_noise_rms_hz=10000,noise_seed=830)
            rows.append(row)
            print(mode,target,row.get('quality',{}).get('corrected_relative_rms'),row.get('failure'),row['qualified'],flush=True)
    passed=all(r['qualified'] for r in rows)
    (P/'evidence/connected-fractional-noise.json').write_text(json.dumps(dict(status='passed' if passed else 'failed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['One finite spectral realization; source amplitudes are assumptions, not measured PDK noise.',
        'Independent tone with loaded reference and wired/host activity; no wideband blocker or full channel-grid coverage.',
        'Acquisition and run-time failures are retained rather than hidden by successful later lock observations.']),indent=2)+'\n')
    assert passed,'Fractional candidate failed noisy qualification; inspect recorded cases'
if __name__=='__main__':main()
