"""Independent conservation and enclosure checks for the selected baseline."""
import unittest
import json
import numpy as np
from baseline_envelope import MODE_CURRENT_A, selected_dc_ledger, rail_excursion
from robustness_envelope import shared_board_candidate


class BaselineBudgetTests(unittest.TestCase):
    def test_internal_switching_charge_fourier_ports_and_budget(self):
        from baseline_envelope import internal_switching_sources
        rate=156.25e6;tau=.2e-9;mean=.020;origin=.17/rate
        load=dict(owner='core',mean_a=mean,event_hz=rate,tau_s=tau,origin_s=origin,harmonics=8)
        ports=internal_switching_sources([load]);period=1/rate
        # Independent time-domain integration of positive periodic pulses.
        t=(np.arange(131072)+.5)*period/131072
        age=(t-origin)%period
        current=sum(mean/rate*(age+j*period)**2*np.exp(-(age+j*period)/tau)/(2*tau**3) for j in range(4))
        self.assertAlmostEqual(float(current.mean()),mean,places=10)
        for k in (1,3,8):
            measured=2*np.mean(current*np.exp(-2j*np.pi*k*rate*t))
            np.testing.assert_allclose(ports[k*rate][3],measured,rtol=1e-8,atol=1e-12)
            self.assertEqual(sum(ports[k*rate]),0)
            self.assertEqual(ports[k*rate][1],-ports[k*rate][3])
        with self.assertRaises(ValueError):internal_switching_sources([load,load,load])
        self.assertEqual(internal_switching_sources([]),{})

    def test_supply_driven_channel_against_augmented_state_space(self):
        from scipy import signal,linalg
        from wired_envelope import physical_receiver
        bits=[1,0,1];edges=np.array([.2,.7,1.3,1.8])
        tones=[dict(frequency_hz=.73e9,clock_rail_voltage_peak_v=.23,voltage_phase_rad=.31),
               dict(frequency_hz=2.17e9,clock_rail_voltage_peak_v=.17,voltage_phase_rad=-.8)]
        for load_tau,ctle in ((.135,True),(.135,False),(.1,False)):
            q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
                signal_scale=.9,rail_dc_v=2.9,rail_tones=tones,rail_modulation_location='driver')
            denominator=np.polymul([.1,1],[load_tau,1]);numerator=[1.]
            if ctle:
                q.update(ctle_zero_s=200e-12,ctle_pole_s=80e-12)
                denominator=np.polymul(denominator,[.08,1]);numerator=[.2,1]
            rx=physical_receiver(bits,2.5e9,0.,0.,100e-12,load_tau*1e-9/50,q,
                source_edges_s=edges*1e-9,hold_final_level=True)
            # Independent real companion states plus real oscillator states,
            # all in nanoseconds. No modal residues or particular solution.
            a,b,c,d=signal.tf2ss(numerator,denominator);n=len(a)
            for sample in (.45,.7001,.85,1.45,2.0):
                state=np.zeros(n)
                for i,bit in enumerate(bits):
                    finish=sample if i==len(bits)-1 else min(sample,edges[i+1])
                    duration=finish-edges[i]
                    if duration<=0:break
                    aug=np.zeros((n+1+2*len(tones),n+1+2*len(tones)))
                    aug[:n,:n]=a;sign=1 if bit else -1;aug[:n,n]=sign*b[:,0]
                    extra=[1.]
                    for k,tone in enumerate(tones):
                        w=2*np.pi*tone['frequency_hz']*1e-9;j=n+1+2*k
                        aug[:n,j]=sign*b[:,0]*tone['clock_rail_voltage_peak_v']/q['rail_dc_v']
                        aug[j,j+1]=-w;aug[j+1,j]=w
                        theta=w*edges[i]+tone['voltage_phase_rad']
                        extra.extend([np.cos(theta),np.sin(theta)])
                    state=(linalg.expm(aug*duration)@np.r_[state,extra])[:n]
                    if finish==sample:break
                expected=.4*q['signal_scale']*float((c@state).item())
                self.assertAlmostEqual(rx.voltage(sample*1e-9*2.5e9),expected,places=10)

    def test_driver_rail_tone_gets_channel_filtering_and_dc_limit(self):
        from wired_envelope import physical_receiver
        rate=2.5e9;frequency=2e9;phase=.37;time=99.3e-9
        q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
            signal_scale=.9,rail_dc_v=3.,rail_modulation_location='driver',
            rail_tones=[dict(frequency_hz=frequency,clock_rail_voltage_peak_v=.3,voltage_phase_rad=phase)],
            ctle_zero_s=200e-12,ctle_pole_s=80e-12)
        rx=physical_receiver([1],rate,0.,0.,100e-12,2.7e-12,q,source_edges_s=[0.,200e-9])
        s=2j*np.pi*frequency
        h=(1+s*200e-12)/((1+s*100e-12)*(1+s*135e-12)*(1+s*80e-12))
        expected=.36*(1+.1*np.real(h*np.exp(2j*np.pi*frequency*time+1j*phase)))
        self.assertAlmostEqual(rx.voltage(time*rate),expected,places=11)
        bits=[1,0,1,1];edges=np.array([0.,.45,.91,1.37,1.9])*1e-9
        driver=dict(q,rail_tones=[])
        receiver=dict(driver,rail_modulation_location='receiver')
        a=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,driver,source_edges_s=edges)
        b=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,receiver,source_edges_s=edges)
        for t in np.linspace(.05e-9,1.85e-9,40):
            self.assertAlmostEqual(a.voltage(t*rate),b.voltage(t*rate),places=11)

    def test_actual_tx_events_preserve_transport_bits_and_chunking(self):
        from baseline_envelope import selected_environment,reference_payload_environment,wired_transmit_transport,P
        contract=json.loads((P/'spec/contract.json').read_text())
        e,_=reference_payload_environment(selected_environment(contract,'wire',2.5e9,312.5e6),
            dict(link_r_ohm=1e-5),False,source_peak_v=.75)
        whole,trace=wired_transmit_transport(e,frames=16,host_service_ppm=-100.)
        split,other=wired_transmit_transport(e,frames=16,host_service_ppm=-100.,chunks=(3,5,8))
        self.assertEqual(whole,split)
        self.assertEqual(trace['bits'],other['bits'])
        np.testing.assert_array_equal(trace['edges_s'],other['edges_s'])
        self.assertIsNone(whole['flow']['fault'])
        self.assertEqual(whole['payload_bit_errors'],0)
        self.assertGreater(whole['flow']['tx']['minimum_bits'],0)
        self.assertLess(whole['maximum_word_event_error_s'],1e-15)
        self.assertAlmostEqual(whole['flow']['host_capacity_bps'],312.5e6*10*59/64)
        # This independent expected source includes the real prefill bits,
        # followed by host-supplied data; no transport output feeds this oracle.
        expected=np.random.default_rng(9021).integers(0,2,2600).tolist()
        self.assertEqual(trace['bits'],expected)

    def test_observed_reference_halt_drains_actual_tx_queue(self):
        from baseline_envelope import selected_environment,reference_payload_environment,wired_transmit_transport,P
        contract=json.loads((P/'spec/contract.json').read_text())
        e,_=reference_payload_environment(selected_environment(contract,'wire',2.5e9,312.5e6),
            dict(link_r_ohm=1e-5),False,source_peak_v=.75)
        result,_=wired_transmit_transport(e,frames=16,reference_stop_s=.5e-6)
        self.assertEqual(result['flow']['fault'],'underflow')
        self.assertEqual(result['chip_state'],'fault')
        self.assertEqual(result['payload_bit_errors'],0)
        self.assertLess(result['flow']['tx']['pending_bits'],10)
        self.assertGreater(result['flow']['simulated_s'],.5e-6)
        self.assertLess(result['flow']['simulated_s'],2e-6)

    def test_nonuniform_serial_edges_against_two_pole_step(self):
        from wired_envelope import physical_receiver
        rate=2.5e9;a=100e-12;b=135e-12
        q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.)
        edge=.2e-9
        rx=physical_receiver([1,1],rate,0.,0.,a,b/50,q,source_edges_s=[edge,.7e-9,1.3e-9])
        self.assertEqual(rx.voltage(.1e-9*rate),0.)
        for time in (.3e-9,.65e-9,.8e-9,1.2e-9):
            elapsed=time-edge
            expected=.4*(1-(a*np.exp(-elapsed/a)-b*np.exp(-elapsed/b))/(a-b))
            self.assertAlmostEqual(rx.voltage(time*rate),expected,places=12)
        bits=[1,0,1,1,0,0,1,0]
        normal=physical_receiver(bits,rate,0.,0.,a,b/50,q)
        explicit=physical_receiver(bits,rate,0.,0.,a,b/50,q,source_edges_s=np.arange(len(bits)+1)/rate)
        for time in np.linspace(.1,len(bits)-.1,71):
            self.assertAlmostEqual(normal.voltage(time),explicit.voltage(time),places=12)
        with self.assertRaises(ValueError):
            physical_receiver(bits,rate,0.,0.,a,b/50,q,source_edges_s=np.zeros(len(bits)+1))

    def test_nonuniform_serial_ctle_against_state_space(self):
        from scipy import signal,linalg
        from wired_envelope import physical_receiver
        q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,ctle_zero_s=200e-12,ctle_pole_s=80e-12)
        bits=[1,0,1];edges=np.array([.2,.7,1.3,1.8])
        rx=physical_receiver(bits,2.5e9,0.,0.,100e-12,2.7e-12,q,source_edges_s=edges*1e-9)
        # Independent real companion-state evolution, in nanosecond units.
        denominator=np.polymul(np.polymul([.1,1],[.135,1]),[.08,1])
        a,b,c,d=signal.tf2ss([.2,1],denominator)
        augmented=np.zeros((4,4));augmented[:3,:3]=a;augmented[:3,3]=b[:,0]
        for time in (.45,.85,1.45):
            state=np.zeros(3)
            for i,bit in enumerate(bits):
                duration=min(time,edges[i+1])-edges[i]
                if duration<=0:break
                transition=linalg.expm(augmented*duration)
                state=transition[:3,:3]@state+transition[:3,3]*(1 if bit else -1)
                if time<=edges[i+1]:break
            self.assertAlmostEqual(rx.voltage(time*1e-9*2.5e9),.4*float((c@state).item()),places=11)

    def test_wired_shared_rails_preserve_mode_budget_and_clock_ownership(self):
        from baseline_envelope import selected_environment,reference_payload_environment,wired_shared_impairment,P
        contract=json.loads((P/'spec/contract.json').read_text())
        original=selected_environment(contract,'wire',2.5e9,312.5e6)
        e,report=reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        self.assertIsNotNone(e)
        self.assertAlmostEqual(report['ledger']['total_chip_supply_current_a'],.288)
        self.assertLess(abs(report['ledger']['power_balance_residual_w']),1e-12)
        impairment=wired_shared_impairment(e)
        self.assertTrue(any(t['frequency_hz']==2.5e9 for t in impairment['rail_tones']))
        # Arbitrary TX phase must not leak into the independent RX aperture.
        changed=dict(e,periodic_clock=None,delivered_phase_tones=[(1e6,100.,0.)])
        self.assertEqual(wired_shared_impairment(changed),impairment)
        with self.assertRaises(ValueError):wired_shared_impairment(dict(e,payload_engine='rf'))

    def test_loaded_threshold_edges_against_analytic_sinusoid(self):
        from selected_rf import coupled_load_clock_edges,DeliveredClock
        f=1e9;period=1/f;root=.75*period
        t=np.linspace(0,10*period,101)
        environment=dict(carrier_hz=f,delivered_phase_tones=[],
            periodic_clock=dict(carrier_hz=f,period_s=period,edges_s=np.array([root])),
            reference_threshold=dict(carrier_v=.2+0j,input_tones=[],downstream_delay_tones=[],
                threshold_v=0.,input_edges_s=np.array([root]),period_s=period))
        response=dict(times_s=t,input_v=np.full_like(t,.01),delay_s=np.full_like(t,2e-12),resolved_offset_hz=5e9)
        edges,report=coupled_load_clock_edges(environment,response)
        interior=(edges['indices']>=2)&(edges['indices']<=7)
        expected=(edges['indices'][interior]+1-np.arccos(-.01/.2)/(2*np.pi))*period+2e-12
        np.testing.assert_allclose(edges['edges_s'][interior],expected,atol=1e-18,rtol=0.)
        clock=DeliveredClock(dict(environment,local_load_response=response))
        actual=edges['edges_s'][interior]
        np.testing.assert_allclose(clock.phase(actual)+2*np.pi*f*actual,2*np.pi*edges['indices'][interior],atol=1e-12)
        self.assertLess(report['maximum_root_residual_v'],1e-10)
        with self.assertRaises(ValueError):
            coupled_load_clock_edges(environment,dict(response,input_v=np.full_like(t,.19)))

    def test_converter_load_transfer_matches_independent_five_node_solution(self):
        from converter_dynamics import coupled_reference_load_transfer,local_impedance
        from baseline_envelope import reference_input_solution,NETWORK_CASES
        frequencies=np.geomspace(1e3,1e10,51)
        for _,ret,esl in NETWORK_CASES:
            candidate=shared_board_candidate()
            candidate['return_l_h']=ret
            candidate['network'].update(die_c=500e-12,die_esr=.5,die_esl=esl)
            ports=coupled_reference_load_transfer(frequencies,candidate)
            for i,f in enumerate(frequencies):
                independent=reference_input_solution(f,candidate,[0,-1,0,1,0],return_options=dict(link_r_ohm=1e-5))
                v=independent['network_voltage']
                for key,expected in [('rail_v_per_a',v[1]-v[3]),('return_v_per_a',v[3]),('input_v_per_a',independent['local_input_v'])]:
                    np.testing.assert_allclose(ports[key][i],expected,rtol=1e-7,atol=1e-9)
            dc=coupled_reference_load_transfer([0.],candidate)
            self.assertAlmostEqual(dc['input_v_per_a'][0].real,-dc['return_v_per_a'][0].real)
            unloaded=coupled_reference_load_transfer(frequencies,candidate,cap_f=0.,link_r_ohm=1e-12)
            np.testing.assert_allclose(unloaded['rail_v_per_a'],local_impedance(frequencies,candidate),rtol=1e-9,atol=1e-10)
        from selected_rf import DeliveredClock
        with self.assertRaisesRegex(ValueError,'threshold-event migration'):
            DeliveredClock(dict(local_load_response=dict(input_v=[0.])))

    def test_differential_reference_load_against_seven_node_solution(self):
        from reference_input_probe import check_network
        checked=check_network()
        self.assertEqual(checked['load_transfer_points'],1404)
        self.assertLess(checked['maximum_load_transfer_difference_ohm'],1e-7)

    def test_current_ownership_and_independent_resistive_node_solution(self):
        c=shared_board_candidate();n=c['network']
        for mode,wire_current,total in [('rf',None,.236),('wire',None,.288),('wire',.050,.242)]:
            r=selected_dc_ledger(mode,c,wire_current_a=wire_current)
            self.assertAlmostEqual(r['total_chip_supply_current_a'],total)
            self.assertAlmostEqual(r['host_node_current_a']+r['h2d_internal_current_within_host_a'],.110)
            self.assertEqual(r['owner_current_a']['timing'],.040)
            gs=1/n['feed_r'];gp=1/n['package_r'];gg=1/c['return_r_ohm']
            vb,vd,vg=np.linalg.solve([[gs+gp,-gp,0],[-gp,gp,0],[0,0,gg]],
                [gs*3.3-r['host_node_current_a'],-r['local_branch_current_a'],total])
            self.assertAlmostEqual(vd-vg,r['local_payload_clock_core_rail_v'])
            self.assertAlmostEqual(vb-vg,r['host_rail_v'])
            self.assertLess(abs(r['power_balance_residual_w']),1e-12)
            self.assertAlmostEqual(sum(r['owner_current_a'].values()),total)
        with self.assertRaises(ValueError):selected_dc_ledger('rf',c,h2d_internal_a=.111)
        with self.assertRaises(ValueError):selected_dc_ledger('rf',c,wire_current_a=.05)
        with self.assertRaises(ValueError):selected_dc_ledger('wire',c,wire_current_a=.097)

    def test_coherent_enclosure_contains_known_sinusoid_extrema(self):
        t=[dict(frequency_hz=1e6,clock_rail_voltage_peak_v=.1,voltage_phase_rad=.31)]
        for resolution in (8,16,32):
            r=rail_excursion(t,dc_v=3.,samples_per_fastest_period=resolution)
            self.assertLessEqual(r['enclosed_interval_v'][0],2.9)
            self.assertGreaterEqual(r['enclosed_interval_v'][1],3.1)
            self.assertGreaterEqual(r['sampled_interval_v'][0],2.9)
            self.assertLessEqual(r['sampled_interval_v'][1],3.1)
        cancel=t+[dict(t[0],voltage_phase_rad=.31+np.pi)]
        r=rail_excursion(cancel,dc_v=3.)
        np.testing.assert_allclose(r['sampled_interval_v'],[3.,3.],atol=1e-12)


class WiredSupplyObservationTests(unittest.TestCase):
    def test_voltage_validity_survives_forecast_snapshots(self):
        from wired_envelope import causal_receiver_envelope
        scenarios=[dict(name='low_constant_rail',delay_tones=[],signal_scale=2.4/3.3,
                        rail_dc_v=2.4,rail_tones=[]),
                   dict(name='valid_constant_rail',delay_tones=[],signal_scale=3./3.3,
                        rail_dc_v=3.,rail_tones=[])]
        result=causal_receiver_envelope(timing_scenarios=scenarios,channel_cases=((2.7e-12,100e-12),))
        for r in result['cases']:
            low=r['impairment']['name']=='low_constant_rail'
            self.assertEqual(r['observed_rail_interval_v'],[2.4,2.4] if low else [3.,3.])
            self.assertEqual(r['rail_observations_outside_legacy_fixture']>0,low)


class HSPadReturnTests(unittest.TestCase):
    def test_loaded_ground_matches_independent_seven_node_network(self):
        from baseline_envelope import hs_pad_transfer
        from protocol_pad import SharedWiredPad
        from robustness_envelope import shared_return_transfer
        n=shared_board_candidate();r=n['network'];rg=n['return_r_ohm'];lg=n['return_l_h']
        for f in (156.25e6,1.875e9):
            w=2*np.pi*f
            ys=1/(r['feed_r']+1j*w*r['feed_l']);yp=1/(r['package_r']+1j*w*r['package_l'])
            yg=1/(rg+1j*w*lg)
            yd=1/(r.get('die_esr',0.)+1j*w*r.get('die_esl',0.)+1/(1j*w*r['die_c']))
            yb=1/(r['board_esr']+1j*w*r['board_esl']+1/(1j*w*r['board_c']))
            m=np.zeros((7,7),complex)
            m[:3,:3]=[[ys+yb+yp,-yp,0],[-yp,yp+yd,-yd],[0,-yd,yg+yd]]
            local=1j*w*SharedWiredPad().C+np.diag([1/42.75,1/47.25])
            m[3:5,3:5]+=local
            m[3:5,2]-=local@np.ones(2);m[2,3:5]-=np.ones(2)@local
            m[2,2]+=np.ones(2)@local@np.ones(2)
            for leg,l in enumerate((1.6e-9,2.4e-9)):
                y=1/(.2+1j*w*l);a,b=3+leg,5+leg
                m[a,a]+=y;m[b,b]+=y+1/45.;m[a,b]-=y;m[b,a]-=y
            source=np.zeros(7);source[2]=1.
            v=np.linalg.solve(m,source)
            z=shared_return_transfer(f,return_r=rg,return_l=lg,injection_weights=(0.,0.,1.),**r)
            h=hs_pad_transfer(f,termination_ohm=(42.75,47.25),bond_l_h=(1.6e-9,2.4e-9))
            g=z['ground_ohm']/(1+z['ground_ohm']*sum(h['ground_board'])/45.)
            np.testing.assert_allclose(v[2],g,rtol=1e-13)
            np.testing.assert_allclose(v[5:],h['ground_board']*g,rtol=1e-13)
            self.assertLess(max(abs(m@v-source)),1e-13)
        with self.assertRaises(ValueError):hs_pad_transfer(1e6,bond_l_h=(-1.,0.))

    def test_dc_return_current_is_redirected_not_added_to_budget(self):
        from baseline_envelope import selected_environment,usb_hs_output,P
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'wire',2.5e9,312.5e6)
        ledger=selected_dc_ledger('wire',e['network'],wire_current_a=.050)
        for node in (None,0,1):
            r=usb_hs_output(e,ledger,drive_node=node)
            board=np.array(r['board_dc_v']);g=r['loaded_dc_ground_v']
            self.assertAlmostEqual(g/e['network']['return_r_ohm']+sum(board)/45.,.242,places=12)
            current=np.zeros(2)
            if node is not None:current[node]=.4/22.5
            die=np.array(r['die_local_dc_v'])+g
            np.testing.assert_allclose((die-g)/45.+(die-board)/.2,current,atol=1e-14)
            np.testing.assert_allclose((die-board)/.2,board/45.,atol=1e-14)
            self.assertTrue(r['quiet_pin_dc_within_20mv'])
            lo,hi=r['differential']['sampled_interval_v']
            self.assertAlmostEqual(lo,hi,places=12)
            self.assertGreater(r['quiet_pin_observed_abs_peak_v'],.02)


class HostRateTradeoffTests(unittest.TestCase):
    def test_rate_comparison_preserves_bandwidth_current_ownership_and_latency(self):
        from baseline_envelope import P,usb_hs_level_campaign,NETWORK_CASES
        r=usb_hs_level_campaign(json.loads((P/'spec/contract.json').read_text()))
        self.assertEqual({x['network_case'] for x in r['host_rate_controls']},{x[0] for x in NETWORK_CASES})
        for c in r['host_rate_controls']:
            word=c['word_hz'];dc=c['ledger']
            self.assertGreaterEqual(c['d2h_harmonics']*word/2,1.875e9)
            self.assertGreaterEqual(c['h2d_harmonics']*word/2,937.5e6)
            self.assertAlmostEqual(dc['total_chip_supply_current_a'],.242)
            self.assertAlmostEqual(dc['host_node_current_a']+dc['h2d_internal_current_within_host_a'],.110)
            for t in c['transport']:
                # Independent accounting of six frame traversals, four queue
                # words and three H0 cycles; fixed analog, FPGA and packing.
                expected=(6*t['frame_words']+4+24)/word+40e-9+34e-9+20/480e6
                self.assertAlmostEqual(t['incomplete_roundtrip_bound_s'],expected,places=18)
                self.assertAlmostEqual(t['payload_capacity_bps'],(t['frame_words']-5)*10*word/t['frame_words'])
        # Default-rate diagnostic must reproduce the actual joined pad case.
        for c in r['cases']:
            if c['fixture']!='matched_2nh_signal_bonds':continue
            control=next(x for x in r['host_rate_controls'] if x['network_case']==c['network_case'] and x['word_hz']==312.5e6)
            self.assertAlmostEqual(control['quiet_pin_enclosed_abs_peak_v'],c['states'][0]['quiet_pin_enclosed_abs_peak_v'],places=15)


class PartitionedReturnTests(unittest.TestCase):
    def test_shorting_returns_recovers_original_three_node_network(self):
        from baseline_envelope import partitioned_return_solution,selected_environment,P
        from robustness_envelope import shared_return_transfer
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'wire',2.5e9,312.5e6);n=e['network']
        for f in (156.25e6,1.875e9):
            for old,new in (((-1.,0.,1.),(-1.,0.,1.,0.,0.)),((0.,-1.,1.),(0.,-1.,1.,0.,0.)),((0.,0.,1.),(0.,0.,0.,1.,0.))):
                reference=shared_return_transfer(f,return_r=n['return_r_ohm'],return_l=n['return_l_h'],injection_weights=old,**n['network'])
                result=partitioned_return_solution(f,n,new,link_r_ohm=1e-7)
                v=result['voltage']
                np.testing.assert_allclose([v[0],v[1],v[3]],
                    [reference['board_ohm'],reference['die_ohm'],reference['ground_ohm']],rtol=2e-6,atol=1e-7)
                self.assertLess(result['kcl_residual_a'],1e-8)

    def test_dc_series_paths_and_current_relocation(self):
        from baseline_envelope import partitioned_return_solution,selected_environment,P
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'wire',2.5e9,312.5e6);n=e['network'];c=.1
        rg=n['return_r_ohm'];rf=n['network']['feed_r'];rp=n['network']['package_r']
        for input_at_feed in (False,True):
            host_feed=.110 if input_at_feed else .110-.0240625;local=.242-host_feed
            source=[3.3/rf-host_feed,-local,.110,.132,0.]
            for fraction in (0.,.25,.5,.75):
                result=partitioned_return_solution(0.,n,source,host_cap_fraction=fraction)
                vb=3.3-rf*.242;common=c*rg*.242
                expected=[vb,vb-rp*local,common+2*(1-c)*rg*.110,
                    common+2*(1-c)*rg*.132,common]
                np.testing.assert_allclose(result['voltage'],expected,rtol=1e-12,atol=1e-14)
                self.assertAlmostEqual((3.3-result['voltage'][0].real)/rf,.242,places=12)

    def test_passive_power_balance_with_capacitive_and_conductive_coupling(self):
        from baseline_envelope import partitioned_return_solution,selected_environment,hs_pad_transfer,P
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'wire',2.5e9,312.5e6);n=e['network']
        for fraction in (0.,.25,.5,.75):
            for link in (None,1.):
                for f in (156.25e6,1.875e9):
                    load=sum(hs_pad_transfer(f)['ground_board'])/45.
                    r=partitioned_return_solution(f,n,[-.01+.02j,-.03,.04-.01j,.01j,0.],
                        host_cap_fraction=fraction,link_r_ohm=link,quiet_load_s=load)
                    self.assertLess(r['kcl_residual_a'],1e-12)
                    self.assertLess(abs(r['power_residual_w']),1e-12)
        with self.assertRaises(ValueError):partitioned_return_solution(1e6,n,[0]*5,coupling_f=-1.)
        with self.assertRaises(ValueError):partitioned_return_solution(1e6,n,[0]*5,host_cap_fraction=1.)


class ReferenceReturnTests(unittest.TestCase):
    def test_loaded_input_matches_series_thevenin_and_power_balance(self):
        from baseline_envelope import selected_environment,partitioned_return_solution,reference_input_solution,P
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'rf',2.484e9,2.484e9/16);n=e['network']
        for options in (dict(link_r_ohm=1e-5),dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=.2)):
            for f in (156.25e6,2.484e9):
                z=partitioned_return_solution(f,n,[0,0,0,1,0],**options)['voltage'][3]
                w=2*np.pi*f;zc=1/(1j*w*3e-12);zs=50.2+1j*w*2e-9
                for source,injection in ((.5,[0]*5),(0.,[-.02,0,.02,0,0])):
                    unloaded=partitioned_return_solution(f,n,injection,**options)['voltage']
                    current=(source-unloaded[3])/(zs+zc+z)
                    r=reference_input_solution(f,n,injection,source_v=source,return_options=options)
                    np.testing.assert_allclose(r['input_return_current_a'],current,rtol=2e-8,atol=1e-12)
                    np.testing.assert_allclose(r['local_input_v'],zc*current,rtol=2e-8,atol=1e-12)
                    np.testing.assert_allclose((r['pad_board_v']-source)/zs+r['local_input_v']/zc,0.,atol=1e-12)
                    if source:
                        independent_loss=(50.2+z.real)*abs(current)**2/2
                        self.assertAlmostEqual(r['source_real_power_w'],independent_loss,places=10)

    def test_exact_coherent_phasor_shift_and_missing_multiple_edges(self):
        from baseline_envelope import reference_edge_screen
        f=2e9;carrier=.2;perturb=.04j;threshold=.02
        r=reference_edge_screen(f,carrier,[(f,perturb)],threshold_v=threshold)
        total=carrier+perturb
        expected=(np.arcsin(threshold/abs(total))-np.angle(total)-np.arcsin(threshold/carrier))/(2*np.pi*f)
        self.assertAlmostEqual(r['static_mean_edge_shift_ps'],expected*1e12,places=7)
        self.assertEqual(r['unique_edge_windows'],1)
        self.assertLess(r['maximum_root_voltage_residual_v'],1e-9)
        missing=reference_edge_screen(f,carrier,[(f,-carrier)])
        self.assertEqual(missing['missing_rising_edge_windows'],1)
        self.assertIsNone(missing['centered_edge_error_rms_ps'])
        multiple=reference_edge_screen(f,carrier,[(2*f,.4)],substeps=64)
        self.assertEqual(multiple['multiple_rising_edge_windows'],1)
        self.assertFalse(multiple['all_windows_have_one_rising_edge'])

    def test_correlated_downstream_delay_cancels_in_small_signal_limit(self):
        from baseline_envelope import reference_edge_screen
        f=2e9;a=.2;threshold=.02;v=1e-5;offset=f/16
        slope=2*np.pi*f*np.sqrt(a*a-threshold*threshold)
        r=reference_edge_screen(f,a,[(offset,v)],threshold_v=threshold,
            downstream_delay_tones=[(offset,v/slope)])
        self.assertGreater(r['centered_edge_error_rms_ps'],.002)
        self.assertLess(r['combined_edge_error_rms_ps'],r['centered_edge_error_rms_ps']/1000)
        self.assertTrue(r['output_clock_order_preserved'])
        refined=reference_edge_screen(f,a,[(offset,v)],threshold_v=threshold,substeps=64,
            downstream_delay_tones=[(offset,v/slope)])
        self.assertAlmostEqual(r['centered_edge_error_rms_ps'],refined['centered_edge_error_rms_ps'],places=8)
        with self.assertRaises(ValueError):reference_edge_screen(f,a,[(offset,complex(float('nan'),0))])


class PeriodicClockConsumerTests(unittest.TestCase):
    def test_phase_and_divider_crossings_follow_edges_across_period_boundaries(self):
        from selected_rf import DeliveredClock,PeriodicEdgePhase
        carrier=1e9;n=32;k=np.arange(n)
        edges=(k+.17+.03*np.cos(2*np.pi*k/8))/carrier
        record=dict(carrier_hz=carrier,period_s=n/carrier,edges_s=edges)
        environment=dict(carrier_hz=carrier,delivered_phase_tones=(),periodic_clock=record)
        clock=DeliveredClock(environment);indices=np.arange(-64,129)
        ideal=indices/carrier
        expected=edges[indices % n]+(indices//n)*n/carrier
        actual=ideal+clock.crossing_error(ideal,carrier)
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-20)
        np.testing.assert_allclose(clock.phase(expected)+2*np.pi*carrier*expected,2*np.pi*indices,atol=1e-11)
        query=np.linspace(-2e-9,60e-9,100)
        np.testing.assert_allclose(clock.phase(query),clock.phase(query+n/carrier),atol=1e-12)
        noisy=DeliveredClock(dict(environment,delivered_phase_tones=((carrier/7,.01,.3),)))
        error=noisy.crossing_error(ideal,carrier)
        self.assertLess(max(abs(error+noisy.phase(ideal+error)/(2*np.pi*carrier))),1e-16)
        with self.assertRaises(ValueError):PeriodicEdgePhase(dict(record,edges_s=edges[:-1]))
        with self.assertRaises(ValueError):PeriodicEdgePhase(dict(record,edges_s=edges[::-1]))
        with self.assertRaises(ValueError):clock.crossing_error(ideal,carrier/2)

    def test_coupled_environment_balances_power_and_rejects_broken_clock(self):
        from baseline_envelope import selected_environment,reference_payload_environment,P
        contract=json.loads((P/'spec/contract.json').read_text())
        e=selected_environment(contract,'rf',2.4e9,2.4e9/16)
        _,nominal=reference_payload_environment(e,dict(link_r_ohm=1e-5),False)
        stronger,large=reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=1.)
        self.assertIsNotNone(stronger)
        self.assertAlmostEqual(large['receiver_carrier_peak_v']/nominal['receiver_carrier_peak_v'],2.)
        self.assertAlmostEqual(large['source_carrier_return_peak_a']/nominal['source_carrier_return_peak_a'],2.)
        self.assertAlmostEqual(large['source_carrier_real_power_w']/nominal['source_carrier_real_power_w'],4.)
        rejected,report=reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=2.)
        self.assertIsNone(rejected)
        self.assertEqual(report['status'],'clock_not_accepted_for_payload')
        for invalid in (0.,-1.,float('nan')):
            with self.assertRaises(ValueError):
                reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=invalid)
        for options,move in ((dict(link_r_ohm=1e-5),False),(dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=.2),True)):
            trial,r=reference_payload_environment(e,options,move)
            self.assertIsNotNone(trial)
            self.assertLess(abs(r['ledger']['power_balance_residual_w']),1e-12)
            self.assertAlmostEqual(r['ledger']['total_chip_supply_current_a'],.236)
            self.assertEqual(trial['phase_components']['supply'],())
            self.assertEqual(trial['rail_maximum_offset_hz'],2.4e9)
            self.assertEqual(len(trial['periodic_clock']['edges_s']),r['resolved_crossings']['carrier_cycles'])
        bad=selected_environment(contract,'rf',2.4e9,2.4e9/16,return_l=2e-9,die_esl=1e-9)
        trial,r=reference_payload_environment(bad,dict(link_r_ohm=1e-5),False)
        self.assertIsNone(trial)
        self.assertEqual(r['status'],'clock_not_accepted_for_payload')


class SelectedRFTests(unittest.TestCase):
    def test_receiver_noise_interventions_preserve_legacy_all_off_control(self):
        from baseline_envelope import selected_environment,P
        from selected_rf import wideband_receive
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'rf',2.484e9,2.484e9/16)
        a=wideband_receive(e,noise=False,gain_settings_db=(54.,))
        b=wideband_receive(e,disabled_noise_sources=('thermal','converter','aperture'),gain_settings_db=(54.,))
        self.assertEqual(a,b)
        with self.assertRaises(ValueError):wideband_receive(e,disabled_noise_sources=('unknown',))

    def test_input_phase_refinement_conserves_noise_and_matches_threshold_crossing(self):
        from oscillator_noise import loaded_clock_input_phase,PhaseNoise
        import math
        carrier=2.484e9;omega=2*math.pi*carrier;variances=[]
        for bins in (32,128,512):
            phase,r=loaded_clock_input_phase(carrier,receiver_noise_v=75e-6,
                downstream_stage_rms_s=15e-15,noise_bins=bins,source_peak_v=.75,threshold_v=.002,am_depth=.01)
            am=PhaseNoise(r['phase_components']['am']);additive=PhaseNoise(r['phase_components']['additive'])
            t=np.arange(512)/512e6
            exact=np.arcsin(.002/(r['receiver_peak_v']*(1+.01*np.sin(2*np.pi*1e6*t))))/omega
            exact-=exact.mean()
            np.testing.assert_allclose(-am.phase(t)/omega,exact,atol=1e-25)
            expected=omega**2*(r['receiver_random_time_rms_s']**2+r['downstream_random_time_rms_s']**2)
            self.assertAlmostEqual(additive.variance_rad2/expected,1.,places=12)
            np.testing.assert_allclose(phase.phase(t),am.phase(t)+additive.phase(t),atol=1e-16)
            variances.append(additive.variance_rad2)
        np.testing.assert_allclose(variances,variances[0],rtol=1e-12)
        with self.assertRaises(ValueError):loaded_clock_input_phase(carrier,am_depth=1.)
        with self.assertRaises(ValueError):loaded_clock_input_phase(carrier,noise_bins=0)

    def test_observed_gain_control_matches_native_transfer_with_moving_headroom(self):
        from ble_packet import bounded_gain_conversion
        from selected_rf import native_adc
        source=np.linspace(-.9,.9,401)*(1+1j)
        headroom=np.linspace(.3,.6,len(source));reference=np.linspace(.99,1.01,len(source))
        # Lock gain at unity to compare transfer laws, then separately retain
        # the existing causal/delayed gain-controller tests.
        codes,report=bounded_gain_conversion(source,np.zeros(len(source)),
            initial_gain_db=0.,maximum_gain_db=0.,reference_scale=reference,
            pga_peak_v=headroom,converter_bits=10)
        limited=np.clip(source.real,-headroom,headroom)+1j*np.clip(source.imag,-headroom,headroom)
        words,_=native_adc(limited,reference,noise=False)
        np.testing.assert_array_equal(codes,(words[:,0]+1j*words[:,1])/2048)
        self.assertTrue(report['native_transport_low_two_bits_zero'])
        self.assertGreater(report['pga_clipped_samples'],0)

    def test_native_converter_codes_reference_and_saturation(self):
        from selected_rf import native_adc, native_dac
        # Every native code must survive both directions at non-unit reference.
        values=np.arange(-512,512)/512
        words,report=native_adc((values+1j*values)*.93,.93,noise=False)
        decoded,dac=native_dac(words,.93)
        np.testing.assert_allclose(decoded,(values+1j*values)*.93,atol=1e-15)
        self.assertEqual(report['clipped_components'],0)
        self.assertEqual(dac['saturated_components'],0)
        # Exhaustive 12-bit input ramp: bounded error, monotonicity, no wrap.
        ramp=np.arange(-2048,2048)
        decoded,dac=native_dac(np.column_stack((ramp,ramp)),1.)
        self.assertTrue(np.all(np.diff(decoded.real)>=0))
        self.assertLessEqual(max(abs(decoded.real-ramp/2048)),3/2048)
        self.assertEqual(decoded[-1].real,511/512)
        words,report=native_adc(np.array([-2-2j,2+2j]),1.,noise=False)
        np.testing.assert_array_equal(words,[[-2048,-2048],[2044,2044]])
        self.assertEqual(report['clipped_components'],4)

    def test_analog_modes_against_independent_state_space_zoh(self):
        from scipy import signal
        from selected_rf import analog_filter
        drive=np.random.default_rng(41).normal(size=1200)
        for family,ba in (
            ('rx_finite_zero',signal.ellip(5,1,36.40776933523119,1,analog=True)),
            ('rx_all_pole_control',signal.butter(5,1,analog=True)),
            ('tx_third_order',signal.butter(3,1,analog=True))):
            dt=2*np.pi*9e6/1e9
            # Independent real companion state-space integration, rather than
            # the residue decomposition used by the baseline implementation.
            _,reference,_=signal.lsim(signal.tf2ss(*ba),np.r_[drive,0.],
                np.arange(len(drive)+1)*dt,interp=False)
            modeled=analog_filter(drive,1e9,family=family,cutoff_hz=9e6)
            np.testing.assert_allclose(modeled,reference[1:],atol=1e-10)

    def test_wideband_noiseless_resolution_and_payload_observation(self):
        from selected_rf import wideband_receive
        e=dict(carrier_hz=2.4e9,delivered_phase_tones=[],reference_fraction_tones=[],
            ledger=dict(local_payload_clock_core_rail_v=3.3),host_spectrum=dict(tones=[]))
        results=[wideband_receive(e,oversample=n,wanted_dbm=-65.,blocker_dbm=None,
            noise=False,gain_settings_db=(42.,)) for n in (64,128)]
        observations=[r['gain_cases'][0]['observation'] for r in results]
        self.assertTrue(all(r['bpsk_errors']==0 for r in observations))
        self.assertTrue(all(r['evm_rms']<.05 for r in observations))
        self.assertLess(abs(observations[0]['evm_rms']-observations[1]['evm_rms']),.002)

    def test_linear_forcing_against_independent_state_space(self):
        from scipy import signal
        from selected_rf import analog_filter
        rng=np.random.default_rng(82)
        drive=rng.normal(size=1200)+1j*rng.normal(size=1200)
        for family,ba in (
            ('rx_finite_zero',signal.ellip(5,1,36.40776933523119,1,analog=True)),
            ('rx_all_pole_control',signal.butter(5,1,analog=True)),
            ('tx_third_order',signal.butter(3,1,analog=True))):
            times=np.arange(len(drive))*2*np.pi*9e6/1e9
            state=signal.tf2ss(*ba)
            _,real,_=signal.lsim(state,drive.real,times,interp=True)
            _,imag,_=signal.lsim(state,drive.imag,times,interp=True)
            actual=analog_filter(drive,1e9,family=family,cutoff_hz=9e6,interpolation='linear')
            np.testing.assert_allclose(actual,real+1j*imag,atol=1e-10)
            self.assertLess(abs(actual[0]),1e-14)

    def test_diagnostic_training_does_not_replace_held_out_payload(self):
        from selected_rf import he_source,he_observation
        wave,_=he_source(oversample=4)
        clean=np.asarray(wave.samples)
        same=he_observation(wave,clean,diagnostic_training=clean)
        self.assertEqual(same['bpsk_errors'],0)
        self.assertTrue(same['diagnostic_external_training'])
        damaged=clean.copy()
        n=256+wave.metadata['cp']
        damaged[2*n:]=0
        result=he_observation(wave,damaged,diagnostic_training=clean)
        self.assertGreater(result['bpsk_errors'],0)
        self.assertAlmostEqual(result['evm_rms'],1.)

    def test_nonuniform_dac_edges_against_independent_state_space(self):
        from scipy import signal, linalg
        from selected_rf import analog_hold_at
        values=np.array([.2+.1j,-.3+.05j,.4-.2j,0j])
        edges=np.array([0.,26.7e-9,53.2e-9,80.05e-9])
        queries=np.linspace(-1e-9,120e-9,61)
        a,b,c,d=signal.tf2ss(*signal.butter(3,1,analog=True))
        augmented=np.zeros((4,4));augmented[:3,:3]=a;augmented[:3,3:]=b
        state=np.zeros(3,complex);current=0j;previous=-1e-9;reference=[]
        # Exact real state-space evolution over the union of event/query times.
        for time in sorted(set(edges)|set(queries)):
            evolution=linalg.expm(augmented*(time-previous)*2*np.pi*20e6)
            state=evolution[:3,:3]@state+evolution[:3,3]*current
            if time in edges:current=values[np.flatnonzero(edges==time)[0]]
            if time in queries:reference.append((c@state)[0])
            previous=time
        modeled=analog_hold_at(values,edges,queries,family='tx_third_order',cutoff_hz=20e6)
        np.testing.assert_allclose(modeled,reference,atol=1e-12)


class SelectedPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from baseline_envelope import P, selected_environment, joined_scan_request
        from converter_dynamics import SARParameters,load_response
        cls.contract=json.loads((P/'spec/contract.json').read_text())
        cls.environment=selected_environment(cls.contract,'rf',2.426e9,2.426e9/16)
        options=dict(seed=317,
            wanted_dbm=-80.,blocker_dbm=-30.,noise_figure_db=6.,rx_cutoff_hz=.5e6,
            blocker_offsets_hz=(2e6,4e6),input_iip3_dbm=0.,converter_bits=10,
            aperture_rms_s=10e-12,dynamic_rail=True,sar_parameters=SARParameters(),mixer_substeps=512)
        capture={}
        joined_scan_request(cls.environment,cls.contract,**options,load_capture=capture)
        response,_=load_response(capture,cls.environment['network'])
        cls.environment=dict(cls.environment,local_load_response=response)
        cls.request=joined_scan_request(cls.environment,cls.contract,**options)
        cls.options=dict(converter_bits=10,reconstruction_order=3,aperture_rms_s=10e-12,
            dynamic_rail=True,rf_bias_a=.044,rx_timestamp_correction_s=1.19e-6,tx_launch_advance_s=.32e-6,mixer_substeps=512)

    def test_conversion_latency_is_charged_to_availability_not_source_timestamp(self):
        from ble_packet import response_budget
        r=self.request
        instantaneous=response_budget(r['observation'],r['settings'],self.environment,self.contract,
            advertiser_address=bytes.fromhex('a6a5a4a3a2c1'))
        self.assertAlmostEqual(r['response']['ready_s']-instantaneous['ready_s'],18e-9,places=14)
        self.assertEqual(r['response']['target_air_start_s'],instantaneous['target_air_start_s'])
        self.assertEqual(r['response']['events'][0]['state'],'complete_last_required_conversion')
        self.assertIsNone(r['adc_enob'])
        self.assertGreater(r['converter']['reference_charge_drawn_c'],0.)

    def test_selected_packet_has_no_source_timestamp_oracle_and_honors_underflow(self):
        from ble_packet import transmitted_scan_response
        self.assertTrue(self.request['correct_request'])
        self.assertTrue(self.request['gain_control']['native_transport_low_two_bits_zero'])
        sent=transmitted_scan_response(self.request,self.environment,self.contract,**self.options)
        self.assertTrue(sent['peer_correct_response'])
        self.assertTrue(sent['exact_nonuniform_reconstruction'])
        self.assertEqual(sent['playback']['peak_occupancy_samples'],32)
        self.assertEqual(sent['playback']['depth_samples'],42)
        self.assertEqual(sent['electrical']['total_rail_bias_a'],.044)
        changed=dict(self.request,source_packet_end_s=self.request['source_packet_end_s']+1e-3)
        other=transmitted_scan_response(changed,self.environment,self.contract,**self.options)
        self.assertEqual(other['first_dac_consumption_s'],sent['first_dac_consumption_s'])
        self.assertEqual(other['peer'],sent['peer'])
        self.assertAlmostEqual(other['scoreboard_rf_half_amplitude_gap_s'],
            sent['scoreboard_rf_half_amplitude_gap_s']-1e-3,places=12)
        stalled=transmitted_scan_response(self.request,self.environment,self.contract,
            **self.options,host_gap_s=10e-6)
        self.assertEqual(stalled['playback']['fault'],'underflow')
        self.assertEqual(stalled['playback']['consumed_samples'],32)
        self.assertFalse(stalled['peer_correct_response'])


class ConverterDynamicsTests(unittest.TestCase):
    def test_live_gain_uses_completed_words_and_is_independent_of_future_input(self):
        from converter_dynamics import paired_sar,ObservedGain,SARParameters
        p=SARParameters();t=(np.arange(400)+1)/10e6
        z=np.full(400,1e-4+1e-4j);z[200:]=.2+.2j
        controllers=[];outputs=[]
        for n in (400,200):
            controller=ObservedGain(sample_hz=10e6,command_latency_s=2e-6,
                acquisition_s=p.acquisition_s,headroom_start=np.full(n,.7),headroom_end=np.full(n,.7))
            words,_,_=paired_sar(z[:n],z[:n],t[:n],lambda t:np.ones_like(t),
                lambda t:np.full_like(t,3.),input_control=controller)
            outputs.append(words);controllers.append(controller)
        np.testing.assert_array_equal(outputs[0][:200],outputs[1])
        self.assertEqual(controllers[0].trace[:200],controllers[1].trace)
        for command in controllers[0].commands:
            self.assertAlmostEqual(command['code_available_s'],t[command['last_observed_code']]+18e-9,places=15)
            self.assertAlmostEqual(command['earliest_apply_s']-command['code_available_s'],2e-6,places=15)
        self.assertGreater(controllers[0].updates,0)

    def test_limited_reference_and_dac_match_independent_ode(self):
        from scipy.integrate import solve_ivp
        from converter_dynamics import recover
        for tau in (.15e-9,1e-9):
            r=10.;c=100e-12;limit=.001;code=.6-.2j
            def ode(t,y):
                current=np.clip((1-y[0])/r,-limit,limit)
                return np.array([current/c,(code.real*y[0]-y[1])/tau,
                    (code.imag*y[0]-y[2])/tau])*1e-9
            answer=solve_ivp(ode,(0,15),[.9,.2,-.1],rtol=1e-10,atol=1e-12).y[:,-1]
            ref,dac,charge=recover(.9,.2-.1j,1.,code,15e-9,r=r,c=c,limit=limit,tau=tau)
            np.testing.assert_allclose([ref,dac.real,dac.imag],answer,atol=2e-10)
            self.assertAlmostEqual(charge,c*(ref-.9),places=20)

    def test_ideal_limit_native_codes_and_conserved_reference_charge(self):
        from converter_dynamics import paired_sar,SARParameters,load_response
        from dataclasses import replace
        z=np.arange(-512,512)/512+1j*np.arange(511,-513,-1)/512
        t=(np.arange(len(z))+1)*30e-9
        p=replace(SARParameters(),sample_resistance_ohm=.01,dac_tau_s=1e-13,dac_effective_cap_f=1e-21)
        words,report,_=paired_sar(z,z,t,lambda t:np.ones_like(t),lambda t:np.full_like(t,3.3),parameters=p,noise=False)
        np.testing.assert_array_equal(words[:,0],np.arange(-512,512)*4)
        np.testing.assert_array_equal(words[:,1],np.arange(511,-513,-1)*4)
        # With finite capacitance, compare a prefix to a longer trajectory;
        # neither code decisions nor reference recovery may depend on future input.
        x=.3*np.exp(2j*np.pi*3e6*t)
        args=(lambda t:np.ones_like(t),lambda t:np.full_like(t,3.0))
        whole,report,trace=paired_sar(x,x,t,*args,noise=True)
        prefix,_,_=paired_sar(x[:100],x[:100],t[:100],*args,noise=True)
        np.testing.assert_array_equal(whole[:100],prefix)
        self.assertLess(abs(report['reference_charge_balance_residual_c']),1e-17)
        self.assertGreater(report['reference_source_average_a'],0)
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        _,load=load_response(trace,c)
        self.assertLess(abs(load['charge_resampling_residual_c']),1e-17)
        positive,_=load_response(trace,c,reference_input={},supply_sign=1.)
        negative,_=load_response(trace,c,reference_input={},supply_sign=-1.)
        for field in ('rail_v','input_v','reference_fraction'):
            np.testing.assert_array_equal(positive[field],negative[field])
        np.testing.assert_allclose(positive['delay_s'],-negative['delay_s'],atol=1e-25)
        reduced,_=load_response(trace,c,reference_input={},sensitivity_ps_per_mv=.025)
        immune,_=load_response(trace,c,reference_input={},sensitivity_ps_per_mv=0.)
        for field in ('rail_v','input_v','reference_fraction'):
            np.testing.assert_array_equal(positive[field],reduced[field])
            np.testing.assert_array_equal(positive[field],immune[field])
        np.testing.assert_allclose(reduced['delay_s'],positive['delay_s']/4,atol=1e-25)
        np.testing.assert_array_equal(immune['delay_s'],np.zeros_like(immune['delay_s']))
        for invalid in (-.1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):load_response(trace,c,sensitivity_ps_per_mv=invalid)
        # The time-domain feedback must preserve common-mode rejection, not
        # feed a single leg into the differential threshold solver.
        paired,load=load_response(trace,c,reference_input=dict(differential=dict(mismatch=.2,opposed=False,cm_gain=-.1)))
        legs=paired['input_leg_v']
        np.testing.assert_allclose(paired['input_v'],legs[:,0]-legs[:,1]-.1*np.mean(legs,axis=1),atol=1e-18,rtol=1e-10)
        np.testing.assert_allclose(load['input_leg_voltage_abs_peak_v'],np.max(abs(legs),axis=0))
        balanced,_=load_response(trace,c,reference_input=dict(differential=dict(mismatch=0.,opposed=False,cm_gain=0.)))
        np.testing.assert_array_equal(balanced['input_v'],np.zeros_like(balanced['input_v']))
        self.assertGreater(float(np.max(abs(balanced['input_leg_v']))),0.)
        with self.assertRaises(ValueError):load_response(trace,c,supply_sign=0.)

    def test_local_supply_transfer_matches_independent_three_node_network(self):
        from converter_dynamics import local_impedance
        from robustness_envelope import shared_return_transfer
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        for f in (1e3,1e6,37.5e6,625e6,2e9):
            expected=shared_return_transfer(f,injection_weights=(0.,-1.,1.),
                return_r=c['return_r_ohm'],return_l=c['return_l_h'],**c['network'])['differential_ohm']
            self.assertAlmostEqual(abs(local_impedance(f,c)-expected),0.,places=10)


class WiredIntegrationTests(unittest.TestCase):
    def test_internal_usb_return_matches_independent_three_node_mna(self):
        from baseline_envelope import selected_environment,pad_ground_tones,internal_switching_sources,P
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'wire',2.5e9,312.5e6)
        before=pad_ground_tones(e)
        e['internal_switching_loads']=[dict(owner='core',mean_a=.02,event_hz=156.25e6,tau_s=.2e-9,harmonics=8)]
        after=pad_ground_tones(e);n=e['network'];net=n['network']
        for f,ports in internal_switching_sources(e['internal_switching_loads']).items():
            omega=2j*np.pi*f;m=np.zeros((3,3),complex)
            def branch(a,b,y):
                m[a,a]+=y
                if b is not None:m[b,b]+=y;m[a,b]-=y;m[b,a]-=y
            def capacitor(c,r,l):return 1/(r+omega*l+1/(omega*c))
            branch(0,None,1/(net['feed_r']+omega*net['feed_l']))
            branch(0,None,capacitor(net['board_c'],net['board_esr'],net['board_esl']))
            branch(0,1,1/(net['package_r']+omega*net['package_l']))
            branch(1,2,capacitor(net['die_c'],net['die_esr'],net['die_esl']))
            branch(2,None,1/(n['return_r_ohm']+omega*n['return_l_h']))
            current=ports[3];expected=np.linalg.solve(m,[0,-current,current])[2]
            np.testing.assert_allclose(after[f]-before.get(f,0j),expected,atol=1e-14,rtol=1e-9)

    def test_usb_dc_voltage_matches_independent_pad_and_board_return_reference(self):
        from baseline_envelope import usb_static_output,selected_environment,P
        from protocol_pad import SharedWiredPad
        e=selected_environment(json.loads((P/'spec/contract.json').read_text()),'wire',2.5e9,312.5e6)
        ledger=dict(e['ledger'],local_payload_clock_core_rail_v=2.9,die_return_v=0.)
        high=usb_static_output(e,ledger,levels=(1,0),load_ohm=15000.)
        pad=SharedWiredPad();pad.configure('usb',role='device',speed='fs',attached=True)
        pad.set_local_passives();pad.set_local_drive('voltage',levels=(1,0),resistance_ohm=30.)
        pad.advance(1e-6,rail=2.9)
        np.testing.assert_allclose(high['dc_output_v'],pad.voltage,atol=1e-6)
        ledger['die_return_v']=.1
        high=usb_static_output(e,ledger,levels=(1,0),load_ohm=15000.)
        self.assertAlmostEqual(high['dc_output_v'][0],3.*15000/15030,places=12)
        low=usb_static_output(e,ledger,levels=(0,0),load_ohm=1500.,load_supply_v=3.6)
        self.assertAlmostEqual(low['dc_output_v'][0],(.1/30+3.6/1500)/(1/30+1/1500),places=12)

    def test_publication_clock_uses_explicit_owner_across_restart(self):
        from behavioral import TimedBulkRecordReturn
        from bit_event_stream import BitEventStream
        rate=39.0625e6*(1-100e-6);phase=.37;duration=.71e-6
        host=TimedBulkRecordReturn(BitEventStream(128),source_hz=rate,
            source_phase=phase,trained=True)
        host.advance(duration)
        count=int(np.floor(duration*rate-phase))+1
        self.assertEqual(host.source_index,count)
        self.assertAlmostEqual(host.next_source,(count+phase)/rate,places=18)
        host.halt(duration);host.restart(2e-6);host.advance(2e-6+duration)
        self.assertEqual(host.source_index,count)
        self.assertAlmostEqual(host.next_source,2e-6+(count+phase)/rate,places=18)
        with self.assertRaises(ValueError):TimedBulkRecordReturn(BitEventStream(128),source_hz=0.)

    def test_modal_channel_matches_independent_state_space_and_is_causal(self):
        from scipy import signal
        from wired_envelope import physical_receiver
        rate=2.5e9;bits=np.random.default_rng(165).integers(0,2,96).tolist()
        q=dict(jitter_rms_s=0.,jitter_hz=1e6,noise_rms_v=0.,offset_v=0.,
            ctle_zero_s=150e-12,ctle_pole_s=80e-12)
        rx=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,q)
        denominator=np.array([1.])
        for tau in (100e-12,135e-12,80e-12):denominator=np.polymul(denominator,[tau*rate,1.])
        t=np.arange(96*32)/32
        drive=np.repeat(2*np.array(bits)-1,32)
        _,expected,_=signal.lsim(([150e-12*rate,1.],denominator),U=drive,T=t,interp=False)
        observed=np.array([rx.voltage(float(at)) for at in t])
        np.testing.assert_allclose(observed,.4*expected,atol=2e-12,rtol=2e-12)
        prefix=physical_receiver(bits[:48],rate,0.,0.,100e-12,2.7e-12,q)
        np.testing.assert_array_equal(observed[:48*32],np.array([prefix.voltage(float(at)) for at in t[:48*32]]))
        held=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,q,hold_final_level=True)
        extended=physical_receiver(bits+[bits[-1]]*16,rate,0.,0.,100e-12,2.7e-12,q)
        tail=np.arange(96,110,.125)
        np.testing.assert_allclose([held.voltage(float(at)) for at in tail],
            [extended.voltage(float(at)) for at in tail],atol=2e-12,rtol=2e-12)


class DriverWakeTests(unittest.TestCase):
    def test_coupled_wake_against_independent_unloaded_state_space(self):
        from selected_rf import driver_wake_response
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        arguments=dict(released_current_a=.028,wake_start_s=2e-6,grid_s=.25e-9)
        exact,_=driver_wake_response(dict(network=c),**arguments)
        spectral,r=driver_wake_response(dict(network=c),**arguments,reference_input=dict(cap_f=0.,link_r_ohm=1e-12))
        difference=abs(exact['rail_v']-spectral['rail_v']);t=exact['times_s']
        # The ideal linear-ramp slope jumps at its corners. Inductive voltage
        # jumps there; a finite Fourier series approaches the midpoint.
        away=(abs(t-2e-6)>2e-9)&(abs(t-2.02e-6)>2e-9)
        self.assertLess(max(difference[away]),20e-6)
        self.assertLess(np.sqrt(np.mean(difference**2)),2e-6)
        self.assertAlmostEqual(r['initial_rail_relief_v'],.028*2.12,places=11)
        short,rs=driver_wake_response(dict(network=c),**arguments,reference_input={})
        long,rl=driver_wake_response(dict(network=c),**arguments,reference_input={},guard_s=16e-6)
        self.assertLess(max(abs(short['rail_v']-long['rail_v'])),1e-6)
        np.testing.assert_allclose(short['driver_current_a'],exact['driver_current_a'],atol=1e-12)

    def test_wake_current_is_within_budget_and_initial_dc_matches_resistors(self):
        from selected_rf import driver_wake_response
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        for released in (0.,.007,.028):
            response,r=driver_wake_response(dict(network=c),released_current_a=released,
                wake_start_s=2.0003e-6,ramp_s=20.4e-9)
            self.assertAlmostEqual(r['initial_rail_relief_v'],released*2.12,places=12)
            self.assertAlmostEqual(r['driver_current_interval_a'][0],.028-released,places=12)
            self.assertAlmostEqual(r['driver_current_interval_a'][1],.028,places=12)
            self.assertLess(abs(r['final_current_delta_a']),1e-12)
            self.assertLess(abs(r['final_rail_delta_v']),1e-9)
            # Independent charge integral for a linear ramp, including fractional bins.
            t=response['times_s'];current=response['driver_current_a']
            before=t<2.0003e-6;after=t>2.0207e-6
            np.testing.assert_allclose(current[before],.028-released,atol=1e-12)
            np.testing.assert_allclose(current[after],.028,atol=1e-12)
            self.assertAlmostEqual(response['delay_s'][0],released*2.12e-10,places=18)
        with self.assertRaises(ValueError):
            driver_wake_response(dict(network=c),released_current_a=.029,wake_start_s=0.)


if __name__=='__main__':unittest.main()
