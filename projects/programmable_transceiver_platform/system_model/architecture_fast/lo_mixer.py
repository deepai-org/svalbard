"""Periodic loaded-LO envelope conversion before receiver filter integration."""
import cmath
import math
from types import MethodType


def connect(chip, desired, image, sidebands=()):
    """Apply (offset Hz, desired, image) coefficient triplets.

    Coefficients multiply z(t) and conjugate(z(t)) with exp(+j*2*pi*f*t).
    Time is absolute chip time, so event subdivision cannot reset sideband phase.
    The zero-offset fundamental is supplied separately for compatibility.
    """
    components=[(0.,complex(desired),complex(image))]
    components.extend((float(f),complex(d),complex(i)) for f,d,i in sidebands)
    if not all(math.isfinite(v) for f,d,i in components
               for v in (f,d.real,d.imag,i.real,i.imag)):
        raise ValueError('Nonfinite mixer coefficients')
    if chip.session.armed or chip.time!=0:
        raise ValueError('LO impairment selection requires initial unarmed chip')
    if chip.tx.reconstruction is None and chip.tx.rx_bank is None:
        raise ValueError('Requires exponential-term receiver integration')
    original=chip.tx.receive_terms
    def terms(state):
        base=original();result=[]
        for frequency,d,i in components:
            shift=2j*math.pi*frequency
            rotation=cmath.exp(shift*state.time)
            result.extend((rotation*d*a,r+shift) for a,r in base if d)
            result.extend((rotation*i*a.conjugate(),r.conjugate()+shift) for a,r in base if i)
        return result
    chip.tx.receive_terms=MethodType(terms,chip.tx)
    chip.rx_lo_projection=dict(desired=complex(desired),image=complex(image),components=components)
