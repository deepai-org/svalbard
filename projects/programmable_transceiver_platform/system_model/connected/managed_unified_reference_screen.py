"""Managed analog advance plus real converter transfer/reference-load boundaries."""
import json
from chip_model import P
from managed_unified_reference import ManagedUnifiedReferenceChip

def main():
    c=ManagedUnifiedReferenceChip(adc_latency_s=30e-9,dac_reference_load_capacitance=1e-12)
    r=c.adc_reference;d=c.loaded_tx.driver
    assert r is c.dac_reference is d.reference
    c.advance(100e-9)
    assert r.time==d.time==c.rf_pll.time==c.tx.time==c.time and r.voltage<1
    rail=d.rail_v;charge=r.charge;c.bits=12
    c.convert_adc(.2+.1j)
    c.reference_dac(c.time,.1+.03j)
    assert r.samples==1 and r.dac_updates==1 and r.charge>charge and d.rail_v==rail
    try:r.advance(c.time+1e-9)
    except ValueError:pass
    else:raise AssertionError('Independent reference advance admitted')
    assert r.time==c.time
    c.advance(150e-9)
    assert r is c.dac_reference is d.reference and r.time==d.time==c.time
    c.set_reference(False,c.time);c.advance(180e-9)
    assert r.time==d.time==c.time and not c.tx_cal.valid
    report=dict(status='passed',reference_voltage_v=r.voltage,driver_rail_v=d.rail_v,
        adc_samples=r.samples,dac_updates=r.dac_updates,total_charge_c=r.charge,
        limitations=['Short managed advancement with direct converter-kernel calls; scheduled calibration/payload not verified.',
            'Shared reference candidate only; separate-reference mode explicitly unsupported in this adapter.',
            'Physical rail/reference/driver parameters remain assumptions.'])
    (P/'evidence/connected-managed-unified-reference.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
