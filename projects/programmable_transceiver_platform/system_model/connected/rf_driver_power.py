"""RMS-envelope power accounting at the existing Thevenin driver boundary.

Observes the passive network only. Does not infer DC current or efficiency;
returned stored energy can make ideal-source power negative during transients.
"""
import numpy as np

def account(network,source):
    v=network.voltage
    if not np.isfinite(source):raise ValueError('Nonfinite source')
    current=(source-v[0])/50
    source_power=float(np.real(source*np.conj(current)))
    source_resistor=float(abs(source-v[0])**2/50)
    go=1/(5 if network.output_on else 1e6)
    gd=1/(5 if network.dummy_on else 1e6)
    losses=dict(source_resistor=source_resistor,pad=float(abs(v[1])**2/50),
        monitor=float(abs(v[2])**2/10000),dummy=float(abs(v[3])**2/50),
        output_switch=float(go*abs(v[0]-v[1])**2),
        dummy_switch=float(gd*abs(v[0]-v[3])**2),
        monitor_tap=float(abs(v[0]-v[2])**2/1000))
    forcing=np.array([source/50,0,0,0],complex)
    dv=network.A@v+np.linalg.solve(network.C,forcing)
    energy_rate=float(np.real(np.vdot(v,network.C@dv)))
    return dict(source_power_w=source_power,resistor_losses_w=losses,
        stored_energy_rate_w=energy_rate,balance_error_w=source_power-sum(losses.values())-energy_rate)
