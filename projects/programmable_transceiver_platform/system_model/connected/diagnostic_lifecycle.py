"""Coherent diagnostics and limited existing management-register semantics."""
import hashlib,json
from chip_model import P,encode_iq
from local_routing_lifecycle import RoutedChip
from playback_memory_lifecycle import ready
from whole_chip_lifecycle import expect_rejection

class DiagnosticChip(RoutedChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.memory_index=0;self.trims={0x10:0,0x11:0,0x12:0};self.write_rejected=False
    def diagnostic(self,time):
        self.advance(time)
        return dict(time_s=self.time,epoch=self.epoch,state=self.state,mode=self.session.mode,
            armed=self.session.armed,ready=dict(self.session.ready),fault=dict(self.session.fault),
            qualified_loop_lock=getattr(getattr(self,'clock',None),'locked',False),
            rf_tx=self.tx.accounting(),wire_tx=self.wire_accounting(),adc_quantization=dict(self.adc_diagnostics),
            capture=dict(enabled=self.capture_bank.enabled,count=self.capture_bank.count,done=self.capture_bank.done),
            playback=dict(selected=self.playback_selected,index=self.play_index,loaded=sum(w is not None for w in self.playback)),
            rx_route=self.tx.rx_route,rx_gain=self.rx_gain,tx_pole=self.tx.pole,rx_pole=self.tx.rx_pole,
            trim_storage=dict(self.trims),trim_mapping_applied=False,write_rejected=self.write_rejected)
    def write_management(self,address,value,time):
        self.advance(time)
        if not isinstance(value,int) or not 0<=value<65536:raise ValueError('Management word width')
        if address==0x20:self.memory_index=value&31;return
        if self.session.armed:self.write_rejected=True;return
        if address in self.trims:self.trims[address]=value
        elif address==4:self.write_rejected=False
        else:self.write_rejected=True
    def read_management(self,address,time):
        self.advance(time)
        fixed={0:0x5356,1:int(self.session.armed),2:int(self.session.mode==1),4:int(self.write_rejected),
            8:1,0x20:self.memory_index,0x23:int(self.playback_selected)+2*int(self.capture_bank.enabled),
            0x24:int(self.capture_bank.done)}
        if address in fixed:return fixed[address]
        if address in self.trims:return self.trims[address]
        if address in (0x25,0x26):
            sample=self.capture_bank.read(self.memory_index)
            return sample&65535 if address==0x25 else sample>>16
        # Do not fabricate a packed hardware status layout from simulator fields.
        raise ValueError('Register not yet modeled; use named diagnostic snapshot')


def run(mode):
    c=DiagnosticChip(watchdog_s=20e-6)
    c.write_management(0x10,0x1234,0);assert c.read_management(0x10,0)==0x1234
    assert c.read_management(0,0)==0x5356
    expect_rejection(lambda:c.read_management(3,0))
    bits=12 if mode==0 else 8
    for i in range(32):c.write_playback(i,encode_iq(.25+.125j,bits))
    c.select_playback(True);ready(c,mode)
    c.write_management(0x10,0xffff,c.time)
    assert c.read_management(4,c.time)==1 and c.read_management(0x10,c.time)==0x1234
    d=c.diagnostic(c.time);assert d['ready']['rf'] and d['playback']['loaded']==32
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    d=c.diagnostic(start+7.5*c.period)
    assert d['playback']['index']==8 and 0<d['capture']['count']<32
    assert c.read_management(0x25,c.time)==0
    d=c.diagnostic(start+32*c.period+2e-6)
    assert d['capture']['done'] and d['rf_tx']['consumed']==32
    for i in range(32):
        c.write_management(0x20,i,c.time)
        word=c.read_management(0x25,c.time)|(c.read_management(0x26,c.time)<<16)
        assert word==c.adc_words[i]
    c.set_reference(False,c.time);fault=c.diagnostic(c.time)
    assert fault['fault']=={'rf':True,'wire':True} and not any(fault['ready'].values())
    assert c.read_management(0x24,c.time)==0
    # A prior snapshot is immutable even after later engine mutations.
    assert d['capture']['done'] and not fault['capture']['done']
    return dict(mode=mode,completed_snapshot=d,fault_snapshot=fault)


def main():
    rows=[run(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        rtl_source_sha256=hashlib.sha256((P/'rtl/pt_spi.sv').read_bytes()).hexdigest(),
        limitations=['Named diagnostic snapshot has no allocated packed register ABI; address3 status deliberately remains unsupported.',
        'Only listed register semantics are modeled; not full SPI transaction or synchronization equivalence.',
        'Trim codes are stored/read back but have no invented analog mapping; calibration remains open.',
        'Coherent snapshots omit CDC visibility/torn multi-register read behavior.'])
    (P/'evidence/connected-diagnostic-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode diagnostic, capture-readback and rejected-write cases')

if __name__=='__main__':main()
