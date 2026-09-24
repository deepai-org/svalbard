"""Canonical composition checks; missing system scenarios remain explicit."""
import hashlib
import json
from pathlib import Path
import numpy as np
from full_chip_model import make_chip, parameters, BACKGROUND_A
from fast_loaded_output import P
from managed_resources import command


def reject(action):
    try:action()
    except ValueError:return
    raise AssertionError('Forbidden operation accepted')


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    files=(list((P/'system_model/connected').glob('*.py'))+
           list((P/'system_model/architecture_fast').glob('*.py'))+
           [P/'verification'/name for name in ('full_chip_model.py','full_chip_check.py',
            'fast_exclusive_engine.py','fast_loaded_output.py','host_bank_supply.py',
            'stream_codec.py','transport_model.py','check_contract.py')]+[P/'spec/contract.json'])
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',canonical_model=parameters(),source_sha256=hashes,
        checks=[],full_chip_closure=False,physical_qualification=False,
        remaining=['Both wired and RF profiles on this exact constructor.',
            'Independent RF quality, calibration accuracy and uncertainty envelopes.',
            'Sustained duplex service, stalls, queue bounds and electrical host sampling.',
            'Reference loss/reacquisition, calibrated retuning and active-to-stopped handovers.',
            'SPI-only operation, supported resource routes and RTL/CDC agreement.',
            'Complete declared current/noise budgets and a fresh common-source regression.',
            'Protocol-specific electrical, deadline, waveform and lifecycle gates for all intended profiles.'])
    output=P/'evidence/canonical-controls.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    def checked(name):
        report['checks'].append(name);save();print(name,flush=True)
    save()
    try:
        c=make_chip();o=c.analog_owner
        assert c.protocol_requirements == report['canonical_model']['protocol_profiles']
        for profile in c.protocol_requirements:
            if profile['model_status']=='requirements_only':
                try: make_chip(protocol=profile['id'])
                except NotImplementedError: pass
                else: raise AssertionError('Unimplemented protocol was accepted')
        reject(lambda: make_chip(protocol='unknown'))
        checked('Protocol inventory and rejection of requirements-only or unknown profiles')
        assert o is not None and o.domains is not None and o.host_bank is not None
        assert c.adc_reference is c.dac_reference is o.reference
        assert c.output_network is o.network and c.tx.rx_bank is o.rx_bank
        assert c.return_q==0 and o.host_bank.externally_owned
        reject(lambda:c.configure(0,c.time))
        for engine in ('rf','wire','none','rf'):
            before=o.host_bank.state.copy();clock=c.time
            c.select_engine(engine)
            assert c.time==clock and np.array_equal(before,o.host_bank.state)
            assert tuple(o.domain_load(c.time,o.domains.voltage))==BACKGROUND_A[engine]
            assert not c.tx_cal.valid and not c.coarse.qualified
            if engine!='wire':reject(lambda:c.accept_wire(17))
            if engine!='rf':reject(lambda:c.execute_management('rf_coarse_start',2437000000,c.time))
            c.advance(c.time+2e-9)
            assert c.time==o.time==o.host_bank.time==o.domains.time
            assert np.array_equal(o.host_bank.state[:7],o.domains.voltage)
            c.emitted_return_word(1023 if engine=='rf' else 0,c.time)
        c.advance(c.time+3e-9)
        h=o.host_bank;d=o.domains
        residual=d.source_energy_j-d.feed_loss_j-d.load_energy_j-d.impulse_energy_j-(h.cap_energy()-h.initial_energy)
        assert abs(residual)<1e-17
        assert max(abs(h.injected_charge-h.consumed_charge-h.pending_charge))<1e-24
        report['energy_residual_j']=float(residual)
        checked('Shared physical ownership, mode loads, retained analog state and event accounting')

        c=make_chip()
        token,apply,reply=c.submit('engine_select',c.time,c.epoch,c.rx_generation,1)
        c.advance(apply-1e-12);assert c.active_engine=='none'
        c.advance(apply);assert c.active_engine=='rf'
        assert c.read_reply(token,reply)['accepted']
        assert command(c,'engine_status')['value']==1
        assert not command(c,'engine_select',3)['accepted']
        token,_,reply=c.submit('engine_select',c.time,c.epoch+1,c.rx_generation,2)
        assert not c.read_reply(token,reply)['accepted'] and c.active_engine=='rf'
        checked('Serialized apply timing, status, reserved selector and stale epoch rejection')
        assert command(c,'engine_select',2)['accepted']
        c.configure(1,c.time)
        assert not command(c,'engine_select',1)['accepted'] and c.active_engine=='wire'
        assert command(c,'stop')['accepted']
        assert command(c,'ack_abort')['accepted'] and command(c,'ack_drain')['accepted']
        assert command(c,'engine_select',0)['accepted'] and c.active_engine=='none'
        checked('Armed handover rejection and serialized stop/acknowledge/release')
        assert all(hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detailed',action='store_true',help='Explicitly allow the slow coupled transient suite')
    args=parser.parse_args()
    if not args.detailed:parser.error('Use make transceiver-math-fast for bounded iteration; --detailed explicitly opts into the slow coupled suite')
    main()
