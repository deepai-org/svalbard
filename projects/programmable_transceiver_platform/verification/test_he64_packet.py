"""Independent coded-OFDM waveform, decoder and error-measurement fixtures.

Ideal channel transformations and injected noise validate the diagnostic peer,
not Wi-Fi 6 compliance or the intended analog conversion chain."""
import unittest
import numpy as np
from he64_packet import source,receive,reference_evm,scalar_observer_evm,POINTS,PUNCTURE

TEST_DESIGN_ROLES = {
    'HE64Tests': ('independent_fixture', 'Independent diagnostic OFDM peer, injected channel/noise, and constellation/error equations.'),
}

class HE64Tests(unittest.TestCase):
    def test_whitened_control_decodes_without_changing_default_stress(self):
        payload=bytes(128)
        for mcs in range(8):
            wave=source(payload,mcs=mcs,whitening_seed=91)
            result=receive(.2j*wave.samples,len(payload),mcs=mcs,whitening_seed=91)
            self.assertEqual(result['payload'],payload);self.assertTrue(result['crc_ok'])
            self.assertFalse(receive(.2j*wave.samples,len(payload),mcs=mcs,whitening_seed=92)['crc_ok'])
            self.assertLess(reference_evm(result,payload,mcs=mcs,whitening_seed=91),1e-12)
            np.testing.assert_array_equal(source(payload,mcs=mcs).samples,
                                          source(payload,mcs=mcs,whitening_seed=None).samples)

    def test_bpsk_padding_whitening_and_explicit_overload_control(self):
        from wideband_packet import source as bpsk_source,receive as bpsk_receive
        for seed,packet in ((1,bytes(128)),(81,None),(902,None)):
            wave,payload,_=bpsk_source(seed,packet=packet)
            result,_=bpsk_receive(wave.samples)
            self.assertTrue(result['crc_ok'])
            self.assertEqual(result['payload_hex'],payload.hex())
            wrong,_=bpsk_receive(wave.samples,whitening_seed=92)
            self.assertFalse(wrong['crc_ok'])
            adverse,_,_=bpsk_source(seed,packet=packet,whitening_seed=None)
            control,_=bpsk_receive(adverse.samples,whitening_seed=None)
            self.assertTrue(control['crc_ok'])
            self.assertLess(max(abs(wave.samples)),max(abs(adverse.samples)))
            np.testing.assert_array_equal(wave.samples[:544],adverse.samples[:544])

    def test_geometry_and_complete_coded_record(self):
        self.assertEqual(len(np.unique(POINTS)),64)
        self.assertAlmostEqual(float(np.mean(abs(POINTS)**2)),1.)
        self.assertEqual(int(PUNCTURE.sum()),6)
        payload=np.random.default_rng(984).integers(0,256,4092,dtype=np.uint8).tobytes()
        wave=source(payload)
        # Unknown constant gain/phase learned from training, not from payload.
        result=receive(wave.samples*.17*np.exp(.71j),len(payload))
        self.assertTrue(result['crc_ok']);self.assertEqual(result['payload'],payload)

    def test_peer_pilot_frequency_measurement_uses_received_signal(self):
        payload=np.random.default_rng(92).integers(0,256,2048,dtype=np.uint8).tobytes()
        wave=source(payload);times=np.arange(len(wave.samples))/20e6
        for offset in (-1000.,0.,1000.):
            result=receive(.2*wave.samples*np.exp(1j*(.37+2*np.pi*offset*times)),len(payload))
            self.assertTrue(result['crc_ok'])
            # Actual intra-symbol CFO also creates ICI in the pilot estimate.
            self.assertLess(abs(result['pilot_frequency_offset_hz']-offset),10.)

    def test_noise_and_corruption_are_not_assumed_success(self):
        payload=bytes(range(128));wave=source(payload);rng=np.random.default_rng(79)
        noise=(rng.normal(size=len(wave.samples))+1j*rng.normal(size=len(wave.samples)))/np.sqrt(2)
        self.assertTrue(receive(wave.samples+.005*noise,len(payload))['crc_ok'])
        self.assertFalse(receive(wave.samples+noise,len(payload))['crc_ok'])

    def test_reference_evm_counts_wrong_constellation_decisions(self):
        payload=bytes(range(128));wave=source(payload)
        result=receive(wave.samples,len(payload))
        self.assertLess(reference_evm(result,payload),1e-12)
        # Rotation by pi leaves every point on the constellation, but destroys
        # the transmitted DATA. Reference scoring must not call it zero error.
        result['equalized']=-result['equalized']
        self.assertAlmostEqual(reference_evm(result,payload),2.,places=12)

    def test_scalar_observer_does_not_hide_frequency_selective_error(self):
        payload=bytes(range(128));wave=source(payload)
        self.assertLess(scalar_observer_evm(.2j*wave.samples,payload),1e-12)
        distorted=wave.samples+.2*np.r_[0j,wave.samples[:-1]]
        decoded=receive(distorted,len(payload))
        self.assertTrue(decoded['crc_ok'])
        self.assertGreater(scalar_observer_evm(distorted,payload),.1)
        self.assertLess(reference_evm(decoded,payload),1e-10)

    def test_diagnostic_window_preserves_fft_samples_and_prices_suffix(self):
        from rf_filter_tradeoff import window_diagnostic_ofdm
        wave=source(bytes(range(128)))
        for w in (0,4,8,16):
            shaped=window_diagnostic_ofdm(wave.samples,w)
            self.assertEqual(len(shaped),len(wave.samples)+w)
            rows=shaped[:len(wave.samples)].reshape(-1,272)
            np.testing.assert_allclose(rows[:,16:],wave.samples.reshape(-1,272)[:,16:])
            self.assertTrue(receive(shaped[:len(wave.samples)],128)['crc_ok'])
        with self.assertRaises(ValueError):window_diagnostic_ofdm(wave.samples,17)
