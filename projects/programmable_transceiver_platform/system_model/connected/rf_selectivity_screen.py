"""Separate channel-edge stress from stopband selectivity; preserve wanted bandwidth."""
import json,math
from chip_model import P
from rf_quality_screen import simulate,quality


def butterworth_order(pass_hz,stop_hz,pass_loss_db,stop_loss_db):
    if not 0<pass_hz<stop_hz or not 0<pass_loss_db<stop_loss_db:
        raise ValueError('Invalid selectivity envelope')
    p=10**(pass_loss_db/10)-1;s=10**(stop_loss_db/10)-1
    n=math.ceil(math.log(s/p)/(2*math.log(stop_hz/pass_hz)))
    cutoff=pass_hz/p**(1/(2*n))
    return n,cutoff


def loss(f,cutoff,order):return 10*math.log10(1+(f/cutoff)**(2*order))


def main():
    # Explicit candidate requirements, not inferred Wi-Fi compliance limits.
    pass_hz=8e6;stop_hz=20e6;pass_db=1.;stop_db=30.
    order,cutoff=butterworth_order(pass_hz,stop_hz,pass_db,stop_db)
    assert loss(pass_hz,cutoff,order)<=pass_db+1e-12
    assert loss(stop_hz,cutoff,order)>=stop_db
    lower=order-1
    lower_cutoff=pass_hz/(10**(pass_db/10)-1)**(1/(2*lower))
    assert loss(stop_hz,lower_cutoff,lower)<stop_db
    rows=[]
    for mode in (0,1):
        baseline,t,reference=simulate(mode,1,'ideal')
        for frequencies in ((10e6,20e6),(20e6,30e6)):
            traffic,times,values=simulate(mode,1,'combined',frequencies)
            assert times==t
            fs=(40e6 if mode==0 else 20e6)*1.0001
            rows.append(dict(mode=mode,blocker_frequencies_hz=frequencies,
                sampled_alias_frequencies_hz=[(f+fs/2)%fs-fs/2 for f in frequencies],
                quality=quality(reference,values),traffic=traffic,
                reference_adc_sha256=baseline['adc_sha256']))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        candidate_filter=dict(passband_edge_hz=pass_hz,passband_loss_db=pass_db,
            stopband_edge_hz=stop_hz,stopband_loss_db=stop_db,minimum_butterworth_order=order,
            cutoff_hz=cutoff,achieved_stop_loss_db=loss(stop_hz,cutoff,order),
            implemented_in_connected_model=False),
        existing_single_pole=dict(cutoff_hz=10e6,loss_at_8mhz_db=loss(8e6,10e6,1),
            loss_at_10mhz_db=loss(10e6,10e6,1),loss_at_20mhz_db=loss(20e6,10e6,1)),
        limitations=['8MHz/1dB and20MHz/30dB are proposed mathematical screening targets, not validated product or Wi-Fi requirements.',
        '20MHz nominal RF channel does not justify rejecting arbitrary energy at its10MHz edge while claiming unchanged channel support.',
        'Butterworth order is a transfer-function feasibility calculation, not implemented connected filtering or transistor feasibility.',
        'Reported alias locations are nominal tones; LO phase variation creates sidebands and nonlinear products.',
        'A single test tone cannot validate wanted-band distortion; a modulated waveform and actual multipole filter are still required.'])
    (P/'evidence/connected-rf-selectivity-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['candidate_filter']))
    for r in rows:print(r['mode'],r['blocker_frequencies_hz'],r['quality']['corrected_relative_rms'])

if __name__=='__main__':main()
