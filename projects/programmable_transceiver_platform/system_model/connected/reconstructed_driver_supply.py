"""Local reconstruction/modulator → coupled driver/rail connection."""
import numpy as np
from tx_output_terms import output_terms

def advance(tx,driver,end,parameters,**solver_options):
    if tx.time!=driver.time:raise ValueError('TX/driver clock mismatch')
    origin=tx.time
    terms=output_terms(tx.transmit_terms(),**parameters) or [(0j,0j)]
    data=np.asarray(terms,complex)
    # Capture the current segment; adaptive solver evaluations do not advance TX.
    def command(time):return complex(np.sum(data[:,0]*np.exp(data[:,1]*(time-origin))))
    driver.advance(end,command,**solver_options)
    tx.advance(end)
