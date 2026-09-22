"""ADC aperture versus DAC reference-load ordering in the unified rail model."""
import json
from chip_model import P
from rf_driver_transient import CoupledDriver
from driver_sensitive_reference import DriverSensitiveReference

def run(skew,adc_first=False):
    ref=DriverSensitiveReference(driver_v_per_v=.05)
    d=CoupledDriver(reference=ref);d.advance(1e-6,.2+0j)
    origin=d.time;rail=d.rail_v
    events=[(origin,'adc'),(origin+skew,'dac')]
    # Shift both timestamps to keep the initial state common for signed skews.
    shift=max(0.,-skew)
    events=[(t+shift,name) for t,name in events]
    events.sort(key=lambda item:(item[0],0 if item[1]==('adc' if adc_first else 'dac') else 1))
    sampled=None
    for t,name in events:
        d.advance(t,.2+0j)
        if name=='adc':sampled=ref.sample(t,.4+.2j)
        else:ref.dac_update(t,.3+.1j,1e-12)
    d.advance(origin+shift+abs(skew)+25e-9,.2+0j)
    assert ref.samples==ref.dac_updates==1 and ref.time==d.time
    return dict(skew_s=skew,tie_order='adc_first' if adc_first else 'dac_first',
        adc_normalized_i=sampled.real,adc_normalized_q=sampled.imag,
        initial_rail_v=rail,final_rail_v=d.rail_v,reference_charge_c=ref.charge)

def main():
    rows=[run(s) for s in (-1e-9,0.,1e-9)]+[run(0.,True)]
    delta=rows[1]['adc_normalized_i']-rows[3]['adc_normalized_i']
    assert delta>0
    report=dict(status='characterized',cases=rows,coincident_order_delta_i=delta,
        delta_in_12bit_lsb=delta*2048,
        limitations=['Local converter reference impulse ordering; no transistor aperture or kickback model.',
            'Both tie orders are sensitivity cases, not a claim that event order is interchangeable.',
            'Scheduled managed-path convention and physical skew envelope must be reconciled.'])
    (P/'evidence/connected-unified-aperture-order.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
