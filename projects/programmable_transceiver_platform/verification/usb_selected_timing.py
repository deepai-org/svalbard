"""Causal direct-stream USB exchange with finite CDC and an external FPGA parser.

Analog reception is assigned an 8-UI tail, not transistor simulation. Host GPIO
capture is ideal after its allocated cycle/board delay. This is a component
system model, not a synthesized controller or canonical whole-chip integration.
An optional BehavioralChip owns transport and monitors startup/reference/faults;
an attached shared pad supplies sampled RX levels and verifies TX levels.
Sampling phase/boundaries and the common dynamic environment remain unqualified.
"""
import math
from dataclasses import asdict
from copy import deepcopy
import sys
from pathlib import Path
from collections import deque
P=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(P/'system_model/connected'),str(P/'system_model/architecture_fast')]
from direct_stream import Decoder,Credits,encode,word,START,END,SampledBurstRecords
from block_receiver_model import BlockFIFO
from bit_event_stream import RawBurstPlayback
from protocol_pad import usb_hs_packet,usb_hs_decode_packet,USBStreamingPacket


def response_bound(*,host_hz=100e6,fpga_s=120e-9,replay_tail_ui=8,
                   analog_s=16e-9,board_margin_s=20e-9):
    if not all(math.isfinite(v) and v>=0 for v in (host_hz,fpga_s,replay_tail_ui,analog_s,board_margin_s)) or host_hz<=0:
        raise ValueError('invalid timing allocation')
    # Conservative nonoverlapped bound. Three RX beats cover partial count/data/end.
    costs=dict(receive_tail=replay_tail_ui/480e6,packing=8/480e6,
               quiet=4/480e6,rx_cdc=3/host_hz,rx_tail_beats=3/host_hz,
               fpga_capture=1/host_hz,fpga=fpga_s,
               tx_phase=1/host_hz,tx_start_prefill=5/host_hz,
               tx_cdc=3/240e6,launch_retime=1/480e6,
               analog=analog_s,board=board_margin_s)
    worst=sum(costs.values());maximum=192/480e6
    return dict(costs_s=costs,worst_s=worst,maximum_s=maximum,minimum_s=8/480e6,
                margin_s=maximum-worst,admissible=worst<=maximum,
                fpga_allowance_s=maximum-(worst-fpga_s))


def require_usb_configuration(configuration):
    from design_definition import ResolvedConfiguration
    if (not isinstance(configuration,ResolvedConfiguration) or configuration.engine!='wire'
            or configuration.wired_pad_path!='bidirectional' or configuration.line_rate_bps!=480e6
            or configuration.direction!='duplex' or configuration.host_clock_source!='host_follow'):
        raise ValueError('USB exchange requires a resolved bidirectional 480 Mb/s configuration')


def configured_response_bound(configuration, *, fpga_s=None):
    """Resolve allocations from the snapshot; never use primitive defaults.

    The event implementation below has a fixed CDC/framing pipeline. Reject a
    design with another pipeline until that implementation is extended, instead
    of reporting a new budget while still exercising the old circuit.
    """
    require_usb_configuration(configuration)
    b=configuration.design.architecture['direct_stream_service']['budget']
    implemented=dict(host_edges='SDR',line_hz=480e6,tx_fifo_read_hz=240e6,
        rx_tail_ui=8,packing_ui=8,quiet_ui=4,rx_cdc_host_cycles=3,
        rx_tail_beats=3,fpga_capture_cycles=1,tx_phase_cycles=1,
        tx_start_and_prefill_beats=5,tx_cdc_cycles=3,retime_ui=1)
    for key,value in implemented.items():
        if b[key]!=value:
            raise ValueError('USB event adapter does not implement design allocation: '+key)
    host=configuration.host_word_hz;line=configuration.line_rate_bps
    if fpga_s is None:fpga_s=b['fpga_decision_s']
    if not math.isfinite(fpga_s) or fpga_s<0:raise ValueError('invalid FPGA decision allocation')
    costs=dict(receive_tail=b['rx_tail_ui']/line,packing=b['packing_ui']/line,
        quiet=b['quiet_ui']/line,rx_cdc=b['rx_cdc_host_cycles']/host,
        rx_tail_beats=b['rx_tail_beats']/host,fpga_capture=b['fpga_capture_cycles']/host,
        fpga=fpga_s,tx_phase=b['tx_phase_cycles']/host,
        tx_start_prefill=b['tx_start_and_prefill_beats']/host,
        tx_cdc=b['tx_cdc_cycles']/b['tx_fifo_read_hz'],launch_retime=b['retime_ui']/line,
        analog=b['analog_output_s'],board=b['board_margin_s'])
    worst=sum(costs.values());maximum=b['deadline_s']
    return dict(costs_s=costs,worst_s=worst,maximum_s=maximum,minimum_s=8/line,
        margin_s=maximum-worst,admissible=worst<=maximum,
        fpga_allowance_s=maximum-(worst-fpga_s))


class DirectHostState:
    """External FPGA state for one chip transport epoch, not on-chip storage."""
    def __init__(self,chip):
        if chip.direct_session is None:raise ValueError('Direct transport required')
        chip.direct_session.require_active()
        if chip.direct_session.consumed:raise ValueError('New host credits require a fresh chip epoch')
        self.session=chip.direct_session
        self.origin=chip.time
        self.decoder=Decoder()
        self.credits=Credits()
        self.credit_returns=deque()
        self.capture=deque()
        self.phases=None
        self.exchanges=0
        self.in_flight=False
        self._configuration_bound=False
        self._configuration_record=None

    def bind(self,chip,host_phase,read_phase,tick,host_hz=100e6,configuration=None):
        self.session.require_active()
        if self.in_flight:raise ValueError('Interrupted exchange requires explicit STOP/recovery')
        if chip.direct_session is not self.session:
            raise ValueError('Host and chip epochs differ')
        if self.phases is not None and self.phases!=(host_phase,read_phase,host_hz):
            raise ValueError('Host clocks cannot change phase between exchanges')
        record=None if configuration is None else configuration.record()
        if self._configuration_bound and record!=self._configuration_record:
            raise ValueError('Retained host state belongs to another design/configuration or fixture scope')
        offset=(chip.time-self.origin)/tick
        if abs(offset-round(offset))>1e-5:
            raise ValueError('This discrete-time bench requires packet start on its tick grid')
        self.phases=(host_phase,read_phase,host_hz)
        self._configuration_record=deepcopy(record)
        self._configuration_bound=True
        self.in_flight=True
        return round(offset)


def reply_trace(*,host_phase=0,read_phase=0,fpga_s=None,payload=b'hello',
                response_payload=None,corrupt=False,stall_every=0,chip=None,host_state=None,request_delay_ui=0,request_dropout_ui=None,analog_observer=None,analog_observation_period_s=100e-9,configuration=None,host_hz=None):
    """Grid-resolved host word events, 240MHz FIFO consumer, 480MHz bit serializer.

    FPGA decisions start only after END and streamed CRC validation. TX credits
    return four host cycles after consumption; no oracle reads of FIFO space.
    response_payload selects a DATA reply for transport stress, not USB legality.
    """
    context=dict(result_role='independent_component_fixture')
    pad_context=None if chip is None or chip.wired_pad is None else chip.wired_pad.construction_context()
    if configuration is not None:
        require_usb_configuration(configuration)
        if pad_context is not None and 'architecture_sha256' in pad_context:
            expected=configuration.design.provenance()['documents']['spec/analog-architecture.json']
            if pad_context['architecture_sha256']!=expected:
                raise ValueError('Pad architecture conflicts with resolved exchange configuration')
        if host_hz is not None and host_hz!=configuration.host_word_hz:
            raise ValueError('Host rate conflicts with resolved configuration')
        host_hz=configuration.host_word_hz
        if chip is not None and any(not math.isclose(312.5e6*scale,host_hz) for scale in
                (chip.a.h2d_clock_scale,chip.a.d2h_clock_scale)):
            raise ValueError('Chip host clocks do not match the resolved exchange configuration')
        if chip is not None:
            resources=chip.resources or {}
            if resources.get('engine')!='wire' or resources.get('line_rate_bps')!=configuration.line_rate_bps:
                raise ValueError('Chip engine/line rate does not match the resolved exchange configuration')
        context=dict(design_provenance=configuration.design.provenance(),
            resolved_configuration=configuration.record(),scenario_overrides=[],
            result_role='configured_component_fixture',diagnostic_model_overrides=[])
        if chip is not None:
            guard=configuration.design.contract['physical_services']['sar_timing']['startup']['assigned_guard_s']
            context['injected_chip_startup_s']=chip.a.startup_s
            if chip.a.startup_s!=guard:
                context['diagnostic_model_overrides'].append(dict(parameter='startup_s',
                    design_value=guard,value=chip.a.startup_s,
                    reason='Injected component fixture has a different startup guard; no nominal startup qualification'))
    elif host_hz is None:host_hz=100e6
    if configuration is None:
        if fpga_s is None:fpga_s=120e-9
        bound=response_bound(host_hz=host_hz,fpga_s=fpga_s)
    else:
        allocated=configuration.design.architecture['direct_stream_service']['budget']['fpga_decision_s']
        context['scenario_stimuli']={'fpga_decision_s':allocated if fpga_s is None else fpga_s}
        context['timing_allocation_overrides']=[] if fpga_s is None or fpga_s==allocated else [
            dict(parameter='fpga_decision_s',value=fpga_s,design_value=allocated,
                 reason='Explicit external FPGA response-time stimulus')]
        bound=configured_response_bound(configuration,fpga_s=fpga_s)
        fpga_s=bound['costs_s']['fpga']
    context['injected_chip_assumptions']=None if chip is None else asdict(chip.a)
    context['injected_chip_assumptions_scope']=(None if chip is None else
        'Caller-supplied behavioral fixture; engine and directional clocks are checked above, '
        'startup differences are recorded, but other scalar assumptions are not shared-design qualification')
    context['pad_supply_input']=(None if chip is None or chip.wired_pad is None else
        dict(kind='constant_fixture',voltage_v=chip.a.supply_v) if chip.wired_pad_supply is None else
        dict(kind='external_callback',scope='Supply waveform identity and conditions belong to the calling bench'))
    context['pad_construction']=pad_context
    context['pad_initial_controls']=None if chip is None or chip.wired_pad is None else chip.wired_pad.control_context()
    context['response_budget']=bound
    if not bound['admissible']:raise ValueError('response deadline allocation')
    tick=1/2.4e9;H=round(1/(host_hz*tick));B=10;UI=5
    if H<1 or not math.isclose(H*tick,1/host_hz,rel_tol=1e-12):
        raise ValueError('Host period must fit the declared USB event grid')
    if not 0<=host_phase<H or not 0<=read_phase<B:raise ValueError('phase')
    context['host_word_hz']=host_hz
    observation_ticks=0
    if analog_observer is not None:
        if (chip is None or chip.analog_qualification is None or not callable(analog_observer) or
                not math.isfinite(analog_observation_period_s) or analog_observation_period_s<=0):
            raise ValueError('USB analog observation requires chip monitor, callable and positive finite period')
        observation_ticks=round(analog_observation_period_s/tick)
        if observation_ticks<1 or not math.isclose(observation_ticks*tick,analog_observation_period_s,rel_tol=1e-10):
            raise ValueError('USB observer period must fit the event grid')
    observation_count=0
    request=usb_hs_packet(0xc3,payload)
    if corrupt:request[len(request)//2]^=1
    if type(request_delay_ui) is not int or request_delay_ui<0:raise ValueError('Nonnegative request delay required')
    request_start=request_delay_ui*UI
    eop=request_start+len(request)*UI
    if request_dropout_ui is not None:
        if (len(request_dropout_ui)!=2 or any(type(x) is not int or x<0 for x in request_dropout_ui)
                or request_dropout_ui[1]<=request_dropout_ui[0] or request_dropout_ui[1]>len(request)):
            raise ValueError('Dropout must be a nonempty source-UI interval')
    context.setdefault('scenario_stimuli',{}).update(
        event_tick_s=tick,host_phase_ticks=host_phase,read_phase_ticks=read_phase,
        fpga_decision_s=fpga_s,request_payload_hex=bytes(payload).hex(),
        response_kind='ACK' if response_payload is None else 'DATA1',
        response_payload_hex=None if response_payload is None else bytes(response_payload).hex(),
        corrupt_request=bool(corrupt),stall_every=stall_every,
        request_delay_ui=request_delay_ui,
        request_dropout_ui=None if request_dropout_ui is None else list(request_dropout_ui),
        analog_observer_enabled=analog_observer is not None,
        analog_observation_period_s=None if analog_observer is None else analog_observation_period_s)
    # Record readiness follows actual incoming bits, not pre-known packet length.
    incoming=deque([(request_start+16*UI,word(START))])
    for i in range(0,len(request),8):
        chunk=request[i:i+8];ready=request_start+(i+len(chunk)+8)*UI
        if len(chunk)<8:incoming.append((ready,word(0x10+len(chunk))))
        incoming.append((ready,word(sum(b<<j for j,b in enumerate(chunk)),True)))
    incoming.append((eop+12*UI,word(END)))
    session=None if chip is None else chip.direct_session
    if chip is not None:
        if session is None:raise ValueError('Configure direct transport first')
        session.require_active()
        if session.consumed and host_state is None:raise ValueError('Retain external host state across exchanges')
    pad=None if chip is None else chip.wired_pad
    if pad is not None:
        if pad.mode!='usb' or pad.speed!='hs' or pad.local!='Z' or pad.peer!='Z' or pad.local_drive is not None:
            raise ValueError('Released configured HS pad required')
        incoming=deque();burst=SampledBurstRecords(ui_ticks=UI)
    if request_dropout_ui is not None and pad is None:raise ValueError('Electrical pad required for source dropout')
    captured=[];physical_tx=[];rx_margin=[];tx_margin=[]
    origin=0. if chip is None else chip.time
    rx=BlockFIFO() if session is None else session.rx
    tx=BlockFIFO() if session is None else session.tx
    if host_state is not None and chip is None:raise ValueError('Persistent host requires chip ownership')
    offset=0 if host_state is None else host_state.bind(chip,host_phase,read_phase,tick,host_hz,configuration)
    rd=Decoder() if host_state is None else host_state.decoder
    td=Decoder();parser=USBStreamingPacket()
    playback=RawBurstPlayback(capacity_bits=128) if session is None else session.playback
    completed_before=playback.completed
    capture=deque() if host_state is None else host_state.capture
    credits=Credits() if host_state is None else host_state.credits
    credit_returns=deque() if host_state is None else host_state.credit_returns
    outgoing=deque();consumed=0 if session is None else session.consumed
    decision=None;validated=None;started=False;start=None;emitted=[];peak=0;sent=0
    reply=usb_hs_packet(0xd2) if response_payload is None else usb_hs_packet(0x4b,response_payload)
    horizon=eop+2000+len(reply)*UI
    for t in range(horizon):
        if analog_observer is not None and t%observation_ticks==0:
            from behavioral import AnalogQualificationError
            try:valid=analog_observer(origin+t*tick)
            except AnalogQualificationError:valid=False
            if valid is not None:
                chip.analog_qualification.observe(origin+t*tick,valid)
                observation_count+=1
        if session is not None:session.advance(origin+t*tick)
        absolute=offset+t
        host=absolute>=host_phase and (absolute-host_phase)%H==0
        byte=absolute>=read_phase and (absolute-read_phase)%B==0
        line=t%UI==0
        if pad is not None and (line or t%UI==2):
            chip.advance_wired_pad(origin+t*tick)
            if line and request_start<=t<=eop:
                source_index=(t-request_start)//UI
                dropout=request_dropout_ui is not None and request_dropout_ui[0]<=source_index<request_dropout_ui[1]
                pad.drive(peer=('J' if request[source_index] else 'K') if t<eop and not dropout else 'Z')
            if t%UI==2 and not burst.closed:
                sense=pad.sense()
                value=None if sense['squelch'] else int(sense['differential_positive'])
                incoming.extend(burst.observe(t,value))
                if value is not None:
                    captured.append(value)
                    # Source truth is confined to this offline voltage score.
                    source_index=(t-request_start)//UI
                    expected=request[source_index] if 0<=source_index<len(request) else 0
                    rx_margin.append((2*expected-1)*float(pad.voltage[0]-pad.voltage[1]))
            elif t%UI==2 and pad.local!='Z':
                sense=pad.sense()
                if sense['squelch']:raise ValueError('Reply below pad squelch threshold')
                physical_tx.append(int(sense['differential_positive']))
                tx_margin.append((2*emitted[-1]-1)*float(pad.voltage[0]-pad.voltage[1]))
        # Consume old serializer state first; no same-edge CDC bypass.
        if line:
            if not started and playback.bits>=32:
                started=True
            if started:
                bit=playback.tick() if session is None else session.tick()
                if bit is not None:
                    if start is None:start=t
                    emitted.append(bit)
                    if pad is not None:pad.drive(local='J' if bit else 'K')
                if playback.completed>completed_before:
                    if pad is not None:pad.drive()
                    break
        if host:
            while credit_returns and credit_returns[0][0]<=absolute:
                _,cell=credit_returns.popleft()
                for kind,value,count in rd.feed(cell):
                    if kind!='credit':raise AssertionError('credit channel')
                    credits.grant(value)
            while capture and capture[0][0]<=absolute:
                _,cell=capture.popleft()
                for kind,value,count in rd.feed(cell):
                    if kind=='data':parser.feed([(value>>j)&1 for j in range(count)])
                    elif kind=='event':
                        try:validated=parser.finish()
                        except ValueError:validated=False
                        if validated:decision=t+math.ceil(fpga_s/tick)
            if decision is not None and t>=decision and not outgoing and sent==0:
                outgoing.extend(encode(reply))
        source=None
        if byte and incoming and incoming[0][0]<=t:
            source=(incoming.popleft()[1],)
        result=rx.step(wr_edge=byte,rd_edge=host,words=source,
                       pop=host and rx.status()['rd_valid'])
        if source is not None and not result['written']:raise AssertionError('RX overflow')
        if result['read'] is not None:capture.append((absolute+H,result['read'][0]))
        source=None
        if host and outgoing and credits.available and not (stall_every and (absolute//H)%stall_every==0):
            source=(outgoing.popleft(),);credits.take();sent+=1
        # Bounded playback staging provides backpressure before overflow.
        result=tx.step(wr_edge=host,rd_edge=byte,words=source,
                       pop=byte and tx.status()['rd_valid'] and playback.bits<=112)
        if source is not None and not result['written']:raise AssertionError('credit failure')
        if result['read'] is not None:
            consumed+=1
            credit_returns.append((absolute+3*H,word(0x40+(consumed%32))))
            if session is not None:
                session.consumed+=1
                session.accept(result['read'][0])
            else:
                for record in td.feed(result['read'][0]):
                    if record[0] in ('data','event'):playback.enqueue([record])
        peak=max(peak,playback.bits)
    if corrupt:
        if validated or emitted:raise AssertionError('invalid packet caused response')
        if host_state is not None:
            host_state.exchanges+=1;host_state.in_flight=False
        return dict(context,rejected=True,reply_bits=0)
    if pad is not None and not validated:raise ValueError('Request acquisition/framing failed from sampled pad squelch')
    if validated!=(0xc3,bytes(payload)):raise AssertionError('FPGA packet validation')
    if emitted!=reply or playback.completed!=completed_before+1:raise AssertionError('reply lost/reordered')
    usb_hs_decode_packet(emitted)
    if pad is not None:
        if physical_tx!=reply:raise AssertionError('Physical reply lost/reordered')
        usb_hs_decode_packet(physical_tx)
    port_start=(start-eop)*tick+bound['costs_s']['analog']+bound['costs_s']['board']
    if port_start>bound['worst_s']+1e-15:raise AssertionError('trace exceeds allocation')
    if host_state is not None:
        host_state.exchanges+=1;host_state.in_flight=False
    return dict(context,port_start_s=port_start,bound_s=bound['worst_s'],margin_s=bound['maximum_s']-port_start,
                reply_bits=len(emitted),peak_staging_bits=peak,fpga_decision_s=fpga_s,
                analog_observations=observation_count,
                analog_observation_period_s=None if analog_observer is None else analog_observation_period_s,
                host_epoch=None if session is None else session.epoch,
                cumulative_consumed=consumed,credits_available=credits.available,
                pending_credit_returns=len(credit_returns),
                pad=None if pad is None else dict(rx_min_signed_v=min(rx_margin),
                    tx_min_signed_v=min(tx_margin),captured_bits=len(captured),
                    peer_received_bits=len(physical_tx),
                    supply='constant' if chip.wired_pad_supply is None else 'time_dependent',
                    scope='retained four-node RC pad; two quiet samples close burst; a returning signal after an erasure aborts; ideal 0.4-UI sampling and assigned pipeline delays'),
                scope='causal raw stream/finite CDC/streaming FPGA CRC/playback; assigned analog bounds')
