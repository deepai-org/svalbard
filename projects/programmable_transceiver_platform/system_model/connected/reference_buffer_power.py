"""Energy-consistent assumed reference buffer current at its RC source boundary.

Converter impulses remove reservoir energy. Buffer replenishment draws supply
power continuously; the impulse is not charged to the supply a second time.
"""
import math

def account(reference_v,target_v,resistance_ohm,rail_v,bias_a=.0001,efficiency=.5):
    if not all(math.isfinite(x) for x in (reference_v,target_v,resistance_ohm,rail_v,bias_a,efficiency)) or min(reference_v,target_v,resistance_ohm,rail_v)<=0 or bias_a<0 or not 0<efficiency<=1:
        raise ValueError('Invalid reference buffer power parameters')
    current=(target_v-reference_v)/resistance_ohm
    source=target_v*current;loss=current*current*resistance_ohm;stored=reference_v*current
    supply=rail_v*bias_a+max(0.,source)/efficiency
    return dict(output_current_a=current,source_power_w=source,resistor_loss_w=loss,
        reservoir_energy_rate_w=stored,dc_current_a=supply/rail_v,dc_power_w=supply,
        buffer_dissipation_w=supply-source,balance_error_w=source-loss-stored)

def reservoir_energy_removed(voltage,charge,capacitance):
    if not all(math.isfinite(x) for x in (voltage,charge,capacitance)) or voltage<=0 or capacitance<=0 or not 0<=charge<=voltage*capacitance:
        raise ValueError('Invalid reservoir extraction')
    return voltage*charge-charge*charge/(2*capacitance)
