"""Two-way replenishment, analytical DC endpoint and impulse-state retention."""
import copy,json
from chip_model import P
from driver_sensitive_reference import DriverSensitiveReference
from reference_rail_feedback import ReferenceRail

def main():
    r=DriverSensitiveReference(driver_v_per_v=.05);c=ReferenceRail(r);split=copy.deepcopy(c)
    c.advance(2e-6)
    split.advance(.4e-6);split.advance(2e-6)
    assert abs(c.rail_v-3.09)<1e-8 and abs(r.voltage-.9895)<1e-8
    assert abs(c.rail_v-split.rail_v)<1e-9 and abs(r.voltage-split.reference.voltage)<1e-9
    rail=c.rail_v;charge=r.charge
    r.sample(c.time,.5+.2j)
    assert c.rail_v==rail and r.charge>charge
    c.advance(c.time+10e-9)
    assert c.rail_v<rail # Replenishment, rather than a duplicate supply impulse.
    dip=c.rail_v;c.advance(4e-6)
    assert abs(c.rail_v-3.09)<1e-8 and r.samples==1
    report=dict(status='passed',settled_rail_v=c.rail_v,settled_reference_v=r.voltage,
        replenishment_rail_v=dip,adc_charge_c=r.charge-charge,
        limitations=['Coupled reference/rail only; other driver draw is prescribed2mA in this test.',
            'Actual nonlinear RF driver and PLL must share this state in final integration.',
            'Assumed bias/efficiency/PSRR law; current-limit/dropout and physical qualification absent.'])
    (P/'evidence/connected-reference-rail-feedback.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
