"""Switching-charge impulses perturb pending recovered wired sample timing."""
import json,math
from chip_model import P
from wired_idle_lifecycle import IdleWireChip
from live_wired_lifecycle import LiveReceiver
from sustained_lifecycle import run,TrafficFault

class SupplyWireChip(IdleWireChip):
    def __init__(self,wire_phase_ui_per_v=0.,**kwargs):
        if not math.isfinite(wire_phase_ui_per_v):raise ValueError('Invalid wired phase sensitivity')
        super().__init__(**kwargs);self.wire_sensitivity=wire_phase_ui_per_v
        self.wire_kicks=0;self.wire_max_kick=0.;self.wire_signed_kick=0.
    def supply_impulse(self,time,delta_v):
        super().supply_impulse(time,delta_v)
        rx=self.live_rx
        if rx is None or rx.done or not rx.enabled or not self.wire_sensitivity or delta_v==0:return
        assert rx.time<=time<=rx.next_time()
        kick=self.wire_sensitivity*delta_v
        rx.disturb(time,kick,0)
        self.wire_kicks+=1;self.wire_max_kick=max(self.wire_max_kick,abs(kick));self.wire_signed_kick+=kick
    def reference_metrics(self):
        r=super().reference_metrics()
        r['wired_clock_impulses']=dict(ui_per_v=self.wire_sensitivity,count=self.wire_kicks,
            max_abs_ui=self.wire_max_kick,total_signed_ui=self.wire_signed_kick)
        return r


def main():
    rx=LiveReceiver([],1.25e9,0);rx.step()  # First external launch.
    deadline=rx.sample_time();when=deadline-.00001*rx.ui
    rx.disturb(when,-.0001,0)
    assert rx.next_time()==when and rx.samples==0
    rx.step()
    assert rx.samples==1 and rx.omitted==0 and rx.next_time()>when
    rows=[];failures=[]
    for mode in (0,1):
        baseline=run(mode,100,chip_factory=IdleWireChip,matched_reference=True,host_ppm=-100)
        for k in (0.,-.02,.02):
            factory=lambda **kw:SupplyWireChip(wire_phase_ui_per_v=k,return_charge_per_transition=50e-15,**kw)
            row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
            if k==0:assert row['adc_sha256']==baseline['adc_sha256']
            else:assert row['reference_metrics']['wired_clock_impulses']['count']>0
            rows.append(row)
        # Deliberately extreme coupling must expose failure, never count as passing performance.
        for k in (-100.,100.):
            chips=[]
            def factory(**kw):
                c=SupplyWireChip(wire_phase_ui_per_v=k,return_charge_per_transition=50e-15,**kw);chips.append(c);return c
            try:run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
            except (TrafficFault,AssertionError) as error:
                c=chips[0]
                # Avoid accepting an unrelated assertion or chronological failure.
                rx=c.live_rx
                assert c.wire_kicks>0 and (c.state=='draining' or c.host_wire!=[(i*37+19)%1024 for i in range(len(c.host_wire))])
                failures.append(dict(mode=mode,ui_per_v=k,state=c.state,received_words=len(c.host_wire),
                                     kicks=c.wire_kicks,error_type=type(error).__name__))
            else:raise AssertionError('Extreme switching coupling unexpectedly passed')
    report=dict(status='passed',cases=rows,negative_cases=failures,complete_architecture=False,physical_qualification=False,
        limitations=['UI/V maps instantaneous rail steps into phase kicks only; no continuous supply-to-frequency transfer or calibrated jitter PSD.',
        'Small and extreme sensitivity values are hypothetical brackets, not GF180 capability or a proven tolerance boundary.',
        'Host switching is causal and timing feedback affects future decisions; RF sample clock and wired TX oscillator coupling remain separate gaps.',
        'Framing/transport failure can be exposed; automatic detection of every data-corrupting slip is not implemented.'])
    (P/'evidence/connected-wired-supply-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six signed/zero coupling cases, two baselines and four expected extreme-coupling failures')

if __name__=='__main__':main()
