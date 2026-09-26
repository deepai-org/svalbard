"""Candidate generic resource command payload; no protocol identifiers.

Pure codec for the existing 32-bit management payload. Register/RTL encoding and
canonical queue dispatch are separate integration obligations. Zero means the
legacy/default clock choice, not a physically zero-frequency clock.
"""
ENGINES=('none','wire','rf')
RATES=(None,480e6,1.25e9,1.5e9,1.62e9,2.5e9,.7425e9,1.485e9)
MASK=(1<<9)-1


def decode_resource_word(word):
    if type(word) is not int or not 0<=word<=MASK:
        raise ValueError('Reserved resource configuration bits or invalid payload')
    owner=word&3;rate=(word>>2)&7
    if owner>=len(ENGINES) or rate>=len(RATES):
        raise ValueError('Reserved resource field encoding')
    result=dict(engine=ENGINES[owner],line_rate_bps=RATES[rate],
        frame_words=8 if word&(1<<5) else 64,
        tx_enabled=bool(word&(1<<6)),rx_enabled=bool(word&(1<<7)),
        pad_path='bidirectional' if word&(1<<8) else 'serial')
    if result['engine']!='wire' and (rate or result['frame_words']!=64 or result['pad_path']!='serial'):
        raise ValueError('Wired resource fields without wired ownership')
    return result


def encode_resource_word(*,engine,line_rate_bps=None,frame_words=64,
                         tx_enabled=True,rx_enabled=True,pad_path='serial'):
    if (engine not in ENGINES or line_rate_bps not in RATES or
            frame_words not in (8,64) or pad_path not in ('serial','bidirectional') or
            type(tx_enabled) is not bool or type(rx_enabled) is not bool):
        raise ValueError('Unsupported resource configuration')
    word=(ENGINES.index(engine)|(RATES.index(line_rate_bps)<<2)|
          (int(frame_words==8)<<5)|(int(tx_enabled)<<6)|(int(rx_enabled)<<7)|
          (int(pad_path=='bidirectional')<<8))
    decode_resource_word(word)
    return word


class ResourceConfigurationCommands:
    """Dispatch adapter for the existing serialized-management apply callback.

    The owning composition must include RESOURCE_COMMANDS in TILE_COMMANDS.
    This adapter does not replace queue timing, epoch fences or chip permissions.
    """
    RESOURCE_COMMANDS=('configure_resources','record_return_configure','configure_wire_interface')

    def execute_management(self,operation,payload,time):
        if operation=='configure_wire_interface':
            if type(payload) is not int or not 0<=payload<=3:
                raise ValueError('Reserved wire-interface bits')
            forwarded=bool(payload&2)
            rate=getattr(self,'wire_rate_override',None)
            if forwarded and rate not in (.7425e9,1.485e9):
                raise ValueError('Unsupported forwarded word-reference rate')
            self.configure_wire_interface(
                electrical='dc_current_sink' if payload&1 else 'ac_differential',
                clock_source='forwarded_word' if forwarded else 'embedded',
                word_reference_hz=rate/10 if forwarded else None)
            return dict(value=payload)
        if operation=='record_return_configure':
            if type(payload) is not int or payload not in (0,1):raise ValueError('Reserved record-return control bits')
            self.configure_record_return(enabled=bool(payload))
            return dict(value=payload)
        if operation=='configure_resources':
            settings=decode_resource_word(payload)
            self.configure_resources(**settings)
            return dict(value=payload)
        return super().execute_management(operation,payload,time)


def validate_wire_timing(line_rate_bps, clock_source='embedded', reference_hz=None):
    """Behavioral tuning target; does not widen the legacy command encoding.

    Physical PLL/CDR tuning bands and reference input limits remain unqualified.
    Forwarded range stays within the two existing video endpoint targets.
    """
    import math
    if not math.isfinite(line_rate_bps) or not 480e6 <= line_rate_bps <= 2.5e9:
        raise ValueError('Wired rate outside candidate envelope')
    if clock_source not in ('embedded', 'forwarded_word'):
        raise ValueError('Unknown clock source')
    if clock_source == 'forwarded_word':
        if (reference_hz is None or not math.isfinite(reference_hz) or
                not 74.25e6/1.001 <= reference_hz <= 148.5e6 or
                not math.isclose(line_rate_bps, 10*reference_hz, rel_tol=1e-12)):
            raise ValueError('Forwarded clock must satisfy bounded x10 relationship')
    elif reference_hz is not None:
        raise ValueError('Embedded timing does not specify a forwarded reference')
    return dict(line_rate_bps=line_rate_bps, clock_source=clock_source,
                word_reference_hz=reference_hz)


def validate_rf_settings(sample_hz=40e6, tx_cutoff_hz=20e6,
                         rx_cutoff_hz=9.157407e6, rx_gain=1., rx_filter_order=1, converter_bits=12,
                         sample_clock_source='reference', lo_hz=None, lo_divider=None):
    """Generic candidate filter-bank/divider settings, not protocol selectors.

    Reference divisors reuse 40 MHz. An alternate direct-LO candidate uses
    uniform integer division, without a second reference or fractional edges.
    This validates rate ownership, not a physical divider or input receiver.
    8/12-bit precision is independent of rate.
    Cutoffs are one-sided analog poles, not occupied channel bandwidths.
    """
    import math
    if type(rx_filter_order) is not int or rx_filter_order not in (1,5):
        raise ValueError('Supported filter reductions are first and fifth order')
    if type(converter_bits) is not int or converter_bits not in (8,12):
        raise ValueError('Converter precision must be 8 or 12 bits')
    values=(sample_hz,tx_cutoff_hz,rx_cutoff_hz,rx_gain)
    if not all(math.isfinite(v) and v>0 for v in values):
        raise ValueError('Positive finite RF settings required')
    clock={}
    if sample_clock_source=='reference':
        if lo_hz is not None or lo_divider is not None:
            raise ValueError('Reference sampling must not claim an external LO owner')
        if sample_hz not in (5e6,10e6,20e6,40e6):
            raise ValueError('Unsupported reference divider')
    elif sample_clock_source=='external_lo':
        if (lo_hz is None or not math.isfinite(lo_hz) or not 2.4e9<=lo_hz<=2.484e9
                or type(lo_divider) is not int or lo_divider not in (64,128,256,512)):
            raise ValueError('External LO candidate needs bounded carrier and integer divider')
        if not math.isclose(sample_hz,lo_hz/lo_divider,rel_tol=1e-12):
            raise ValueError('Converter rate must follow its actual external LO divider')
        clock=dict(sample_clock_source=sample_clock_source,lo_hz=lo_hz,lo_divider=lo_divider)
    else:
        raise ValueError('Unknown RF sample clock owner')
    if not (.1e6<=rx_cutoff_hz<=9.157407e6 and .1e6<=tx_cutoff_hz<=20e6
            and max(tx_cutoff_hz,rx_cutoff_hz)<=sample_hz/2 and .5<=rx_gain<=2.):
        raise ValueError('RF setting outside candidate envelope')
    return dict(sample_hz=sample_hz,tx_cutoff_hz=tx_cutoff_hz,
                rx_cutoff_hz=rx_cutoff_hz,rx_gain=rx_gain,rx_filter_order=rx_filter_order,converter_bits=converter_bits,**clock)


def rf_transition_budget(*, before, after, operation, epoch, host_word_hz,
                         command_words, cdc_cycles, control_hz,
                         boundary_wait_s, analog_settle_s, source_lock_s,
                         host_training_words, fpga_recovery_s, deadline_s,
                         prearmed=False, fixed_host_clock_hz=None,d2h_lo_divider=16):
    """Generic control/service requirement, not an analog transition simulation.

    Durations are explicit assigned upper bounds. Retune/fault recovery requires
    a new epoch; same-channel turnaround preserves clocks and stream identity.
    Existing numeric resource validation applies to both endpoints.
    """
    import math
    old=validate_rf_settings(**before);new=validate_rf_settings(**after)
    if type(d2h_lo_divider) is not int or d2h_lo_divider not in (16,32):
        raise ValueError('Explicit supported LO-to-D2H clock divider required')
    if operation not in ('turnaround','retune','fault_recovery'):
        raise ValueError('Unknown RF transition')
    if type(epoch) is not int or epoch<0 or type(prearmed) is not bool:
        raise ValueError('Nonnegative epoch and explicit prearm choice required')
    if any(type(v) is not int or v<0 for v in (command_words,cdc_cycles,host_training_words)):
        raise ValueError('Nonnegative integer service counts required')
    values=(host_word_hz,control_hz,boundary_wait_s,analog_settle_s,source_lock_s,fpga_recovery_s,deadline_s)
    if not all(math.isfinite(v) for v in values) or min(host_word_hz,control_hz,deadline_s)<=0 or min(boundary_wait_s,analog_settle_s,source_lock_s,fpga_recovery_s)<0:
        raise ValueError('Explicit finite rate/time bounds required')
    if fixed_host_clock_hz is not None and (not math.isfinite(fixed_host_clock_hz) or fixed_host_clock_hz<=0):
        raise ValueError('Independent fixed host clock must have a real positive rate')
    if operation=='turnaround' and (old!=new or source_lock_s or host_training_words or fpga_recovery_s):
        raise ValueError('Same-channel turnaround preserves settings and qualified clocks')
    if operation!='turnaround' and (not host_training_words or not command_words):
        raise ValueError('Retune/fault recovery requires explicit command and training service')
    def d2h(settings):
        if fixed_host_clock_hz is not None:return fixed_host_clock_hz
        if settings.get('sample_clock_source')=='external_lo':return settings['lo_hz']/d2h_lo_divider
        raise ValueError('Reference-sampled configuration needs explicit host clock ownership')
    old_host=d2h(old);new_host=d2h(new)
    events=[];now=0.
    def step(name,duration,owner):
        nonlocal now
        events.append(dict(state=name,start_s=now,end_s=now+duration,owner=owner));now+=duration
    command_time=command_words/host_word_hz+cdc_cycles/control_hz
    step('scheduled_trigger' if prearmed else 'command_and_cdc',0. if prearmed else command_time,'host/control')
    step('quiesce_at_safe_boundary',boundary_wait_s,'chip')
    if operation!='turnaround':
        step('invalidate_old_epoch_and_gate_affected_clocks',0.,'chip/FPGA')
        step('source_reacquisition',source_lock_s,'timing_source')
    step('analog_path_settling',analog_settle_s,'chip/board')
    if operation!='turnaround':
        step('host_capture_training',host_training_words/(2*new_host),'chip/FPGA')
        step('fpga_resampler_and_queue_recovery',fpga_recovery_s,'FPGA')
    step('ready_for_current_epoch',0.,'chip/FPGA')
    overhead=now-analog_settle_s
    return dict(operation=operation,old_epoch=epoch,new_epoch=epoch+(operation!='turnaround'),
        preserves_stream_epoch=operation=='turnaround',clocks_kept_running=operation=='turnaround',
        old_sample_hz=old['sample_hz'],new_sample_hz=new['sample_hz'],
        old_d2h_clock_hz=old_host,new_d2h_clock_hz=new_host,
        h2d_clock_unchanged=True,host_clock_rate_changes=old_host!=new_host,
        d2h_lo_divider=d2h_lo_divider if fixed_host_clock_hz is None else None,
        queue_policy='retain_paced_current_epoch' if operation=='turnaround' else 'discard_old_epoch_before_rearm',
        prearm_required_lead_s=command_time if prearmed else 0.,events=events,
        total_s=now,deadline_s=deadline_s,margin_s=deadline_s-now,
        maximum_analog_settle_s=deadline_s-overhead,
        fits_assigned_deadline=now<=deadline_s,
        scope='Control/service timing contract only: no pad switching, PLL settling waveform, glitchless gate or packet acceptance proof')
