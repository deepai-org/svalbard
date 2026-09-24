"""External testbench recipes for protocol-independent chip configurations.

Models PHY primitives. Packet stacks, certification and fast host ABI remain open.
No separate analog owner or protocol-specific ideal supply is constructed here.
"""
import math
from protocol_signals import fixture, receiver_projection, transmitter_projection
from protocol_pad import SharedWiredPad, sata_oob, detect_oob, response_budget, usb_framed_turnaround


class ProtocolService:
    def __init__(self,chip,profiles):
        self.chip=chip;self.profiles={p['id']:p for p in profiles}
        self.selected=None;self.role=None
        self.contexts={};self.context_epoch=0

    def select(self,profile,role=None):
        c=self.chip
        if profile not in self.profiles:raise ValueError('Unknown protocol profile')
        p=self.profiles[profile]
        roles=p.get('roles',['radio']);role=role or roles[0]
        if role not in roles:raise ValueError('Unsupported profile role')
        if c.state!='reset' or c.session.armed:raise ValueError('Profile selection requires stopped chip')
        pad=c.analog_owner.pad_branch
        if pad is not None and (pad.local!='Z' or pad.peer!='Z'):
            raise ValueError('Release USB drivers before changing profile')
        c.configure_resources(engine=p['engine'],line_rate_bps=p.get('line_rate_bps'),
            frame_words=8 if p.get('host_service')=='short_framed' else 64,
            pad_path='bidirectional' if profile=='usb2' else 'serial',
            tx_enabled=not (profile in ('displayport_rbr','dvi_single_link','hdmi_tmds') and role=='sink'),
            rx_enabled=not (profile in ('displayport_rbr','dvi_single_link','hdmi_tmds') and role=='source'))
        if profile in ('dvi_single_link','hdmi_tmds'):
            c.configure_wire_interface(electrical='dc_current_sink',clock_source='forwarded_word',
                word_reference_hz=p['line_rate_bps']/10)
        self.selected=p;self.role=role;self.context_epoch+=1
        if profile=='usb2':
            if pad is None:
                pad=SharedWiredPad();pad.time=c.time;c.analog_owner.pad_branch=pad
            pad.configure('usb',role,'fs',attached=False)
        return self.status()

    def status(self):
        return dict(profile=self.selected['id'] if self.selected else None,role=self.role,
                    model_scope='executable PHY primitives; packet lifecycle incomplete',
                    context_epoch=self.context_epoch,standards_compliant=False)

    def configure_transport(self,mode):
        if self.selected is None:raise ValueError('Select profile first')
        if self.selected['id']=='usb2' and mode!=0:
            raise ValueError('USB short framing requires DDR125 mode')
        self.chip.configure(mode,self.chip.time)

    def waveform(self,variant='',seed=81):
        if self.selected is None or self.selected['engine']!='rf':raise ValueError('RF profile required')
        return fixture(self.selected['id'],variant,seed)

    def inject_receive(self,waveform,carrier_hz,amplitude=.1,start=None):
        if self.selected is None or self.selected['engine']!='rf':raise ValueError('RF profile required')
        if not self.selected['carrier_min_hz']<=carrier_hz<=self.selected['carrier_max_hz']:
            raise ValueError('Carrier outside profile')
        self.chip.install_external_waveform(waveform,carrier_hz,start,amplitude)

    def project_receive(self,waveform,**kwargs):
        """Reduced diagnostic, explicitly separate from time advancement of the chip."""
        if self.selected is None or self.selected['engine']!='rf':raise ValueError('RF profile required')
        b=self.chip.analog_owner.rx_bank
        kwargs.setdefault('frontend',self.chip.frontend)
        kwargs.setdefault('gain',self.chip.rx_gain)
        return receiver_projection(waveform,b['poles'],b['weights'],**kwargs)

    def project_transmit(self,waveform,**kwargs):
        if self.selected is None or self.selected['engine']!='rf':raise ValueError('RF profile required')
        return transmitter_projection(waveform,self.chip.tx.reconstruction,
                                      self.chip.tx_output_parameters,**kwargs)

    def project_link(self,waveform,*,bits=12,amplitude=.1,channel_gain=1.,
                     frequency_offset_hz=0.,noise_rms=0.,seed=81,
                     tx_phase_rad=None,rx_phase_rad=None):
        """TX through an external complex-envelope channel into the same RX design.

        This is a frozen-rail, prescribed-clock reduction, not simultaneous RF
        operation or canonical time advancement. No oracle gain/phase equalizer
        is applied. Noise RMS is complex input-referred voltage after channel gain.
        """
        import numpy as np
        from protocol_signals import Waveform
        if (not all(math.isfinite(v) for v in
                    (channel_gain,frequency_offset_hz,noise_rms)) or
                channel_gain<0 or noise_rms<0):
            raise ValueError('Finite nonnegative channel gain and noise required')
        tx=self.project_transmit(waveform,bits=bits,amplitude=amplitude,phase_rad=tx_phase_rad)
        t=np.arange(len(tx))/waveform.sample_hz
        incoming=channel_gain*tx*np.exp(2j*math.pi*frequency_offset_hz*t)
        rng=np.random.default_rng(seed)
        incoming+=noise_rms/math.sqrt(2)*(rng.normal(size=len(tx))+1j*rng.normal(size=len(tx)))
        received=Waveform(incoming,waveform.sample_hz,waveform.kind,
                          waveform.symbols,waveform.metadata)
        return self.project_receive(received,bits=bits,amplitude=1.,phase_rad=rx_phase_rad)

    def project_lo_history(self,duration,*,sample_hz=40e6,acquisition_s=20e-6,noise=None):
        """Isolated configured oscillator projection, not chip readiness.

        Clone existing loop coefficients/state, explicitly supply a reference and
        freeze rail history. Coarse-search/host/startup sequencing stays outside
        this diagnostic. Phase is unwrapped relative to the chip carrier frame.
        """
        import copy
        import numpy as np
        if any(not math.isfinite(v) or v<=0 for v in (duration,sample_hz,acquisition_s)):
            raise ValueError('Positive finite projection interval and cadence required')
        clock=copy.deepcopy(self.chip.rf_pll)
        if not clock.powered:raise ValueError('RF oscillator must be powered')
        clock.supply_trajectory=None
        clock.set_reference(True,clock.time)
        if noise is not None:clock.set_noise(clock.time,noise)
        origin=clock.time
        for i in range(1,math.ceil(acquisition_s*clock.reference_hz)+1):
            clock.advance(origin+i/clock.reference_hz);clock.observe_lock()
        acquired=clock.locked;start=clock.time
        count=math.ceil(duration*sample_hz)
        times=np.arange(count+1)/sample_hz;phases=[]
        for t in times:
            clock.advance(start+float(t))
            phases.append(2*math.pi*((clock.reference_hz*clock.divider-self.chip.rf_carrier)*clock.time
                -clock.divider*clock.error+clock.phase_offset))
        return dict(times=times,phase_rad=np.asarray(phases),acquired=bool(acquired),
            acquisition_s=start-origin,sample_hz=sample_hz,frozen_supplies=True,
            canonical_chip_ready=False,clock_class=type(clock).__name__)

    def project_clocked_link(self,waveform,*,bits=12,amplitude=.1,substeps=4,
                             tx_phase=None,rx_phase=None):
        """Frozen-rail conversion chain at the supported 40/20 MS/s clocks.

        Source values use the Waveform ZOH contract at DAC update times. Finer
        integration repeats those DAC codes, never increases conversion rate.
        RX sees previous substep TX voltage; ADC samples at converter boundaries.
        No resampling back to fixture rate or modem decisions are hidden here.
        """
        import numpy as np
        from protocol_signals import Waveform
        if bits not in (8,12) or type(substeps) is not int or not 1<=substeps<=16:
            raise ValueError('Supported converter mode and bounded refinement required')
        if any(p is not None and not callable(p) for p in (tx_phase,rx_phase)):
            raise ValueError("Phase histories must be functions of physical time")
        rate=40e6 if bits==12 else 20e6
        count=math.ceil(waveform.duration*rate)
        from fractions import Fraction
        ratio=Fraction(str(waveform.sample_hz))/Fraction(str(rate))
        indices=np.fromiter((i*ratio.numerator//ratio.denominator for i in range(count)),dtype=np.int64,count=count)
        codes=waveform.samples[np.minimum(indices,len(waveform.samples)-1)]
        held=Waveform(np.repeat(codes,substeps),rate*substeps,waveform.kind,
            waveform.symbols,waveform.metadata)
        grid=np.arange(len(held.samples))/(rate*substeps)
        # Reconstruction emits right endpoints; RX forcing is left-held.
        tx_angles=None if tx_phase is None else tx_phase(grid+1/(rate*substeps))
        rx_angles=None if rx_phase is None else rx_phase(grid)
        tx=self.project_transmit(held,bits=bits,amplitude=amplitude,phase_rad=tx_angles)
        # Preserve the actual output/dummy switch setting and stored state.
        # The output network receives the preceding TX substep, not future data.
        network=self.chip.output_network
        tx=network.project_samples(np.r_[0j,tx[:-1]],rate*substeps,node=1)
        # Left-endpoint forcing avoids feeding a future TX value into RX.
        incoming=Waveform(np.r_[0j,tx[:-1]],rate*substeps,waveform.kind,
            waveform.symbols,waveform.metadata)
        received,clipped=self.project_receive(incoming,bits=bits,amplitude=1.,
            sample_stride=substeps,phase_rad=rx_angles)
        assert len(received)==count
        return dict(samples=received,times=(np.arange(count)+1)/rate,
            converter_hz=rate,dac_updates=count,adc_samples=count,adc_clipped_samples=clipped,
            integration_substeps=substeps,source_hold='zero order',frozen_supplies=True,
            tx_pad_included=True,output_enabled=network.output_on,dummy_enabled=network.dummy_on)

    def usb_mode(self,speed,attached=True):
        if not self.selected or self.selected['id']!='usb2':raise ValueError('USB profile required')
        self.chip.analog_owner.pad_branch.configure('usb',self.role,speed,attached)

    def usb_hold(self,seconds,local='Z',peer='Z'):
        if not self.selected or self.selected['id']!='usb2':raise ValueError('USB profile required')
        if not math.isfinite(seconds) or seconds<=0:raise ValueError('Positive line-state interval')
        pad=self.chip.analog_owner.pad_branch
        pad.drive(local,peer)
        self.chip.advance(self.chip.time+seconds)
        return pad.observe()

    def oob(self,kind):
        if not self.selected or self.selected['id']!='sata_gen1':raise ValueError('SATA profile required')
        if (kind=='reset' and self.role!='host') or (kind=='init' and self.role!='device'):
            raise ValueError('SATA OOB role')
        return sata_oob(kind)

    def oob_receiver(self,**kwargs):
        """Reduced envelope observer; does not assert canonical link readiness."""
        if not self.selected or self.selected['id']!='sata_gen1':raise ValueError('SATA profile required')
        from protocol_pad import sata_envelope_receiver
        return sata_envelope_receiver(**kwargs)

    def save_context(self,key,carrier_hz,gain=1.):
        if not self.selected or self.selected['engine']!='rf':raise ValueError('RF profile required')
        if not self.selected['carrier_min_hz']<=carrier_hz<=self.selected['carrier_max_hz'] or gain not in (.5,1.,2.):
            raise ValueError('RF context envelope')
        if key not in self.contexts and len(self.contexts)>=80:raise ValueError('RF context memory full')
        # Saved requested settings are not an invented calibrated/locked bank.
        self.contexts[key]=((self.context_epoch,getattr(self.chip,'resource_generation',0)),carrier_hz,gain)

    def request_hop(self,key):
        c=self.chip
        if key not in self.contexts or self.contexts[key][0]!=(self.context_epoch,getattr(c,'resource_generation',0)):
            raise ValueError('Missing or stale RF context')
        _,carrier,gain=self.contexts[key]
        # Actual existing retune service remains the owner. No instant lock flag.
        c.configure_rx_gain(gain)
        c.execute_management('rf_coarse_start',int(carrier),c.time)
        return dict(requested_at=c.time,carrier_hz=carrier,ready=False)

    def deadline(self,**kwargs):return response_budget(**kwargs)

    def usb_transport(self):
        if not self.selected or self.selected['id']!='usb2':raise ValueError('USB profile required')
        from stream_codec import Receiver
        return Receiver(0,frame_words=8)

    def usb_response_bound(self,**kwargs):return usb_framed_turnaround(**kwargs)
