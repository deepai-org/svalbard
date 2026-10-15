"""Conditional clock architecture budgets; no silicon or protocol qualification."""
import hashlib,json,math,sys
from pathlib import Path
from statistics import NormalDist
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/architecture_fast'))
from design_definition import load_design

def clock_envelope(design=None):
    design=load_design() if design is None else design
    rf=[]
    for db in [-20,-25,-30,-35]:
        phase=10**(db/20)/2 # quarter of total EVM power
        total=phase/(2*math.pi*2.4e9)
        # Four equal variance allocations: source, conditioning, phase generation,
        # distribution. In autonomous mode conditioning includes loop additive noise.
        stage=total/2
        for mode in ['autonomous','external_lo']:
            rf.append(dict(mode=mode,total_evm_db=db,residual_phase_rms_rad=phase,
                total_time_rms_ps=total*1e12,equal_stage_time_rms_ps=stage*1e12,
                coherent_equal_stage_peak_ps=total*math.sqrt(2)/4*1e12,
                maximum_external_source_ps=total*1e12 if mode=='external_lo' else None,
                maximum_source_ps_with_other_three_at_0_5ps=math.sqrt(total**2-3*(.5e-12)**2)*1e12 if total**2>=3*(.5e-12)**2 else None))
    adc=[]
    for bits in [6,8,9]:
        snr=6.02*bits+1.76
        for f in [1e6,10e6,20e6]:
            jitter=.5*10**(-snr/20)/(2*math.pi*f)
            adc.append(dict(target_equivalent_bits=bits,input_hz=f,noise_budget_snr_db=snr,
                quarter_noise_power_aperture_jitter_ps=jitter*1e12))
    # Engineering eye budget: allowed timing closure 0.30UI total, 0.10UI bounded
    # deterministic jitter, remaining assigned to Gaussian relative timing error.
    q=NormalDist().inv_cdf(1-1e-12/2)
    wired=[]
    for rate in [1.25e9,1.5e9,1.62e9,2.5e9]:
        ui=1/rate
        wired.append(dict(rate_bps=rate,ui_ps=ui*1e12,allowed_total_timing_closure_ui=.30,
            assigned_deterministic_pp_ui=.10,two_sided_tail_probability=1e-12,
            maximum_relative_random_rms_ps=.20*ui/(2*q)*1e12))
    pushing=[]
    for gain in [10e6,65e6]:
        for offset in [1e6,10e6,100e6]:
            phase=10**(-30/20)/2
            pushing.append(dict(supply_pushing_hz_per_v=gain,ripple_hz=offset,
                max_peak_ripple_v_if_entire_phase_budget=phase*math.sqrt(2)*offset/gain,
                scope='Uncorrected sinusoidal FM; constant pushing extrapolation, no PLL/tracking rejection.'))
    external=[]
    for cap in [.79e-12,1.07e-12,3e-12]:
        f=2.4e9; a=.5; r=50
        attenuation=1/math.sqrt(1+(2*math.pi*f*r*cap)**2)
        slew=2*math.pi*f*a*attenuation
        external.append(dict(source_peak_v=a,source_ohm=r,pad_load_pf=cap*1e12,
            receiver_peak_v=a*attenuation,threshold_slew_v_per_ns=slew*1e-9,
            maximum_receiver_rms_noise_mv_for_0_5ps=slew*.5e-12*1e3,
            scope='One-pole capacitive load and sine zero crossing; no package resonance, threshold offset, protection nonlinearity or input bandwidth guarantee.'))
    contract=design.contract
    # Shared protected input branch: extend the old RC-only requirement to a
    # series bond plus shunt pad/receiver capacitance. All L/C values are hypotheses.
    external_loaded=[]
    for f in (2.4e9,2.484e9,4.8e9):
     for cap in (.8e-12,1.1e-12,3e-12,5e-12):
      for bond_l in (.5e-9,2e-9,5e-9):
       for termination in (None,50.):
        omega=2*math.pi*f;source=.5;rs=50.;bond_r=.2
        admittance=1j*omega*cap+(0. if termination is None else 1/termination)
        series=rs+bond_r+1j*omega*bond_l
        transfer=1/(1+series*admittance)
        node=source*transfer;current=node*admittance
        # KVL and AC power conservation independently check the voltage divider.
        assert abs(source-node-current*series)<1e-12
        delivered=(source*current.conjugate()).real/2
        losses=abs(current)**2*(rs+bond_r)/2+(0. if termination is None else abs(node)**2/(2*termination))
        assert abs(delivered-losses)<1e-12
        peak=abs(node);threshold=.020;low=.9*peak;high=1.1*peak
        slew=omega*math.sqrt(max(0.,peak**2-threshold**2))
        am_to_time=(math.asin(threshold/low)-math.asin(threshold/high))/omega if low>threshold else None
        left=0.;right=low*(1-1e-12)
        for _ in range(50):
            middle=(left+right)/2
            if (math.asin(middle/low)-math.asin(middle/high))/omega<=.5e-12:left=middle
            else:right=middle
        # Independent zero-L, high-Z limit recovers the historical one-pole screen.
        rc=1/(1+(rs+bond_r)*1j*omega*cap)
        assert math.isclose(abs(rc),1/math.sqrt(1+((rs+bond_r)*omega*cap)**2),rel_tol=1e-12)
        shifted=1/(1+series*(1j*omega*cap*1.01+(0. if termination is None else 1/termination)))
        external_loaded.append(dict(frequency_hz=f,pad_receiver_cap_pf=cap*1e12,bond_l_nh=bond_l*1e9,
            termination_ohm=termination,receiver_peak_v=peak,
            threshold_slew_v_per_ns=slew*1e-9,
            receiver_noise_mv_for_0_5ps=slew*.5e-12*1e3,
            jitter_ps_with_1mv_receiver_noise=1e9/slew if slew else None,
            amplitude_modulation_10percent_threshold_offset_20mv_pp_ps=None if am_to_time is None else am_to_time*1e12,
            maximum_threshold_offset_mv_for_0_5ps_pp_at_10percent_am=left*1e3,
            phase_delay_change_for_1percent_cap_change_ps=abs(np.angle(shifted/transfer))/omega*1e12,
            within_assigned_0_6v_peak=peak<=.6))
    external_loading=dict(cases=external_loaded,qualified=False,
     assumptions=['0.5 V peak open-circuit Thevenin source, 50 ohm source resistance, 0.2 ohm bond resistance; matched available source power about -2.04 dBm.',
     'Series bond L includes an assigned effective return loop; C combines pad/protection/receiver and disconnected-branch loading. No extracted package or nonlinear ESD model.',
     '50 ohm or high-impedance die termination; no external matching network has been granted ideal compensation.',
     '20 mV threshold offset, 1 mV integrated receiver noise, 0.5 ps additive jitter and 0.6 V peak are diagnostic assignments, not GF180 limits.',
     '10 percent source AM converts to timing only with nonzero threshold offset; report is peak-to-peak, not independent random RMS jitter.',
     'A fixed capacitance error gives static phase/delay, not jitter. The 1 percent differential only bounds sensitivity if capacitance changes with signal, supply or temperature.',
     '4.8 GHz illustrates divide-by-two quadrature input burden, not a selected new carrier target. Intrinsic receiver speed, bias, I/Q generation, noise spectra and physical power remain open.'])
    pll_domain=next(d for d in contract['power']['domains'] if d['id']=='PLL')
    clock_ceiling_ma=len(pll_domain['supply_pins'])*pll_domain['per_connection_budget_ma']
    assert clock_ceiling_ma==48, 'Update clock envelope when domain allocation changes'
    power=[]
    for f in [2.4e9,4.8e9]:
        for bias in [12,24,36]:
            # Sum of switched capacitances, alpha=1 per full clock cycle; no overlap
            # with static-current allocation. Total domain ceiling 48mA at3.3V.
            c=(clock_ceiling_ma-bias)*1e-3/(3.3*f)
            power.append(dict(clock_hz=f,static_current_ma=bias,domain_ceiling_ma=clock_ceiling_ma,
                supply_v=3.3,domain_ceiling_mw=3.3*clock_ceiling_ma,
                maximum_sum_alpha_c_pf=c*1e12,
                scope='Remaining CV^2f budget only, not a gate-count or speed feasibility claim.'))
    # First-order closed-loop sensitivity model; bandwidth is an assigned pole,
    # not a claim about the eventual PLL's order, peaking or stability margins.
    # S_phi=2*10^(L/10) is one-sided phase PSD for SSB phase noise L.
    spectral=[]
    for points in [8193,16385]:
     f=np.geomspace(1e3,20e6,points)
     integrate=np.trapezoid
     rows=[]
     for tracking in [0.,1e4,1e5]:
      residual=np.ones_like(f) if tracking==0 else f*f/(f*f+tracking**2)
      for mode in ['autonomous','external_lo']:
       for pole in ([1e4,1e5,1e6] if mode=='autonomous' else [None]):
        source=np.ones_like(f) if pole is None else f*f/(f*f+pole**2)
        reference=np.zeros_like(f) if pole is None else pole**2/(f*f+pole**2)
        # Separate integrals retain the tradeoff: widening loop rejects more VCO
        # noise but admits more output-referred reference noise.
        colored=float(integrate(residual*source/f**2,f))
        white=float(integrate(residual*source,f))
        ref=float(integrate(residual*reference,f))
        additive=float(integrate(residual,f))
        if tracking==0 and pole is not None:
         exact=(math.atan(f[-1]/pole)-math.atan(f[0]/pole))/pole
         assert abs(colored/exact-1)<2e-6
        # Three independent additive blocks, each 0.3ps integrated BEFORE tracking
        # over this exact band, assigned white timing noise. Same burden both modes.
        omega=2*math.pi*2.4e9
        added=3*(omega*.3e-12)**2*additive/(f[-1]-f[0])
        # Reference floor is output-referred after multiplication; an assumption.
        reference_floor=2*10**(-130/10)
        reserved=added+reference_floor*ref
        budget=(10**(-30/20)/2)**2
        remaining=budget-reserved
        rows.append(dict(mode=mode,pll_pole_hz=pole,tracking_pole_hz=tracking,
           offset_band_hz=[float(f[0]),float(f[-1])],reference_output_referred_floor_dbc_hz=-130 if pole else None,
           additive_block_untracked_rms_ps=.3,additive_block_count=3,
           reserved_phase_variance=reserved,remaining_source_phase_variance=remaining,
           source_colored_integral=colored,source_white_integral_hz=white,
           maximum_source_L_at_100khz_for_pure_inverse_square_dbc_hz=10*math.log10(remaining/colored/1e10/2) if remaining>0 else None,
           maximum_source_flat_floor_dbc_hz=10*math.log10(remaining/white/2) if remaining>0 else None,
           reference_equivalent_time_rms_ps=math.sqrt(reference_floor*ref)/omega*1e12,
           additive_residual_time_rms_ps=math.sqrt(added)/omega*1e12))
     if points==8193:coarse=rows
     else:spectral=rows
    max_quadrature_change=max(abs(a['source_colored_integral']/b['source_colored_integral']-1) for a,b in zip(coarse,spectral))
    assert max_quadrature_change<2e-6
    # Combine budgets rather than spending the same allowance independently.
    # IQ image error is |b/a| for y=a*x+b*conj(x), proper complex input, after
    # common complex-gain removal. No IQ calibration assumed.
    iq=[]
    for gain_db,phase_deg in [(0.,.5),(.1,.5),(.5,2.)]:
     g=10**(gain_db/20);phase=math.radians(phase_deg)
     image=(1+g*g-2*g*math.cos(phase))/(1+g*g+2*g*math.cos(phase))
     # Independent complex mixing-coefficient expression.
     z=g*complex(math.cos(phase),math.sin(phase))
     assert math.isclose(image,abs((1-z)/(1+z))**2,rel_tol=1e-10)
     iq.append(dict(gain_imbalance_db=gain_db,phase_error_deg=phase_deg,
       image_evm_squared=image,image_rejection_db=-10*math.log10(image)))
    combined=[]
    for row in spectral:
     for source_db in [-110.,-100.,-90.]:
      # Hypothetical source spectrum, no device attribution: colored plus floor.
      colored=2*10**(source_db/10)*1e10
      floor=2*10**(-145/10)
      random=row['reserved_phase_variance']+colored*row['source_colored_integral']+floor*row['source_white_integral_hz']
      for imbalance in iq:
       for spur_peak in [0.,.01]:
        spur_hz=1e5;tracking=row['tracking_pole_hz']
        transfer=1 if tracking==0 else spur_hz**2/(spur_hz**2+tracking**2)
        # Spur is specified at the LO output, after any PLL, before tracking.
        spur_variance=spur_peak**2/2*transfer
        limit=(10**(-30/20)/2)**2
        used=random+imbalance['image_evm_squared']+spur_variance
        combined.append(dict(mode=row['mode'],pll_pole_hz=row['pll_pole_hz'],tracking_pole_hz=tracking,
          synthetic_source_colored_L100khz_dbc_hz=source_db,synthetic_source_floor_dbc_hz=-145,
          iq_gain_db=imbalance['gain_imbalance_db'],iq_phase_deg=imbalance['phase_error_deg'],
          output_phase_spur_peak_rad=spur_peak,spur_hz=spur_hz,
          random_phase_variance=random,image_error_power=imbalance['image_evm_squared'],spur_phase_variance=spur_variance,
          combined_clock_error_rms=math.sqrt(used),clock_error_allowance_rms=math.sqrt(limit),
          within_joint_clock_allocation=bool(used<=limit),
          dominant_contributor=max({'random':random,'iq_image':imbalance['image_evm_squared'],'spur':spur_variance},key=lambda k:{'random':random,'iq_image':imbalance['image_evm_squared'],'spur':spur_variance}[k])))
    assert any(r['within_joint_clock_allocation'] for r in combined)
    assert any(not r['within_joint_clock_allocation'] for r in combined)
    # Loaded input and source share one RF clock allowance. Replace the old
    # conditioning placeholder with input-noise/slew and exact AM crossing error;
    # retain only phase-generation and distribution as two 0.3 ps placeholders.
    loaded_joint=[]
    base_spectrum=next(x for x in spectral if x['mode']=='external_lo' and x['tracking_pole_hz']==0.)
    for index,port in enumerate(external_loaded):
     input_hz=port['frequency_hz'];division=2 if input_hz==4.8e9 else 1
     carrier=input_hz/division;omega=2*math.pi*carrier
     peak=port['receiver_peak_v'];threshold=.020
     amplitude_ok=1.1*peak<=.6
     crossings_ok=.9*peak>threshold
     common=dict(input_case_index=index,input_hz=input_hz,rf_carrier_hz=carrier,
         input_to_lo_division=division,amplitude_with_10percent_am_within_assigned_limit=amplitude_ok,
         crossings_preserved=crossings_ok)
     if not crossings_ok:
      loaded_joint.append(dict(**common,source_budget_exists=False,reason='missing_crossings',maximum_source_colored_L100khz_dbc_hz=None))
      continue
     phase_grid=np.arange(512)*2*math.pi/512
     crossing=np.arcsin(threshold/(peak*(1+.1*np.sin(phase_grid))))/(2*math.pi*input_hz)
     crossing-=crossing.mean()
     # AM is 1 MHz; retain harmonics in the same 1 kHz–20 MHz budget band.
     coeff=np.fft.rfft(crossing)/len(crossing)
     am_time_variance=2*float(np.sum(abs(coeff[1:21])**2))
     assert am_time_variance<=float(np.mean(crossing**2))*(1+1e-12)
     # Average additive-noise timing variance over the AM cycle; nominal slew
     # alone slightly understates noise when input amplitude varies.
     input_time_variance=float(np.mean(1e-6/((2*math.pi*input_hz)**2*((peak*(1+.1*np.sin(phase_grid)))**2-threshold**2))))
     other_time_variance=2*(.3e-12)**2
     image=iq[1]['image_evm_squared'] # 0.1 dB, 0.5 degree assigned imbalance
     source_floor_variance=2*10**(-145/10)*base_spectrum['source_white_integral_hz']/division**2
     limit=(10**(-30/20)/2)**2
     reserved=omega**2*(am_time_variance+input_time_variance+other_time_variance)+image+source_floor_variance
     remaining=limit-reserved
     maximum_source=(10*math.log10(remaining*division**2/(2*1e10*base_spectrum['source_colored_integral'])) if remaining>0 else None)
     if maximum_source is not None:
      restored=2*10**(maximum_source/10)*1e10*base_spectrum['source_colored_integral']/division**2
      assert math.isclose(restored+reserved,limit,rel_tol=1e-12)
     # Evaluate the -115 dBc/Hz source hypothesis used by the joined model,
     # now at the external input plane rather than after ideal conditioning.
     tested_source_l100=-115.
     tested_source_power=2*10**(tested_source_l100/10)*1e10*base_spectrum['source_colored_integral']/division**2
     loaded_joint.append(dict(**common,evaluated_external_source_L100khz_dbc_hz=tested_source_l100,
         evaluated_source_colored_error_power=tested_source_power,
         evaluated_total_clock_error_power=reserved+tested_source_power,
         evaluated_source_and_input_fit=amplitude_ok and reserved+tested_source_power<=limit,
         source_budget_exists=remaining>0,
         input_receiver_random_time_rms_ps=math.sqrt(input_time_variance)*1e12,
         input_am_time_rms_ps=math.sqrt(am_time_variance)*1e12,
         downstream_other_time_rms_ps=math.sqrt(other_time_variance)*1e12,
         reserved_clock_error_power=reserved,clock_error_power_limit=limit,
         remaining_source_colored_phase_variance=remaining,
         maximum_source_colored_L100khz_dbc_hz=maximum_source,
         conditional_input_and_clock_budget_fit=amplitude_ok and remaining>0))
    loaded_joint_budget=dict(cases=loaded_joint,qualified=False,
     assumptions=['Same quarter of -30 dB EVM power as preceding clock budget; not a protocol acceptance mask.',
     '1 kHz–20 MHz offset band, no carrier tracking; source colored spectrum follows inverse-square offset, plus fixed -145 dBc/Hz floor.',
     'Input receiver noise is assigned 1 mV RMS in this band; AM is +/-10 percent at 1 MHz with 20 mV threshold offset.',
     'Input stage replaces one additive placeholder; quadrature generation and distribution each retain assigned 0.3 ps RMS, plus 0.1 dB/0.5 degree I/Q mismatch.',
     'Independent random contributors add in variance. Correlation with AM, host supply and source noise is not modeled; common disturbances must not be blindly RSS combined.',
     'Ideal divide-by-two reduces source phase noise by four in variance but preserves absolute crossing time error. Divider additive noise is not free.',
     'Positive source budget is a requirement, not demonstrated source/receiver/phase-generation capability. RF reciprocal mixing and packet acquisition remain separate.'])
    # Published external-source precedent, not a measured GF180 source model.
    external_precedent=dict(device='ADF4351',source_url='https://www.analog.com/media/en/technical-documentation/data-sheets/adf4351.pdf',
     datasheet_revision='A',table_pages=[3,4],output_range_hz=[34.375e6,4.4e9],
     typical_jitter_ps=.27,jitter_test_output_hz=2111.28e6,jitter_test_reference_hz=122.88e6,
     jitter_test_pfd_hz=30.72e6,jitter_test_loop_bandwidth_hz=60e3,
     jitter_integration_band_hz=None,used_as_same_band_source_model=False,
     programmable_matched_output_dbm=[-4,5],
     assumed_receiver_source_thevenin_peak_v=.5,
     corresponding_available_power_dbm=10*math.log10((.5/2)**2/(2*50)/1e-3),
     supports_direct_2_4ghz=True,supports_4_8ghz_divide_by_two_source=False,
     inference='External sub-picosecond timing is supported as a published operating-point precedent. It is not a same-band2.4GHz guarantee or a GF180 receiver qualification. Output ceiling rules this part out as a4.8GHz source.',
     limitations=['Jitter test frequency differs from target and its integration band is not recovered here; do not insert0.27ps into the1kHz–20MHz spectral comparison.',
     'Available-power calculation assumes50ohm Thevenin source and matching; real output network, termination,bias and protection must be modeled.',
     'An external module needs reference,loop filter,power and control; board power is not zero.'])
    # REF_IN cannot simultaneously carry a40MHz reference and GHz direct LO.
    # Candidate integer division preserves uniform sampling while making its rate
    # depend on LO frequency. It is not yet wired into the selected clock owner.
    converter_clock=[]
    for lo_hz in [2.4e9,2.437e9,2.484e9]:
     ratio=lo_hz/40e6
     rate=lo_hz/64
     assert 20e6<rate<=40e6
     converter_clock.append(dict(external_lo_hz=lo_hz,exact_40msps_integer_divider_available=ratio.is_integer(),
       hypothetical_uniform_divisor=64,resulting_sample_hz=rate,
       status='numeric_waveform_candidate_live_clock_owner_unimplemented',
       numeric_report='evidence/robustness-envelope.json',
       requires_fpga_resampling_for_fixed_40msps=True))
    # Independent algebraic round trips, including a negative budget case.
    for row in rf:
     assert math.isclose(row['total_time_rms_ps'],2*row['equal_stage_time_rms_ps'])
     assert math.isclose(row['coherent_equal_stage_peak_ps']*4/math.sqrt(2),row['total_time_rms_ps'])
    for row in adc:
     j=row['quarter_noise_power_aperture_jitter_ps']*1e-12
     assert math.isclose((2*math.pi*row['input_hz']*j)**2,.25*10**(-row['noise_budget_snr_db']/10))
    assert rf[-1]['maximum_source_ps_with_other_three_at_0_5ps'] is None
    report=dict(design_provenance=design.provenance(),model_role='explicit_analytical_requirement_scenarios',status='conditional_feasibility_envelope_not_physical_qualification',rf=rf,external_loaded_input=external_loading,external_loaded_joint_budget=loaded_joint_budget,
     converter_clock_candidates=converter_clock,external_source_precedent=external_precedent,iq_image_scenarios=iq,joint_clock_scenarios=combined,spectral_source_boundaries=spectral,spectral_quadrature_relative_change=max_quadrature_change,adc=adc,wired=wired,supply_pushing=pushing,external_receiver=external,power=power,
     assumptions=['RF residual phase uses one common integration band after explicitly selected tracking; no phase-noise spectrum or tracking transfer is inferred.',
     'Joint scenarios allocate the SAME quarter EVM power to random phase, IQ image and output spur together. Synthetic source spectra are not GF180 predictions. Proper-complex waveform and small independent phase errors assumed; no correlated image/spur cross terms or reciprocal mixing.',
     'Independent errors combine in variance; coherent sinusoidal disturbances add peak amplitudes. Do not RSS common supply errors.',
     'Wired Gaussian extrapolation is an engineering allocation, not a standards jitter mask or proof of BER; ISI, setup/hold and CDR transfer must be budgeted separately.',
     'ADC timing uses analog input frequency, not RF carrier. Equivalent-bit SNR here is a design allocation, not measured ENOB.',
     '48mA is the existing PLL/reference domain ceiling; charge all local clock circuitry exactly once, including any on other domains. External module power is off chip but must be reported at system level.',
     'No finite GF180 physical phase-noise uncertainty range is established; these calculations find requirements, not achievable distributions.'],
     source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),P/'system_model/architecture_fast/design_definition.py']})
    return report

if __name__=='__main__':
    print(json.dumps(clock_envelope(),indent=2))
