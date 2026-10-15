"""RF allocation arithmetic, not measured performance or packet qualification.

Noise contributions may be RSS-combined only with an explicit independence
assumption. Deterministic residuals use a triangle bound, including their
combination with noise, so cancellation is never credited as design margin.
"""
import math


def evaluate_budget(allocation, *, independent_noise=True, noise_correlation=None):
    noise = allocation['uncorrelated_rms_fraction']
    residual = allocation['bounded_residual_fraction']
    values = [*noise.values(), *residual.values()]
    if not values or not all(math.isfinite(x) and x >= 0 for x in values):
        raise ValueError('Finite nonnegative error fractions required')
    # A common nonnegative pair correlation gives an explicit intermediate
    # stress bound between independent RSS and fully coherent addition. It is
    # not an inferred covariance matrix of physical noise sources.
    rho=(0. if independent_noise else 1.) if noise_correlation is None else noise_correlation
    if not math.isfinite(rho) or not 0<=rho<=1:
        raise ValueError('Noise correlation must be in [0,1]')
    if not independent_noise and noise_correlation is not None and rho!=1:
        raise ValueError('Conflicting correlation assumptions')
    variance=sum(x*x for x in noise.values())
    cross=sum(noise.values())**2-variance
    noise_total=math.sqrt(variance+rho*cross)
    total = noise_total + sum(residual.values())
    target = 10**(allocation['design_target_db']/20)
    limit = 10**(allocation['tx_limit_db']/20)
    residual_total=sum(residual.values())
    correlation_limit=(None if math.sqrt(variance)+residual_total>target else
                       min(1.,((target-residual_total)**2-variance)/cross) if cross>0 else 1.)
    return dict(evm_fraction=total, evm_db=20*math.log10(total) if total else -math.inf,
                target_margin_fraction=target-total, tx_limit_margin_fraction=limit-total,
                meets_allocation=total<=target, meets_tx_limit=total<=limit,
                independent_noise=rho==0,noise_correlation=rho,
                maximum_correlation_for_target=correlation_limit,
                qualification='allocation only; RX packet errors and TX spectrum remain separate')


def current_allocation(architecture,mode,*,branch=None,additional_ma=None):
    """Configuration-specific allocation; no activity or unmodeled shutdown credit."""
    policy=architecture['resource_policy']
    if mode not in architecture['operating_modes']:raise ValueError('Operating mode')
    currents={name:block['resource_allocation']['current_budget_ma'][mode]
              for name,block in architecture['blocks'].items()}
    if branch is not None:
        if branch not in policy['branch_current_modes'] or mode not in policy['branch_current_modes'][branch]:
            raise ValueError('Current branch incompatible with mode')
        for name,current in policy['branch_current_overrides_ma'][branch].items():
            if name not in currents:raise ValueError('Unknown override block')
            currents[name]=current
    for name,extra in (additional_ma or {}).items():
        if name not in currents or not math.isfinite(extra) or extra<0:
            raise ValueError('Candidate additions must be explicit nonnegative block current')
        currents[name]+=extra
    if not all(math.isfinite(x) and x>=0 for x in currents.values()):raise ValueError('Current allocation')
    rail_currents={}
    for name,current in currents.items():
        rail=architecture['blocks'][name]['supply']
        rail_currents.setdefault(rail,[]).append(current)
    rails={rail:math.fsum(values) for rail,values in rail_currents.items()}
    total=math.fsum(currents.values());ceiling=policy['current_ceiling_ma'][mode]
    return dict(mode=mode,branch=branch,by_block_ma=currents,by_rail_ma=rails,
                total_ma=total,ceiling_ma=ceiling,margin_ma=ceiling-total,
                meets_allocation=total<=ceiling,physical_qualification=False)


def converter_noise_fraction(enob, backoff_db):
    """Sine-referenced estimate; not an OFDM clipping or measured ENOB model."""
    if not all(math.isfinite(v) for v in (enob,backoff_db)) or enob<=0 or backoff_db<0:
        raise ValueError('Converter allocation')
    return 10**(-(6.02*enob+1.76-backoff_db)/20)


def support_budget_audit(architecture, *, capacitor_density_ff_um2=.9,
                        supply_v=3.3, carrier_hz=2.5e9):
    """Expose hidden support limits using assigned budgets, not device estimates.

    I/(V*f) is an optimistic aggregate switched-capacitance ceiling with zero
    static current, not a predicted load or valid model of CML bias consumption.
    Plate area excludes routing, guards and active reference circuitry.
    """
    if not all(math.isfinite(x) and x>0 for x in
               (capacitor_density_ff_um2,supply_v,carrier_hz)):
        raise ValueError('Positive audit assumptions required')
    b=architecture['blocks'];p=architecture['resource_policy']
    plate=lambda pf:pf*1000/capacitor_density_ff_um2
    adc=b['adc_i']['parameters']
    cycle=sum(adc[k] for k in ('acquisition_s','decision_s','reset_s'))
    owners=('refpad','refinput','quadrature','clocktree','bias','refbuf',
            'monitor','aosc','wirepad','txpad','rxselect','rxlevel','hostio','digital')
    return dict(physical_qualification=False,
        assumptions=dict(capacitor_density_ff_um2=capacitor_density_ff_um2,
                         supply_v=supply_v,carrier_hz=carrier_hz),
        support_owners={n:b[n]['resource_allocation'] for n in owners},
        reference_plate_um2=plate(p['converter_reference_reservoir_pf']),
        reference_nonplate_area_ceiling_um2=b['refbuf']['resource_allocation']['area_ceiling_um2']-plate(p['converter_reference_reservoir_pf']),
        supply_plate_um2=plate(sum(p['decoupling_pf'].values())),
        supply_nonplate_area_ceiling_um2=b['power']['resource_allocation']['area_ceiling_um2']-plate(sum(p['decoupling_pf'].values())),
        memory_allocated_bits=sum(p['memory_bits'].values()),
        memory_unassigned_bits=p['memory_total_cap_bits']-sum(p['memory_bits'].values()),
        adc_phase_sum_s=cycle,adc_at_max_rate_margin_s=1/adc['sample_rate_max_hz']-cycle,
        adc_direct_div64_margin_s=64/carrier_hz-cycle,
        zero_static_clock_cap_ceiling_f={n:b[n]['resource_allocation']['current_budget_ma']['rf_tx']*1e-3/(supply_v*carrier_hz)
            for n in ('refinput','quadrature','clocktree')},
        missing='Per-support transistor sizing, extracted loading, leakage, routing and reset/trim/test overhead decomposition. Block ceilings are not bottom-up implementation evidence.')


def air_response_budget(*, sample_hz, rx_delay_s, fpga_decision_s,
                        tx_delay_s, board_settle_s, uncertainty_s,
                        response_gap_s, d2h_words_hz=156.25e6,
                        h2d_words_hz=312.5e6, prefill_pairs=16):
    """Causal response bound; transport wait/stage/emit and prefill are charged.

    Response gap is supplied by the external protocol implementation. A small
    readiness bound does not prove accurate launch; uncertainty is also returned.
    FPGA compute includes the last decoder/FCS decision, not just MAC lookup.
    """
    vals=(sample_hz,rx_delay_s,fpga_decision_s,tx_delay_s,board_settle_s,
          uncertainty_s,response_gap_s,d2h_words_hz,h2d_words_hz)
    if not all(math.isfinite(v) and v>=0 for v in vals) or min(sample_hz,d2h_words_hz,h2d_words_hz)<=0:
        raise ValueError('Response allocation')
    if type(prefill_pairs) is not int or prefill_pairs<1:
        raise ValueError('Positive integral prefill required')
    parts=dict(rx=rx_delay_s,rx_frame_path=192/d2h_words_hz,
               fpga=fpga_decision_s,tx_frame_path=384/h2d_words_hz,
               cdc=6/(h2d_words_hz/2),prefill=prefill_pairs/sample_hz,
               tx=tx_delay_s,board=board_settle_s,uncertainty=uncertainty_s)
    total=sum(parts.values())
    # Raw throughput ceiling prices the same 59/64 packing efficiency used on chip.
    iq_bits=24*sample_hz
    capacity=min(d2h_words_hz,h2d_words_hz)*10*59/64
    return dict(parts_s=parts,total_s=total,margin_s=response_gap_s-total,
                admitted=total<=response_gap_s and iq_bits<capacity,
                iq_bits_s=iq_bits,host_capacity_bits_s=capacity,
                launch_uncertainty_s=uncertainty_s)


def frontend_recovery_budget(*,initial_residual_dbm,steady_residual_dbm,
                             allowed_residual_dbm,recovery_tau_s,switch_settle_s,
                             available_s):
    """Input-referred exponential residue plus coherent steady leakage bound.

    Initial residue is a characterization input, not necessarily equal to TX
    leakage: saturation/charge storage may make recovery worse. This scalar
    screen cannot establish receiver survival, nonlinear recovery or PER.
    """
    values=(initial_residual_dbm,steady_residual_dbm,allowed_residual_dbm,
            recovery_tau_s,switch_settle_s,available_s)
    if not all(math.isfinite(x) for x in values) or recovery_tau_s<=0 or min(switch_settle_s,available_s)<0:
        raise ValueError('Finite frontend recovery bounds required')
    initial=10**(initial_residual_dbm/20)
    floor=10**(steady_residual_dbm/20)
    allowed=10**(allowed_residual_dbm/20)
    if floor>=allowed:
        return dict(admitted=False,required_s=None,reason='Steady leakage exceeds residual allowance')
    decay=max(0.,math.log(initial/(allowed-floor)))
    required=switch_settle_s+recovery_tau_s*decay
    return dict(admitted=required<=available_s,required_s=required,
                margin_s=available_s-required,
                maximum_tau_s=(max(0.,available_s-switch_settle_s)/decay if decay else None),
                reason='Conditional exponential recovery allocation')


def receiver_recovery_admission(*,peer_gap_s,tx_tail_s,switch_s,recovery_s,
                                receive_pipeline_s,reserve_s):
    """Conservative sequential recovery, ready before earliest peer RF arrival.

    All times refer to the calibrated antenna end marker. Do not count the
    peer's preamble as recovery time or assume overlapping stages without proof.
    """
    values=(peer_gap_s,tx_tail_s,switch_s,recovery_s,receive_pipeline_s,reserve_s)
    if not all(math.isfinite(v) and v>=0 for v in values):
        raise ValueError('Finite nonnegative receiver recovery timing required')
    fixed=tx_tail_s+switch_s+receive_pipeline_s+reserve_s
    available=peer_gap_s-fixed
    return dict(available_recovery_s=available,required_total_s=fixed+recovery_s,
                margin_s=available-recovery_s,admissible=recovery_s<=available)


if __name__=='__main__':
    import argparse
    import copy
    import json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,
        help='Independent inventory accounting fixture; omit to use the shared design')
    args=parser.parse_args()
    if args.inventory is None:
        from design_definition import load_design
        design=load_design();architecture=design.architecture
        context=dict(design_provenance=design.provenance(),
            model_role='shared_design_allocation_sensitivity')
    else:
        import hashlib
        raw=args.inventory.read_bytes();architecture=json.loads(raw)
        context=dict(design_provenance=None,model_role='independent_inventory_accounting_fixture',
            inventory_content_sha256=hashlib.sha256(raw).hexdigest(),inventory_path=str(args.inventory))
    context['diagnostic_assumptions']=dict(
        converter_enob=[8.,7.5,7.],noise_correlation=[0.,.25,.5,1.],
        current_candidates='Assigned alternative filter-current allocation; not a configured circuit',
        recovery='Independent exponential residual and switch-settling examples')
    allocation=architecture['rf_interoperability']['tx_error_allocation']
    ceiling=architecture['rf_interoperability']['external_frontend']['tx_filter_candidate_resource_screen']['per_filter_current_ceiling_ma']
    extra={name:ceiling-architecture['blocks'][name]['resource_allocation']['current_budget_ma']['rf_tx'] for name in ('txfilter_i','txfilter_q')}
    currents=[dict(candidate=candidate,**current_allocation(architecture,'rf_tx',branch=branch,additional_ma=extra if candidate else None))
              for branch in (None,'external_rf_clock') for candidate in (False,True)]
    rows=[]
    for enob in (8.,7.5,7.):
        for rho in (0.,.25,.5,1.):
            case=copy.deepcopy(allocation)
            case['uncorrelated_rms_fraction']['converter']=converter_noise_fraction(enob,allocation['backoff_db'])
            rows.append(dict(enob=enob,**evaluate_budget(case,noise_correlation=rho)))
    recovery=[]
    for isolation in (22.,40.,60.):
        for tau in (20e-9,50e-9,100e-9):
            recovery.append(dict(assumed_tx_to_rx_isolation_db=isolation,tau_s=tau,
                **frontend_recovery_budget(initial_residual_dbm=10-isolation,
                    steady_residual_dbm=-100.,allowed_residual_dbm=-90.,
                    recovery_tau_s=tau,switch_settle_s=100e-9,available_s=.5e-6)))
    print(json.dumps(dict(context,scope='Allocation sensitivity, not measured covariance or packet qualification',
        support_audit=support_budget_audit(architecture),current_cases=currents,selected=evaluate_budget(allocation),cases=rows,frontend_recovery=recovery),indent=2))
