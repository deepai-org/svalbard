"""Actual reconstruction and nonlinear output driving the coupled rail/network."""
import json,copy
import numpy as np
from chip_model import P
from tx_dac_correction_screen import make
from tx_output_candidate import PARAMETERS
from rf_driver_transient import CoupledDriver
from reconstructed_driver_supply import advance

def main():
    tx=make(12);driver=CoupledDriver();driver.network.configure(True,False)
    txfine=copy.deepcopy(tx);fine=copy.deepcopy(driver)
    rows=[];maxerror=0.
    for index in range(12):
        start=index*25e-9;end=(index+1)*25e-9
        value=.15*np.exp(.7j*index)+.07*np.exp(-.3j*index)
        tx.apply_sample(value,start);txfine.apply_sample(value,start)
        advance(tx,driver,end,PARAMETERS,max_step=1e-9)
        advance(txfine,fine,(start+end)/2,PARAMETERS,max_step=.25e-9,rtol=1e-10,atol=1e-13)
        advance(txfine,fine,end,PARAMETERS,max_step=.25e-9,rtol=1e-10,atol=1e-13)
        error=float(max(abs(driver.network.voltage-fine.network.voltage)))
        maxerror=max(error,maxerror)
        assert error<1e-7 and abs(driver.rail_v-fine.rail_v)<1e-7
        assert tx.time==driver.time==end
        rows.append(dict(time_s=end,pad_magnitude_v=float(abs(driver.network.voltage[1])),rail_v=driver.rail_v))
    assert max(r['pad_magnitude_v'] for r in rows)>.01
    assert min(r['rail_v'] for r in rows)<3.1
    report=dict(status='passed',dac_updates=12,max_refinement_voltage_error_v=maxerror,trace=rows,
        limitations=['Local real reconstruction/modulator segments and driver feedback; ideal carrier frame.',
            'Autonomous LO, detector integration and shared full-chip supply/clock coupling remain absent.',
            'Finite record and assumed driver law; no waveform/protocol or physical qualification.'])
    (P/'evidence/connected-reconstructed-driver-supply.json').write_text(json.dumps(report,indent=2)+'\n');print('Passed12 updates; max refined error',maxerror)

if __name__=='__main__':main()
