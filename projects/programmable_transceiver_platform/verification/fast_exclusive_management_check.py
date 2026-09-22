"""Serialized engine selection: deferred apply, rejection and epoch fences."""
import hashlib,json
from pathlib import Path
from fast_exclusive_engine import ExclusiveEngineChip
from fast_loaded_output import P
from managed_resources import command

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    c=ExclusiveEngineChip(watchdog_s=1e-3)
    token,apply,reply=c.submit('engine_select',c.time,c.epoch,c.rx_generation,1)
    c.advance(apply-1e-12);assert c.active_engine=='none'
    c.advance(apply);assert c.active_engine=='rf'
    assert c.read_reply(token,reply)['accepted']
    assert command(c,'engine_status')['value']==1
    assert not command(c,'engine_select',3)['accepted'] and c.active_engine=='rf'
    assert not command(c,'engine_status',1)['accepted']
    # Existing serialized epoch fencing must precede ownership changes.
    token,_,reply=c.submit('engine_select',c.time,c.epoch+1,c.rx_generation,2)
    assert not c.read_reply(token,reply)['accepted'] and c.active_engine=='rf'
    c.configure(0,c.time);c.advance(c.time+8e-6)
    assert not command(c,'engine_select',2)['accepted'] and c.active_engine=='rf'
    assert command(c,'stop')['accepted']
    assert command(c,'ack_abort')['accepted'] and command(c,'ack_drain')['accepted']
    assert command(c,'engine_select',2)['accepted'] and c.active_engine=='wire'
    assert command(c,'engine_status')['value']==2
    assert not command(c,'tx_cal_start')['accepted']
    assert command(c,'engine_select',0)['accepted']
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[P/'verification'/n for n in ('fast_loaded_output.py','fast_exclusive_engine.py','fast_exclusive_management_check.py')]
    out=dict(status='passed',source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        checks=['deferred selection at apply edge','reserved payload rejection','stale epoch rejection','live switch rejection','stopped switch acceptance','inactive calibration rejection','status readback'],
        limitations=['Serialized transaction timing model, not SPI-pin or RTL opcode qualification.',
                    'Analog clock/bias shutdown and shared synthesizer implementation remain open.'])
    (P/'evidence/fast-exclusive-management.json').write_text(json.dumps(out,indent=2)+'\n');print(out['checks'])
if __name__=='__main__':main()
