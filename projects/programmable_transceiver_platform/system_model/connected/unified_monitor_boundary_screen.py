"""Serialized monitor selection and coupled-reference read ownership while quiet."""
import json,pickle
from chip_model import P
from managed_resources import command
from managed_unified_reference import ManagedUnifiedReferenceChip

def main():
    c=ManagedUnifiedReferenceChip(adc_latency_s=30e-9,watchdog_s=1e-3)
    assert command(c,'monitor_select',2)['accepted']
    print('Reference monitor selected',c.time,flush=True)
    r=c.adc_reference
    before=pickle.dumps(r.__dict__)
    observed=c.monitor_value(c.time)
    assert observed==1-r.voltage and pickle.dumps(r.__dict__)==before
    try:c.monitor_value(c.time+1e-9)
    except ValueError:pass
    else:raise AssertionError('Monitor advanced reference without analog owner')
    assert pickle.dumps(r.__dict__)==before
    status=command(c,'monitor_status');assert status['accepted']
    assert not status['value']&256 # Quiet startup is not a qualified monitor sample.
    assert r.time==c.time==c.tx.time==c.loaded_tx.driver.time
    assert r.samples==r.dac_updates==0
    report=dict(status='passed',monitor_route=c.monitor_route,monitor_status=status['value'],
        observed_reference_error_v=observed,reference_voltage_v=r.voltage,
        limitations=['Quiet serialized selection/read ownership; active cadence, tile/ADC transport and recovery remain to test.',
            'Monitor buffer loading/noise and physical detection freshness are not qualified.'])
    (P/'evidence/connected-unified-monitor-boundary.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
