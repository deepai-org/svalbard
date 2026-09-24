"""Independent RF quality during calibrated continuous four-path traffic."""
from warm_chip import WarmTransceiverChip
from managed_resources import command


class PreparedChip(WarmTransceiverChip):
    def __init__(self,initial_mode=0,**kwargs):
        super().__init__(rf_free_offset=.96*.995-1,coarse_noise_bound_hz=80000.,**kwargs)
        assert command(self,"rf_coarse_start",2437000000)["accepted"]
        self.advance(self.time+35e-6)
        first=command(self,'tx_cal_start');assert first['accepted']
        self.advance(self.time+25e-6)
        assert command(self,'tx_cal_commit',first['value'])['accepted']
        assert command(self,'configure_mode',initial_mode)['accepted']
        assert command(self,'stop')['accepted']
        assert command(self,'ack_abort')['accepted'] and command(self,'ack_drain')['accepted']
        assert command(self,'detect_rearm')['accepted']
        assert command(self,"rf_coarse_start",2500000000)["accepted"]
        self.advance(self.time+35e-6)
        assert self.coarse.qualified and self.rf_pll.locked
        for target in (0,1):
            assert command(self,'cal_start',48|(target<<16))['accepted']
            self.advance(self.time+40e-6)
        start=command(self,'tx_cal_start');assert start['accepted']
        self.advance(self.time+25e-6)
        assert command(self,'tx_cal_commit',start['value'])['accepted']
        self.applied_inputs=[]
        original=self.tx.apply_sample
        def observed(value,time):
            original(value,time)
            self.applied_inputs.append(value)
        self.tx.apply_sample=observed

from coarse_quality import simulate as simulate_prepared, run_quality

def simulate(mode,impaired):
    return simulate_prepared(mode,impaired,prepared_class=PreparedChip,
                             initial_options={'initial_mode':mode})

def main():
    return run_quality(simulate,warm=True)

if __name__=='__main__':main()
