"""Experimental managed source/LO/shared-detector connection to coupled driver.

Driver rail is currently local. It does not yet pull the autonomous PLL or shared
reference; this adapter is not the selected full-chip quality candidate.
"""
import numpy as np
from programmable_calibration_dwell import ProgrammableDwellChip
from rf_driver_transient import CoupledDriver

class CoupledLoad:
    def __init__(self,driver):
        self.driver=driver;self.network=driver.network;self.detector=driver.detector
    def advance(self,time,terms):
        origin=self.network.time;data=np.asarray(terms,complex)
        def source(t):return complex(np.sum(data[:,0]*np.exp(data[:,1]*(t-origin))))
        self.driver.advance(time,source,max_step=1e-9)
        return self.network.voltage.copy()

class ManagedCoupledDriverChip(ProgrammableDwellChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        driver=CoupledDriver(network=self.loaded_tx.network,detector=self.tx_detector)
        self.loaded_tx=CoupledLoad(driver)
