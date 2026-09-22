"""32x24 one-shot capture bank connected to actual ADC sample words."""
import hashlib,json
from chip_model import P
from shared_supply_lifecycle import CoupledChip
from sustained_lifecycle import run

class CaptureBank:
    def __init__(self):
        self.words=[0]*32;self.count=0;self.enabled=False;self.done=False
    def enable(self,value):
        self.enabled=bool(value)
        if not value:self.count=0;self.done=False
    def sample(self,word):
        if not isinstance(word,int) or not 0<=word<1<<24:raise ValueError('Capture width')
        if self.enabled and not self.done:
            self.words[self.count]=word;self.count+=1;self.done=self.count==32
    def read(self,index):
        if not isinstance(index,int) or not 0<=index<32:raise ValueError('Capture address')
        return self.words[index] if self.done else 0

class CaptureChip(CoupledChip):
    def __init__(self,capture_enabled=True,**kwargs):
        super().__init__(**kwargs)
        self.capture_start=0
        self.capture_bank=CaptureBank();self.capture_bank.enable(capture_enabled)
    def configure_capture(self,enabled):
        if self.session.armed:raise ValueError('Capture configuration requires disarmed state')
        if enabled and not self.capture_bank.enabled:self.capture_start=len(self.adc_words)
        self.capture_bank.enable(enabled)
    def adc_became_valid(self,word,time):
        super().adc_became_valid(word,time);self.capture_bank.sample(word)
    def quiesce(self,time,reason):
        super().quiesce(time,reason);self.capture_bank.enable(False)
    def reference_metrics(self):
        r=super().reference_metrics();b=self.capture_bank
        if b.enabled and len(self.adc_words)-self.capture_start>=32:
            assert b.done and [b.read(i) for i in range(32)]==self.adc_words[self.capture_start:self.capture_start+32]
        r['capture']=dict(enabled=b.enabled,done=b.done,count=b.count,
            data_sha256=hashlib.sha256(json.dumps([b.read(i) for i in range(32)]).encode()).hexdigest())
        return r


def controls():
    b=CaptureBank();b.enable(True)
    for i in range(31):b.sample(i+100)
    assert not b.done and all(b.read(i)==0 for i in range(32))
    b.sample(131);snapshot=[b.read(i) for i in range(32)]
    assert snapshot==list(range(100,132))
    for i in range(100):b.sample(i)
    assert snapshot==[b.read(i) for i in range(32)]
    b.enable(False);assert not b.done and b.count==0 and b.read(0)==0
    b.enable(True)
    for i in range(32):b.sample(1000+i)
    assert b.read(0)==1000 and b.read(31)==1031
    c=CaptureChip();c.configure(0,0)
    while c.state!='active':c.advance(c.next_reference)
    try:c.configure_capture(False)
    except ValueError:pass
    else:raise AssertionError('Live capture configuration accepted')
    for i in range(10):c.capture_bank.sample(i)
    c.set_reference(False,c.time)
    assert c.capture_bank.count==0 and not c.capture_bank.done


def main():
    controls();rows=[]
    for mode in (0,1):
        factory=lambda **kw:CaptureChip(coupling_per_v=1,dac_coupling_per_v=-1,
            return_charge_per_transition=100e-15,frontend=dict(gain_error=.02,noise_rms=.001),**kw)
        row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100,disturbance_sign=1)
        assert row['reference_metrics']['capture']['done']
        rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        rtl_contract_sha256=hashlib.sha256((P/'rtl/pt_memory.sv').read_bytes()).hexdigest(),
        limitations=['Functional capture contract follows32x24 RTL bank; no RTL equivalence or SPI/CDC timing proof.',
        'Capture reads are coherent management accesses; capture-only MCU mode and playback remain to connect.',
        'Mode1 stores16-bit IQ in the low bits of24-bit entries; this packing needs explicit ABI agreement.',
        'Quiesce disables capture in this candidate controller; hardware reset/enable synchronization remains open.'])
    (P/'evidence/connected-capture-memory-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed two integrated capture cases and one-shot/read/reset/ownership controls')

if __name__=='__main__':main()
