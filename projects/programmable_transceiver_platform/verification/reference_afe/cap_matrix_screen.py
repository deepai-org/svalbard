"""Charge-conserving matrix checks; conditional coupling, not field extraction."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'system_model/connected'))
from capacitor_network import CapacitorNetwork
rows=[]
for coupling_pf in [0,.1,1.]:
    branches=[('top','b0',.75e-12),('top','b1',.75e-12)]
    if coupling_pf:branches.append(('b0','b1',coupling_pf*1e-12))
    network=CapacitorNetwork(['top','b0','b1'],branches)
    initial=dict(top=1.65,b0=.8,b1=.8)
    final,charge=network.step(initial,dict(b0=2.5,b1=.8))
    assert abs(final['top']-2.5)<1e-12
    assert abs(charge['top'])<1e-25
    expected=.75e-12*.5*1.7+coupling_pf*1e-12*1.7
    assert abs(charge['b0']-expected)<1e-25
    # Reverse transition independently checks state conservation and charge sign.
    restored,returned=network.step(final,dict(b0=.8,b1=.8))
    assert all(abs(restored[k]-v)<1e-12 for k,v in initial.items())
    assert all(abs(returned[k]+charge[k])<1e-25 for k in charge)
    assert np.linalg.eigvalsh(network.matrix).min()>-1e-25
    rows.append(dict(inter_bit_coupling_pf=coupling_pf,final_top_v=final['top'],
                     high_source_charge_pc=charge['b0']*1e12,low_source_charge_pc=charge['b1']*1e12))
# Ground parasitic attenuates redistribution, unlike coupling between driven bits.
net=CapacitorNetwork(['top','b0','b1'],[('top','b0',.75e-12),('top','b1',.75e-12),('top',None,.5e-12)])
a,q=net.step(dict(top=1.65,b0=.8,b1=.8),dict(b0=2.5,b1=.8))
assert abs(a['top']-(1.65+1.7*.75/2))<1e-12
try:network.step(initial,{})
except ValueError:pass
else:raise AssertionError('Unanchored floating network accepted')
# Independent charge-sharing formula: C1V1+C2V2=(C1+C2)Vfinal.
sharing=CapacitorNetwork(['bit','rail'],[('bit',None,1e-12),('rail',None,100e-12)])
volts,charges=sharing.redistribute(dict(bit=2.5,rail=.8),[('bit','rail')])
expected=(1*2.5+100*.8)/101
assert abs(volts['rail']-expected)<1e-14 and volts['bit']==volts['rail']
assert abs(sum(charges.values()))<1e-25
energy_before=.5e-12*2.5**2+.5*100e-12*.8**2
energy_after=.5*101e-12*expected**2
expected_loss=.5*(1e-12*100e-12/101e-12)*(2.5-.8)**2
assert abs(energy_before-energy_after-expected_loss)<1e-25
try:sharing.redistribute(dict(bit=2.5,rail=.8),[('bit','rail')],dict(bit=2.5,rail=.8))
except ValueError:pass
else:raise AssertionError('Conflicting tied ideal sources accepted')
sharing_case=dict(bit_capacitance_pf=1,rail_capacitance_pf=100,
 rail_rise_mv=(volts['rail']-.8)*1000,charge_conservation_error_c=sum(charges.values()),
 dissipated_energy_j=energy_before-energy_after)
# Actual floating top-plate reduces the effective switched load by series action.
network=CapacitorNetwork(['top','bit','low'],[('top','bit',.75e-12),('top',None,.75e-12),('low',None,100e-12)])
volts,charges=network.redistribute(dict(top=1.65,bit=2.5,low=.8),[('bit','low')])
expected_rise=(.375/(100+.375))*1.7
assert abs(volts['low']-.8-expected_rise)<1e-14
assert abs(charges['top'])<1e-25 and abs(charges['bit']+charges['low'])<1e-25
sharing_case['floating_top_rail_rise_mv']=expected_rise*1000

# Exact RC result for the combined reservoir+effective floating-top capacitance.
initial=dict(top=1.65,bit=2.5,low=.8)
connections=[('bit','low')]
shared,_=network.redistribute(initial,connections)
end=network.relax(shared,connections,dict(low=(.8,1000)),50e-9)
expected=.8+expected_rise*np.exp(-50e-9/(1000*100.375e-12))
assert abs(end['low']-expected)<1e-13
middle=network.relax(shared,connections,dict(low=(.8,1000)),20e-9)
partitioned=network.relax(middle,connections,dict(low=(.8,1000)),30e-9)
assert all(abs(partitioned[n]-end[n])<1e-13 for n in end)
sharing_case['rail_rise_after_50ns_with_1kohm_mv']=(end['low']-.8)*1000
# Two coupled references checked against an independently assembled ODE.
from scipy.integrate import solve_ivp
coupled=CapacitorNetwork(['high','low'],[('high',None,100e-12),('low',None,80e-12),('high','low',2e-12)])
state=dict(high=2.49,low=.815)
actual=coupled.relax(state,[],dict(high=(2.5,1000),low=(.8,2000)),50e-9)
c=np.array([[102,-2],[-2,82]])*1e-12
numeric=solve_ivp(lambda t,v:np.linalg.solve(c,[(2.5-v[0])/1000,(.8-v[1])/2000]),(0,50e-9),[2.49,.815],rtol=1e-11,atol=1e-13)
assert numeric.success and max(abs(np.array(list(actual.values()))-numeric.y[:,-1]))<1e-10
sharing_case['coupled_reference_ode_max_error_v']=float(max(abs(np.array(list(actual.values()))-numeric.y[:,-1])))

# Use the observed B0/B2 route estimate with all13 area-only plate weights.
geometry_path=root/'evidence/reference-afe-cap-geometry.json'
field_path=root/'evidence/reference-afe-fringe-screen.json'
geometry=json.loads(geometry_path.read_text())
field=json.loads(field_path.read_text())['lateral_routing_screen']
bits=[f'B{i}' for i in range(13)]
plate=[('top',b,geometry['bit_geometry'][b]['m3_m4_overlap_um2']*.0394e-15) for b in bits]
initial=dict(top=1.65,**{b:.8 for b in bits});drive={b:(2.5 if b=='B0' else .8) for b in bits}
route_rows=[]
for cap_ff in [0]+field['conditional_extruded_mutual_capacitance_ff']:
    branches=plate+([('B0','B2',cap_ff*1e-15)] if cap_ff else [])
    net=CapacitorNetwork(['top']+bits,branches)
    end,charge=net.step(initial,drive)
    route_rows.append(dict(route_coupling_ff=cap_ff,top_voltage_v=end['top'],
       b0_charge_pc=charge['B0']*1e12,b2_charge_pc=charge['B2']*1e12))
base=route_rows[0]
for row in route_rows[1:]:
    delta=row['route_coupling_ff']*.001*1.7
    assert abs(row['b0_charge_pc']-base['b0_charge_pc']-delta)<1e-14
    assert abs(row['b2_charge_pc']-base['b2_charge_pc']+delta)<1e-14
    assert abs(row['top_voltage_v']-base['top_voltage_v'])<1e-12
    row['b0_charge_increase_percent']=100*delta/base['b0_charge_pc']
# Feed the matrix-derived charge into the existing fixed-target reference law.
# A1V target is used as a local voltage-error reference, not a recovered rail.
from causal_reference_lifecycle import CurrentLimitedReference
from scipy.integrate import solve_ivp
recovery=[]
for capacitance_pf in [10,100,1000]:
 for resistance in [10,1000]:
  for route in [route_rows[0],route_rows[-1]]:
   charge=route['b0_charge_pc']*1e-12
   ref=CurrentLimitedReference(resistance=resistance,capacitance=capacitance_pf*1e-12,load_capacitance=0)
   ref.voltage-=charge/ref.c
   initial_voltage=ref.voltage
   samples=[]
   for ns in [1,3,10,50]:
    ref.advance(ns*1e-9)
    samples.append(dict(time_ns=ns,droop_mv=(1-ref.voltage)*1000))
   # Independent integration verifies the fixed-target current-limited law.
   numeric=solve_ivp(lambda t,v:[min(150e-6,max(-150e-6,(1-v[0])/resistance))/ref.c],
       (0,50e-9),[initial_voltage],rtol=1e-10,atol=1e-12,max_step=.1e-9)
   assert numeric.success and abs(numeric.y[0,-1]-ref.voltage)<1e-8
   assert abs(ref.recharge_c-ref.c*(ref.voltage-initial_voltage))<1e-24
   recovery.append(dict(capacitance_pf=capacitance_pf,resistance_ohm=resistance,
       route_coupling_ff=route['route_coupling_ff'],charge_pc=charge*1e12,
       mean_current_for_one_event_per_20msps_ua=charge*20e6*1e6,
       current_limited_duration_ns=ref.limited_s*1e9,samples=samples))
# Inverse diagnostic against the independently recovered MOS-switch replay.
# Ideal instantaneous redistribution gives dV=Ce*span/(Cr+Ce). Its inversion
# is an equivalent impulse load, NOT an identification of physical capacitance.
transient_path=root/'evidence/reference-afe-reference-transient.json'
transient=json.loads(transient_path.read_text())
residuals=[]
for direction,replay,metric in [
    ('low_to_high',transient,'maximum_high_reference_droop_mv'),
    ('high_to_low',transient['high_to_low_replay'],'maximum_low_reference_rise_mv')]:
    for case in replay['cases']:
        if case['ideal_reference'] or case['maximum_timestep_ns']!=.02:continue
        effective_pf=.375 if case['common_node']=='floating' else .75
        reservoir_pf=case['reservoir_per_rail_pf']
        excursion=case[metric]/1000
        span=1.7
        assert 0<excursion<span
        ideal=effective_pf*span/(reservoir_pf+effective_pf)
        inferred_pf=reservoir_pf*excursion/(span-excursion)
        # Forward substitution checks units and the inverse algebra only.
        assert abs(inferred_pf*span/(reservoir_pf+inferred_pf)-excursion)<1e-14
        residuals.append(dict(transition=direction,common_node=case['common_node'],
            reservoir_pf=reservoir_pf,ideal_sharing_excursion_mv=ideal*1000,
            transistor_peak_excursion_mv=excursion*1000,
            equivalent_extra_switched_capacitance_ff=(inferred_pf-effective_pf)*1000,
            equivalent_impulse_residual_pc=(reservoir_pf+effective_pf)*excursion-effective_pf*span))
assert len(residuals)==12
# Separate reference-span sensitivity from a fitted fixed capacitance.
# Hold nominal1.7V out of the affine fit; do not extrapolate beyond these spans.
span_rows=list(transient['span_sensitivity']['cases'])
span_rows += [dict(case,reference_span_v=1.7) for replay in [transient,transient['high_to_low_replay']] for case in replay['cases'][-2:]]
span_reductions=[]
for common in ['floating','clamped']:
    for direction in ['low_to_high','high_to_low']:
        selected=sorted([r for r in span_rows if r['common_node']==common and r['transition']==direction],key=lambda r:r['reference_span_v'])
        sign=1 if direction=='low_to_high' else -1
        x=np.array([r['reference_span_v'] for r in selected])
        y=np.array([-sign*sum(r['terminal_charge_5_to_20ns_pc'][k] for k in ['gate','pmos_body','nmos_body']) for r in selected])
        train=x!=1.7
        slope,intercept=np.polyfit(x[train],y[train],1)
        nominal=float(y[~train][0]);prediction=float(intercept+slope*1.7)
        fixed_cap_prediction=nominal*x/1.7
        span_reductions.append(dict(common_node=common,transition=direction,
            spans_v=x.tolist(),extra_terminal_charge_pc=y.tolist(),
            affine_intercept_pc=float(intercept),affine_slope_pf=float(slope),
            maximum_training_residual_pc=float(max(abs(y[train]-(intercept+slope*x[train])))),
            held_out_span_v=1.7,held_out_error_pc=prediction-nominal,
            fixed_nominal_cap_max_relative_charge_error=float(max(abs(fixed_cap_prediction-y)/abs(y)))))
print(json.dumps(dict(reference_span_reduction=span_reductions,transistor_reference_comparison=residuals,finite_reservoir_charge_sharing=sharing_case,reference_recovery_scenarios=recovery,layout_informed_route_scenarios=route_rows,
 source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [geometry_path,field_path,transient_path,root/'system_model/connected/causal_reference_lifecycle.py',root/'system_model/connected/capacitor_network.py']},
 coupling_scenarios=rows,ground_parasitic_case=dict(capacitance_pf=.5,final_top_v=a['top']),
 conclusions=['Coupling between ideal-driven bottom plates increases reference charge without changing final top-plate voltage.',
 'Top-to-ground capacitance changes final redistribution. Matrix location matters, not total capacitance alone.'],
 limitations=['Affine charge law is conditional on the recovered MSB driver and fixed midpoint/gate swing, fitted over0.5-2.3V. It is not a universal device capacitance or transient rail-partition model.',
 'Equivalent extra switched capacitance is an inverse diagnostic of conditional PDK transients, not measured silicon capacitance. MOS charge, finite edges, conduction and reference recovery are confounded; peak times may differ.',
 '13-bit route scenarios use area-only plate weights plus one conditional isolated-route estimate, not a complete extracted matrix or SAR sequence.',
 'Assigned two-bit1.5pF array and0/0.1/1pF coupling; no extracted full capacitance matrix.',
 'Ideal-switch redistribution includes finite-reservoir charge sharing. Matrix relaxation solves linear resistive reference recovery, without current clipping, switch injection or finite switch resistance.',
 'Separate impulse-recovery scenarios reuse the fixed-target current-limited reference law with assigned R/C and150uA limit; feedback from droop to switching charge, supply coupling and repeated bit events omitted.',
 'This component is not yet connected to the whole-chip ADC conversion path.']),indent=2))
