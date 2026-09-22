"""Combined signed RF nonlinearity/blockers and autonomous-clock coexistence."""
import json
from chip_model import P
from wideband_clock_quality import simulate
from rf_quality_screen import quality


def main():
    blockers=((.1,20e6),(.1,30e6));rows=[]
    for mode in (0,1):
        baseline,times,reference=simulate(mode,False)
        for sign in (-1,1):
            traffic,actual,measured=simulate(mode,True,sign,blockers,sign*.05)
            assert times==actual
            q=quality(reference,measured)
            rows.append(dict(mode=mode,sign=sign,quality=q,traffic=traffic))
            print('Mode',mode,'sign',sign,'relative RMS',q['corrected_relative_rms'],'passes',q['screen_pass'],flush=True)
    report=dict(status='passed',quality_pass=all(r['quality']['screen_pass'] for r in rows),
        cases=rows,blockers=blockers,cubic_magnitude=.05,complete_architecture=False,physical_qualification=False,
        limitations=['Four signed points with one source/noise realization and32 traffic frames are not an uncertainty envelope.',
        'Blocker amplitudes are normalized envelopes, not calibrated antenna power or receiver sensitivity.',
        'Held-out incremental waveform error uses a matched analog/filter reference and one fitted complex gain; not modem EVM.',
        'Actual pump-loop integration, fractional divider edge noise, resource/calibration and overload behavior remain open.'])
    (P/'evidence/connected-wideband-blocker-quality.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
