"""Shared-rail sensitivity sampled by DAC updates before continuous filtering."""
import json
from chip_model import P
from shared_supply_lifecycle import CoupledChip
from receiver_impairments import ImpairedChip
from sustained_lifecycle import run
from rf_tx_state import RfTxState,controls as tx_controls
from session import Session

def controls():
    tx_controls()
    s=Session();s.configure(0);s.host_ready=True;s.ready.update(rf=True,wire=True);s.arm()
    t=RfTxState(s);g=[.8];t.dac_gain=lambda time:g[0]
    t.accept(.5);t.clock(0);assert t.held==.4
    g[0]=1.2;t.advance(10e-9);assert t.held==.4
    t.accept(.5);t.clock(20e-9);assert t.held==.6
    assert t.accounting()['consumed']==2

def main():
    controls();rows=[]
    for mode in (0,1):
        baseline=run(mode,100,chip_factory=ImpairedChip,disturbance_sign=1)
        for sensitivity in (0,-2,2):
            factory=lambda **kw:CoupledChip(dac_coupling_per_v=sensitivity,
                return_charge_per_transition=100e-15,**kw)
            row=run(mode,100,chip_factory=factory,disturbance_sign=1)
            m=row['reference_metrics']['dac_supply']
            assert m['updates']==row['rf_samples_each_direction']
            if sensitivity==0:assert row['adc_sha256']==baseline['adc_sha256']
            else:
                assert row['adc_sha256']!=baseline['adc_sha256']
                assert m['gain_min']<1 if sensitivity>0 else m['gain_max']>1
            rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['DAC gain samples the rail at updates and holds; continuous feedthrough during hold is omitted.',
        'DAC sensitivity and RC/charge values are uncalibrated; no GF180 capability or worst-case bound.',
        'PLL supply response, domain separation and package inductance remain absent.'])
    (P/'evidence/connected-dac-supply-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six sustained DAC supply cases and hold/accounting controls')

if __name__=='__main__':main()
