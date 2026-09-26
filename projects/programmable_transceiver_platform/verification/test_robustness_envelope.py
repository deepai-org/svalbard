"""Independent signal/timing checks for the direct-LO mitigation candidate."""
import json
import math
import unittest
from dataclasses import replace
import numpy as np
from robustness_envelope import (P, external_settings, clock_host_candidate,
    resampler_cost, summarize_quality)
from behavioral import Assumptions, BehavioralChip, bandlimited_samples, waveform_screen
from protocol_signals import fixture
from resource_configuration import validate_rf_settings
from oscillator_noise import PhaseNoise


class RecoveryStudyTests(unittest.TestCase):
    def test_longer_known_prefix_improves_estimation_without_hiding_wideband_failure(self):
        from robustness_envelope import lora_recovery_suite
        r=lora_recovery_suite(json.loads((P/'spec/contract.json').read_text()))
        rows=[x for x in r['cases'] if x['rx_cutoff_multiplier']==1 and x['blocker'] is None]
        for recipe in {x['recipe'] for x in rows}:
            short=[x for x in rows if x['recipe']==recipe and x['training_samples']==512]
            long=[x for x in rows if x['recipe']==recipe and x['training_samples']==2048]
            self.assertLess(max(abs(x['estimation_error_hz']) for x in long),max(abs(x['estimation_error_hz']) for x in short)/5)
        narrow=[x for x in rows if x['recipe']=='lora_24__5000000.0' and x['training_samples']==2048]
        wide=[x for x in rows if x['recipe']=='lora_24__10000000.0' and x['training_samples']==2048]
        self.assertTrue(all(x['quality']['conditional_waveform_pass'] for x in narrow))
        self.assertTrue(all(not x['quality']['conditional_waveform_pass'] for x in wide))

        combined=[x for x in r['cases'] if x['rx_cutoff_multiplier']==2 and x['training_samples']==2048 and x['blocker'] is None]
        self.assertTrue(combined and all(x['quality']['conditional_waveform_pass'] for x in combined))
        self.assertTrue(all(x['frontend_noise_variance_multiplier']==2. for x in combined))
        self.assertTrue(all(x['frontend_evm_rms']>r['assumptions']['frontend_evm_rms'] for x in combined))

        blocked=next(x for x in r['cases'] if x['rx_cutoff_multiplier']==2 and x['blocker'] is not None)
        self.assertFalse(blocked['quality']['conditional_waveform_pass'])

    def test_frequency_estimator_does_not_use_payload_labels(self):
        from robustness_envelope import make_wave, external_settings, CASES
        c=json.loads((P/'spec/contract.json').read_text())
        case=next(x for x in c['behavioral_configuration_cases'] if x['id']=='lora_24__5000000.0')
        settings=external_settings(case['rf'],2.437e9)
        a=replace(Assumptions(),**CASES['moderate_precision'])
        estimates=[]
        for payload_seed in (81,82):
            q=waveform_screen(make_wave(case,payload_seed),a,{'estimated_rail_v':{'RF':3.25}},
                settings=settings,seed=81,recover_carrier=True,fpga_resampling=True,
                training_samples=2048,carrier_offset_hz=5000.)
            estimates.append(q['carrier_recovery']['estimate_hz'])
        self.assertEqual(estimates[0],estimates[1])


class ResourceJoinTests(unittest.TestCase):
    def test_host_internal_charge_and_board_impedance_tradeoff(self):
        from robustness_envelope import joined_rf_resource_screen,host_charge_pdn_bridge
        c=json.loads((P/'spec/contract.json').read_text())
        result=host_charge_pdn_bridge(c,joined_rf_resource_screen(c))
        rows={r['name']:r for r in result['cases']}
        base,more,low=[rows[k] for k in ('existing_10uf','more_capacitance','lower_esr')]
        self.assertAlmostEqual(base['host_activity_current_tone_peak_a'],.5*(base['host_data_capacitive_average_a']+base['host_data_internal_average_a']))
        self.assertAlmostEqual(base['host_data_internal_average_a']/base['host_data_capacitive_average_a'],14/33)
        self.assertLess(abs(more['die_ripple_peak_v']/base['die_ripple_peak_v']-1),.01)
        self.assertLess(low['die_ripple_peak_v'],.6*base['die_ripple_peak_v'])
        self.assertEqual(base['modeled_clock_rail_dc_v'],low['modeled_clock_rail_dc_v'])
        self.assertLess(base['modeled_clock_rail_dc_v'],3.12)
        feed=rows['lower_feed_resistance'];adverse=rows['lower_feed_adverse_cap']
        self.assertEqual(feed['network']['package_r'],base['network']['package_r'])
        self.assertAlmostEqual(feed['modeled_clock_rail_dc_v']-base['modeled_clock_rail_dc_v'],1.9*(base['host_average_current_a']+base['clock_victim_current_a']))
        self.assertAlmostEqual(feed['dc_board_feed_loss_w']/base['dc_board_feed_loss_w'],.05)
        self.assertGreater(feed['transfer_scan_peak']['transimpedance_ohm'],base['transfer_scan_peak']['transimpedance_ohm'])
        for candidate in (feed,adverse):
            self.assertGreater(candidate['modeled_clock_rail_dc_v'],3.24)
            self.assertTrue(next(x for x in candidate['spectral_cases'] if x['board_blocker_attenuation_db']==20)['quality']['conditional_waveform_pass'])

        for r in rows.values():
            self.assertLess(r['kcl_residual_a'],1e-10)
            self.assertTrue(all(not x['quality']['conditional_waveform_pass'] for x in r['spectral_cases'] if x['board_blocker_attenuation_db']==0))


    def test_joined_dc_rail_reaches_signal_path_and_retains_clock_failures(self):
        from robustness_envelope import joined_rf_resource_screen,rf_dc_quality_bridge
        c=json.loads((P/'spec/contract.json').read_text());budgets=joined_rf_resource_screen(c)
        report=rf_dc_quality_bridge(c,budgets)
        chosen=[]
        for r in report['cases']:
            budget=next(x for x in budgets['cases'] if x['lo_hz']==2.437e9 and x['clock_static_current_a']==.012 and x['data_rising_probability']==r['data_rising_probability'])
            self.assertEqual(r['rf_rail_v'],budget['estimated_rail_v']['RF'])
            good=next(x for x in r['spectral_cases'] if x['clock']=='external_clean' and x['rail_ripple_peak_v']==.001 and x['board_blocker_attenuation_db']==20)
            self.assertTrue(good['quality']['conditional_waveform_pass'])
            self.assertTrue(all(not x['quality']['conditional_waveform_pass'] for x in r['spectral_cases'] if x['clock']=='external_noisy' or x['rail_ripple_peak_v']==.01))
            chosen.append((r['rf_rail_v'],good['pga_headroom']['signal_peak_per_component_v']))
        self.assertLess(chosen[1][0],chosen[0][0])
        self.assertAlmostEqual(chosen[1][1]/chosen[0][1],chosen[1][0]/chosen[0][0],places=12)


    def test_join_charges_host_transitions_and_rf_driver_once(self):
        from robustness_envelope import joined_rf_resource_screen
        report=joined_rf_resource_screen(json.loads((P/'spec/contract.json').read_text()))
        rows=report['cases']
        for r in rows:
            self.assertEqual(r['assigned_current_a']['RF'],.037)
            self.assertAlmostEqual(r['total_assigned_supply_power_w'],3.3*sum(r['assigned_current_a'].values()))
        low=[r for r in rows if r['clock_static_current_a']==.012]
        self.assertTrue(all(r['conditional_allocation_pass'] for r in low))
        medium=[r for r in rows if r['clock_static_current_a']==.024]
        self.assertTrue(all(r['conditional_allocation_pass']==(r['lo_hz']==2.4e9) for r in medium))
        worst=next(r for r in low if r['lo_hz']==2.484e9 and r['data_rising_probability']==.5)
        self.assertAlmostEqual(worst['assigned_current_a']['HOST_B'],.0457805)
        self.assertFalse(report['joint_fit_verified'])


class CoverageTests(unittest.TestCase):
    def test_weak_recipe_controls_retain_deterministic_error(self):
        from robustness_envelope import weak_rf_recipe_controls
        r=weak_rf_recipe_controls(json.loads((P/'spec/contract.json').read_text()))
        ble=next(x for x in r['cases'] if x['recipe'].startswith('bluetooth_le_2m') and x['lo_hz']==2.4e9)
        self.assertGreater(ble['quality']['evm_rms'],.1)
        self.assertEqual(ble['quality']['symbol_errors'],0)
        self.assertFalse(ble['quality']['conditional_waveform_pass'])
        self.assertEqual(r['assumptions']['frontend_evm_rms'],0.)
        rows=r['configuration_comparisons']
        wider=[x for x in rows if x['recipe'].startswith('bluetooth_le_2m') and x['configuration_change']=='wider_rx']
        self.assertTrue(all(x['quality']['conditional_waveform_pass'] for x in wider if x['blocker'] is None))
        blocked=next(x for x in wider if x['blocker'] is not None)
        self.assertGreater(blocked['quality']['symbol_errors'],0)
        self.assertFalse(blocked['quality']['acquisition'])
        for x in rows:
            self.assertEqual(x['converter_rate_ratio_to_baseline'],2. if x['configuration_change']=='faster_sampling' else 1.)
        fast_lora=[x for x in rows if x['recipe'].startswith('lora_24') and x['configuration_change']=='faster_sampling']
        self.assertTrue(any(x['quality']['evm_rms']>.4 for x in fast_lora))



    def test_coverage_does_not_hide_missing_target_or_failed_recipe(self):
        from robustness_envelope import capability_coverage
        contract=json.loads((P/'spec/contract.json').read_text())
        recipe=next(c['id'] for c in contract['behavioral_configuration_cases'] if c.get('fixture')=='bluetooth_le')
        configs={name:dict(recipe=recipe,clock='external_lo',lo_hz=lo) for name,lo in [('a',2.4e9),('b',2.48e9)]}
        observations=[dict(configuration_id=name,impairment_case='moderate_precision',fpga_resampling=True,
            quality=dict(conditional_waveform_pass=passed,evm_rms=evm,symbol_errors=errors))
            for name,passed,evm,errors in [('a',True,.08,0),('b',False,.2,3)]]
        report=capability_coverage(contract,configs,observations)
        self.assertEqual({r['target'] for r in report['capabilities']},{r['id'] for r in contract['protocol_profiles']})
        row=report['external_lo_resampled_rf_slices'][0]
        self.assertEqual(row['lo_hz_with_a_diagnostic_passing_configuration'],[2.4e9])
        self.assertEqual(row['maximum_fixture_symbol_errors'],3)
        self.assertTrue(all(not r['complete_operating_envelope'] for r in report['capabilities']))


class RobustnessTests(unittest.TestCase):
    def test_explicit_loss_restoration_and_pre_adc_clipping(self):
        a=replace(Assumptions(),converter_enob=12.,sample_jitter_s=0.,
                  relative_lo_phase_rms_rad=0.,frontend_evm_rms=0.)
        power={'estimated_rail_v':{'RF':3.25}}
        wave=fixture('wifi_he20')
        common=dict(recover_carrier=True,fpga_resampling=True)
        baseline=waveform_screen(wave,a,power,settings=self.settings,**common)
        restored=waveform_screen(wave,a,power,settings=dict(self.settings,rx_gain=10**(.1)),
                                 frontend_loss_db=2.,**common)
        self.assertAlmostEqual(baseline['pga_headroom']['signal_peak_per_component_v'],
                               restored['pga_headroom']['signal_peak_per_component_v'],places=12)
        self.assertAlmostEqual(baseline['equalized']['evm_rms'],restored['equalized']['evm_rms'],places=10)
        clipped=waveform_screen(wave,a,power,settings=self.settings,pga_peak_limit_v=.1,**common)
        self.assertGreater(clipped['pga_headroom']['clipped_signal_samples'],0)
        self.assertEqual(clipped['adc_clipped_samples'],0)
        self.assertFalse(clipped['conditional_screen_pass'])

    def test_existing_gain_setting_rescues_limited_headroom(self):
        from robustness_envelope import explicit_gain_suite
        result=explicit_gain_suite(self.contract)
        for clock in ('external_clean','autonomous_wider'):
            rows=[r for r in result['cases'] if r['clock']==clock and
                  r['pga_headroom']['peak_limit_v']==.35]
            restored=next(r for r in rows if r['restore_gain'])
            reduced=next(r for r in rows if r['pga_headroom']['configured_gain']==.5)
            self.assertGreater(restored['pga_headroom']['clipped_signal_samples'],0)
            self.assertEqual(restored['quality']['adc_clipped_samples'],0)
            self.assertFalse(restored['quality']['conditional_waveform_pass'])
            self.assertEqual(reduced['pga_headroom']['clipped_signal_samples'],0)
            self.assertTrue(reduced['quality']['conditional_waveform_pass'])

    @classmethod
    def setUpClass(cls):
        cls.contract=json.loads((P/'spec/contract.json').read_text())
        cls.settings=next(c['rf'] for c in cls.contract['behavioral_configuration_cases']
                          if c['id']=='wifi_he20__40000000.0')

    def test_external_clock_owner_and_integer_rates(self):
        for lo in (2.4e9,2.437e9,2.484e9):
            for base in (5e6,10e6,20e6,40e6):
                s=external_settings(dict(self.settings,sample_hz=base,
                    tx_cutoff_hz=base/2,rx_cutoff_hz=min(base/4,9.157407e6)),lo)
                self.assertEqual(s['sample_hz']*s['lo_divider'],lo)
                host=clock_host_candidate(s,self.contract)
                self.assertTrue(host['capacity_pass'])
                self.assertTrue(host['within_existing_maximum_gpio_rate'])
                self.assertEqual(host['extra_signal_pins'],0)
                self.assertAlmostEqual(s['sample_hz']/(2*host['d2h_clock_hz']),8/s['lo_divider'])
        s=external_settings(self.settings,2.437e9)
        for changes in ({'sample_hz':40e6},{'lo_divider':64.5},
                        {'lo_divider':True},{'sample_clock_source':'reference'},
                        {'lo_hz':4.874e9}):
            with self.assertRaises(ValueError):validate_rf_settings(**dict(s,**changes))
        with self.assertRaises(ValueError):validate_rf_settings(sample_hz=38e6)

    def test_reference_timing_cannot_be_attached_to_direct_lo(self):
        c=BehavioralChip(Assumptions())
        c.configure_numeric(engine='rf',rf=external_settings(self.settings,2.437e9))
        c.attach_rf_stream(lambda i:0j)
        self.assertEqual(c.rf_stream.settings['sample_clock_source'],'external_lo')
        with self.assertRaises(ValueError):c.attach_rf_timing({})
        with self.assertRaises(ValueError):c.attach_pulse_rf(c.rf_stream)

    def test_filter_margin_uses_existing_faster_divider(self):
        base=dict(self.settings,sample_hz=20e6,tx_cutoff_hz=10e6,converter_bits=8)
        wave=fixture('wifi_he20')
        a=replace(Assumptions(),converter_enob=8.,relative_lo_phase_rms_rad=.015)
        for lo in (2.4e9,2.437e9,2.484e9):
            low=external_settings(base,lo)
            high=external_settings(base,lo,minimum_filter_samples=3.)
            self.assertEqual(low['lo_divider'],128)
            self.assertEqual(high['lo_divider'],64)
            self.assertEqual(high['converter_bits'],8)
            q=summarize_quality(waveform_screen(wave,a,{'estimated_rail_v':{'RF':3.25}},
                    settings=high,recover_carrier=True,fpga_resampling=True))
            self.assertTrue(q['conditional_waveform_pass'])
            self.assertLess(q['evm_rms'],.06)

    def test_fir_delay_makes_tx_causal(self):
        rng=np.random.default_rng(39)
        original=rng.normal(size=300)+1j*rng.normal(size=300)
        changed=original.copy();changed[101:]+=100
        # At t=100.3 input periods, delayed positions cannot see sample 101.
        positions=np.linspace(0,100.3,201)-32
        np.testing.assert_array_equal(bandlimited_samples(original,positions),
                                      bandlimited_samples(changed,positions))
        # Later outputs really do respond to the changed input (not a frozen trace).
        self.assertGreater(abs(bandlimited_samples(original,np.array([110.]))[0]-
                               bandlimited_samples(changed,np.array([110.]))[0]),10)

    def test_fir_interpolates_tone_and_integer_samples(self):
        n=np.arange(600);x=np.exp(2j*np.pi*.07*n)
        p=np.linspace(80.1,499.7,1000)
        error=bandlimited_samples(x,p)-np.exp(2j*np.pi*.07*p)
        self.assertLess(np.max(abs(error)),1e-4)
        np.testing.assert_allclose(bandlimited_samples(x,n[64:-64]),x[64:-64],atol=1e-13)

    def test_wideband_rescue_and_adverse_noise_boundary(self):
        wave=fixture('wifi_he20',seed=81)
        power={'estimated_rail_v':{'RF':3.25}}
        a=replace(Assumptions(),converter_enob=8.,relative_lo_phase_rms_rad=.015)
        for lo in (2.4e9,2.437e9,2.484e9):
            settings=external_settings(self.settings,lo)
            raw=summarize_quality(waveform_screen(wave,a,power,settings=settings,recover_carrier=True))
            fixed=summarize_quality(waveform_screen(wave,a,power,settings=settings,
                                      recover_carrier=True,fpga_resampling=True))
            self.assertGreater(raw['evm_rms'],.30)
            self.assertTrue(fixed['conditional_waveform_pass'])
            self.assertLess(fixed['evm_rms'],.07)
        adverse=replace(a,converter_enob=6.,relative_lo_phase_rms_rad=.06,frontend_evm_rms=.10)
        q=summarize_quality(waveform_screen(wave,adverse,power,settings=settings,
                               recover_carrier=True,fpga_resampling=True))
        self.assertFalse(q['conditional_waveform_pass'])
        self.assertGreater(q['evm_rms'],.10)
        cost=resampler_cost(20e6,2.437e9/64)
        self.assertEqual(cost['on_chip_storage_bits'],0)
        self.assertEqual(cost['history_bits_per_direction'],2304)
        self.assertGreater(cost['tx_real_macs_per_second'],4e9)
        self.assertFalse(cost['throughput_implemented'])


class SpectralClockTests(unittest.TestCase):
    def test_ssb_integral_and_loop_transfer(self):
        lo,hi=1e3,8e6
        source=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-100.,floor_dbc_hz=-145.)
        exact=2*10**(-100/10)*1e10*(1/lo-1/hi)+2*10**(-145/10)*(hi-lo)
        self.assertAlmostEqual(source.variance_rad2/exact,1.,places=12)
        pole=1e5
        exact_filtered=(2*10**(-100/10)*1e10/pole*
            (math.atan(hi/pole)-math.atan(lo/pole))+
            2*10**(-145/10)*(hi-lo-pole*(math.atan(hi/pole)-math.atan(lo/pole))))
        errors=[]
        for bins in (48,96,192):
            filtered=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-100.,floor_dbc_hz=-145.,
                loop_pole_hz=pole,injection='vco',bins=bins)
            errors.append(abs(filtered.variance_rad2/exact_filtered-1))
        self.assertLess(errors[-1],errors[0]/10)
        self.assertLess(errors[-1],.0002)

    def test_chunk_queries_and_coherent_supply_addition(self):
        source=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-100.,floor_dbc_hz=-145.)
        times=np.linspace(0,1e-4,1000)
        np.testing.assert_array_equal(source.phase(times),
            np.r_[source.phase(times[:371]),source.phase(times[371:])])
        self.assertAlmostEqual(source.plus(source).variance_rad2/source.variance_rad2,4.)
        cancelled=source.plus(PhaseNoise(tuple((f,-a,p) for f,a,p in source.tones)))
        self.assertLess(cancelled.variance_rad2,1e-25)

    def test_shared_clock_and_legacy_phase_are_not_double_counted(self):
        contract=json.loads((P/'spec/contract.json').read_text())
        base=next(c['rf'] for c in contract['behavioral_configuration_cases']
                  if c['id']=='wifi_he20__40000000.0')
        s=external_settings(base,2.437e9)
        phase=PhaseNoise(((1e6,.01,0.),))
        with self.assertRaises(ValueError):
            waveform_screen(fixture('wifi_he20'),Assumptions(),{'estimated_rail_v':{'RF':3.25}},
                            settings=s,mixer_phase_noise=phase)
        # A reference-derived converter must not silently inherit LO/divider timing.
        with self.assertRaises(ValueError):
            waveform_screen(fixture('wifi_he20'),replace(Assumptions(),relative_lo_phase_rms_rad=0),
                            {'estimated_rail_v':{'RF':3.25}},sample_phase_noise=phase)

    def test_blocker_is_reciprocally_mixed_before_filter(self):
        from unittest.mock import patch
        from scipy.special import jv
        import behavioral
        original=behavioral.multipole_envelope
        captured=[]
        def observe(values,*args):
            captured.append(np.array(values,copy=True))
            return original(values,*args)
        phase=PhaseNoise(((1e6,.1,0.),))
        a=replace(Assumptions(),relative_lo_phase_rms_rad=0.)
        with patch.object(behavioral,'multipole_envelope',observe):
            for blocker in (None,dict(offset_hz=1e6,relative_power_db=-10.)):
                waveform_screen(fixture('wifi_he20'),a,{'estimated_rail_v':{'RF':3.25}},
                    mixer_phase_noise=phase,blocker=blocker,mixer_substeps=4)
        # exp(jwt)*exp(-j*beta*cos(wt)) has DC coefficient -j*J1(beta).
        # Subtracting paired mixer inputs removes wanted signal exactly. This
        # tests the actual injection point, not just a standalone PSD formula.
        difference=captured[1]-captured[0]
        n=(len(difference)//160)*160  # Whole 1 MHz periods at 160 MS/s.
        amplitude=10**(-a.converter_backoff_db/20)*10**(-10/20)
        self.assertLess(abs(np.mean(difference[:n])+1j*amplitude*jv(1,.1)),1e-12)

    def test_joint_mitigation_has_two_conditional_paths_and_retains_failures(self):
        from robustness_envelope import spectral_rf_mitigations
        contract=json.loads((P/'spec/contract.json').read_text())
        result=spectral_rf_mitigations(contract,seed_offsets=(0,))
        cases={(x['clock'],x['rail_ripple_peak_v'],x['board_blocker_attenuation_db']):x
               for x in result['cases']}
        for clock in ('external_clean','autonomous_wider'):
            rescued=cases[clock,.001,20.]
            self.assertTrue(rescued['quality']['conditional_waveform_pass'])
            self.assertLess(rescued['quality']['evm_rms'],.08)
            self.assertFalse(cases[clock,.001,0.]['quality']['conditional_waveform_pass'])
        self.assertFalse(cases['external_noisy',.001,20.]['quality']['conditional_waveform_pass'])
        self.assertFalse(cases['autonomous_narrow',.001,20.]['quality']['conditional_waveform_pass'])
        self.assertGreater(cases['external_clean',.001,20.]['spectral_clock']['shared_sample_time_error_rms_s'],0)
        self.assertEqual(cases['autonomous_wider',.001,20.]['spectral_clock']['shared_sample_time_error_rms_s'],0)


class HostPdnTests(unittest.TestCase):
    def test_shared_return_limit_kcl_and_power(self):
        from robustness_envelope import board_die_transfer,shared_return_transfer
        for f in (1e3,1e6,3e8):
            old=board_die_transfer(f,board_c=10e-6,package_r=2.)
            ideal=shared_return_transfer(f,return_r=0,return_l=0,board_c=10e-6,package_r=2.)
            self.assertEqual(old['die_ohm'],ideal['differential_ohm'])
            for fraction in (0.,.3,1.):
                r=shared_return_transfer(f,shared_fraction=fraction,board_c=10e-6,package_r=2.)
                self.assertLess(r['kcl_residual_a'],1e-12)
                self.assertLess(abs(r['power_residual_w']),1e-11)
                self.assertEqual(r['differential_ohm'],r['die_ohm']-r['ground_ohm'])

    def test_low_frequency_common_return_cannot_be_bypassed_by_board_cap(self):
        from robustness_envelope import shared_return_transfer
        # Small local C leaves local return bounce essentially I*R. A large
        # BOARD capacitor holds its supply node but does not short die ground.
        r=shared_return_transfer(1e3,return_r=.1,return_l=0,board_c=1.,
            board_esr=0,board_esl=0,die_c=1e-15,package_r=2.)
        self.assertAlmostEqual(r['ground_ohm'].real,.1,places=8)
        self.assertAlmostEqual(r['differential_ohm'].real,-.1,places=6)

    def test_unshunted_network_matches_closed_form(self):
        from robustness_envelope import board_die_transfer
        for f in (1e3,1e6,1e8,1e9):
            w=2*math.pi*f
            zs=2+1j*w*2e-9;zp=.1+1j*w*2e-9
            expected=-zs/(1+1j*w*100e-12*(zs+zp))
            r=board_die_transfer(f)
            self.assertLess(abs(r['die_ohm']-expected),1e-12)
            self.assertLess(r['kcl_residual_a'],1e-12)

    def test_passive_ac_power_balance(self):
        from robustness_envelope import board_die_transfer
        for f in (1e6,3e8):
            w=2*math.pi*f
            r=board_die_transfer(f,board_c=1e-6)
            vb,vd=r['board_ohm'],r['die_ohm']
            zs=2+1j*w*2e-9;zp=.1+1j*w*2e-9
            zc=.05+1j*w*1e-9+1/(1j*w*1e-6)
            supplied=-vb.real/2
            dissipated=(abs(vb/zs)**2*2+abs((vb-vd)/zp)**2*.1+abs(vb/zc)**2*.05)/2
            self.assertAlmostEqual(supplied,dissipated,places=11)
            self.assertGreater(supplied,0)

    def test_damping_cost_and_nonideal_board_cap(self):
        from robustness_envelope import host_pdn_scenarios
        r={x['name']:x for x in host_pdn_scenarios()}
        self.assertGreater(r['no_board_cap']['die_ripple_peak_v'],.02)
        self.assertLess(r['board_1uf']['die_ripple_peak_v'],.0021)
        self.assertGreater(r['board_1uf']['frequency_scan_peak']['transimpedance_ohm'],20)
        self.assertLess(r['board_1uf_damped']['frequency_scan_peak']['transimpedance_ohm'],4)
        self.assertAlmostEqual(r['board_1uf']['dc_victim_rail_v']-
                               r['board_1uf_damped']['dc_victim_rail_v'],1.9*.024)
        self.assertEqual(r['board_1uf']['ideal_die_cap_plate_area_um2'],50000.)


class DiagnosticTests(unittest.TestCase):
    def test_rf_bench_pairs_ignore_unobservable_injected_truth(self):
        import copy
        from robustness_envelope import rf_bench_diagnostics
        base=dict(recipe='test',lo_hz=2.437e9,seed=81,injected_offset_hz=5000.,
            rx_cutoff_multiplier=1.,blocker=None,carrier_estimate_hz=4990.,
            training_samples=512,estimation_error_hz=-10.,
            quality=dict(evm_rms=.2,symbol_errors=0,acquisition=True,carrier_acquired=True,adc_clipped_samples=19))
        after=copy.deepcopy(base);after.update(training_samples=2048,carrier_estimate_hz=4999.,estimation_error_hz=-1.)
        after['quality']['evm_rms']=.08
        study=dict(cases=[base,after]);first=rf_bench_diagnostics(study)
        for row in study['cases']:
            row['estimation_error_hz']=1e9
            row['quality']['adc_clipped_samples']=1000000
        self.assertEqual(first,rf_bench_diagnostics(study))
        pair=first['paired_observations'][0]
        self.assertAlmostEqual(pair['evm_change'],-.12)
        self.assertEqual(set(pair['observations_after']),{'known_stimulus_evm','known_stimulus_symbol_errors','carrier_estimate_hz','acquired'})


    def test_interventions_discriminate_but_do_not_invent_hidden_noise_source(self):
        from robustness_envelope import diagnostic_observability_suite
        report=diagnostic_observability_suite(json.loads((P/'spec/contract.json').read_text()))
        for row in report['observations']:
            for observation in row['observations'].values():
                self.assertEqual(set(observation),{'evm_rms','digitized_rms','acquired'})
        pairs=report['pairwise_discrimination']
        alias=next(p for p in pairs if set(p['hypotheses'])=={'converter_noise','post_pga_sampler_noise'})
        self.assertFalse(alias['separated_in_this_sweep'])
        self.assertIsNone(alias['separating_feature'])
        self.assertTrue(any(p['separated_in_this_sweep'] and not p['baseline_only_separated'] for p in pairs))
        p=next(p for p in pairs if set(p['hypotheses'])=={'source_phase','pga_headroom'})
        self.assertTrue(p['separated_in_this_sweep'])


class TxSpectralTests(unittest.TestCase):
    def test_interpolation_removes_host_images_without_hiding_dac_image(self):
        from robustness_envelope import tx_image_attribution_suite
        r=tx_image_attribution_suite()
        rows=r['cases']
        for seed in (953,977):
            select=lambda mode,ideal:next(x for x in rows if x['payload_seed']==seed and x['interpolation']==mode and x['ideal_output']==ideal)
            original=select('repeat',False);fixed=select('fir',False)
            self.assertLess(fixed['band_power_ratios']['adjacent_10_30mhz'],original['band_power_ratios']['adjacent_10_30mhz']/500)
            self.assertGreater(fixed['band_power_ratios']['dac_image_30_50mhz'],.003)
            self.assertLess(abs(original['band_power_ratios']['adjacent_10_30mhz']-select('repeat',True)['band_power_ratios']['adjacent_10_30mhz']),.001)
            self.assertTrue(fixed['electrical']['within_declared_compliance'])
            self.assertEqual(fixed['dac_clips'],0)
        self.assertGreater(r['fir_cost']['tx_real_macs_per_second'],0)
        for seed in (953,977):
            selected={x['tx_cutoff_hz']:x for x in rows if x['payload_seed']==seed and x['interpolation']=='fir' and not x['ideal_output']}
            narrow,base,wide=[selected[f] for f in (5e6,10e6,15e6)]
            self.assertLess(narrow['band_power_ratios']['dac_image_30_50mhz'],base['band_power_ratios']['dac_image_30_50mhz'])
            self.assertLess(base['band_power_ratios']['dac_image_30_50mhz'],wide['band_power_ratios']['dac_image_30_50mhz'])
            self.assertLess(narrow['average_load_power_w'],base['average_load_power_w'])
            self.assertLess(narrow['reconstruction_gain_at_9mhz_db'],-6.)
            requirement=narrow['same_average_power_requirement']
            self.assertAlmostEqual(requirement['voltage_multiplier']**2*narrow['average_load_power_w'],base['average_load_power_w'])



    def test_phase_power_conservation_and_loaded_output_backoff(self):
        from robustness_envelope import tx_spectral_suite
        rows=tx_spectral_suite()['cases']
        for r in rows:
            self.assertAlmostEqual(r['emitted_average_load_power_w'],r['average_load_power_w'],places=13)
            self.assertLessEqual(r['incremental_constant_fit_evm_rms'],r['incremental_raw_evm_rms']+1e-12)
        self.assertTrue(all(r['electrical']['within_declared_compliance'] for r in rows if r['tx_voltage_scale']==4.5))
        self.assertTrue(any(not r['electrical']['within_declared_compliance'] for r in rows if r['tx_voltage_scale']==5.02))
        clean=[r for r in rows if r['clock']=='external_clean']
        self.assertTrue(all(r['incremental_constant_fit_evm_rms']<.01 for r in clean if r['rail_ripple_peak_v']==0))
        self.assertTrue(all(r['incremental_constant_fit_evm_rms']>.4 for r in clean if r['rail_ripple_peak_v']==.01))


class WiredEnvelopeTests(unittest.TestCase):
    def test_inverse_resource_requirements_and_nonclosure(self):
        from wired_envelope import wired_resource_requirements
        r=wired_resource_requirements(json.loads((P/'spec/contract.json').read_text()))
        for x in r['clock_distribution']:
            current=x['static_current_ma']+1000*x['maximum_equivalent_full_swing_cap_f']*3.3*r['rate_bps']
            self.assertAlmostEqual(current,r['domain_ceiling_ma']['PLL'])
        for x in r['driver_pole']:
            gm=x['conditional_single_pole_bias_ma']/1000*x['assumed_gm_over_id_per_v']
            self.assertAlmostEqual(x['internal_pole_cap_f']/gm/x['switch_tau_s'],1.)
        self.assertAlmostEqual(r['termination_source_power_w'],.0264)
        self.assertIsNone(r['area_estimate_um2'])
        self.assertFalse(r['joint_fit_verified'])


    def test_feedback_receiver_distinguishes_decoding_from_stable_timing(self):
        from wired_envelope import causal_receiver_envelope
        all_rows=causal_receiver_envelope(impaired=True)['cases']
        rows=[r for r in all_rows if r['impairment']['name']=='baseline']
        good=[r for r in rows if r['switch_tau_s']<=100e-12]
        slow=[r for r in rows if r['switch_tau_s']>100e-12]
        self.assertTrue(good and slow)
        self.assertTrue(all(r['heldout_errors']==0 and r['heldout_qualified_fraction']==1 for r in good))
        self.assertTrue(all(r['heldout_errors']==0 and not r['final_timing_qualified'] for r in slow))
        self.assertTrue(all(r['heldout_qualified_fraction']<.25 for r in slow))
        for r in all_rows:
            self.assertGreater(r['heldout_minimum_actual_sample_interval_s'],0)
            self.assertLessEqual(r['maximum_aperture_displacement_s'],math.sqrt(2)*r['impairment']['jitter_rms_s']+1e-21)
            self.assertEqual(r['heldout_errors']>0,r['heldout_minimum_signed_sample_v']<0)
        cleaner=[r for r in all_rows if r['impairment']['name']=='cleaner_aperture_same_voltage' and r['switch_tau_s']==100e-12]
        self.assertTrue(cleaner and all(r['heldout_qualified_fraction']==1 for r in cleaner))
        moderate=[r for r in all_rows if r['impairment']['name']=='moderate_aperture_voltage']
        self.assertTrue(all(r['heldout_qualified_fraction']==1 for r in moderate if r['switch_tau_s']==50e-12))
        self.assertTrue(any(r['heldout_qualified_fraction']<1 for r in moderate if r['switch_tau_s']==100e-12))
        self.assertTrue(all(r['heldout_minimum_signed_sample_v']>.25 for r in moderate if r['switch_tau_s']==100e-12))



    def test_history_bound_against_stateful_witness(self):
        from wired_envelope import history_margin
        from wired_blocks import CurrentSwitchChannel
        for emphasis in (0.,.25,.5):
            rate=2.5e9;sample=.35/rate
            bound=history_margin(rate,sample,100e-12,50e-12,emphasis)
            taps=bound['coefficients']
            symbols=[1]+[-1 if x>=0 else 1 for x in taps[1:]]
            channel=CurrentSwitchChannel(rate,switch_tau_s=100e-12,load_tau_s=50e-12)
            previous=0
            for symbol in reversed(symbols[1:]):
                drive=(symbol-emphasis*previous)/(1+emphasis)
                channel.advance_state(drive,1/rate);previous=symbol
            channel.advance_state((1-emphasis*previous)/(1+emphasis),sample)
            self.assertAlmostEqual(channel.state,bound['normalized_margin']+bound['tail_bound'],places=12)

    def test_rate_dependence_and_joint_electrical_mitigation(self):
        from wired_envelope import wired_operating_envelopes
        c=json.loads((P/'spec/contract.json').read_text());report=wired_operating_envelopes(c)
        def find(rate,cap,tau):
            return next(x for x in report['cases'] if x['rate_bps']==rate and x['pad_cap_f']==cap
                and x['switch_tau_s']==tau and x['relative_jitter_rms_s']==5e-12 and x['postcursor']==0)
        self.assertTrue(find(1.25e9,2e-12,100e-12)['diagnostic_pass'])
        self.assertFalse(find(2.5e9,2e-12,100e-12)['diagnostic_pass'])
        self.assertTrue(find(2.5e9,1e-12,50e-12)['diagnostic_pass'])
        rescued=find(2.5e9,2e-12,100e-12)
        self.assertTrue(rescued['phase_adjusted_diagnostic_pass'])
        self.assertAlmostEqual(rescued['selected_phase_ui'],.8)
        self.assertFalse(find(2.5e9,2e-12,200e-12)['phase_adjusted_diagnostic_pass'])
        for row in report['cases']:
            self.assertGreaterEqual(row['phase_adjusted_minimum_signed_sample_v']+1e-14,row['minimum_signed_sample_v'])
        covered={name for row in report['cases'] for name in row['targets']}
        self.assertTrue({p['id'] for p in c['protocol_profiles'] if p['engine']=='wire'}<=covered)


if __name__=='__main__':unittest.main()
