"""Experimental finite output-network adapter for the common fast chip.

Pad observation, calibration detection and RX loopback use the finite network. Not a replacement default or closure claim.
"""
import cmath,math,sys
from types import MethodType
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/architecture_fast'))
from chip import TransceiverChip
from rf_switched_load import SwitchedLoad
from rf_loaded_detector import voltage_terms
from tx_output_terms import output_terms

class LoadedOutputChip(TransceiverChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.output_network=SwitchedLoad(frequency_hz=self.rf_carrier)
        self._output_modes=None
        original_receive=self.tx.receive_terms
        self.tx.receive_terms=MethodType(lambda state:self.loaded_receive_terms(state,original_receive),self.tx)
        original=self.tx.advance
        def advance(time):
            if getattr(self,'analog_owner',None) is not None:
                self.advance_coupled_analog(time)
                return
            n=self.output_network
            if time>self.tx.time:
                if n.time!=self.tx.time:raise ValueError('Output network history mismatch')
                terms=self.output_source_terms()
                modes=voltage_terms(n,terms)
                self._output_modes=(self.tx.time,modes)
                self.tx_detector.advance(time,[(complex(v[2]),complex(r)) for v,r in modes])
                dt=time-n.time
                n.voltage=sum((v*np.exp(r*dt) for v,r in modes),np.zeros(4,dtype=complex))
                n.time=time
            original(time)
        self.tx.advance=advance
    def advance_coupled_analog(self,time):
        from rf_tx_state import RfTxState
        owner=self.analog_owner
        self.configure_analog_loads()
        if time<self.tx.time:raise ValueError('Nonmonotonic analog time')
        if time==self.tx.time:return
        if owner.time!=self.tx.time:raise ValueError('Coupled analog history mismatch')
        start=self.tx.time
        terms=self.output_source_terms()
        def drive(t):return sum(a*cmath.exp(r*(t-start)) for a,r in terms)
        state=self.tx
        def receive(t,pad):
            if not getattr(self.rf_pll,'powered',True):return 0j
            if state.rx_route=='loopback':signal=pad
            elif state.rx_route=='external_tone':
                signal=state.external_amplitude*cmath.exp(2j*math.pi*state.external_frequency*t)
            else:signal=0j
            signal+=sum(a*cmath.exp(2j*math.pi*f*t) for a,f in state.rf_blockers)
            if (state.rf_cubic or state.rf_blockers) and abs(signal)>state.rf_envelope_limit:
                raise ValueError('Coupled RF input outside declared cubic-model range')
            signal+=state.rf_cubic*signal*abs(signal)**2
            return signal*cmath.exp(-1j*(2*math.pi*state.rx_lo_hz*t+state.rx_lo_phase))
        owner.receive=receive
        forecast=getattr(self,'_analog_forecast',None)
        if forecast is None:
            owner.advance(time,drive)
        else:
            start,end,candidate=forecast
            if owner.time!=start or time!=end:
                raise ValueError('Unscheduled boundary inside coupled analog forecast')
            owner.network.__dict__.update(candidate.network.__dict__)
            owner.reference.__dict__.update(candidate.reference.__dict__)
            owner.detector.__dict__.update(candidate.detector.__dict__)
            owner.rx_bank.update(candidate.rx_bank)
            owner.received=candidate.received
            owner.rail_v=candidate.rail_v;owner.time=candidate.time
            owner.rail_trajectory=candidate.rail_trajectory
            for name in ('source_energy_j','rail_resistor_energy_j','load_energy_j','extra_load_energy_j'):
                setattr(owner,name,getattr(candidate,name))
            self._analog_forecast=None
        # The owner has advanced RX; advance only the independent TX reconstruction.
        RfTxState.advance(state,time)
        state.rx_bank=owner.rx_bank;state.received=owner.received
        self.supply.delta=owner.rail_v-owner.law.nominal_v
        self.supply.time=time
        self.supply.minimum=min(self.supply.minimum,self.supply.delta)

    def loaded_receive_terms(self,state,original_receive):
        if not getattr(self.rf_pll,'powered',True):return []
        if state.rx_route!='loopback':return original_receive()
        if self._output_modes is not None and self._output_modes[0]==state.time:
            modes=self._output_modes[1]
        else:
            if self.output_network.time!=state.time:raise ValueError('Loopback history mismatch')
            modes=voltage_terms(self.output_network,self.output_source_terms())
        terms=[(complex(v[1]),complex(r)) for v,r in modes]
        terms.extend((a*cmath.exp(2j*math.pi*f*state.time),2j*math.pi*f)
                     for a,f in state.rf_blockers)
        if (state.rf_cubic or state.rf_blockers) and sum(abs(a) for a,r in terms)>state.rf_envelope_limit:
            raise ValueError('Loaded RF envelope outside declared cubic-model range')
        products=list(terms)
        if state.rf_cubic:
            products.extend((state.rf_cubic*a*b*c.conjugate(),ra+rb+rc.conjugate())
                for a,ra in terms for b,rb in terms for c,rc in terms)
        rate=-2j*math.pi*state.rx_lo_hz
        rotation=cmath.exp(rate*state.time-1j*state.rx_lo_phase)
        return [(rotation*a,r+rate) for a,r in products]
    def _advance_tx_monitor(self,end):
        # Network hook owns detector integration at actual DAC/LO boundaries.
        pass
    def output_source_terms(self):
        if not getattr(self.rf_pll,'powered',True):return [(0j,0j)]
        # Fast LO segments are already expressed relative to fixed rf_carrier.
        rate=2j*math.pi*self.tx.tx_lo_hz
        rotation=cmath.exp(rate*self.tx.time+1j*self.tx.tx_lo_phase)
        terms=output_terms(self.tx.transmit_terms(),**self.tx_output_parameters)
        return [(rotation*a,r+rate) for a,r in terms] or [(0j,0j)]
    def complete_dac(self,time):
        before=self.dac_pipeline_updates
        result=super().complete_dac(time)
        if self.dac_pipeline_updates>before:
            assert self.output_network.time==time
            self.output_network.configure(True,False)
        return result
    def quiesce(self,time,reason):
        self.tx.advance(time)
        self.output_network.configure(False,True)
        return super().quiesce(time,reason)
    def convert_adc(self,value):
        word=super().convert_adc(value)
        assert self.output_network.time==self.tx.time
        self.tx_probe[-1]=complex(self.output_network.voltage[1])
        return word
