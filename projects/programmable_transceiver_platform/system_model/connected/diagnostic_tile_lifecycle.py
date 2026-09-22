"""Exclusive slow tile-to-I-ADC route, with Q held at zero.

Tile inputs are held diagnostic buffer values supplied explicitly by the caller;
Physical monitor selection remains to be implemented. Timed named commands
use the existing serialized management transport and epoch fences.
"""
from analog_tile import AnalogTile
from receiver_detect_lifecycle import ReceiverDetectChip

class DiagnosticChip(ReceiverDetectChip):
    TILE_COMMANDS=('diagnostic_select','tile_configure','tile_discharge','tile_status')
    def submit(self,operation,time,expected_epoch,expected_generation,payload=0):
        if operation not in self.TILE_COMMANDS:
            return super().submit(operation,time,expected_epoch,expected_generation,payload)
        if not isinstance(payload,int) or not 0<=payload<2**32:raise ValueError('Invalid tile payload')
        token,apply,reply=super().submit('status',time,expected_epoch,expected_generation,0)
        for when,key,stage,data in self.command_events:
            if key==token and stage=='apply':
                data['operation']=operation;data['payload']=payload;break
        else:raise AssertionError('Queued tile command missing')
        return token,apply,reply
    def __init__(self,**kwargs):
        self.tile=AnalogTile();self.diagnostic_selected=False
        super().__init__(**kwargs)
    def select_diagnostic(self,selected):
        if not isinstance(selected,bool):raise ValueError('Invalid diagnostic selection')
        if self.session.armed or self.adc_left or self.adc_pending:
            raise ValueError('Diagnostic route requires disarmed idle ADC')
        self.diagnostic_selected=selected
    def receiver_value(self):
        if self.diagnostic_selected:return complex(self.tile.advance(self.tx.time),0)
        return super().receiver_value()
    def advance(self,time):
        super().advance(time)
        self.tile.advance(self.time)
    def execute_management(self,operation,payload,time):
        if operation in self.TILE_COMMANDS:
            if operation=='tile_status':
                if payload:raise ValueError('Reserved tile status payload')
                self.tile.advance(time)
                return dict(value=int(self.tile.comparator)|(int(self.diagnostic_selected)<<1)|(int(self.tile.enabled)<<2))
            if self.session.armed or self.adc_left or self.adc_pending:
                raise ValueError('Tile configuration requires disarmed idle ADC')
            if operation=='diagnostic_select':
                if payload not in (0,1):raise ValueError('Reserved diagnostic select bits')
                self.select_diagnostic(bool(payload))
            elif operation=='tile_discharge':
                if payload:raise ValueError('Reserved tile discharge bits')
                self.tile.discharge(time)
            else:
                weights=(-1.,-.5,0.,.5,1.)
                a=payload&7;b=(payload>>3)&7
                if payload>>7 or a>=len(weights) or b>=len(weights):raise ValueError('Reserved tile configuration bits')
                self.tile.configure(time,(weights[a],weights[b]),bool(payload&64))
            return {}
        if operation=='resource_count':
            if payload:raise ValueError('Reserved resource-count payload')
            return dict(value=8)
        if operation=='resource_status' and (payload==7 or payload==0 and self.diagnostic_selected):
            assigned=self.diagnostic_selected
            busy=assigned and bool(self.adc_left or self.adc_pending)
            return dict(value=(8 if assigned else 0)|(int(busy)<<8)|(int(self.session.armed)<<9)|(int(assigned)<<10))
        return super().execute_management(operation,payload,time)
