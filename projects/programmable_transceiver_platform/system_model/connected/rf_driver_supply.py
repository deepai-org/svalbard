"""Exploratory nonregenerative RF driver and self-consistent DC rail load.

Not a transistor-derived law. Supply-dependent source swing drives the existing
50-ohm Thevenin boundary. Negative RF source power dissipates locally rather
than producing negative rail current. Dynamic supply/network coupling is absent.
"""
import copy,math
from scipy.optimize import brentq
from rf_driver_power import account

class DriverSupplyLaw:
    def __init__(self,nominal_v=3.3,bias_a=.002,efficiency=.35,swing_fraction=.2):
        if not all(math.isfinite(x) for x in (nominal_v,bias_a,efficiency,swing_fraction)) or nominal_v<=0 or bias_a<0 or not 0<efficiency<=1 or not 0<swing_fraction<=1:
            raise ValueError('Invalid driver parameters')
        self.nominal_v=nominal_v;self.bias_a=bias_a;self.efficiency=efficiency;self.swing_fraction=swing_fraction
    def source(self,command,rail_v):
        if not math.isfinite(rail_v) or rail_v<=0 or not math.isfinite(command.real) or not math.isfinite(command.imag):raise ValueError('Invalid driver input')
        # Smooth finite swing; command is nominal-rail RMS source voltage.
        linear=command*rail_v/self.nominal_v
        limit=self.swing_fraction*rail_v
        return linear/math.sqrt(1+abs(linear/limit)**2)
    def consumption(self,rail_v,rf_power_w):
        if not math.isfinite(rail_v) or rail_v<=0 or not math.isfinite(rf_power_w):raise ValueError('Invalid power input')
        dc=rail_v*self.bias_a+max(0.,rf_power_w)/self.efficiency
        return dict(dc_current_a=dc/rail_v,dc_power_w=dc,driver_dissipation_w=dc-rf_power_w)
    def operating_point(self,network,command,rail_resistance_ohm,minimum_rail_v=2.5):
        if not math.isfinite(rail_resistance_ohm) or rail_resistance_ohm<0 or not 0<minimum_rail_v<self.nominal_v:raise ValueError('Invalid rail envelope')
        local=copy.deepcopy(network)
        def at(v):
            source=self.source(command,v);local.voltage=local.steady(source)
            power=account(local,source);consumed=self.consumption(v,power['source_power_w'])
            return power,consumed,source
        def residual(v):
            _,consumed,_=at(v)
            return v-self.nominal_v+rail_resistance_ohm*consumed['dc_current_a']
        if residual(minimum_rail_v)>0:raise ValueError('No operating point in declared rail envelope')
        v=brentq(residual,minimum_rail_v,self.nominal_v,xtol=1e-13)
        power,consumed,source=at(v)
        return dict(rail_v=v,source_rms_v=abs(source),pad_power_w=power['resistor_losses_w']['pad'],
            rf_source_power_w=power['source_power_w'],rail_residual_v=residual(v),**consumed)
