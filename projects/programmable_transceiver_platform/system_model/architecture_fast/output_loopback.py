"""Connect modulator/output distortion ahead of internal loopback RX filtering."""
import cmath
import math
from types import MethodType
import run as architecture
from rf_cascade_state import RfCascadeState
from tx_output_terms import output_terms

def receive_terms(state,parameters):
    if state.rx_route!='loopback':return RfCascadeState.receive_terms(state)
    rotation=cmath.exp(1j*(2*math.pi*state.tx_lo_hz*state.time+state.tx_lo_phase))
    terms=[(a*rotation,r+2j*math.pi*state.tx_lo_hz)
           for a,r in output_terms(state.transmit_terms(),**parameters)]
    bound=sum(abs(a) for a,r in terms)+sum(abs(a) for a,f in state.rf_blockers)
    if (state.rf_cubic or state.rf_blockers) and bound>state.rf_envelope_limit:
        raise ValueError('Distorted loopback exceeds receiver polynomial envelope')
    terms.extend((a*cmath.exp(2j*math.pi*f*state.time),2j*math.pi*f) for a,f in state.rf_blockers)
    products=list(terms)
    if state.rf_cubic:
        products.extend((state.rf_cubic*a*b*c.conjugate(),p+q+r.conjugate())
                        for a,p in terms for b,q in terms for c,r in terms)
    rotation=cmath.exp(-1j*(2*math.pi*state.rx_lo_hz*state.time+state.rx_lo_phase))
    return [(rotation*a,r-2j*math.pi*state.rx_lo_hz) for a,r in products]

def connect(chip):
    if chip.tx.reconstruction is None and chip.tx.rx_bank is None:
        raise ValueError('Output loopback requires exponential-term RX integration')
    def terms(state):return receive_terms(state,chip.tx_output_parameters)
    chip.tx.receive_terms=MethodType(terms,chip.tx)
