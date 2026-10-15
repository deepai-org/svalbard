"""Independent calibration mathematics, synthetic measurements and validity checks.

Assigned operating ranges and external RF component examples are fixture inputs;
no physical calibration accuracy or shared-chip performance is inferred."""
import unittest
from rf_power_calibration import PowerCalibration,requested_uplink_power

TEST_DESIGN_ROLES = {
    'PowerCalibrationTests': ('independent_fixture', 'Synthetic equipment tables and operating-validity records; no chip parameter allocation.'),
    'IQCalibrationTests': ('independent_fixture', 'Independent complex affine channel and unseen-signal fit check.'),
    'PACompressionTests': ('independent_fixture', 'Assigned PA transfer and analytical amplitude/phase references.'),
    'AttenuatorBudgetTests': ('independent_fixture', 'Thermal equilibrium and independent resistor-network equations.'),
    'RFDriveRequirementTests': ('independent_fixture', 'Assigned RF source/load values checked against sine-power and quadrature-current equations.'),
}

class PowerCalibrationTests(unittest.TestCase):
    def test_rx_and_timing_consumers_require_current_operating_qualification(self):
        from rf_power_calibration import CalibrationValidity,ReceivePowerCalibration,AntennaTimingCalibration
        context=('die','board','configuration')
        validity=CalibrationValidity(context,(25.,30.),{'VDD':(3.25,3.35)},0.,1.)
        operating=dict(temperature_c=(26.,27.),supplies_v={'VDD':(3.28,3.32)},now_s=.5)
        rx=ReceivePowerCalibration(context,-50.,.01,(-60.,-40.),.2,validity)
        timing=AntennaTimingCalibration(context,.4e-6,.4e-6,validity)
        self.assertEqual(rx.estimate(.01,context=context,operating=operating),-50.)
        timing.schedule(10e-6,sample_hz=40e6,context=context,tolerance_s=1e-8,operating=operating)
        for changed in (None,dict(operating,now_s=1.1),dict(operating,temperature_c=(24.,27.))):
            with self.assertRaises(ValueError):rx.estimate(.01,context=context,operating=changed)
            with self.assertRaises(ValueError):timing.schedule(10e-6,sample_hz=40e6,
                context=context,tolerance_s=1e-8,operating=changed)

    def test_qualification_uses_uncertainty_and_age_not_nominal_conditions(self):
        from rf_power_calibration import CalibrationValidity
        ctx=('die_A','board_A','gain0','filter0',2412e6)
        validity=CalibrationValidity(ctx,(25.,30.),{'VDD':(3.25,3.35)},100.,60.)
        table=PowerCalibration(ctx,((.03,-20.),(.06,-14.)),.2,validity)
        operating=dict(temperature_c=(26.,28.),supplies_v={'VDD':(3.28,3.32)},now_s=110.)
        self.assertAlmostEqual(table.amplitude(-14.,context=ctx,maximum_dbm=-13.,operating=operating),.06)
        for changed in ({'temperature_c':(24.9,27.)},{'now_s':161.},
                        {'supplies_v':{'VDD':(3.30,3.36)}},{'supplies_v':{}}):
            with self.assertRaises(ValueError):
                table.amplitude(-14.,context=ctx,maximum_dbm=-13.,operating=dict(operating,**changed))
        with self.assertRaises(ValueError):
            table.amplitude(-14.,context=ctx,maximum_dbm=-13.)

    def test_restored_rails_do_not_restore_pre_fault_calibration(self):
        from dataclasses import replace
        from rf_power_calibration import CalibrationValidity
        context=('die','board','configuration')
        validity=CalibrationValidity(context,(25.,30.),{'VDD':(3.25,3.35)},0.,1.,condition_generation=4)
        table=PowerCalibration(context,((.03,-20.),(.06,-14.)),.2,validity)
        operating=dict(temperature_c=(26.,27.),supplies_v={'VDD':(3.28,3.32)},now_s=.5,condition_generation=4)
        self.assertAlmostEqual(table.amplitude(-14.,context=context,maximum_dbm=-13.,operating=operating),.06)
        # All measured conditions match again, but a fault has invalidated
        # the old qualification. Boolean/absent tokens cannot bypass this.
        for generation in (None,5,True,-1):
            with self.assertRaisesRegex(ValueError,'generation'):
                table.amplitude(-14.,context=context,maximum_dbm=-13.,
                    operating=dict(operating,condition_generation=generation))
        fresh=replace(table,validity=replace(validity,condition_generation=5,characterized_at_s=.6))
        self.assertAlmostEqual(fresh.amplitude(-14.,context=context,maximum_dbm=-13.,
            operating=dict(operating,condition_generation=5,now_s=.7)),.06)

    def test_characterized_inverse_and_limits(self):
        # Synthetic equipment readings, not a claim of GF180 output power.
        table=PowerCalibration(('boardA',2412e6,'gain0'),((.03,-20.),(.06,-14.),(.12,-8.)),.7)
        ctx=table.context
        self.assertAlmostEqual(table.amplitude(-14.,context=ctx,maximum_dbm=-7.),.06)
        self.assertAlmostEqual(table.amplitude(-17.,context=ctx,maximum_dbm=-7.),(.03*.06)**.5)
        for power in (-21.,-7.):
            with self.assertRaisesRegex(ValueError,'characterized'):
                table.amplitude(power,context=ctx,maximum_dbm=0.)
        with self.assertRaisesRegex(ValueError,'ceiling'):
            table.amplitude(-8.,context=ctx,maximum_dbm=-8.)
        with self.assertRaisesRegex(ValueError,'context'):
            table.amplitude(-14.,context=('another board',),maximum_dbm=0.)

    def test_reciprocal_path_request(self):
        self.assertEqual(requested_uplink_power(15.,-55.,-65.),5.)
        self.assertEqual(requested_uplink_power(15.,-65.,-65.),15.)


class IQCalibrationTests(unittest.TestCase):
    def test_external_fit_generalizes_to_unseen_signal_and_rejects_bad_context(self):
        import numpy as np
        from rf_power_calibration import IQCalibration
        rng=np.random.default_rng(291)
        context=('board_A',2412e6,'gain_1','filter_1',27.,3.3)
        training=.2*(rng.normal(size=4096)+1j*rng.normal(size=4096))
        a=.93*np.exp(.13j);b=.06+.025j;c=.012-.009j
        measured=a*training+b*training.conj()+c
        measured+=.0002*(rng.normal(size=len(training))+1j*rng.normal(size=len(training)))
        fit=IQCalibration.fit(training,measured,context=context)
        desired=.15*(rng.normal(size=2048)+1j*rng.normal(size=2048))
        corrected=fit.correct(desired,context=context)
        emitted=a*corrected+b*corrected.conj()+c
        self.assertLess(np.linalg.norm(emitted-desired)/np.linalg.norm(desired),.001)
        with self.assertRaisesRegex(ValueError,'context mismatch'):
            fit.correct(desired,context=('different_board',))
        with self.assertRaisesRegex(ValueError,'cannot identify'):
            IQCalibration.fit(np.ones(100),np.ones(100),context=context)


class PACompressionTests(unittest.TestCase):
    def test_phase_reference_and_amplitude_preservation(self):
        import numpy as np
        from rf_power_calibration import pa_compression
        x=np.array([.5,1.,1j])
        baseline=pa_compression(x,input_p1db_envelope=1.)
        phased=pa_compression(x,input_p1db_envelope=1.,phase_deg_at_p1db=4.)
        np.testing.assert_allclose(abs(phased),abs(baseline))
        np.testing.assert_allclose(np.angle(phased/baseline)*180/np.pi,[1.,4.,4.])

    def test_one_db_reference_and_phase_preservation(self):
        import numpy as np
        from rf_power_calibration import pa_compression
        x=np.array([0,1,1j,-1,-1j,1e-6],complex)
        y=pa_compression(x,input_p1db_envelope=1.)
        np.testing.assert_allclose(y[1:5]/x[1:5],10**(-1/20))
        self.assertEqual(y[0],0)
        self.assertAlmostEqual(abs(y[-1]/x[-1]),1.)
        # Same physical threshold for a tail; no per-call renormalization.
        np.testing.assert_allclose(pa_compression(x[3:],input_p1db_envelope=1.),y[3:])


class AttenuatorBudgetTests(unittest.TestCase):
    def test_matching_and_thermal_equilibrium(self):
        from rf_power_calibration import matched_attenuator_budget
        for loss in (0.,3.,7.60422483423212,20.):
            r=matched_attenuator_budget(loss_db=loss,input_power_dbm=-3.,bandwidth_hz=20e6)
            equilibrium=1.380649e-23*300.15*20e6
            self.assertAlmostEqual((equilibrium*r['power_gain']+r['added_noise_w'])/equilibrium,1.)
            if loss:
                shunt=r['pi_shunt_ohm'];series=r['pi_series_ohm']
                load=1/(1/shunt+1/50.)
                input_r=1/(1/shunt+1/(series+load))
                self.assertAlmostEqual(input_r,50.)
                self.assertAlmostEqual((load/(series+load))**2,r['power_gain'])
            else:self.assertEqual(r['added_noise_w'],0.)


class RFDriveRequirementTests(unittest.TestCase):
    def test_capacitive_current_is_in_quadrature(self):
        import math
        from rf_power_calibration import rf_drive_requirement
        r=rf_drive_requirement(mean_power_dbm=0.,crest_db=0.,pad_cap_f=1/(2*math.pi*2412e6*50))
        self.assertAlmostEqual(r['total_driver_peak_current_a']/r['load_carrier_peak_current_a'],math.sqrt(2))
        self.assertAlmostEqual(r['source_resistor_mean_dissipation_w'],2*.001*40/50)

    def test_sine_power_convention_and_source_drop(self):
        from rf_power_calibration import rf_drive_requirement
        r=rf_drive_requirement(mean_power_dbm=0.,crest_db=0.)
        self.assertAlmostEqual(r['load_envelope_peak_v']**2/(2*50),.001)
        self.assertAlmostEqual(r['source_differential_peak_v'],r['load_carrier_peak_current_a']*90)
        ten=rf_drive_requirement(mean_power_dbm=0.,crest_db=10.)
        self.assertAlmostEqual((ten['load_envelope_peak_v']/r['load_envelope_peak_v'])**2,10.)
        self.assertEqual(ten['source_resistor_mean_dissipation_w'],r['source_resistor_mean_dissipation_w'])
