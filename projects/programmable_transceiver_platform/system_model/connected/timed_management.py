"""Bounded named management transactions with serialized transport and epoch fencing."""
import heapq,json,math,copy
from chip_model import P
from external_rf_lifecycle import ExternalChip
from wired_equalizer import EqualizerControls
from resource_inventory import RESOURCES,resource_word
from playback_memory_lifecycle import ready
from whole_chip_lifecycle import expect_rejection

class ManagedChip(EqualizerControls,ExternalChip):
    def __init__(self,spi_hz=20e6,control_hz=40e6,control_phase_s=0.,command_capacity=4,**kwargs):
        if not all(math.isfinite(v) and v>0 for v in (spi_hz,control_hz)) or not math.isfinite(control_phase_s) or control_phase_s<0 or not isinstance(command_capacity,int) or command_capacity<1:
            raise ValueError('Invalid management timing')
        super().__init__(**kwargs)
        self.spi_period=1/spi_hz;self.control_period=1/control_hz;self.control_phase=control_phase_s
        self.local_rx_offset_s=10e-9
        self.command_capacity=command_capacity;self.command_events=[];self.command_results={}
        self.command_outstanding=set();self.command_index=0;self.bus_free=0.
    def submit(self,operation,time,expected_epoch,expected_generation,payload=0):
        if operation not in ('resource_status','resource_count','status','ack_wire_idle','clear_adc_diagnostics','configure_rx','write_playback','select_playback','capture_enable','read_capture','configure_mode','configure_wire_rx','configure_wire_tx','configure_local_timing','configure_rf_carrier','start_local','stop','ack_abort','ack_drain') or not math.isfinite(time) or time<self.time or not all(isinstance(v,int) and 0<=v<2**32 for v in (expected_epoch,expected_generation)):
            raise ValueError('Invalid management request')
        if not isinstance(payload,int) or not 0<=payload<2**32:raise ValueError('Management payload width')
        self.advance(time)
        if self.command_index>=65536:raise OverflowError('Management token space requires a new transport session')
        if len(self.command_outstanding)>=self.command_capacity:raise OverflowError('Management queue full')
        start=max(time,self.bus_free);arrival=start+128*self.spi_period
        edge=math.ceil((arrival-self.control_phase)/self.control_period)
        apply_time=self.control_phase+(edge+2)*self.control_period
        # Explicit separate128-bit response transaction, after response data exists.
        reply_time=apply_time+128*self.spi_period
        token=self.command_index;self.command_index+=1;self.bus_free=reply_time
        self.command_outstanding.add(token)
        heapq.heappush(self.command_events,(apply_time,token,'apply',dict(operation=operation,
            epoch=expected_epoch,generation=expected_generation,payload=payload,reply_time=reply_time)))
        return token,apply_time,reply_time
    def read_reply(self,token,time):
        self.advance(time)
        if token not in self.command_results:raise ValueError('Reply not yet visible or unknown token')
        return dict(self.command_results[token])
    def execute_management(self,operation,payload,time):
        if operation=='resource_count':
            if payload:raise ValueError('Reserved capability payload')
            return dict(value=len(RESOURCES))
        elif operation=='resource_status':
            return dict(value=resource_word(self,payload))
        elif operation=='configure_rx':
            if payload>>8:raise ValueError('Reserved RX configuration bits')
            routes=('loopback','external_tone','mute');gains=(.5,1,2);bands=(2e6,5e6,10e6,20e6)
            route=payload&3;gain=(payload>>2)&3
            if route>=3 or gain>=3:raise ValueError('Invalid RX route/gain encoding')
            self.configure_rx(routes[route],gains[gain],bands[(payload>>4)&3],bands[(payload>>6)&3],
                self.tx.external_amplitude,self.tx.external_frequency)
        elif operation=='configure_wire_rx':
            if payload>=4:raise ValueError('Invalid RX equalizer encoding')
            self.configure_wire_rx((0.,.5,1.,2.)[payload])
        elif operation=='configure_wire_tx':
            if payload>>4 or (payload&3)>=3 or ((payload>>2)&3)>=3:raise ValueError('Invalid wired TX encoding')
            self.configure_wire_tx((.25,.5,1.)[payload&3],(0.,.25,.5)[(payload>>2)&3])
        elif operation=='write_playback':
            if payload>>29:raise ValueError('Reserved playback bits')
            self.write_playback(payload>>24,payload&0xffffff)
        elif operation in ('select_playback','capture_enable','configure_mode'):
            if payload not in (0,1):raise ValueError('Invalid binary configuration')
            if operation=='select_playback':self.select_playback(bool(payload))
            elif operation=='capture_enable':self.configure_capture(bool(payload))
            else:self.configure(payload,time)
        elif operation=='configure_rf_carrier':
            tune=getattr(self,'configure_rf_carrier',None)
            if tune is None:raise ValueError('RF tuning unavailable in this model profile')
            tune(payload)
        elif operation=='configure_local_timing':
            if self.session.armed:raise ValueError('Local timing requires disarmed state')
            # Signed 16-bit offset in control-clock periods; upper bits reserved.
            if payload>>16:raise ValueError('Reserved local timing bits')
            ticks=payload if payload<32768 else payload-65536
            self.local_rx_offset_s=ticks*self.control_period
        elif operation=='start_local':
            flags=payload&3;count=(payload>>2)&0xffff;delay=payload>>18
            if flags==0 or count!=32 or delay<1:
                raise ValueError('Local run requires selected direction(s),32 samples and future start')
            if flags&1 and not self.playback_selected:raise ValueError('Local TX requires playback memory selection')
            if flags&2 and (not self.capture_bank.enabled or self.capture_bank.done):
                raise ValueError('Local RX requires armed fresh capture bank')
            # These schedule methods assign new scheduler/codec objects and read
            # shared analog state; they do not advance time or mutate that state.
            # Stage both directions so a failing second schedule cannot start TX.
            candidate=copy.copy(self);start=time+delay*self.control_period
            if flags&1:candidate.schedule(count,start)
            if flags&2:candidate.capture(count,start+self.local_rx_offset_s)
            planner=getattr(candidate,'plan_local_converter_clocks',None)
            if planner is not None:planner(start,self.local_rx_offset_s,flags)
            self.__dict__.update(candidate.__dict__)
            return dict(value=count|(flags<<16))
        elif operation=='read_capture':
            if payload>=32:raise ValueError('Capture index range')
            return dict(value=self.capture_bank.read(payload))
        else:
            if payload:raise ValueError('Reserved command payload')
            if operation=='ack_wire_idle':self.acknowledge_wire_idle(time)
            elif operation=='clear_adc_diagnostics':self.clear_adc_diagnostics()
            elif operation=='stop':self.quiesce(time,'management stop')
            elif operation=='ack_abort':self.acknowledge_host_abort(self.epoch,time)
            elif operation=='ack_drain':
                self.acknowledge_drain(self.epoch,time)
                return dict(value=self.epoch)
            elif operation=='status':return dict(idle=self.detector.idle,idle_latched=self.rx_idle_latched,
                                                adc_clipped=min(65535,self.adc_diagnostics['clipped_samples']),capture_done=self.capture_bank.done)
        return {}

    def advance(self,time):
        while self.command_events and self.command_events[0][0]<=time:
            when,token,stage,data=heapq.heappop(self.command_events)
            super().advance(when)
            if stage=='reply':
                self.command_results[token]=data;self.command_outstanding.remove(token);continue
            result=dict(token=token,operation=data['operation'],applied_at=when,epoch=self.epoch,
                        generation=self.rx_generation,accepted=False)
            if data['epoch']!=self.epoch or data['generation']!=self.rx_generation:
                result['reason']='stale epoch or receive generation'
            else:
                try:
                    result.update(self.execute_management(data['operation'],data['payload'],when))
                    result['accepted']=True
                except ValueError as error:result['reason']=str(error)
            heapq.heappush(self.command_events,(data['reply_time'],token,'reply',result))
        super().advance(time)


def run(mode,phase):
    c=ManagedChip(control_phase_s=phase,watchdog_s=50e-6)
    c.external_source([.2+.1j],0,25e-9);ready(c,mode)
    c.incoming_wire([1023]*64,c.time);rx=c.live_rx
    while rx.framer.state!='PAYLOAD':c.advance(rx.next_time())
    c.set_wire_swing(c.time,0);c.advance(c.time+24*rx.ui)
    assert c.rx_idle_latched
    c.advance(rx.stop+100e-9);c.set_wire_swing(c.time,1);c.advance(c.time+24*rx.ui)
    assert c.detector.idle is False
    c.capture(32,c.time+1e-6)
    token,apply_time,reply_time=c.submit('ack_wire_idle',c.time,c.epoch,c.rx_generation)
    c.advance(apply_time-1e-12);assert not c.rx_idle_ack
    expect_rejection(lambda:c.read_reply(token,c.time))
    c.advance(apply_time);assert c.rx_idle_ack
    expect_rejection(lambda:c.read_reply(token,c.time))
    reply=c.read_reply(token,reply_time);assert reply['accepted']
    # Queue another old-generation acknowledgement, then change generation before it applies.
    old,old_apply,old_reply=c.submit('ack_wire_idle',c.time,c.epoch,c.rx_generation)
    c.incoming_wire([0x123],c.time)
    c.advance(old_apply);assert not c.rx_idle_ack and c.rx_generation==2
    stale=c.read_reply(old,old_reply);assert not stale['accepted'] and stale['reason']=='stale epoch or receive generation'
    status,_,status_reply=c.submit('status',c.time,c.epoch,c.rx_generation)
    snap=c.read_reply(status,status_reply);assert snap['accepted'] and snap['generation']==2
    snap['generation']=999;assert c.read_reply(status,c.time)['generation']==2
    c.host_decoder.finish();assert c.host_samples==c.adc_words and len(c.host_samples)==32
    return dict(mode=mode,control_phase_s=phase,rf_samples=len(c.host_samples),ack=reply,stale=stale,status=c.read_reply(status,c.time))


def controls():
    c=ManagedChip(command_capacity=1)
    token,apply_time,reply_time=c.submit('status',0,c.epoch,c.rx_generation)
    try:c.submit('status',0,c.epoch,c.rx_generation)
    except OverflowError:pass
    else:raise AssertionError('Queue capacity ignored')
    c.advance(reply_time);assert c.read_reply(token,c.time)['accepted']
    # An epoch change invalidates queued writes without making transport disappear.
    c=ManagedChip(watchdog_s=50e-6);ready(c,0)
    token,_,reply_time=c.submit('clear_adc_diagnostics',c.time,c.epoch,c.rx_generation)
    c.set_reference(False,c.time);epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    reply=c.read_reply(token,reply_time);assert not reply['accepted'] and reply['reason']=='stale epoch or receive generation'


def main():
    controls();rows=[run(m,p) for m in (0,1) for p in (0.,7e-9)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        contract=['Serialized128-bit request, next control edge plus two control cycles, then separate128-bit response.',
        'Candidate fields:16-bit header/status,16-bit token,32-bit epoch,32-bit RX generation,32-bit payload; timestamps are trace metadata, not wire fields.',
        'Status payload carries flags and a saturating16-bit clipped-sample count; token exhaustion rejects new commands rather than wrapping.',
        'Queue capacity counts requests until response visibility; commands act at arrival and replies retain that snapshot.',
        'Every command is fenced by explicit expected global epoch and wired RX generation; stale writes are rejected.'],
        limitations=['Named transaction abstraction, not the existing single-word SPI/register ABI; four-word assembly and generation fields still need hardware implementation.',
        'No stochastic metastability model; stated CDC delay is a bounded assumption.',
        'Timed adapter covers status, RX idle acknowledgement, ADC diagnostics, RX settings, playback/capture, mode and stop/abort/drain; LO/trim/calibration and autonomous run controls remain open.'])
    (P/'evidence/connected-timed-management.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four timed management cases, bounded queue and stale-epoch controls')

if __name__=='__main__':main()
