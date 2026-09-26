"""Physical amplifier inventory and conditional measurement inversion.
Inputs are JSON from preamp_extract.py for opamp1 and opamp2 respectively.
"""
import json
import math
import sys

amps=[json.load(open(p)) for p in sys.argv[1:]]
assert len(amps)==2
for a in amps:assert not a['disconnected_label_aliases']
cs=[d for d in amps[1]['devices'] if d['type']=='mim_2ff']
assert len(cs)==2 and all(math.isclose(d['parameters']['C'],5e-12) for d in cs)
assert all('vout' in d['terminals'].values() for d in cs)
measured_gain=10**(92/20)
rows=[]
for equivalent_pf in [4.5,5,5.5,9,10,11]:
 rows.append(dict(assumed_equivalent_compensation_pf=equivalent_pf,
                 effective_gm_ms=2*math.pi*12.5e6*equivalent_pf*1e-12*1e3))
print(json.dumps(dict(
 layouts=amps,
 identification='opamp2 is structurally consistent with published complementary-input hybrid amplifier; opamp1 is the separate two-stage design. Paper-to-pad/test-channel identity still needs confirmation.',
 physical_capacitors=dict(plate_count=8,each_plate_um=[25,25],each_branch_parallel_plates=4,nominal_branch_pf=5,branch_density_sweep_pf=[4.5,5.5]),
 conditional_inversion=dict(single_dominant_pole_hz=12.5e6/measured_gain,simulated_single_dominant_pole_hz=14e6/10**(99/20),gm_scenarios=rows),
 limitations=['Compensation branches connect output to different output-transistor gate nodes; cannot simply sum them without a small-signal model.',
 'gm=2*pi*GBW*C is a single-dominant-pole equivalent, not measured input-transistor gm.',
 'Generic three-terminal MOS reconstruction omits body effect and special device classification; resistor values outside ADC high-poly need checking.',
 'MIM density 2fF/um2 assumed from process/design context; 1.8..2.2 density sweep excludes fringe and systematic area offsets.',
 'Measured amplifier power is shared-rail upper estimate; it does not identify branch currents.']),indent=2))
