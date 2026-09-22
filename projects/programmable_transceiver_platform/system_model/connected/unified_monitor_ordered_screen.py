"""Unified analog state: active reference monitor through tile, ADC and host."""
import json
from chip_model import P
from managed_unified_reference import ManagedUnifiedReferenceChip
from managed_resources import command

def main():
    rows=[]
    for mode in (0,1):
        c=ManagedUnifiedReferenceChip(watchdog_s=1e-3,adc_latency_s=30e-9)
        assert command(c,'rf_coarse_start',2412000000)['accepted']
        c.advance(c.time+50e-6)
        assert c.coarse.qualified
        print('Coarse acquired',mode,c.time,flush=True)
        assert command(c,'monitor_select',2)['accepted']
        assert command(c,'diagnostic_select',1)['accepted']
        c.configure(mode,c.time)
        c.advance(c.time+60e-6)
        print('Monitor configured',mode,c.state,c.time,flush=True)
        assert c.state=='active'
        start=c.time; updates=c.monitor_updates
        c.capture(64,start+100e-9)
        c.advance(start+6e-6)
        c.host_decoder.finish()
        assert len(c.host_samples)==64 and c.host_samples==c.adc_words
        assert c.monitor_updates>updates and c.monitor_valid and c.monitor_epoch==c.epoch
        assert abs(c.tile.voltage)>0
        r=c.adc_reference;d=c.loaded_tx.driver
        assert r is c.dac_reference is d.reference
        assert r.time==d.time==c.rf_pll.time==c.tx.time==c.time
        status=command(c,'monitor_status')
        assert status['accepted'] and status['value']&256
        count=c.monitor_updates
        c.set_reference(False,c.time)
        c.advance(c.time+1e-6)
        assert not c.monitor_valid and c.monitor_updates==count
        rows.append(dict(mode=mode,host_samples=len(c.host_samples),updates=count,
            tile_voltage=c.tile.voltage,reference_voltage=r.voltage,rail_voltage=d.rail_v,
            reference_loss_invalidated=True))
        print('Monitor transported and invalidated',rows[-1],flush=True)
    report=dict(status='passed',cases=rows,limitations=[
        'Finite diagnostic capture, not simultaneous full-rate payload or rearm qualification.',
        'Ideal monitor buffer and assumed cadence; no physical mux kickback/noise qualification.'])
    (P/'evidence/connected-unified-monitor-transport.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
