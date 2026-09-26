"""Explicit mixer-phase timing and chunk-boundary controls."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model'/'architecture_fast'))
from behavioral import SampledRFStream,live_host_rf_observation,diagnostic_chirp_prefix,acquire_live_prefix,ClockQualificationError,LiveRFTransportFailure,BehavioralChip,Assumptions,gfsk_decision_quality,gfsk,RailDrivenPulsePLL,SharedRail

from stream_codec import Receiver,discontinuity_suffix,encode,PacketHoldback
from bit_event_codec import TrainedRecordReceiver

SETTINGS=dict(sample_hz=10e6,tx_cutoff_hz=2.5e6,rx_cutoff_hz=1.25e6,
              rx_filter_order=5,converter_bits=12,rx_gain=1.)

class MixerPhaseTests(unittest.TestCase):
    def test_shared_rf_rail_uses_mapped_clock_loads(self):
        import json
        from behavioral import rf_demonstration_rail, P
        caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
        rx=rf_demonstration_rail(.012)
        tx=rf_demonstration_rail(.037)
        self.assertEqual(tx['block_write_cap_f'],caps['wr_clk'])
        self.assertEqual(tx['block_read_cap_f'],caps['rd_clk'])
        self.assertEqual(tx['inductance_h'],5e-9)
        self.assertTrue(tx['full_host_activity'])
        self.assertEqual(tx.pop('bias_current_a'),.037)
        self.assertEqual(rx.pop('bias_current_a'),.012)
        self.assertEqual(tx,rx)
        for invalid in (-.001,float('nan'),float('inf')):
            with self.assertRaises(ValueError):rf_demonstration_rail(invalid)

    def test_tx_peak_bound_includes_unsampled_interval_endpoint(self):
        captured=[]
        core=SampledRFStream(SETTINGS,external_substeps=2,
            tx_port_observer=lambda t,z:captured.extend(z),noise_rms=0.)
        core.process(np.array([.2,.2]),sample_times_s=np.array([1.,2.])/10e6)
        code=SampledRFStream.quantize(np.array([.2]),12)[0][0]
        expected=.5*abs(code)*(1-np.exp(-core.tx.rate/10e6))
        self.assertAlmostEqual(core.tx_peak_open_v,expected,places=14)
        self.assertGreater(core.tx_peak_open_v,max(abs(np.asarray(captured))))

    def test_ofdm_crest_budget_preserves_power_when_source_impedance_changes(self):
        from behavioral import tx_ofdm_crest_screen
        old=tx_ofdm_crest_screen((953,977))
        new=tx_ofdm_crest_screen((953,977),source_resistance_ohm=40.,
            tx_voltage_scale=4.518,peak_current_limit_a=.028)
        self.assertEqual(old['failed_current_cases'],1)
        self.assertEqual(new['failed_current_cases'],0)
        for a,b in zip(old['cases'],new['cases']):
            self.assertEqual(a['dac_clips'],0)
            self.assertAlmostEqual(a['average_load_power_w'],b['average_load_power_w'],places=14)
            self.assertAlmostEqual(a['peak_current_a'],b['peak_current_a'],places=12)
            self.assertLess(b['required_peak_open_v'],a['required_peak_open_v'])

    def test_tx_active_power_weights_actual_converter_intervals(self):
        from behavioral import rf_tx_power_requirement
        times=np.array([.25,.75,1.75,3.25])*1e-6
        voltage=np.array([.1,.1,.2j,.2j])
        r=rf_tx_power_requirement(times,voltage,substeps=2,source_resistance_ohm=50.,
                                 load_resistance_ohm=50.,target_average_power_w=.001)
        self.assertAlmostEqual(r['average_load_power_w'],.000325)
        self.assertAlmostEqual(r['peak_to_average_power'],.0004/.000325)
        self.assertAlmostEqual(r['required_peak_load_current_a'],.2/50*np.sqrt(.001/.000325))
        with self.assertRaises(ValueError):
            rf_tx_power_requirement(times,np.zeros(4),substeps=2,source_resistance_ohm=50.,
                                    load_resistance_ohm=50.,target_average_power_w=.001)

    def test_external_rf_filter_prevents_out_of_band_alias(self):
        from behavioral import sample_rf_voltage
        times=np.arange(12800)/640e6
        config=dict(sample_hz=640e6,cutoff_hz=10e6,order=5)
        unwanted=np.exp(2j*np.pi*45e6*times)
        raw=sample_rf_voltage(times,unwanted,sample_hz=40e6,clock_ppm=0.)
        filtered=sample_rf_voltage(times,unwanted,sample_hz=40e6,clock_ppm=0.,observer_filter=config)
        wanted=sample_rf_voltage(times,np.exp(2j*np.pi*5e6*times),
            sample_hz=40e6,clock_ppm=0.,observer_filter=config)
        self.assertGreater(np.mean(abs(raw[200:])),.9)
        self.assertLess(np.mean(abs(filtered[200:])),.002)
        self.assertGreater(np.mean(abs(wanted[200:])),.98)
        with self.assertRaises(ValueError):
            sample_rf_voltage(times[::8],unwanted[::8],sample_hz=40e6,clock_ppm=0.,observer_filter=config)

    def test_independent_ofdm_tx_receiver_uses_training_not_payload(self):
        from behavioral import fixture,receive_tx_he20_port
        fs=40e6;known=diagnostic_chirp_prefix(fs)
        training=fixture('wifi_he20',seed=1907);wave=fixture('wifi_he20',seed=953)
        train=.2*training.samples
        packet=np.r_[np.zeros(73),known,np.zeros(128),
                     np.repeat(np.r_[train,.2*wave.samples],2),np.zeros(256)]
        times=np.arange(len(packet))/fs
        data,fit,q=receive_tx_he20_port(times,.25*packet,known,training,train,
            fs=fs,payload_blocks=4,receiver_clock_ppm=100.)
        self.assertTrue(q['packet_quality_pass'])
        np.testing.assert_array_equal((data.real>0).ravel(),wave.symbols)
        damaged=packet.copy();damaged[73+len(known)+128+2*len(train):]=0
        with self.assertRaisesRegex(ValueError,'Missing or nonfinite pilot observations'):
            receive_tx_he20_port(times,.25*damaged,known,training,train,
                fs=fs,payload_blocks=4,receiver_clock_ppm=100.)

    def test_rx_bias_requires_an_explicit_shared_clock_case(self):
        from behavioral import connected_he20_payload
        for value in (-.001,float('nan'),float('inf'),.012):
            with self.assertRaises(ValueError):connected_he20_payload(pulse_bias_current_a=value)

    def test_tx_compliance_budget_rejects_unfunded_or_overrange_output(self):
        from behavioral import rf_tx_compliance_budget
        args=dict(peak_open_v=.1,minimum_supply_v=3.2,total_rail_bias_a=.012,
            source_resistance_ohm=50.,load_resistance_ohm=50.,
            driver_bias_current_a=.003,peak_current_limit_a=.002,headroom_per_rail_v=.3)
        good=rf_tx_compliance_budget(**args)
        self.assertTrue(good['within_declared_compliance'])
        self.assertAlmostEqual(good['peak_load_current_a'],.001)
        self.assertAlmostEqual(good['peak_load_power_w'],25e-6)
        self.assertAlmostEqual(good['minimum_driver_dc_power_w'],.0096)
        low_supply=rf_tx_compliance_budget(**dict(args,minimum_supply_v=.7))
        self.assertFalse(low_supply['checks']['voltage_headroom'])
        weak=rf_tx_compliance_budget(**dict(args,peak_current_limit_a=.0005))
        self.assertFalse(weak['checks']['peak_current'])
        single=rf_tx_compliance_budget(**dict(args,peak_open_v=1.8,
            driver_bias_current_a=.020,total_rail_bias_a=.029,peak_current_limit_a=.020))
        differential=rf_tx_compliance_budget(**dict(args,peak_open_v=1.8,
            driver_bias_current_a=.020,total_rail_bias_a=.029,peak_current_limit_a=.020,differential=True))
        self.assertFalse(single['checks']['voltage_headroom'])
        self.assertTrue(differential['checks']['voltage_headroom'])
        self.assertEqual(single['peak_load_current_a'],differential['peak_load_current_a'])
        with self.assertRaises(ValueError):
            rf_tx_compliance_budget(**dict(args,total_rail_bias_a=.001))
        with self.assertRaises(ValueError):
            rf_tx_compliance_budget(**dict(args,peak_current_limit_a=.004))

    def test_constant_bias_rail_matches_independent_state_equations(self):
        from scipy.linalg import expm
        for inductance in (0.,5e-9):
            rail=SharedRail(bias_current_a=.012,inductance_h=inductance)
            rail.load(rail.c*.02)
            if inductance:rail.current=.003
            end=30e-9
            integral=rail.droop_integral(0.,end)
            if inductance:
                matrix=np.array([[0.,-1/rail.c,0.,rail.bias/rail.c],
                    [1/rail.l,-rail.r/rail.l,0.,0.],[1.,0.,0.,0.],[0.,0.,0.,0.]])
                expected=expm(matrix*end)@np.array([.02,.003,0.,1.])
                self.assertAlmostEqual(integral,expected[2],places=20)
            else:
                steady=rail.r*rail.bias;tau=rail.r*rail.c
                expected=[steady+(.02-steady)*np.exp(-end/tau)]
                self.assertAlmostEqual(integral,steady*end+(.02-steady)*tau*(1-np.exp(-end/tau)),places=20)
            rail.advance(end)
            self.assertAlmostEqual(rail.droop,expected[0],places=13)
            if inductance:self.assertAlmostEqual(rail.current,expected[1],places=13)
            self.assertAlmostEqual(rail.bias_charge,.012*end,places=20)
            self.assertLess(abs(rail.report()['charge_balance_error_c']),1e-24)
            pulse=RailDrivenPulsePLL()
            # A fresh common epoch tests the PLL's forcing integral directly.
            fresh=SharedRail(bias_current_a=.012,inductance_h=inductance)
            pulse.bind_rail_interval(fresh,end)
            self.assertAlmostEqual(pulse.rail_phase_integral(0.,end),
                -fresh.lo_sensitivity*fresh.droop_integral(0.,end),places=15)

    def test_tx_driver_distortion_precedes_oscillator_rotation(self):
        from tx_output_stage import output_envelope
        parameters=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=.0025,cubic=.06)
        captures=[]
        for distorted,split in ((False,False),(True,False),(True,True)):
            out=[]
            core=SampledRFStream(SETTINGS,external_substeps=4,
                tx_port_observer=lambda t,z:out.extend(z),
                mixer_phase_source=lambda t:np.full(len(t),.7),
                tx_output_parameters=parameters if distorted else None)
            values=np.full(16,.2+.1j);times=(np.arange(16)+1)/10e6
            if split:
                core.process(values[:3],sample_times_s=times[:3])
                core.process(values[3:],sample_times_s=times[3:])
            else:core.process(values,sample_times_s=times)
            captures.append(np.asarray(out))
        local=captures[0]*np.exp(.7j)/.5
        expected=.5*output_envelope(local,np.full(len(local),np.exp(-.7j)),**parameters)
        np.testing.assert_allclose(captures[1],expected,rtol=1e-13,atol=1e-15)
        np.testing.assert_array_equal(captures[1],captures[2])
        self.assertGreater(abs(captures[1][0]),0.) # Zero DAC does not mute LO leakage.

    def test_independent_tx_receiver_does_not_fit_payload_errors(self):
        from behavioral import receive_tx_gfsk_port
        fs=10e6;known=diagnostic_chirp_prefix(fs)
        bits=np.random.default_rng(955).integers(0,2,128)
        wave=gfsk(bits,fs=fs)
        packet=np.r_[np.zeros(73),known,np.zeros(128),.2*wave.samples,np.zeros(256)]
        voltage=packet*.25
        times=np.arange(len(packet))/fs
        _,fit,quality=receive_tx_gfsk_port(times,voltage,known,fs=fs,symbols=128,receiver_clock_ppm=0.)
        self.assertTrue(quality['packet_quality_pass'])
        self.assertEqual(quality['candidate_payload_bits'],bits.tolist())
        damaged=voltage.copy()
        damaged[73+len(known)+128+640:]*=np.exp(.6j)
        _,bad_fit,bad=receive_tx_gfsk_port(times,damaged,known,fs=fs,symbols=128,receiver_clock_ppm=0.)
        self.assertEqual(fit,bad_fit)
        self.assertFalse(bad['packet_quality_pass'])
        self.assertEqual(bad['candidate_payload_bits'],[])

    def test_tx_resistive_reference_plane(self):
        from behavioral import rf_tx_resistive_port
        z=np.array([0.,.1,.1j,-.1],complex)
        matched=rf_tx_resistive_port(z,source_resistance_ohm=50.,load_resistance_ohm=50.)
        np.testing.assert_allclose(matched['envelope_v'],z/2)
        np.testing.assert_allclose(matched['load_power_w'],matched['available_power_w'])
        self.assertAlmostEqual(matched['load_power_w'][1],25e-6)
        for load in (10.,100.,1000.):
            port=rf_tx_resistive_port(z,source_resistance_ohm=50.,load_resistance_ohm=load)
            self.assertTrue(np.all(port['load_power_w']<=port['available_power_w']))
            current=z/(50+load)
            supplied=np.real(z*np.conj(current))/2
            np.testing.assert_allclose(supplied,port['load_power_w']+port['source_dissipation_w'])
        with self.assertRaises(ValueError):
            rf_tx_resistive_port(z,source_resistance_ohm=0.,load_resistance_ohm=50.)

    def test_electrical_rf_noise_reference_plane(self):
        from behavioral import rf_receiver_electrical_budget
        args=dict(temperature_k=300.15,noise_bandwidth_hz=20e6,noise_figure_db=10.,
                  conversion_voltage_gain_db=52.86,volts_per_normalized_unit=.5)
        base=rf_receiver_electrical_budget(**args)
        self.assertAlmostEqual(base['input_signal_dbm'],-62.86)
        self.assertAlmostEqual(base['frontend_noise_rms'],.008003055131611014)
        weak=rf_receiver_electrical_budget(**args,signal_normalized_rms=.1)
        self.assertEqual(base['frontend_noise_rms'],weak['frontend_noise_rms'])
        self.assertAlmostEqual(weak['frontend_evm_rms'],2*base['frontend_evm_rms'])
        wide=rf_receiver_electrical_budget(**dict(args,noise_bandwidth_hz=80e6))
        self.assertAlmostEqual(wide['frontend_noise_rms'],2*base['frontend_noise_rms'])
        for field in ('temperature_k','noise_bandwidth_hz','volts_per_normalized_unit'):
            with self.assertRaises(ValueError):rf_receiver_electrical_budget(**dict(args,**{field:0.}))

    def test_common_80mhz_reference_divides_converter_edges(self):
        def make(reference_hz=80e6):
            c=BehavioralChip(Assumptions())
            settings=dict(SETTINGS,sample_hz=40e6)
            c.configure_numeric(engine='rf',rf=settings);c.attach_shared_rail()
            c.attach_rf_stream(lambda i:.2,external_substeps=4)
            pulse=RailDrivenPulsePLL(rate_hz=2437000000,reference_hz=reference_hz,
                                    bandwidth_hz=1e6,fast_fraction=.25)
            c.shared_rail.attach_pulse_clock(pulse);c.attach_pulse_rf(c.rf_stream)
            return c,pulse
        c,pulse=make();c.attach_rf_timing(dict(absolute_time=True))
        self.assertEqual(c.rf_clock_config['reference_hz'],80e6)
        self.assertEqual(c.rf_clock_config['divider'],2)
        clock=c.rf_clock;clock.arm(0.,2)
        for _ in range(4):
            edge=clock.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
            self.assertEqual(edge.index%2,0)
            self.assertAlmostEqual(edge.time,edge.index/80e6+1e-9,places=18)
            clock.consumed(edge.time,1)
        c.shared_rail.advance(clock.last_time);c.time=clock.last_time
        c.set_common_reference(False)
        self.assertFalse(pulse.present);self.assertFalse(clock.present)
        self.assertIsNone(clock.index);self.assertIsNone(clock.proposal)
        other,_=make()
        with self.assertRaises(ValueError):other.attach_rf_timing(dict(absolute_time=True,reference_hz=40e6))
        reverse=BehavioralChip(Assumptions())
        reverse.configure_numeric(engine='rf',rf=dict(SETTINGS,sample_hz=40e6))
        reverse.attach_rf_stream(lambda i:.2);reverse.attach_rf_timing(dict(absolute_time=True))
        reverse.attach_shared_rail()
        reverse.shared_rail.attach_pulse_clock(RailDrivenPulsePLL(reference_hz=80e6))
        with self.assertRaises(ValueError):reverse.attach_pulse_rf(reverse.rf_stream)

        third,_=make(120e6);third.attach_rf_timing(dict(absolute_time=True))
        self.assertEqual(third.rf_clock_config['divider'],3)
        third.rf_clock.arm(0.,3)
        for _ in range(4):
            edge=third.rf_clock.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
            self.assertEqual(edge.index%3,0)
            self.assertAlmostEqual(edge.time,edge.index/120e6+1e-9,places=18)
            third.rf_clock.consumed(edge.time,1)

    def test_tx_port_is_causal_and_independent_of_rx(self):
        def make(receive):
            captured=[]
            core=SampledRFStream(SETTINGS,noise_rms=0.,external_substeps=4,
                receive_source=lambda t:np.full(len(t),receive,complex),
                mixer_phase_source=lambda t:np.full(len(t),.4),
                tx_volts_per_unit=.5,
                tx_port_observer=lambda times,values:captured.extend(zip(times,values)))
            return core,captured
        a,whole=make(.1);b,parts=make(.7)
        values=np.full(16,.2,complex);times=(np.arange(16)+1)/10e6
        a.process(values,sample_times_s=times)
        b.process(values[:3],sample_times_s=times[:3]);b.process(values[3:],sample_times_s=times[3:])
        np.testing.assert_array_equal(np.array(whole),np.array(parts))
        self.assertTrue(all(value==0 for _,value in whole[:4]))
        code=SampledRFStream.quantize(np.array([.2+0j]),12)[0][0]
        fractions=(np.arange(4)+.5)/4
        expected=.5*code*(1-np.exp(-a.tx.rate*fractions/10e6))*np.exp(-.4j)
        np.testing.assert_allclose([v for _,v in whole[4:8]],expected,rtol=1e-13)
        self.assertTrue(all(t<=times[-1] for t,_ in whole))

    def test_stateful_quadrature_is_monotonic_and_chunk_independent(self):
        def make():
            last=[-float('inf')]
            def phase(t):
                self.assertGreater(t[0],last[0])
                self.assertTrue(np.all(np.diff(t)>0))
                last[0]=t[-1]
                return .2*np.sin(2*np.pi*1e6*t)
            return SampledRFStream(SETTINGS,receive_source=lambda t:.2*np.exp(2j*np.pi*1e5*t),
                                   external_substeps=16,mixer_phase_source=phase)
        values=np.zeros(128);times=(np.arange(128)+1)/10e6
        a=make();b=make()
        whole=a.process(values,sample_times_s=times)
        split=np.r_[b.process(values[:37],sample_times_s=times[:37]),
                    b.process(values[37:],sample_times_s=times[37:])]
        np.testing.assert_array_equal(whole,split)

    def test_absolute_converter_time_preserves_startup_epoch(self):
        minimum=[]
        for absolute in (False,True):
            captured=[]
            def source(times):
                captured.extend(times)
                return np.full(len(times),.2,complex)
            _,report=live_host_rf_observation(np.zeros(64),SETTINGS,
                receive_source=source,external_substeps=8,
                converter_clock_config=dict(absolute_time=absolute),
                host_mode=0,transport_allocation='exclusive')
            self.assertEqual(report['stage'],'transport')
            self.assertEqual(report['converter_clock']['absolute_time'],absolute)
            minimum.append(min(captured))
        self.assertLess(minimum[0],1e-6)
        self.assertGreater(minimum[1],19e-6)
        self.assertAlmostEqual(minimum[1]-minimum[0],20e-6,places=12)

    def test_prefix_search_uses_capture_not_assumed_launch(self):
        known=diagnostic_chirp_prefix(20e6,bandwidth=812500.)
        for lag in (73,273,1024):
            _,estimate=acquire_live_prefix(np.r_[np.zeros(lag),known,np.zeros(32)],known,20e6)
            self.assertEqual(estimate['start'],lag)
        with self.assertRaises(ValueError):
            acquire_live_prefix(np.zeros(4096),known,20e6)

    def test_unqualified_mixer_stops_before_host_payload(self):
        def phase(times):
            raise ClockQualificationError('Test clock is not acquired')
        with self.assertRaises(LiveRFTransportFailure) as failure:
            live_host_rf_observation(np.zeros(64),SETTINGS,
                mixer_phase_source=phase,host_mode=0,transport_allocation='exclusive',
                host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37)
        report=failure.exception.report
        self.assertEqual(report['flow']['fault'],'lo_unqualified')
        self.assertEqual(report['flow']['produced_bits'],0)
        self.assertEqual(report['flow']['returned_bits'],0)
        self.assertEqual(report['dac_samples'],0)

    def test_startup_wait_release_and_timeout(self):
        captured=[]
        def source(times):
            captured.extend(times)
            return np.full(len(times),.2,complex)
        _,report=live_host_rf_observation(np.zeros(64),SETTINGS,
            receive_source=source,external_substeps=8,
            converter_clock_config=dict(absolute_time=True),
            startup_ready=lambda t:t>=40e-6,startup_deadline_s=50e-6,
            host_mode=0,transport_allocation='exclusive')
        self.assertAlmostEqual(report['startup_wait']['qualified_at_s'],40e-6)
        self.assertGreaterEqual(min(captured),40e-6)
        self.assertGreater(report['startup_wait']['transport_start_s'],40e-6)
        with self.assertRaises(LiveRFTransportFailure) as failure:
            live_host_rf_observation(np.zeros(64),SETTINGS,
                startup_ready=lambda t:False,startup_deadline_s=30e-6,
                host_mode=0,transport_allocation='exclusive')
        report=failure.exception.report
        self.assertEqual(report['stage'],'startup')
        self.assertEqual(report['flow']['fault'],'startup_acquisition_timeout')
        self.assertEqual(report['flow']['returned_bits'],0)
        self.assertEqual(report['dac_samples'],0)

    def test_active_clock_loss_latches_and_stop_accounts_for_pending_data(self):
        calls=[0]
        def phase(times):
            if calls[0]>=33:raise ClockQualificationError('Injected active loss')
            calls[0]+=len(times)
            return np.zeros(len(times))
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
        chip.configure_transport('exclusive')
        chip.attach_rf_stream(lambda index:.2,mixer_phase_source=phase)
        chip.start();chip.advance(chip.ready_at)
        epoch=chip.epoch
        observer=TrainedRecordReceiver(decoder=Receiver(0,owner='iq'),startup_timeout_s=30e-6)
        # Aligned-link fixture: existing training precedes the first stream word.
        for i,word in enumerate(observer.training):
            observer.feed(word,chip.time-(8-i)/250e6)
        pending=[];wire_trace=[]
        def host_word(time,word):
            wire_trace.append((time,word))
            for event in observer.feed(word,time):
                if event[0]=='iq':pending.append(event[1])
        arguments=dict(mode=0,source_hz=10e6,sample_bits=24,frames=64,
            epoch=epoch,tx_source=lambda index:0,host_block_words=8,
            host_cdc_read_hz=40e6,host_cdc_phase=.37,host_word_observer=host_word)
        report=chip.transfer(**arguments)
        self.assertEqual(report['fault'],'lo_unqualified')
        self.assertEqual(chip.state,'fault')
        self.assertEqual(chip.rf_stream.index,33)
        self.assertEqual(report['produced_bits'],33*24)
        self.assertGreater(report['returned_bits'],0)
        self.assertGreater(report['pending_bits'],0)
        self.assertEqual(len(pending)*10,report['returned_bits'])
        self.assertEqual(pending,chip.stream['rx_words'])
        self.assertIsNone(observer.fault)
        # Alternate fault policy: forwarded clock continues with a protected abort.
        running=TrainedRecordReceiver(decoder=Receiver(0,owner='iq',fault_status=True),startup_timeout_s=30e-6)
        for i,word in enumerate(running.training):running.feed(word,wire_trace[0][0]-(8-i)/250e6)
        held=[]
        for time,word in wire_trace:
            held.extend(value for kind,value in running.feed(word,time) if kind=='iq')
        holdback=PacketHoldback(1e-3+68/250e6,4096)
        holdback.submit(tuple(held),wire_trace[-1][0])
        suffix=discontinuity_suffix(chip.stream['rx_slot'],chip.stream['rx_header'])
        for i,word in enumerate(suffix):
            time=chip.stream['origin']+(chip.stream['rx_slot']+i)/250e6
            try:
                held.extend(value for kind,value in running.feed(word,time) if kind=='iq')
            except ValueError:
                self.assertEqual(i,len(suffix)-1)
                holdback.invalidate(time,running.fault)
                held.clear()
        self.assertEqual(running.fault,'Remote stream discontinuity')
        self.assertEqual(holdback.advance(time+2e-3),[])
        self.assertEqual(held,[])
        self.assertLessEqual(time-chip.time,68/250e6+1e-15)
        observer.advance(observer.deadline())
        self.assertEqual(observer.fault,'Host clock timeout')
        # External packet holdback invalidates its candidate on watchdog only.
        if observer.fault:pending.clear()
        self.assertEqual(pending,[])
        with self.assertRaises(ValueError):observer.feed(0,observer.time+4e-9)
        self.assertEqual(report['produced_bits'],report['returned_bits']+report['pending_bits'])
        with self.assertRaises(ValueError):chip.transfer(**arguments)
        preserved=chip.rf_stream
        discarded=chip.stop()
        self.assertEqual(discarded['rx_bits'],report['pending_bits'])
        self.assertEqual(discarded['tx_bits'],report['tx']['pending_bits'])
        self.assertEqual(discarded['host_staged_bits'],report['host_staging']['pending_bits'])
        self.assertIs(chip.parked_rf,preserved)
        self.assertEqual(preserved.index,33)
        self.assertGreater(chip.epoch,epoch)
        with self.assertRaises(ValueError):chip.transfer(**arguments)

    def test_running_clock_abort_at_every_frame_position(self):
        for sequence in (0,63):
            frame=encode(0,[],list(range(59)),sequence,owner='iq')
            for position in range(64):
                receiver=Receiver(0,owner='iq',fault_status=True)
                receiver.sequence=sequence
                for word in frame[:position]:receiver.feed(word)
                suffix=discontinuity_suffix(sequence*64+position,frame[:5])
                self.assertLessEqual(len(suffix),68)
                for word in suffix[:-1]:receiver.feed(word)
                with self.assertRaisesRegex(ValueError,'Remote stream discontinuity'):
                    receiver.feed(suffix[-1])
                self.assertTrue(receiver.fault)

    def test_bounded_packet_release_fault_tie_and_overflow(self):
        for rate in (250e6,312.5e6):
            delay=68/rate
            healthy=PacketHoldback(delay,8)
            healthy.submit((1,2,3),1e-6)
            self.assertEqual(healthy.advance(1e-6+delay),[])
            self.assertEqual(healthy.advance(1e-6+delay+1e-12),[(1,2,3)])
            self.assertEqual(healthy.words,0)
            failed=PacketHoldback(delay,8)
            failed.submit((1,2,3),1e-6)
            self.assertEqual(failed.advance(1e-6+delay),[])
            self.assertEqual(failed.invalidate(1e-6+delay,'Remote stream discontinuity'),3)
            self.assertEqual(failed.advance(2e-6),[])
            with self.assertRaises(ValueError):failed.submit((4,),2e-6)
        limited=PacketHoldback(1e-3,4)
        limited.submit((1,2,3),0.)
        with self.assertRaisesRegex(ValueError,'capacity'):
            limited.submit((4,5),1e-6)
        self.assertEqual(limited.words,0)
        self.assertEqual(limited.advance(2e-3),[])

    def test_decision_quality_is_not_payload_integrity(self):
        expected=np.random.default_rng(761).integers(0,2,64)
        different=expected.copy();different[20]^=1
        for rate,fs in ((1e6,10e6),(2e6,20e6)):
            observed=.2*gfsk(different,fs=fs,rate=rate,h=.5).samples
            quality=gfsk_decision_quality(observed,fs=fs,symbol_rate_hz=rate,modulation_index=.5)
            self.assertTrue(quality['packet_quality_pass'])
            np.testing.assert_array_equal(quality['candidate_payload_bits'],different)
            self.assertFalse(np.array_equal(quality['candidate_payload_bits'],expected))
            erased=gfsk_decision_quality(np.zeros_like(observed),fs=fs,symbol_rate_hz=rate,modulation_index=.5)
            self.assertFalse(erased['packet_quality_pass'])
            self.assertEqual(erased['candidate_payload_bits'],[])

    def test_external_integrity_rejects_clean_wrong_candidate(self):
        import zlib
        payload=bytes(range(8))
        packet=payload+zlib.crc32(payload).to_bytes(4,'little')
        source=np.unpackbits(np.frombuffer(packet,dtype=np.uint8),bitorder='little')
        for corrupted in (False,True):
            bits=source.copy()
            if corrupted:bits[20]^=1
            waveform=.2*gfsk(bits,fs=20e6,rate=2e6,h=.5).samples
            quality=gfsk_decision_quality(waveform,fs=20e6,symbol_rate_hz=2e6)
            self.assertTrue(quality['packet_quality_pass'])
            self.assertFalse(quality['integrity_checked'])
            received=np.packbits(np.array(quality['candidate_payload_bits'],dtype=np.uint8),bitorder='little').tobytes()
            valid=zlib.crc32(received[:-4])==int.from_bytes(received[-4:],'little')
            self.assertEqual(valid,not corrupted)
        # Diagnostic external CRC fixture only; not a BLE packet or on-chip CRC.

    def test_shared_rail_pulse_pll_integral_and_partition(self):
        for inductance in (0.,5e-9):
            rail=SharedRail(inductance_h=inductance);rail.load(20e-12)
            whole=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
            whole.bind_rail_interval(rail,200e-9)
            exact=whole.rail_phase_integral(0.,200e-9)
            dt=200e-9/20000
            numeric=sum(whole.rail_frequency((i+.5)*dt)*dt for i in range(20000))
            self.assertAlmostEqual(exact,numeric,delta=1e-8)
            self.assertAlmostEqual(exact,whole.rail_phase_integral(0.,73e-9)+whole.rail_phase_integral(73e-9,200e-9),delta=1e-12)
            split=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
            self.assertTrue(whole.advance(200e-9))
            for i in range(1,201):
                end=i*1e-9
                split.bind_rail_interval(rail,end)
                self.assertTrue(split.advance(end));rail.advance(end)
            self.assertAlmostEqual(whole.phase,split.phase,delta=1e-6)
            self.assertAlmostEqual(whole.filter.v,split.filter.v,delta=1e-9)
            self.assertEqual(whole.feedback_edges,split.feedback_edges)
            with self.assertRaises(ValueError):whole.advance(201e-9)

    def test_shared_rail_owns_loaded_pulse_clock_timeline(self):
        def run(inductance,subdivide,sensitivity):
            rail=SharedRail(inductance_h=inductance,lo_hz_per_v=sensitivity,
                full_host_activity=True,input_transition_charge_c=.3e-12)
            clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
            rail.attach_pulse_clock(clock)
            with self.assertRaises(ValueError):rail.attach_pulse_clock(clock)
            for index in range(250):
                start=index*4e-9;end=(index+1)*4e-9
                rail.host_word(1023 if index%2 else 0)
                rail.host_input(341 if index%2 else 682)
                if index%5==0:rail.converter()
                if subdivide:rail.advance((start+end)/2)
                rail.advance(end)
                self.assertEqual(clock.time,rail.time)
                self.assertIsNone(clock.rail_segment[0].pulse_clock)
            return rail,clock
        for inductance in (0.,5e-9):
            rail,clock=run(inductance,False,1e8)
            split,other=run(inductance,True,1e8)
            uncoupled,quiet=run(inductance,False,0.)
            self.assertEqual((rail.host_events,rail.input_events,rail.converter_events),(250,250,50))
            self.assertEqual(rail.pulse_clock_intervals,250)
            self.assertEqual(split.pulse_clock_intervals,500)
            self.assertAlmostEqual(rail.charge,split.charge,delta=1e-20)
            self.assertAlmostEqual(rail.voltage,uncoupled.voltage,delta=1e-12)
            self.assertAlmostEqual(clock.phase,other.phase,delta=1e-6)
            self.assertAlmostEqual(clock.filter.v,other.filter.v,delta=1e-9)
            self.assertEqual(clock.feedback_edges,other.feedback_edges)
            self.assertGreater(abs(clock.phase-quiet.phase),1e-5)

    def test_pulse_phase_history_is_bounded_and_nonmutating(self):
        rail=SharedRail(inductance_h=5e-9)
        clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
        rail.attach_pulse_clock(clock);rail.load(20e-12)
        rail.advance(2e-9);expected=clock.phase
        rail.advance(4e-9);rail.host_word(1023);rail.advance(8e-9)
        state=(clock.time,clock.phase,clock.feedback_edges,clock.filter.v)
        self.assertAlmostEqual(clock.observed_phase([2e-9])[0],expected,delta=1e-9)
        self.assertEqual(state,(clock.time,clock.phase,clock.feedback_edges,clock.filter.v))
        with self.assertRaises(ValueError):clock.observed_phase([9e-9])
        for index in range(1,514):rail.advance(8e-9+index*1e-9)
        self.assertEqual(len(clock.phase_intervals),512)
        with self.assertRaises(ValueError):clock.observed_phase([2e-9])

    def test_shared_pulse_rf_uses_history_without_double_supply_phase(self):
        chip=BehavioralChip(Assumptions());chip.attach_shared_rail(inductance_h=5e-9)
        rail=chip.shared_rail
        clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
        rail.attach_pulse_clock(clock)
        def make():
            return SampledRFStream(SETTINGS,receive_source=lambda t:np.full(len(t),.2+.1j),
                                   external_substeps=16,noise_rms=0.)
        actual=make();reference=make();double=make()
        chip.attach_pulse_rf(actual)
        reference.mixer_phase_source=actual.mixer_phase_source
        double.mixer_phase_source=actual.mixer_phase_source
        changed=False
        for index in range(1,9):
            rail.host_word(1023 if index%2 else 0)
            rail.advance(index/SETTINGS['sample_hz']);chip.rf_sample_time=rail.time
            result=chip._rf_step(actual,[0.])
            scale=1+(rail.voltage/rail.nominal-1)*rail.rf_gain_fraction
            expected=reference.process([0.],supply_scale=scale,sample_times_s=[rail.time])
            wrong=double.process([0.],supply_scale=scale,sample_times_s=[rail.time],supply_phase_rad=rail.phase)
            np.testing.assert_array_equal(result,expected)
            changed|=not np.array_equal(result,wrong)
        self.assertTrue(changed)
        with self.assertRaises(ValueError):chip.attach_pulse_rf(actual)
        chip.rf_sample_time=None
        with self.assertRaises(ValueError):chip._rf_step(actual,[0.])

    def test_shared_pulse_count_interlock_blocks_premature_live_payload(self):
        with self.assertRaises(LiveRFTransportFailure) as caught:
            live_host_rf_observation(np.full(8,.2+.1j),SETTINGS,
                rail_config=dict(inductance_h=5e-9,full_host_activity=True),
                pulse_clock_config=dict(rate_hz=2437000000,bandwidth_hz=1e6,
                    fast_fraction=.1,require_acquisition=True),
                converter_clock_config=dict(absolute_time=True),
                host_mode=0,transport_allocation='exclusive')
        report=caught.exception.report
        self.assertEqual(report['flow']['fault'],'lo_unqualified')
        self.assertEqual(report['dac_samples'],0)
        self.assertFalse(report['pulse_clock']['count_acquired'])
        self.assertIsNone(report['pulse_clock']['first_acquired_s'])

    def test_shared_pulse_startup_deadline_withholds_transport(self):
        with self.assertRaises(LiveRFTransportFailure) as caught:
            live_host_rf_observation(np.full(8,.2+.1j),SETTINGS,
                rail_config=dict(inductance_h=5e-9),
                pulse_clock_config=dict(rate_hz=2437000000,bandwidth_hz=1e6,
                    fast_fraction=.1,require_acquisition=True,wait_for_acquisition=True),
                converter_clock_config=dict(absolute_time=True),startup_deadline_s=21e-6,
                host_mode=0,transport_allocation='exclusive')
        report=caught.exception.report
        self.assertEqual(report['stage'],'startup')
        self.assertEqual(report['flow']['fault'],'startup_acquisition_timeout')
        self.assertEqual(report['flow']['tx']['prefill_bits'],0)
        self.assertEqual(report['dac_samples'],0)
        self.assertTrue(report['startup_wait']['enabled'])

    def test_shared_pulse_reference_loss_preserves_state_and_copy_isolation(self):
        import copy
        rail=SharedRail(inductance_h=5e-9)
        clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,
                                fast_fraction=.1,require_acquisition=True)
        rail.attach_pulse_clock(clock);rail.advance(1e-6)
        clock.bind_rail_interval(rail,1.2e-6)
        clone=copy.copy(clock)
        before=(clock.acquisition.time,clock.acquisition.edges,len(clock.phase_intervals))
        self.assertTrue(clone.advance(1.1e-6))
        self.assertEqual(before,(clock.acquisition.time,clock.acquisition.edges,len(clock.phase_intervals)))
        phase=clock.phase;voltage=clock.filter.v;feedback=clock.feedback_edges
        clock.set_reference(False,rail.time)
        self.assertEqual((clock.phase,clock.filter.v,clock.feedback_edges),(phase,voltage,feedback))
        rail.advance(1.2e-6)
        self.assertIsNone(clock.acquisition.anchor)
        self.assertEqual(clock.acquisition.good,0)
        self.assertFalse(clock.acquisition.acquired)
        self.assertGreater(clock.phase,phase)
        phase=clock.phase;voltage=clock.filter.v
        clock.set_reference(True,rail.time)
        self.assertEqual((clock.phase,clock.filter.v),(phase,voltage))
        rail.advance(1.3e-6)
        self.assertIsNotNone(clock.acquisition.anchor)
        self.assertFalse(clock.acquisition.acquired)
        self.assertGreater(clock.acquisition.last_edge,1.2e-6)

    def test_scheduled_reference_gap_matches_manual_persistent_clock(self):
        def make(events):
            rail=SharedRail(inductance_h=5e-9)
            clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,
                fast_fraction=.1,require_acquisition=True,reference_events=events)
            rail.attach_pulse_clock(clock);rail.load(20e-12)
            return rail,clock
        rail,clock=make(((1e-6,False),(1.2e-6,True)))
        manual,other=make(())
        rail.advance(1.4e-6)
        manual.advance(1e-6);other.set_reference(False,manual.time)
        manual.advance(1.2e-6);other.set_reference(True,manual.time)
        manual.advance(1.4e-6)
        self.assertAlmostEqual(clock.phase,other.phase,delta=1e-6)
        self.assertAlmostEqual(clock.filter.v,other.filter.v,delta=1e-9)
        self.assertEqual(clock.feedback_edges,other.feedback_edges)
        self.assertEqual(clock.acquisition.edges,other.acquisition.edges)
        self.assertFalse(clock.acquisition.acquired)
        self.assertEqual(clock.reference_event_index,2)
        self.assertTrue(np.all(np.isfinite(clock.observed_phase([1.05e-6,1.25e-6]))))

    def test_live_fixture_external_host_observer_decodes_actual_words(self):
        observer=TrainedRecordReceiver(decoder=Receiver(0,owner='iq'),startup_timeout_s=30e-6)
        received=[];seen=[]
        def consume(time,word):
            if not seen:
                for i,training in enumerate(observer.training):
                    observer.feed(training,time-(8-i)/250e6)
            seen.append((time,word))
            received.extend(value for kind,value in observer.feed(word,time) if kind=='iq')
        samples,report=live_host_rf_observation(np.full(8,.2+.1j),SETTINGS,
            host_mode=0,transport_allocation='exclusive',host_word_observer=consume)
        self.assertEqual(len(received)*10,report['flow']['returned_bits'])
        packed=sum(word<<(10*i) for i,word in enumerate(received))
        def signed(value):return value if value<2048 else value-4096
        unpacked=np.array([(signed((packed>>(24*i))&4095)+
                          1j*signed((packed>>(24*i+12))&4095))/2048 for i in range(8)])
        np.testing.assert_array_equal(unpacked,samples)
        self.assertIsNone(observer.fault)
        observer.advance(observer.deadline())
        self.assertEqual(observer.fault,'Host clock timeout')

    def test_absolute_pulse_rf_normal_stop_keeps_converter_epoch(self):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
        chip.configure_transport('exclusive');chip.attach_shared_rail(inductance_h=5e-9)
        clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
        chip.shared_rail.attach_pulse_clock(clock)
        chip.attach_rf_stream(lambda index:.2+.1j)
        chip.attach_pulse_rf(chip.rf_stream);chip.attach_rf_timing(dict(absolute_time=True))
        chip.start();chip.advance(chip.ready_at)
        result=chip.transfer(mode=0,source_hz=SETTINGS['sample_hz'],sample_bits=24,
            frames=4,epoch=chip.epoch,tx_source=lambda index:0,**chip.timed_rf_callbacks())
        self.assertIsNone(result['fault'])
        core=chip.rf_stream;last=core.last_sample_time;count=core.index
        chip.stop();chip.advance(chip.time+1e-6)
        self.assertIs(chip.parked_rf,core)
        self.assertGreater(core.index,count)
        self.assertGreater(core.last_sample_time,last)
        self.assertEqual(chip.shared_rail.time,clock.time)
        self.assertEqual(chip.time,clock.time)
        chip.resume_rf_stream(lambda index:.2+.1j);chip.start();chip.advance(chip.ready_at)
        resumed=chip.transfer(mode=0,source_hz=SETTINGS['sample_hz'],sample_bits=24,
            frames=4,epoch=chip.epoch,tx_source=lambda index:0,**chip.timed_rf_callbacks())
        self.assertIsNone(resumed['fault'])
        self.assertIs(chip.rf_stream,core)
        self.assertGreater(core.last_sample_time,last)

    def test_common_reference_cancels_converter_proposal_without_analog_reset(self):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
        chip.attach_shared_rail();clock=RailDrivenPulsePLL(rate_hz=2437000000,require_acquisition=True)
        chip.shared_rail.attach_pulse_clock(clock);chip.attach_rf_stream(lambda i:.2)
        chip.attach_pulse_rf(chip.rf_stream);chip.attach_rf_timing(dict(absolute_time=True))
        chip.rf_clock.arm(0.,4);proposal=chip._forecast_rf_edge()
        before=(clock.phase,clock.filter.v,clock.feedback_edges,chip.rf_stream.index)
        event=chip.set_common_reference(False)
        self.assertEqual(event['cancelled_edge_s'],proposal.time)
        self.assertFalse(clock.present);self.assertFalse(chip.rf_clock.present)
        self.assertIsNone(chip.rf_clock.proposal);self.assertIsNone(chip.rf_clock.index)
        self.assertEqual(before,(clock.phase,clock.filter.v,clock.feedback_edges,chip.rf_stream.index))
        chip.set_common_reference(True)
        self.assertTrue(clock.present);self.assertTrue(chip.rf_clock.present)
        self.assertIsNone(chip.rf_clock.index)
        with self.assertRaises(ValueError):chip.start()
        self.assertTrue(chip.rf_timing_recovery_required)

    def test_timed_dac_update_cannot_drive_the_preceding_interval(self):
        first=SampledRFStream(SETTINGS,noise_rms=0.)
        other=SampledRFStream(SETTINGS,noise_rms=0.)
        first.process([.5],sample_times_s=[1e-7])
        other.process([-.5],sample_times_s=[1e-7])
        self.assertEqual(first.tx.state,0j)
        self.assertEqual(other.tx.state,0j)
        self.assertEqual(first.held_dac,.5)
        first.process([-.25],sample_times_s=[3e-7])
        expected=.5*(-np.expm1(-2*np.pi*SETTINGS['tx_cutoff_hz']*2e-7))
        self.assertAlmostEqual(first.tx.state.real,expected,delta=1e-14)
        whole=SampledRFStream(SETTINGS,noise_rms=0.)
        whole.process([.5,-.25],sample_times_s=[1e-7,3e-7])
        self.assertEqual(whole.tx.state,first.tx.state)
        self.assertEqual(whole.held_dac,first.held_dac)

    def test_local_tx_quadrature_is_causal_and_chunk_equivalent(self):
        def make():return SampledRFStream(SETTINGS,external_substeps=16,noise_rms=0.)
        a=make();b=make();values=np.array([.5,-.25,.1j,.2,.3j]);times=np.arange(1,6)/1e7
        whole=a.process(values,sample_times_s=times)
        pieces=np.r_[b.process(values[:2],sample_times_s=times[:2]),
                     b.process(values[2:],sample_times_s=times[2:])]
        np.testing.assert_array_equal(whole,pieces)
        self.assertEqual(whole[0],0j)
        self.assertEqual(a.tx.state,b.tx.state)
        np.testing.assert_allclose(a.rx.state,b.rx.state,atol=1e-15)

    def test_analog_hold_evolves_filters_without_fabricating_samples(self):
        import copy
        a=SampledRFStream(SETTINGS,external_substeps=16,noise_rms=.01,frontend_noise_rms=.01,phase_rms_rad=.01)
        a.process([.5],sample_times_s=[1e-7]);b=copy.deepcopy(a)
        before=(a.index,a.last_sample_time,a.dac_clips,a.adc_clips)
        random_states=[copy.deepcopy(g.bit_generator.state) for g in (a.rng,a.frontend_rng,a.phase_rng)]
        for time in (2e-7,3e-7,4e-7):
            self.assertEqual(len(a.advance_analog_hold(time)),0)
            b.process([.5],sample_times_s=[time])
        self.assertEqual(before,(a.index,a.last_sample_time,a.dac_clips,a.adc_clips))
        self.assertEqual(random_states,[g.bit_generator.state for g in (a.rng,a.frontend_rng,a.phase_rng)])
        self.assertAlmostEqual(a.tx.state.real,.5*(-np.expm1(-a.tx.rate*3e-7)),delta=1e-14)
        self.assertEqual(a.tx.state,b.tx.state)
        np.testing.assert_array_equal(a.rx.state,b.rx.state)
        a.process([-.25],sample_times_s=[5e-7]);b.process([-.25],sample_times_s=[5e-7])
        self.assertEqual(a.tx.state,b.tx.state)
        np.testing.assert_array_equal(a.rx.state,b.rx.state)
        self.assertEqual(a.index,2)
        self.assertAlmostEqual(a.maximum_interval,4e-7,delta=1e-20)

    def test_common_reference_gap_evolves_retained_chip_without_converter_edges(self):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
        chip.configure_transport('exclusive');chip.attach_shared_rail(inductance_h=5e-9)
        clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
        chip.shared_rail.attach_pulse_clock(clock)
        chip.attach_rf_stream(lambda i:.25+.125j,external_substeps=16)
        chip.attach_pulse_rf(chip.rf_stream);chip.attach_rf_timing(dict(absolute_time=True))
        chip.start();chip.advance(chip.ready_at)
        flow=chip.transfer(mode=0,source_hz=SETTINGS['sample_hz'],sample_bits=24,frames=4,
            epoch=chip.epoch,tx_source=lambda i:0,**chip.timed_rf_callbacks())
        self.assertIsNone(flow['fault'])
        chip.set_common_reference(False);chip.stop()
        core=chip.parked_rf;rail=chip.shared_rail
        before=(core.index,rail.converter_events,rail.host_events,core.last_sample_time,core.held_dac)
        phase=clock.phase
        chip.advance_reference_gap(chip.time+200e-9)
        self.assertEqual(before,(core.index,rail.converter_events,rail.host_events,core.last_sample_time,core.held_dac))
        self.assertGreater(clock.phase,phase)
        self.assertEqual(core.analog_time,chip.time)
        self.assertEqual(rail.time,clock.time)
        with self.assertRaises(ValueError):chip.rearm_after_reference()
        chip.set_common_reference(True)
        chip.advance_reference_gap(chip.time+200e-9)
        with self.assertRaises(ValueError):chip.rearm_after_reference()
        self.assertIsNone(chip.rf_clock.index)
        self.assertTrue(chip.rf_timing_recovery_required)
        with self.assertRaises(ValueError):chip.resume_rf_stream(lambda i:0j)

    def test_external_retraining_decodes_only_resumed_host_epoch(self):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
        chip.configure_transport('exclusive');chip.attach_rf_stream(lambda i:.2+.1j)
        observer=TrainedRecordReceiver(decoder=Receiver(0,owner='iq'),startup_timeout_s=30e-6)
        received=[]
        def transfer():
            for i,word in enumerate(observer.training):
                observer.feed(word,chip.time-(8-i)/250e6)
            def emitted(time,word):
                received.extend(value for kind,value in observer.feed(word,time) if kind=='iq')
            return chip.transfer(mode=0,source_hz=10e6,sample_bits=24,frames=8,
                epoch=chip.epoch,tx_source=lambda i:0,host_word_observer=emitted)
        chip.start();chip.advance(chip.ready_at);first=transfer()
        self.assertEqual(received,chip.stream['rx_words'])
        old=list(received);epoch=chip.epoch;core=chip.rf_stream
        discarded=chip.stop()
        observer.advance(observer.deadline());received.clear()
        self.assertEqual(observer.fault,'Host clock timeout')
        with self.assertRaises(ValueError):observer.feed(old[0],observer.time+4e-9)
        self.assertEqual(discarded['rx_bits'],first['pending_bits'])
        chip.advance(observer.time+1e-6);observer.arm(chip.time)
        chip.resume_rf_stream(lambda i:-.3+.15j);chip.start();chip.advance(chip.ready_at)
        second=transfer()
        self.assertEqual(second['fault'],None)
        self.assertEqual(received,chip.stream['rx_words'])
        self.assertEqual(len(received)*10,second['returned_bits'])
        self.assertNotEqual(received,old)
        self.assertIs(chip.rf_stream,core)
        self.assertGreater(chip.epoch,epoch)
        with self.assertRaises(ValueError):
            chip.transfer(mode=0,source_hz=10e6,sample_bits=24,frames=1,epoch=epoch)

    def test_common_reference_loss_watchdog_runs_without_converter_events(self):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
        chip.configure_transport('exclusive');chip.attach_shared_rail()
        clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
        chip.shared_rail.attach_pulse_clock(clock)
        chip.attach_rf_stream(lambda i:.2,external_substeps=4)
        chip.attach_pulse_rf(chip.rf_stream);chip.attach_rf_timing(dict(absolute_time=True))
        chip.start();chip.advance(chip.ready_at)
        args=dict(mode=0,source_hz=10e6,sample_bits=24,frames=4,epoch=chip.epoch,
                  tx_source=lambda i:0,**chip.timed_rf_callbacks())
        initial=chip.transfer(**args);self.assertIsNone(initial['fault'])
        core=chip.rf_stream;count=core.index;events=chip.shared_rail.converter_events;at=chip.time
        chip.set_common_reference(False)
        result=chip.transfer(**args)
        self.assertEqual(result['fault'],'reference_lost')
        self.assertEqual(core.index,count)
        self.assertEqual(chip.shared_rail.converter_events,events)
        self.assertLessEqual(chip.time-at,104e-9)
        self.assertEqual(result['produced_bits'],result['returned_bits']+result['pending_bits'])
        chip.stop();chip.advance_reference_gap(chip.time+200e-9)
        self.assertEqual(core.index,count)

    def test_scheduled_common_loss_preempts_a_converter_edge(self):
        for offset,expected in ((-1e-9,0),(0.,0),(1e-9,1),(100e-9,1)):
            chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=SETTINGS)
            chip.configure_transport('exclusive');chip.attach_shared_rail()
            clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
            chip.shared_rail.attach_pulse_clock(clock)
            chip.attach_rf_stream(lambda i:.2,external_substeps=4)
            chip.attach_pulse_rf(chip.rf_stream);chip.attach_rf_timing(dict(absolute_time=True))
            chip.start();chip.advance(chip.ready_at)
            callbacks=chip.timed_rf_callbacks()
            first=chip.time+callbacks['rx_event_time'](0)
            loss=first+offset
            chip.schedule_common_reference_loss(loss)
            result=chip.transfer(mode=0,source_hz=10e6,sample_bits=24,frames=4,epoch=chip.epoch,
                tx_source=lambda i:0,**callbacks)
            self.assertEqual(result['fault'],'reference_lost')
            self.assertEqual(chip.rf_stream.index,expected)
            self.assertEqual(chip.shared_rail.converter_events,expected)
            self.assertIsNone(chip.pending_common_reference_loss)
            self.assertLessEqual(chip.time-loss,104e-9)

    def test_common_loss_timer_fires_without_a_host_edge(self):
        chip=BehavioralChip(Assumptions(host_clock_scale=.001))
        chip.configure_numeric(engine='rf',rf=SETTINGS);chip.configure_transport('exclusive')
        chip.attach_shared_rail();clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1)
        chip.shared_rail.attach_pulse_clock(clock);chip.attach_rf_stream(lambda i:.2,external_substeps=4)
        chip.attach_pulse_rf(chip.rf_stream);chip.attach_rf_timing(dict(absolute_time=True))
        chip.start();chip.advance(chip.ready_at);callbacks=chip.timed_rf_callbacks()
        loss=chip.time+callbacks['rx_event_time'](0);chip.schedule_common_reference_loss(loss)
        emitted=[]
        result=chip.transfer(mode=0,source_hz=10e6,sample_bits=24,frames=1,epoch=chip.epoch,
            tx_source=lambda i:0,host_word_observer=lambda at,word:emitted.append(at),**callbacks)
        self.assertEqual(result['fault'],'reference_lost')
        self.assertTrue(emitted)
        self.assertLess(max(emitted),loss)
        self.assertLessEqual(chip.time-loss,100e-9+1e-15)
        self.assertEqual(chip.rf_stream.index,0)

    def test_lora_quality_is_not_packet_integrity(self):
        from behavioral import lora,lora_decision_quality
        symbols=[0,32,64,96,7,53,91,22]
        wave=.2*lora(symbols,oversample=16).samples
        good=lora_decision_quality(wave)
        self.assertTrue(good['packet_quality_pass'])
        self.assertFalse(good['integrity_checked'])
        self.assertEqual(good['candidate_payload_symbols'],symbols[4:])
        erased=wave.copy();erased[-128*16:]=0
        bad=lora_decision_quality(erased)
        self.assertFalse(bad['packet_quality_pass'])
        self.assertEqual(bad['candidate_payload_symbols'],[])
        changed=symbols[:-1]+[23]
        wrong=lora_decision_quality(.2*lora(changed,oversample=16).samples)
        self.assertTrue(wrong['packet_quality_pass'])
        self.assertNotEqual(wrong['candidate_payload_symbols'],symbols[4:])
        self.assertFalse(wrong['integrity_checked'])

    def test_invalid_phase_does_not_commit_converter_samples(self):
        for subdivisions in (0,16):
            stream=SampledRFStream(SETTINGS,receive_source=lambda t:np.zeros(len(t),complex),
                external_substeps=subdivisions,mixer_phase_source=lambda t:np.full(len(t),np.nan))
            with self.assertRaises(ValueError):stream.process(np.zeros(8))
            self.assertEqual(stream.index,0)

if __name__=='__main__':unittest.main()
