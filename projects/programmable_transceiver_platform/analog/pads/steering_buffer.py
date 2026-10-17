"""Parametric supply-powered CMOS predriver for a TX steering gate.

A noninverting tapered chain replaces the fixture's zero-impedance output.
Input data/qualification remains a declared upstream boundary. No delay, drive
current or bandwidth is inferred from the sizing recipe alone.
"""
import math
from circuits import Circuit, Mos


def build(n_widths_um=(2.,8.,32.,128.), p_to_n_ratio=2., unit_width_um=16., length_um=.28):
    if len(n_widths_um)<2 or len(n_widths_um)%2:
        raise ValueError('Noninverting driver requires an even number of stages')
    values=[*n_widths_um,p_to_n_ratio,unit_width_um,length_um]
    if any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('Invalid driver geometry')
    if not .8<=unit_width_um<=20 or length_um<.28:raise ValueError('Unsupported driver unit geometry')
    devices=[];incoming='IN'
    for stage,nwidth in enumerate(n_widths_um):
        outgoing='OUT' if stage==len(n_widths_um)-1 else f'STAGE_{stage}'
        for kind,width,rail in [('n',nwidth,'VSS'),('p',nwidth*p_to_n_ratio,'VDD')]:
            count=math.ceil(width/unit_width_um);unit=width/count
            if unit<.8:raise ValueError('Driver finger narrower than supported PCell')
            for finger in range(count):
                devices.append(Mos(f'S{stage}_{kind}{finger}',(outgoing,incoming,rail,rail),
                    ('nfet_' if kind=='n' else 'pfet_')+'03v3',unit,length_um))
        incoming=outgoing
    return Circuit('tx_steering_buffer',['VDD','VSS','IN','OUT'],devices,{},[
        'Supply-powered finite driver; input data gating and qualification are upstream boundaries.',
        'Nominal sizing is not a demonstrated edge-rate, loading, power or PVT specification.',
        'Default-off input behavior, upstream power-domain crossings and shared supply impedance require integration.'])
