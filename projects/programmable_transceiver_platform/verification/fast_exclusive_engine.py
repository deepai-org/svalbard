"""Experimental payload ownership interlock on the loaded common-chip model.

Inactive analog clock/bias shutdown and serialized management encoding remain
unimplemented. This adapter gates admission and actual session enables.
"""
from types import MethodType
from fast_loaded_output import LoadedOutputChip

class ExclusiveEngineChip(LoadedOutputChip):
    def __init__(self,**kwargs):
        self.active_engine='none'
        super().__init__(**kwargs)
        enabled=self.session.enabled
        self.session.enabled=MethodType(lambda session,engine:
            engine==self.active_engine and enabled(engine),self.session)
    def select_engine(self,engine):
        if engine not in ('none','rf','wire'):raise ValueError('Invalid engine')
        if self.state!='reset' or self.session.armed or self.tx_cal.busy:
            raise ValueError('Engine selection requires stopped unarmed chip')
        if self.adc_pending or self.dac_pending or self.maintenance_pending is not None:
            raise ValueError('Pending conversion owns shared resources')
        if engine!=self.active_engine:
            self.tx_cal.cancel(self.time,'engine ownership changed')
            self.output_network.configure(False,True)
            self.active_engine=engine
    def require_engine(self,engine):
        if self.active_engine!=engine:raise ValueError('Inactive payload engine')
    def configure(self,*args,**kwargs):
        if self.active_engine=='none':raise ValueError('Select payload engine before configuration')
        return super().configure(*args,**kwargs)
    def capture(self,*args,**kwargs):
        self.require_engine('rf');return super().capture(*args,**kwargs)
    def schedule(self,*args,**kwargs):
        self.require_engine('rf');return super().schedule(*args,**kwargs)
    def schedule_wire(self,*args,**kwargs):
        self.require_engine('wire');return super().schedule_wire(*args,**kwargs)
    def incoming_wire(self,*args,**kwargs):
        self.require_engine('wire');return super().incoming_wire(*args,**kwargs)
    def execute_management(self,operation,payload,time):
        if operation in ('tx_cal_start','rx_stream_start','tx_stream_start','stream_start'):
            self.require_engine('rf')
        return super().execute_management(operation,payload,time)
