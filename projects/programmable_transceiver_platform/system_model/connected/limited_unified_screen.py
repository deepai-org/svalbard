"""Finite-current unified advancement, charge impulses, and rollback."""
import json,pickle
from chip_model import P
from managed_limited_reference import ManagedLimitedReferenceChip

def state(c):
    d=c.loaded_tx.driver
    return pickle.dumps((d.time,d.rail_v,d.network.__dict__,d.reference.__dict__,c.rf_pll.__dict__))

def main():
    c=ManagedLimitedReferenceChip(adc_latency_s=30e-9,resistance=50.,load_capacitance=2e-12,dac_reference_load_capacitance=2e-12)
    d=c.loaded_tx.driver;r=c.adc_reference
    assert r is d.reference is c.dac_reference and d.detector is c.tx_detector
    c.advance(100e-9)
    c.bits=12;c.convert_adc(.6+.3j);c.reference_dac(c.time,-.6-.3j)
    charge=r.charge
    c.advance(150e-9)
    assert r.samples==r.dac_updates==1 and r.charge==charge
    assert r.time==d.time==c.time==c.rf_pll.time
    # Force an out-of-envelope driver demand and confirm feedback rollback.
    from driver_pll_feedback import advance_feedback
    from rf_driver_supply import DriverSupplyLaw
    d.law=DriverSupplyLaw(bias_a=.02)
    before=state(c)
    try:advance_feedback(d,c.rf_pll,c.time+100e-9,[(.2+0j,0j)],1e6,1e-9)
    except ValueError:pass
    else:raise AssertionError('Overloaded rail admitted')
    assert state(c)==before
    report=dict(status='passed',reference_voltage_v=r.voltage,rail_v=d.rail_v,charge_c=charge,
        limitations=['Short managed advancement and direct converter calls; acquisition and payload remain.',
        'Exploratory finite-current law; no transistor power/bandwidth qualification.'])
    (P/'evidence/connected-limited-unified.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
