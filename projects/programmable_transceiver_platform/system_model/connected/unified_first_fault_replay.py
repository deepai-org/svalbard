"""Replay unchanged unified mode0 traffic with first-fault state observation."""
import json
from chip_model import P
import unified_pad_quality as harness
from managed_unified_reference import ManagedUnifiedReferenceChip

class ObservedUnifiedChip(ManagedUnifiedReferenceChip):
    def __init__(self,**kwargs):
        self.first_fault_written=False
        super().__init__(**kwargs)
    def quiesce(self,time,reason):
        if not self.first_fault_written:
            self.first_fault_written=True
            host=getattr(self,'host_activation',None)
            pll=getattr(self,'rf_pll',None)
            record=dict(time_s=time,reason=reason,state=self.state,epoch=self.epoch,
                prior_events=self.events[-12:],host={} if host is None else {
                    k:getattr(host,k,None) for k in ('state','reason','last','words','epoch','period')},
                pll={} if pll is None else {k:str(v) for k,v in pll.__dict__.items()
                    if isinstance(v,(int,float,bool,str,type(None)))},
                driver_rail_v=self.loaded_tx.driver.rail_v,reference_v=self.adc_reference.voltage,
                calibration_state=self.tx_cal.state,calibration_valid=self.tx_cal.valid)
            (P/'evidence/unified-mode0-first-fault.json').write_text(json.dumps(record,indent=2)+'\n')
            print('FIRST FAULT',json.dumps(record),flush=True)
        return super().quiesce(time,reason)

if __name__=='__main__':
    harness.ManagedUnifiedReferenceChip=ObservedUnifiedChip
    harness.main(0)
