"""Conditional electrical constraints from the extracted resistive preamplifier.
These are sensitivity scenarios, not measurements or fitted process parameters.
"""
import json
import math

rows=[]
for resistance in [800,1000,1200]:
    for capacitance_ff in [50,100,200,500]:
        tau=resistance*capacitance_ff*1e-15
        rows.append(dict(load_ohm=resistance,output_capacitance_ff=capacitance_ff,
                         pole_hz=1/(2*math.pi*tau),
                         settling_7bit_half_lsb_ns=8*math.log(2)*tau*1e9))
print(json.dumps(dict(
    provenance='Extracted 10 parallel 10-square high-poly resistors per output; nominal 1 kohm/square.',
    load_sweep_note='800..1200 ohm/square foundry wide-monitor sheet range; narrow 1um resistor end/width effects omitted. Not guaranteed load bounds.',
    capacitance_sweep_note='50..500 fF assigned scenarios; not extracted or measured.',
    scenarios=rows,
    differential_pair_relations=dict(
        differential_gain='gm * (Rload || ro)',
        output_common_mode='VDD - Itail * Rload / 2',
        resistive_pole='1 / (2*pi*(Rload || ro)*Cout)',
        load_resistor_input_noise_psd='8*k*T / (gm^2 * Rload), symmetric differential convention; transistor noise additional'),
    limitations=['Linear single-pole settling only; excludes slew, comparator regeneration, kickback and sample timing.',
                 'No bias current inferred from overall chip power or measured ADC SNR.',
                 'Overall ADC 20MS/s or >30MS/s does not identify per-decision timing.',
                 'No direct transfer of these loads or gain to the proposed transceiver.']),indent=2))
