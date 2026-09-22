"""Clocked slow monitor buffer feeding the existing local analog tile.

100ns default sampling is an assumed diagnostic service, not a qualified clock.
Coincident ADC/command events execute before the monitor buffer updates.
"""
import math
from diagnostic_tile_lifecycle import DiagnosticChip

class MonitorChip(DiagnosticChip):
    TILE_COMMANDS=DiagnosticChip.TILE_COMMANDS+('monitor_select','monitor_status')
    def __init__(self,monitor_period_s=100e-9,**kwargs):
        if not math.isfinite(monitor_period_s) or monitor_period_s<=0:raise ValueError('Invalid monitor period')
        self.monitor_period=monitor_period_s;self.monitor_route=0
        self.monitor_origin=0.;self.monitor_tick=0;self.monitor_updates=0;self.monitor_last=0.;self.monitor_valid=False;self.monitor_epoch=None
        super().__init__(**kwargs)
    def execute_management(self,operation,payload,time):
        if operation=='monitor_status':
            if payload:raise ValueError('Reserved monitor status payload')
            valid=self.monitor_valid and self.monitor_epoch==self.epoch and self.state=='active'
            return dict(value=self.monitor_route|(int(valid)<<8)|(int(self.state=='active')<<9))
        if operation!='monitor_select':return super().execute_management(operation,payload,time)
        if payload not in (0,1,2,3):raise ValueError('Unknown internal monitor route')
        if self.session.armed or self.adc_left or self.adc_pending:raise ValueError('Monitor selection requires disarmed idle ADC')
        self.tile.advance(time)
        self.monitor_route=payload;self.monitor_origin=time;self.monitor_tick=1
        self.monitor_valid=False;self.monitor_epoch=None
        # Disconnecting the mux restores a zero held input, not a hidden fixture.
        self.tile.drive(time,0.,0.)
        return {}
    def quiesce(self,time,reason):
        self.monitor_valid=False;self.monitor_epoch=None
        return super().quiesce(time,reason)
    def monitor_value(self,time):
        if self.monitor_route==1:
            self.supply.advance(time);return self.supply.delta
        if self.monitor_route==2:
            self.adc_reference.advance(time);return 1-self.adc_reference.voltage
        if self.monitor_route==3:
            self.probe.advance(time);return float(self.probe.legs[0].x[0])
        return 0.
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid monitor time')
        while self.time<time:
            edge=self.monitor_origin+self.monitor_tick*self.monitor_period if self.monitor_route else math.inf
            command=self.command_events[0][0] if self.command_events else math.inf
            end=min(time,edge,command)
            super().advance(end)
            # Recompute after commands which may have changed the route/phase.
            edge=self.monitor_origin+self.monitor_tick*self.monitor_period if self.monitor_route else math.inf
            if edge<=self.time:
                if self.state=='active':
                    self.monitor_last=self.monitor_value(self.time)
                    self.tile.drive(self.time,self.monitor_last,0.)
                    self.monitor_updates+=1
                    self.monitor_valid=True;self.monitor_epoch=self.epoch
                self.monitor_tick+=1
        super().advance(time)
