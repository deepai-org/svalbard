"""External FPGA/host single-tone calibration example, not on-chip modem logic."""
import numpy as np

def estimate(samples,fs,pilot_hz=1e6,modulated=False,symbol_samples=8):
    assert symbol_samples in (2,4,8)
    samples=np.asarray(samples);t=np.arange(len(samples))/fs
    train=np.arange(64,256)
    assert len(samples)>=1536 and np.all(abs(samples[train])>1e-3)
    residual=samples[train]*np.exp(-2j*np.pi*pilot_hz*t[train])
    slope,phase=np.polyfit(t[train],np.unwrap(np.angle(residual)),1)
    offset=slope/(2*np.pi)
    gain=np.mean(samples[train]*np.exp(-1j*(2*np.pi*pilot_hz+slope)*t[train]))
    assert abs(gain)>1e-3
    # Freeze both estimates; do not refit on the held-out tail.
    test=np.arange(len(samples)-1024,len(samples))
    corrected=samples[test]*np.exp(-1j*slope*t[test])/gain
    desired=np.exp(2j*np.pi*pilot_hz*t[test])
    result=dict(estimated_offset_hz=float(offset),gain_real=float(gain.real),gain_imag=float(gain.imag),
        training_samples=192,held_out_samples=1024,
        held_out_normalized_rms_error=float(np.sqrt(np.mean(abs(corrected-desired)**2))))
    if modulated:
        selected=(test>=512)&((test-512)%symbol_samples==symbol_samples-1)
        ids=(test[selected]-512)//symbol_samples
        labels=((ids*13)^(ids>>2)^2)&3
        decisions=(corrected[selected].real<0).astype(int)+2*(corrected[selected].imag<0).astype(int)
        desired_symbols=((1-2*(labels&1))+1j*(1-2*((labels>>1)&1)))/np.sqrt(2)
        observed=corrected[selected]
        # Reserve 64 known QPSK symbols before scoring; no held-out samples
        # contribute to this complex-gain estimate. Frequency remains frozen.
        cal=np.arange(len(samples)-1536,len(samples)-1024)
        cal=cal[(cal>=512)&((cal-512)%symbol_samples==symbol_samples-1)]
        assert len(cal)==512//symbol_samples and cal[-1]<test[0]
        cal_ids=(cal-512)//symbol_samples
        cal_labels=((cal_ids*13)^(cal_ids>>2)^2)&3
        cal_desired=((1-2*(cal_labels&1))+1j*(1-2*((cal_labels>>1)&1)))/np.sqrt(2)
        cal_received=samples[cal]*np.exp(-1j*slope*t[cal])/gain
        cal_gain=np.vdot(cal_desired,cal_received)/np.vdot(cal_desired,cal_desired)
        assert abs(cal_gain)>1e-3
        calibrated=observed/cal_gain
        calibrated_decisions=(calibrated.real<0).astype(int)+2*(calibrated.imag<0).astype(int)
        result['known_symbol_calibration']=dict(
            first_sample=int(cal[0]),last_sample=int(cal[-1]),training_symbols=len(cal),
            gain_real=float(cal_gain.real),gain_imag=float(cal_gain.imag),
            held_out_normalized_rms_error=float(np.sqrt(np.mean(abs(calibrated-desired_symbols)**2))),
            symbol_errors=int(np.sum(calibrated_decisions!=labels)),
            scope='External host; reserved known symbols and supplied timing; scalar correction frozen before scoring.')
        basis=np.column_stack((cal_desired,cal_desired.conj()*np.exp(-2j*slope*t[cal])))
        coefficients,_,rank,_=np.linalg.lstsq(basis,cal_received,rcond=None)
        a,b=coefficients
        determinant=float(abs(a)**2-abs(b)**2)
        assert rank==2 and determinant>1e-3
        rotating_b=b*np.exp(-2j*slope*t[test[selected]])
        image_corrected=(a.conjugate()*observed-rotating_b*observed.conj())/determinant
        image_decisions=(image_corrected.real<0).astype(int)+2*(image_corrected.imag<0).astype(int)
        result['known_symbol_image_calibration']=dict(
            training_symbols=len(cal),basis_condition=float(np.linalg.cond(basis)),
            direct_real=float(a.real),direct_imag=float(a.imag),
            image_real=float(b.real),image_imag=float(b.imag),determinant=determinant,
            held_out_normalized_rms_error=float(np.sqrt(np.mean(abs(image_corrected-desired_symbols)**2))),
            symbol_errors=int(np.sum(image_decisions!=labels)),
            scope='External host; rotating-image fit on reserved symbols; frequency and coefficients frozen before scoring.')
        error=abs(observed-desired_symbols)
        # Diagnostic projection only: uses known test symbols, never decisions or
        # the operational correction. Orthogonal residual separates scalar bias
        # from distortion that a single complex gain cannot remove.
        scalar=np.vdot(desired_symbols,observed)/np.vdot(desired_symbols,desired_symbols)
        residual_error=float(np.mean(abs(observed-scalar*desired_symbols)**2))
        scalar_error=float(abs(scalar-1)**2)
        assert abs(float(np.mean(error**2))-scalar_error-residual_error)<1e-12
        result.pop('held_out_normalized_rms_error')
        result.update(held_out_qpsk_symbols=int(selected.sum()),
                      held_out_qpsk_normalized_rms_error=float(np.sqrt(np.mean(error**2))),
                      held_out_qpsk_normalized_peak_error=float(np.max(error)),
                      diagnostic_known_symbol_projection=dict(
                          scalar_real=float(scalar.real),scalar_imag=float(scalar.imag),
                          scalar_bias_rms=float(np.sqrt(scalar_error)),
                          nonscalar_residual_rms=float(np.sqrt(residual_error)),
                          scope='Uses held-out truth; attribution only, not deployable calibration or corrected performance.'),
                      symbol_errors=int(np.sum(labels!=decisions)),
                      symbol_sampling=f'Last of {symbol_samples} samples; symbol timing supplied by test setup.')
    return result

def controls():
    fs=20e6;t=np.arange(2560)/fs
    for offset in (-100e3,100e3):
        s=(.3+.2j)*np.exp(2j*np.pi*(1e6+offset)*t)
        r=estimate(s,fs)
        assert abs(r['estimated_offset_hz']-offset)<1e-6
        assert r['held_out_normalized_rms_error']<1e-10
    # A later frequency change must not be hidden by fitting the test interval.
    s=.4*np.exp(2j*np.pi*1.1e6*t)
    s[1536:]*=np.exp(2j*np.pi*20e3*(t[1536:]-t[1536]))
    assert estimate(s,fs)['held_out_normalized_rms_error']>.5


def modulation_controls():
    fs=20e6;t=np.arange(2560)/fs
    s=.4*np.exp(2j*np.pi*1e6*t)
    for i in range(512,len(s)):
        label=((((i-512)//8)*13)^(((i-512)//8)>>2)^2)&3
        s[i]=.4*complex(1-2*(label&1),1-2*((label>>1)&1))/np.sqrt(2)
    clean=estimate(s,fs,modulated=True)
    assert clean['symbol_errors']==0
    assert clean['held_out_qpsk_normalized_rms_error']<1e-10
    s[-1]*=-1
    flipped=estimate(s,fs,modulated=True)
    assert flipped['symbol_errors']==1
    assert abs(flipped['held_out_qpsk_normalized_peak_error']-2)<1e-10
    assert abs(flipped['held_out_qpsk_normalized_rms_error']-2/np.sqrt(128))<1e-10

    # A uniform complex gain is scalar bias, while one inverted symbol also
    # leaves a nonzero orthogonal residual. Neither is hidden in reported error.
    s[-1]*=-1
    s[-1024:] *= .8*np.exp(.2j)
    biased=estimate(s,fs,modulated=True)
    projection=biased['diagnostic_known_symbol_projection']
    assert projection['nonscalar_residual_rms']<1e-10
    assert abs(projection['scalar_bias_rms']-abs(.8*np.exp(.2j)-1))<1e-10
    assert flipped['diagnostic_known_symbol_projection']['nonscalar_residual_rms']>.1

    # Changing only scored samples cannot change the trained correction.
    assert clean['known_symbol_calibration']['held_out_normalized_rms_error']<1e-10
    for field in ('gain_real','gain_imag'):
        assert clean['known_symbol_calibration'][field]==biased['known_symbol_calibration'][field]
    assert biased['known_symbol_calibration']['held_out_normalized_rms_error']>.2
    # A persistent scalar change present in training and scoring is correctable.
    s[-1024:] /= .8*np.exp(.2j)
    s[1024:] *= .8*np.exp(.2j)
    assert estimate(s,fs,modulated=True)['known_symbol_calibration']['held_out_normalized_rms_error']<1e-10

    # Held-out changes must also leave the image estimator untouched.
    for field in ('direct_real','direct_imag','image_real','image_imag'):
        assert clean['known_symbol_image_calibration'][field]==biased['known_symbol_image_calibration'][field]
    assert clean['known_symbol_image_calibration']['held_out_normalized_rms_error']<1e-10
    assert biased['known_symbol_image_calibration']['held_out_normalized_rms_error']>.2
    # Known zero-offset image injected after the tone: training must estimate
    # it without receiving the injected coefficients as arguments.
    s[1024:] /= .8*np.exp(.2j)
    s[512:] = (1+.1j)*s[512:] + (.12-.04j)*s[512:].conj()
    fitted=estimate(s,fs,modulated=True)
    assert fitted['known_symbol_image_calibration']['held_out_normalized_rms_error']<1e-10
    assert fitted['known_symbol_calibration']['held_out_normalized_rms_error']>.1
