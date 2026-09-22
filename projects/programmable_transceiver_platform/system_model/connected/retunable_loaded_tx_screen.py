"""Carrier requests must preserve loaded capacitor state and oscillator phase."""
import json
import numpy as np
from chip_model import P
from retunable_loaded_tx import RetunableLoadedTxChip
from loaded_pad_observer import observe
from managed_resources import command

def main():
    c=RetunableLoadedTxChip(watchdog_s=1e-3)
    c.advance(100e-9)
    try:c.configure_rf_carrier(2437000000)
    except ValueError:pass
    else:raise AssertionError('Unqualified carrier admitted')
    assert command(c,'rf_coarse_start',2437000000)['accepted']
    c.advance(c.time+50e-6)
    assert c.coarse.qualified

    rows=[]
    for frequency in (2437000000,):
        voltage=c.loaded_tx.network.voltage.copy();clock_phase=c.rf_pll.output_phase_cycles
        omega=c.loaded_tx.network.omega;before=observe(c.loaded_tx.network,c.time,2412000000)
        c.configure_rf_carrier(frequency)
        assert np.array_equal(voltage,c.loaded_tx.network.voltage)
        assert c.rf_pll.output_phase_cycles==clock_phase
        assert c.loaded_tx.network.omega==omega
        assert observe(c.loaded_tx.network,c.time,2412000000)==before
        c.advance(c.time+20e-9)
        assert c.tx.time==c.loaded_tx.network.time==c.tx_detector.time==c.time
        rows.append(dict(target_hz=frequency,pad_magnitude=abs(c.pad_envelope())))
    before=(c.rf_pll.output_phase_cycles,c.rf_target_hz,c.loaded_tx.network.voltage.copy())
    for invalid in (2437500000,2299000000):
        try:c.configure_rf_carrier(invalid)
        except ValueError:pass
        else:raise AssertionError('Invalid retarget accepted')
        assert c.rf_pll.output_phase_cycles==before[0] and c.rf_target_hz==before[1]
        assert np.array_equal(c.loaded_tx.network.voltage,before[2])
    r=dict(status='passed',cases=rows,limitations=[
        'Managed coarse qualification at2437MHz; sustained lock and both-mode traffic not verified here.',
        'No calibrated recovery or full-chain quality after retarget.',
        'Network coordinate frame remains fixed; actual oscillator trajectory supplies frequency difference.'])
    (P/'evidence/connected-retunable-loaded-tx.json').write_text(json.dumps(r,indent=2)+'\n');print(r)

if __name__=='__main__':main()
