"""Linear two-node RF output/monitor loading budget (RMS phasors).

The source has finite resistance, the RF pad drives a resistive load, and a
series resistor feeds the detector's input resistance/capacitance. Off state
retains capacitance and an explicit off resistance; no ideal disappearing tap.
All values are exploratory lumped parameters, not package/PDK extraction.
"""
import math

def solve(frequency_hz,*,source_v=1.,source_ohm=50.,load_ohm=50.,tap_ohm=1000.,input_ohm=10000.,input_f=50e-15):
    if not all(math.isfinite(v) and v>0 for v in (frequency_hz,source_ohm,load_ohm,tap_ohm,input_ohm)) or not math.isfinite(input_f) or input_f<0 or not math.isfinite(source_v):
        raise ValueError('Invalid passive network')
    admittance=1/input_ohm+2j*math.pi*frequency_hz*input_f
    branch=admittance/(1+tap_ohm*admittance)
    output=source_v/(1+source_ohm*(1/load_ohm+branch))
    monitor=output/(1+tap_ohm*admittance)
    source_i=(source_v-output)/source_ohm;tap_i=(output-monitor)/tap_ohm
    losses=dict(source_resistor=abs(source_i)**2*source_ohm,external_load=abs(output)**2/load_ohm,
        tap_resistor=abs(tap_i)**2*tap_ohm,detector_resistor=abs(monitor)**2/input_ohm)
    delivered=(source_v*source_i.conjugate()).real
    unloaded=source_v*load_ohm/(source_ohm+load_ohm)
    return dict(output=output,monitor=monitor,source_current=source_i,tap_current=tap_i,
        losses=losses,source_real_power=delivered,relative_output=output/unloaded if unloaded else 0j,
        pad_kcl_error=abs(source_i-output/load_ohm-tap_i),monitor_kcl_error=abs(tap_i-monitor*admittance))
