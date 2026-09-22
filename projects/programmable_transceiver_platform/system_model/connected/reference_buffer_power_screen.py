"""Reference replenishment/sinking balance and existing conversion impulse energy."""
import json
from chip_model import P
from causal_reference_lifecycle import Reference
from reference_buffer_power import account,reservoir_energy_removed

def main():
    rows=[account(v,1.,1000.,3.1) for v in (.98,1.,1.02)]
    for r in rows:
        assert abs(r['balance_error_w'])<1e-18 and r['buffer_dissipation_w']>=0
    assert rows[0]['dc_current_a']>rows[1]['dc_current_a']
    assert rows[2]['dc_current_a']==rows[1]['dc_current_a'] and rows[2]['source_power_w']<0
    r=Reference();v=r.voltage;before=r.charge
    r.sample(0,.2+.1j);q=r.charge-before
    measured=.5*r.c*(v*v-r.voltage*r.voltage)
    expected=reservoir_energy_removed(v,q,r.c)
    assert abs(measured-expected)<1e-25
    try:reservoir_energy_removed(1,2,1)
    except ValueError:pass
    else:raise AssertionError('Overdraw admitted')
    report=dict(status='passed',buffer_cases=rows,adc_charge_c=q,reservoir_energy_removed_j=measured,
        limitations=['Reference RC source energy accounting; not yet connected as driver-supply load.',
            'Nonregenerative efficiency/bias assumptions; headroom/current limits and transistor behavior absent.'])
    (P/'evidence/connected-reference-buffer-power.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
