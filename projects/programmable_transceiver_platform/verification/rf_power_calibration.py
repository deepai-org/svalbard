"""FPGA-owned inversion of externally characterized RF power, no chip storage.

Points are (digital amplitude, measured antenna-port dBm), for one fixed
frequency, gain, filter, board and operating-condition context. Qualification
must separately establish EVM/mask at every admitted operating point.
"""
from dataclasses import dataclass
import math
import numpy as np

def validate_calibration_generation(recorded,current):
    """FPGA-side identity gate, independent of analog accuracy qualification."""
    if (type(recorded) is not int or recorded<0 or type(current) is not int or
            current<0 or current!=recorded):
        raise ValueError('Calibration health generation missing or stale')
    return True

@dataclass(frozen=True)
class CalibrationValidity:
    """FPGA-owned qualification envelope; measurements supply its bounds.

    Context includes die/board/firmware/path/rate/filter/gain/reference identity.
    Supply and temperature inputs are uncertainty intervals, not exact sensors.
    This gate checks a supplied qualification; it does not create one.
    """
    context: tuple
    temperature_c: tuple
    supplies_v: dict
    characterized_at_s: float
    maximum_age_s: float
    condition_generation: int | None = None

    def validate(self, *, context, temperature_c, supplies_v, now_s, condition_generation=None):
        # FPGA-owned health generation, distinct from routine stream epochs.
        # A supplied generation makes fault invalidation mandatory for this
        # record; omitted generations retain the legacy standalone fixture.
        if self.condition_generation is not None:
            validate_calibration_generation(self.condition_generation,condition_generation)
        if context!=self.context or set(supplies_v)!=set(self.supplies_v):
            raise ValueError('Calibration identity or supply coverage mismatch')
        if (not all(math.isfinite(x) for x in
                    (now_s,self.characterized_at_s,self.maximum_age_s))
                or self.maximum_age_s<=0
                or not 0<=now_s-self.characterized_at_s<=self.maximum_age_s):
            raise ValueError('Calibration expired or time origin invalid')
        for measured,qualified in [(temperature_c,self.temperature_c)]+[
                (supplies_v[k],self.supplies_v[k]) for k in supplies_v]:
            if (len(measured)!=2 or len(qualified)!=2
                    or not all(math.isfinite(x) for x in (*measured,*qualified))
                    or not qualified[0]<=measured[0]<=measured[1]<=qualified[1]):
                raise ValueError('Operating uncertainty outside calibrated envelope')
        return True

def validate_calibration(validity, *, context, operating):
    """Check externally supplied qualification whenever a calibrated result is used."""
    if validity is not None:
        if operating is None:
            raise ValueError('Operating measurements required for calibration validity')
        validity.validate(context=context,**operating)


@dataclass(frozen=True)
class PowerCalibration:
    context: tuple
    points: tuple
    uncertainty_db: float
    validity: CalibrationValidity | None = None

    def amplitude(self, requested_dbm, *, context, maximum_dbm, operating=None):
        validate_calibration(self.validity,context=context,operating=operating)
        if context != self.context:
            raise ValueError('Calibration context mismatch')
        p=np.asarray(self.points,dtype=float)
        if (p.ndim!=2 or p.shape[1]!=2 or len(p)<2 or
                not np.all(np.isfinite(p)) or np.any(p[:,0]<=0) or
                np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,1])<=0)):
            raise ValueError('Monotonic finite calibration required')
        if not all(math.isfinite(x) for x in (requested_dbm,maximum_dbm,self.uncertainty_db)) or self.uncertainty_db<0:
            raise ValueError('Finite power bounds required')
        if not p[0,1]<=requested_dbm<=p[-1,1]:
            raise ValueError('Requested power outside characterized range')
        if requested_dbm+self.uncertainty_db>maximum_dbm:
            raise ValueError('Power uncertainty exceeds configured ceiling')
        # Interpolate measured dBm against log amplitude; do not extrapolate a
        # square-law assumption into uncharacterized compression or low SNR.
        return float(10**np.interp(requested_dbm,p[:,1],np.log10(p[:,0])))


def requested_uplink_power(peer_tx_dbm, measured_peer_rssi_dbm, target_peer_rssi_dbm):
    """Reciprocal-path estimate; antenna/calibration asymmetry stays in error budget."""
    values=(peer_tx_dbm,measured_peer_rssi_dbm,target_peer_rssi_dbm)
    if not all(math.isfinite(x) for x in values):
        raise ValueError('Finite link measurements required')
    return target_peer_rssi_dbm+peer_tx_dbm-measured_peer_rssi_dbm


def validate_tx_samples(samples, *, peak_limit=511/512):
    """FPGA preflight after resampling/NCO/IQ/DC corrections, before native DAC packing.

    This catches digital clipping only. Analog reconstruction overshoot and PA
    compression require separately characterized peak and spectral limits.
    """
    z=np.asarray(samples,dtype=complex)
    if z.ndim!=1 or not len(z) or not np.all(np.isfinite(z)):
        raise ValueError('Finite nonempty TX waveform required')
    if not math.isfinite(peak_limit) or not 0<peak_limit<=511/512:
        raise ValueError('Native DAC peak limit')
    peak=float(max(np.max(abs(z.real)),np.max(abs(z.imag))))
    if peak>peak_limit:
        raise ValueError(f'TX waveform exceeds DAC peak allowance: {peak:.6f} > {peak_limit:.6f}')
    return dict(component_peak=peak,mean_square=float(np.mean(abs(z)**2)),
                peak_margin=peak_limit-peak)


@dataclass(frozen=True)
class ReceivePowerCalibration:
    """External known-level reference for a fixed RX gain/filter/board context.

    Use the same measurement window/statistic during calibration and reception.
    No extrapolation beyond the externally established linear input interval.
    """
    context: tuple
    reference_dbm: float
    reference_mean_square: float
    valid_dbm: tuple
    uncertainty_db: float

    validity: CalibrationValidity | None = None

    def estimate(self, measured_mean_square, *, context, operating=None):
        validate_calibration(self.validity,context=context,operating=operating)
        if context != self.context:
            raise ValueError('RX calibration context mismatch')
        lo,hi=self.valid_dbm
        vals=(self.reference_dbm,self.reference_mean_square,measured_mean_square,
              lo,hi,self.uncertainty_db)
        if (not all(math.isfinite(v) for v in vals) or
                min(self.reference_mean_square,measured_mean_square)<=0 or
                self.uncertainty_db<0 or not lo<=self.reference_dbm<=hi):
            raise ValueError('Invalid RX calibration')
        estimate=self.reference_dbm+10*math.log10(measured_mean_square/self.reference_mean_square)
        if estimate-self.uncertainty_db<lo or estimate+self.uncertainty_db>hi:
            raise ValueError('RX power outside calibrated interval')
        return estimate


@dataclass(frozen=True)
class AntennaTimingCalibration:
    """FPGA-owned DAC-edge to antenna-marker delay interval.

    Context must identify board, filter, waveform correction and marker
    definition. A preamble-alignment marker is not first emitted RF energy.
    Bounds are supplied characterization evidence, not measured by this helper.
    """
    context: tuple
    minimum_s: float
    maximum_s: float

    validity: CalibrationValidity | None = None

    def schedule(self, desired_s, *, sample_hz, context, tolerance_s, operating=None):
        validate_calibration(self.validity,context=context,operating=operating)
        if context != self.context:
            raise ValueError('Timing calibration context mismatch')
        if (not all(math.isfinite(x) for x in
                    (desired_s,sample_hz,tolerance_s,self.minimum_s,self.maximum_s))
                or sample_hz<=0 or tolerance_s<0 or self.minimum_s<0
                or self.maximum_s<self.minimum_s):
            raise ValueError('Finite ordered timing bounds required')
        tick=round((desired_s-(self.minimum_s+self.maximum_s)/2)*sample_hz)
        if tick<0:raise ValueError('Antenna target precedes available DAC edge')
        earliest=tick/sample_hz+self.minimum_s
        latest=tick/sample_hz+self.maximum_s
        if earliest<desired_s-tolerance_s or latest>desired_s+tolerance_s:
            raise ValueError('Antenna timing uncertainty exceeds tolerance')
        return dict(counter=tick+1,launch_s=tick/sample_hz,
                    earliest_s=earliest,latest_s=latest)


@dataclass(frozen=True)
class IQCalibration:
    """Externally fitted flat complex gain/image/DC correction, stored by FPGA.

    Reference and observed samples must already share timing, frequency and
    reference plane. This cannot identify frequency-dependent imbalance, phase
    noise, compression or distinguish board LO leakage from instrument offset.
    """
    context: tuple
    direct: complex
    image: complex
    offset: complex
    relative_fit_error: float
    validity: CalibrationValidity | None = None

    def __post_init__(self):
        if (not np.all(np.isfinite([self.direct,self.image,self.offset,self.relative_fit_error]))
                or self.relative_fit_error<0
                or abs(self.direct)**2-abs(self.image)**2<=.01*(abs(self.direct)**2+abs(self.image)**2)):
            raise ValueError('Finite well-conditioned I/Q calibration required')

    @classmethod
    def fit(cls, reference, observed, *, context):
        x=np.asarray(reference,complex);y=np.asarray(observed,complex)
        if (x.ndim!=1 or x.shape!=y.shape or len(x)<4 or
                not np.all(np.isfinite(x)) or not np.all(np.isfinite(y))):
            raise ValueError('Aligned finite complex calibration vectors required')
        matrix=np.column_stack((x,x.conj(),np.ones(len(x))))
        if np.linalg.cond(matrix)>1e6:
            raise ValueError('Calibration stimulus cannot identify I/Q and offset')
        coefficients=np.linalg.lstsq(matrix,y,rcond=None)[0]
        residual=y-matrix@coefficients
        error=float(np.linalg.norm(residual)/max(np.linalg.norm(y-np.mean(y)),1e-30))
        a,b,c=coefficients
        if abs(a)**2-abs(b)**2<=.01*(abs(a)**2+abs(b)**2):
            raise ValueError('I/Q inverse is singular or excessively ill-conditioned')
        return cls(context,complex(a),complex(b),complex(c),error)

    def correct(self, desired, *, context, operating=None):
        validate_calibration(self.validity,context=context,operating=operating)
        if context!=self.context:raise ValueError('I/Q calibration context mismatch')
        z=np.asarray(desired,complex)
        if z.ndim!=1 or not np.all(np.isfinite(z)):raise ValueError('Finite correction vector required')
        z=z-self.offset
        return (self.direct.conjugate()*z-self.image*z.conj())/(abs(self.direct)**2-abs(self.image)**2)


def tx_rx_filter_coupling(*,tx_power_dbm,isolation_db,tx_reference_envelope_rms,
                          early_gain_db=20.,impedance_ohm=50.):
    """Map a calibrated TX reference to linear RX-filter voltage forcing.

    Envelope convention is P=mean(|z|^2)/(2R), matching receive_frontend.
    Isolation is total antenna-TX to chip RX-input loss; do not add it twice.
    No compression, PA memory, clamp charge or off-state loading is inferred.
    """
    values=(tx_power_dbm,isolation_db,tx_reference_envelope_rms,early_gain_db,impedance_ohm)
    if not all(math.isfinite(v) for v in values) or isolation_db<0 or min(tx_reference_envelope_rms,impedance_ohm)<=0:
        raise ValueError('Finite power/gain, nonnegative isolation and positive reference/impedance required')
    leak_dbm=tx_power_dbm-isolation_db
    rx_envelope=math.sqrt(2*impedance_ohm*1e-3*10**(leak_dbm/10))
    return dict(rx_input_dbm=leak_dbm,rx_input_envelope_rms_v=rx_envelope,
                filter_input_envelope_rms_v=rx_envelope*10**(early_gain_db/20),
                effective_voltage_ratio=rx_envelope*10**(early_gain_db/20)/tx_reference_envelope_rms)


def pa_compression(samples, *, input_p1db_envelope, smoothness=2.,phase_deg_at_p1db=0.):
    """Unity-small-signal-gain memoryless AM/AM and AM/PM hypotheses, not a PA fit.

    At input_p1db_envelope the voltage gain is exactly -1 dB. Envelope units
    match samples. Optional phase rotation scales with input envelope power and
    equals phase_deg_at_p1db at that input amplitude. No memory, noise,
    gain, impedance or watts inferred.
    """
    x=np.asarray(samples,complex)
    if (x.ndim!=1 or not np.all(np.isfinite(x)) or
        not math.isfinite(input_p1db_envelope) or input_p1db_envelope<=0 or
        not math.isfinite(smoothness) or smoothness<=0 or not math.isfinite(phase_deg_at_p1db)):
        raise ValueError('Finite vector and positive PA threshold/smoothness required')
    factor=10**(smoothness/10)-1
    phase=math.radians(phase_deg_at_p1db)*(abs(x)/input_p1db_envelope)**2
    return x*np.exp(1j*phase)/(1+factor*(abs(x)/input_p1db_envelope)**(2*smoothness))**(1/(2*smoothness))


def matched_attenuator_budget(*,loss_db,input_power_dbm,bandwidth_hz,temperature_k=300.15,impedance_ohm=50.):
    """Ideal matched passive TX pad: available power and internally added kTB.

    Source noise is excluded: attenuated source noise must be added separately.
    No RF parasitic, resistor tolerance, PA mismatch or output-power qualification.
    """
    vals=(loss_db,input_power_dbm,bandwidth_hz,temperature_k,impedance_ohm)
    if not all(math.isfinite(v) for v in vals) or loss_db<0 or min(bandwidth_hz,temperature_k,impedance_ohm)<=0:
        raise ValueError('Finite passive loss/power and positive bandwidth/temperature/impedance required')
    gain=10**(-loss_db/10)
    output_w=1e-3*10**(input_power_dbm/10)*gain
    added_noise_w=1.380649e-23*temperature_k*bandwidth_hz*(1-gain)
    ratio=10**(loss_db/20)
    return dict(power_gain=gain,output_power_dbm=input_power_dbm-loss_db,
        added_noise_w=added_noise_w,added_noise_rms_fraction=math.sqrt(added_noise_w/output_w),
        pi_series_ohm=impedance_ohm*(ratio*ratio-1)/(2*ratio),
        pi_shunt_ohm=(impedance_ohm*(ratio+1)/(ratio-1) if loss_db else None),
        qualification=False)


def rf_drive_requirement(*,mean_power_dbm,crest_db,load_ohm=50.,source_ohm=40.,pad_cap_f=0.,carrier_hz=2412e6):
    """Inverse matched-load drive requirement, not an RF gain/power prediction.

    Complex envelope convention: mean power = mean(abs(envelope)**2)/(2R).
    Source R and shunt C are differential equivalents, not per-pin values.
    Carrier-frequency phasor screen only: no package inductance, broadband
    matching, transistor output impedance or voltage-doubling credit.
    """
    if (not all(math.isfinite(v) for v in (mean_power_dbm,crest_db,load_ohm,source_ohm,pad_cap_f,carrier_hz))
        or crest_db<0 or load_ohm<=0 or source_ohm<0 or pad_cap_f<0 or carrier_hz<=0):
        raise ValueError('Finite RF power, nonnegative crest/source R and positive load required')
    power=1e-3*10**(mean_power_dbm/10)
    rms_envelope=math.sqrt(2*load_ohm*power)
    peak=rms_envelope*10**(crest_db/20)
    admittance=1/load_ohm+2j*math.pi*carrier_hz*pad_cap_f
    return dict(load_envelope_rms_v=rms_envelope,load_envelope_peak_v=peak,
        load_carrier_peak_current_a=peak/load_ohm,
        pad_cap_f=pad_cap_f,carrier_hz=carrier_hz,
        total_driver_peak_current_a=peak*abs(admittance),
        source_differential_peak_v=peak*abs(1+source_ohm*admittance),
        source_resistor_mean_dissipation_w=rms_envelope**2*abs(admittance)**2*source_ohm/2,
        qualification=False)
