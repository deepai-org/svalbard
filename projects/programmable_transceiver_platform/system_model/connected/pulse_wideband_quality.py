"""Both pulse loops with independent wideband RF, shared reference loads and host traffic."""
import json
from chip_model import P
from pulse_chip import PulseChip
from combined_detector_quality import run_quality

PROFILE_PATH=P/'spec/pulse-top-profile.json'
PROFILE=json.loads(PROFILE_PATH.read_text())

class CombinedChip(PulseChip):
    def configure(self,mode,time):
        super().configure(mode,time)
        self.advance(time+PROFILE['settle_s'])
        assert self.state=='active'
        self.detect_start(self.time,self.epoch)
        self.advance(time+PROFILE['detection_end_s'])
        assert self.detect_result(self.epoch)['decision']=='present'
        assert self.probe.drive is None

def main():
    run_quality(CombinedChip, PROFILE, PROFILE_PATH,
                'connected-pulse-wideband-quality.json', pulse=True)

if __name__=='__main__':main()
