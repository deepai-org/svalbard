"""Signed phase sensitivity against an unquantized matched analog reference."""
import json
from chip_model import P
from rf_quality_screen import simulate,quality
from rf_selectivity_screen import butterworth_order
from rf_modulated_quality import Multicarrier


def main():
    order,cutoff=butterworth_order(8e6,20e6,1,30);rows=[];baselines=[]
    for sign in (-1,1):
        wave=Multicarrier()
        baseline,t,reference=simulate(1,sign,'ideal',rx_filter=(order,cutoff),waveform=wave,analog_reference=True)
        baselines.append(dict(sign=sign,quantization=baseline['ideal_adc_quantization_quality']))
        signed=[]
        for phase_scale in (0.,.5,1.):
            stimulus=Multicarrier()
            traffic,times,values=simulate(1,sign,'combined',(20e6,30e6),rx_filter=(order,cutoff),
                waveform=stimulus,phase_scale=phase_scale)
            assert t==times and wave.metadata==stimulus.metadata
            row=dict(mode=1,sign=sign,phase_scale=phase_scale,per_lo_absolute_phase_bound_rad=.15*phase_scale,
                quality=quality(reference,values),traffic=traffic,waveform=stimulus.metadata)
            signed.append(row);rows.append(row)
            print(sign,phase_scale,row['quality']['corrected_relative_rms'],row['quality']['screen_pass'],flush=True)
        assert signed[0]['quality']['corrected_relative_rms']<signed[-1]['quality']['corrected_relative_rms']
        assert not signed[-1]['quality']['screen_pass']
    report=dict(status='passed',cases=rows,ideal_adc_baselines=baselines,complete_architecture=False,physical_qualification=False,
        limitations=['Unquantized reference includes intended TX/RX filtering and DAC codes; measures receive-chain waveform error including ADC quantization, not total link EVM.',
        'Three seeded phase-amplitude points do not establish a continuous or stochastic phase-noise tolerance boundary.',
        'Other impairments, full wanted bandwidth, blockers and10%screen remain fixed; reduced-phase cases are conditional requirements, not improved physical oscillators.',
        'Only mode1 and one multicarrier seed are screened here; independent-source RF reception and autonomous RF clocks remain open.'])
    (P/'evidence/connected-rf-phase-budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Ideal ADC quantization:',baselines)

if __name__=='__main__':main()
