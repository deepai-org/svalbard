"""Fast connected architecture acceptance. Physical feasibility is a separate gate."""
import cmath
import math
import hashlib
import json
import sys
import time
from pathlib import Path
P=Path(__file__).resolve().parents[2]
D=P/'system_model/connected'
sys.path.insert(0,str(D))
from oscillator_supply_lifecycle import OscillatorSupplyChip
from sustained_lifecycle import run
from chip_model import decode_iq
from rf_modulated_quality import Multicarrier
from rf_quality_screen import quality,controls as quality_controls


class ObservedChip(OscillatorSupplyChip):
    """External ideal RF probe; never feeds back into the chip or receiver."""
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.tx_probe=[];self.probe_times=[]
    def convert_adc(self,value):
        t=self.tx.time
        phase=self.tx.tx_lo_phase+2*math.pi*self.tx.tx_lo_hz*t
        self.tx_probe.append(self.tx.output_value(t)*cmath.exp(1j*phase))
        self.probe_times.append(t)
        return super().convert_adc(value)


def simulate(mode,sign,independent):
    chips=[]
    def factory(**kw):
        options=dict(load_capacitance=0) if sign==0 else dict(
            load_capacitance=1e-12,dac_reference_load_capacitance=.2e-12,
            coupling_per_v=sign,dac_coupling_per_v=sign,
            return_charge_per_transition=50e-15,rf_hz_per_v=sign*1e6,
            wire_hz_per_v=sign*1e5,
            frontend=dict(gain_error=sign*.03,phase_error=sign*.03,
                          saturation=.8,noise_rms=.001,seed=800))
        c=ObservedChip(**options,**kw)
        if independent:
            source=Multicarrier(seed=828)
            c.external_source(source(1024,40e6),0,25e-9,offset_hz=250e3)
        chips.append(c);return c
    traffic=run(mode,0,frames=16,chip_factory=factory,matched_reference=True,
                waveform=Multicarrier(seed=804))
    c=chips[0]
    assert c.rf_pll.locked and c.wire_pll.locked
    values=[decode_iq(w,c.bits) for w in c.host_samples]
    # Exercise reference-loss admission and opposite-mode reopening on this same
    # chip after actual bidirectional traffic, retaining analog state semantics.
    c.set_reference(False,c.time)
    assert c.state=='draining' and not c.session.enabled('rf') and not c.session.enabled('wire')
    c.advance(c.time+1e-6)
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.set_reference(True,c.time);c.configure(1-mode,c.time)
    c.advance(c.time+5e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    return traffic,values,c.tx_probe,c.probe_times,dict(reference_loss_disables_paths=True,opposite_mode_reacquired=True)


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic();quality_controls()
    files=list(D.glob('*.py'))+[Path(__file__),P/'verification/stream_codec.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',abstraction='connected averaged-clock complex-envelope architecture',
        physical_qualification=False,complete_architecture=False,cases=[],source_sha256=hashes,
        assumptions=['All analog parameter values are hypotheses, not GF180 characterization.',
          'RF PLL uses averaged feedback; physical integer-edge PLL remains a separate refinement.',
          'Waveform quality uses an external frozen complex-gain fit, not validated on-chip calibration.',
          'Reference and supply use lumped RC/charge equations; package/parasitics are unqualified.',
          'Finite records and selected faults do not establish exhaustive lifecycle coverage.',
          'External FPGA provides protocols/modem; no PCIe endpoint or Wi-Fi compliance claim.'])
    output=P/'evidence/fast-whole-chip.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            for independent in (False,True):
                baseline,reference,tx_reference,reference_times,recovery=simulate(mode,0,independent)
                for sign in (-1,1):
                    traffic,measured,tx_measured,times,recovery=simulate(mode,sign,independent)
                    assert times==reference_times, "Do not conceal clock errors by realigning observations"
                    q=quality(reference,measured)
                    txq=quality(tx_reference,tx_measured)
                    split=len(tx_measured)//4
                    corrupted=tx_measured[:split]+[-v for v in tx_measured[split:]]
                    assert not quality(tx_reference,corrupted)["screen_pass"]
                    row=dict(mode=mode,independent_rf_input=independent,impairment_sign=sign,
                             traffic=traffic,rf_quality=q,independent_tx_quality=txq,
                             tx_phase_fault_detected=True,recovery=recovery)
                    report['cases'].append(row);save()
                    print(mode,independent,sign,q['corrected_relative_rms'],q['screen_pass'],flush=True)
                    assert q['screen_pass'] and txq['screen_pass'],row
        assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',functional_scenarios_passed=True,elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc),elapsed_s=time.monotonic()-start);raise
    finally:save()
    print('Connected architecture scenarios passed in',round(report['elapsed_s'],2),'seconds.')

if __name__=='__main__':main()
