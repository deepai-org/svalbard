"""Independent codec checks plus shared-campaign adapter boundary tests.

Numerical codec fixtures remain independent; campaign tests invoke the shared
factory indirectly and use explicit mocked rejection/analog boundaries. Neither
role establishes analog or protocol qualification."""
import itertools
import unittest
import numpy as np
from wideband_packet import encode,decode,source,receive,PERMUTATION,legacy_preamble,acquisition_source,acquire

TEST_DESIGN_ROLES = {
    'CodedDataTests': ('independent_fixture', 'Polynomial/exhaustive decoder checks and explicitly synthesized acquisition captures.'),
    'CodedDataTests.test_packet_entry_defaults_follow_the_inventory_gain_limit': ('shared_design', 'Shared packet context and malformed-binding guards; mocked analog entry isolates parameter forwarding.'),
    'CodedDataTests.test_campaign_records_rejected_clocks_without_decoding': ('shared_design', 'Campaign loads shared design; imposed clock rejection verifies result routing before packet generation.'),
}


def polynomial_encoder(bits):
    # Polynomial convolution, independently of the state-transition encoder.
    a=np.array([1,0,1,1,0,1,1]);b=np.array([1,1,1,1,0,0,1])
    return np.column_stack((np.convolve(bits,a)[:len(bits)]%2,
                            np.convolve(bits,b)[:len(bits)]%2)).ravel()


class CodedDataTests(unittest.TestCase):
    def test_packet_entry_defaults_follow_the_inventory_gain_limit(self):
        from unittest.mock import patch
        import wideband_packet as w
        class ReachedAnalog(Exception):pass
        for run in (
            lambda: w.run_case({},431),
            lambda: w.run_acquisition_case({},431,start_sample=137,carrier_offset_hz=0.),
        ):
            with patch.object(w.b,'receiver_inventory_options',return_value={'maximum_gain_db':39.}), \
                 patch.object(w.b,'coupled_wideband_feedback',side_effect=ReachedAnalog) as analog:
                with self.assertRaises(ReachedAnalog):run()
            self.assertEqual(analog.call_args.kwargs['gain_db'],39.)
        with patch.object(w.b,'coupled_wideband_feedback',side_effect=ReachedAnalog) as analog:
            with self.assertRaises(ReachedAnalog):
                w.run_acquisition_case({},431,start_sample=137,carrier_offset_hz=0.,gain_db=54.)
        self.assertEqual(analog.call_args.kwargs['gain_db'],54.)  # Explicit sensitivity override.

        for environment in ({'design_provenance':{}},{'resolved_configuration':{}},
                            {'inventory_current_report':{}}):
            with patch.object(w,'source',side_effect=AssertionError('Source must not run')):
                with self.assertRaises(ValueError):w.run_case(environment,431)
                with self.assertRaises(ValueError):
                    w.run_acquisition_case(environment,431,start_sample=137,carrier_offset_hz=0.)
        from design_definition import load_design
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,sample_divider=64,pga_gain_db=39)
        environment=w.b.configured_environment(config)
        payload=b'Independent packet context'
        context=w.packet_context(environment,payload,seed=431,wanted_dbm=-80.,blocker_dbm=-50.)
        import hashlib
        self.assertEqual(context['resolved_configuration'],config.record())
        self.assertEqual(context['packet_stimuli']['payload_sha256'],hashlib.sha256(payload).hexdigest())
        self.assertEqual(context['packet_stimuli']['payload_bytes'],len(payload))
        environment['resolved_configuration']['sample_hz']=1.
        self.assertEqual(context['resolved_configuration'],config.record())

    def test_campaign_records_rejected_clocks_without_decoding(self):
        from unittest.mock import patch
        import wideband_packet as w
        for args in ([],['--acquisition']):
            with patch.object(w.b,'reference_payload_environment',return_value=(None,{'accepted':False})), \
                 patch.object(w,'run_case') as coded, patch.object(w,'run_acquisition_case') as acquisition, \
                 patch.object(w.b,'write_evidence'):
                report=w.main(args)
            self.assertEqual(len(report['cases']),4)
            self.assertTrue(all(row['status']=='clock_rejected' for row in report['cases']))
            coded.assert_not_called();acquisition.assert_not_called()
            self.assertIn('spec/analog-architecture.json',report['sources_sha256'])

    def test_variable_length_coded_records_include_4096_octets(self):
        from wideband_packet import coded_data_geometry
        for length in (1,128,4092):
            wave,payload,_=source(431,payload_bytes=length)
            result,_=receive(wave.samples,payload_bytes=length)
            self.assertTrue(result['crc_ok']);self.assertTrue(result['tail_zero'])
            self.assertEqual(bytes.fromhex(result['payload_hex']),payload)
        g=coded_data_geometry(4092)
        self.assertEqual(g['framed_bytes'],4096)
        self.assertGreaterEqual(g['uncoded_bits']-g['framed_bits'],6)
        self.assertEqual(g['data_symbols'],281)
        with self.assertRaises(ValueError):coded_data_geometry(0)

    def test_encoder_impulse_and_polynomial_convolution(self):
        np.testing.assert_array_equal(encode([1,0,0,0,0,0,0]),[1,1,0,1,1,1,1,1,0,0,1,0,1,1])
        bits=np.random.default_rng(731).integers(0,2,1200)
        np.testing.assert_array_equal(encode(bits),polynomial_encoder(bits))

    def test_soft_decoder_against_exhaustive_path_search(self):
        messages=[np.r_[bits,np.zeros(6,dtype=int)] for bits in itertools.product((0,1),repeat=6)]
        words=np.array([2*polynomial_encoder(bits)-1 for bits in messages])
        for seed in range(8):
            soft=np.random.default_rng(seed).normal(size=24)
            best=int(np.argmin(np.sum((words-soft)**2,axis=1)))
            np.testing.assert_array_equal(decode(soft),messages[best])

    def test_single_error_recovery_and_interleaver_bijection(self):
        np.testing.assert_array_equal(np.sort(PERMUTATION),np.arange(234))
        bits=np.r_[np.random.default_rng(19).integers(0,2,117),np.zeros(6,dtype=int)]
        soft=2*encode(bits).astype(float)-1
        soft[91]*=-1
        np.testing.assert_array_equal(decode(soft),bits)

    def test_payload_receiver_with_independent_phase_and_gain(self):
        for seed in (431,719,9021):
            wave,payload,_=source(seed)
            samples=.017*np.asarray(wave.samples)*np.exp(.73j)
            result,_=receive(samples)
            self.assertTrue(result['crc_ok'])
            self.assertEqual(result['payload_hex'],payload.hex())
            self.assertFalse(result['real_preamble_acquisition'])

    def test_legacy_field_lengths_power_and_oversampled_consistency(self):
        low,ltf=legacy_preamble();high,_=legacy_preamble(8)
        self.assertEqual(len(low),320)
        np.testing.assert_allclose(high[::8],low,atol=1e-14)
        self.assertAlmostEqual(float(np.mean(abs(low[:160])**2)),1.)
        self.assertAlmostEqual(float(np.mean(abs(ltf)**2)),1.)
        np.testing.assert_allclose(low[:144],low[16:160],atol=1e-14)
        np.testing.assert_allclose(low[192:256],low[256:320],atol=1e-14)

    def test_acquisition_without_arrival_or_offset_truth(self):
        wave,payload,_=source(719)
        for start,cfo in ((73,-120e3),(411,0.),(137,120e3)):
            _,samples=acquisition_source(wave,1,start,cfo)
            acquisition,corrected=acquire(samples*.12*np.exp(.93j))
            self.assertTrue(acquisition['legacy_training_acquired'])
            self.assertEqual(acquisition['data_start_sample'],start+320)
            self.assertAlmostEqual(acquisition['estimated_cfo_hz'],cfo,places=7)
            self.assertLess(acquisition['decision_sample'],start+320+544)
            i=acquisition['data_start_sample'];result,_=receive(corrected[i:i+len(wave.samples)])
            self.assertTrue(result['crc_ok'])
            self.assertEqual(result['payload_hex'],payload.hex())

    def test_acquisition_in_independent_noisy_offset_captures(self):
        wave,_,_=source(719)
        for seed in range(32):
            rng=np.random.default_rng(seed);start=80+7*seed
            _,samples=acquisition_source(wave,1,start,(-1)**seed*120e3)
            samples+=np.sqrt(.5*10**(-3/10))*(rng.normal(size=len(samples))+1j*rng.normal(size=len(samples)))
            result,_=acquire(samples)
            self.assertTrue(result['legacy_training_acquired'])
            self.assertLessEqual(abs(result['data_start_sample']-(start+320)),2)

    def test_acquisition_rejects_noise_and_unmodulated_blocker(self):
        rng=np.random.default_rng(81);n=np.arange(4000)
        noise=.1*(rng.normal(size=len(n))+1j*rng.normal(size=len(n)))
        for samples in (noise,np.exp(2j*np.pi*.013*n)+noise,np.zeros(len(n),complex)):
            result,_=acquire(samples)
            self.assertFalse(result['legacy_training_acquired'])

if __name__=='__main__':unittest.main()
