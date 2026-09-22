"""Common-chip output distortion reaches loopback without altering external RX."""
import hashlib,json,time
from pathlib import Path
from chip import TransceiverChip
from shared_tx_traffic import scenario

def run(route,distorted):
    params=dict(gain_imbalance_db=.25 if distorted else 0.,phase_error_deg=2. if distorted else 0.,lo_feedthrough=.0025 if distorted else 0.,cubic=.06 if distorted else 0.)
    c=TransceiverChip(output_parameters=params,watchdog_s=1e-3)
    if route=='external':c.external_source([.15+.05j],0.,1.,offset_hz=250e3)
    c.advance(8e-6)
    # Direct analog stimulus isolates routing; managed calibrated traffic is a
    # separate acceptance case. No controller receives hidden plant state.
    c.tx.apply_sample(.2+.1j,c.time)
    c.configure(0,c.time);c.advance(c.time+8e-6)
    c.capture(32,c.time+100e-9);c.advance(c.time+3e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.host_samples)==32
    return c.host_samples,c.analog_samples

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    a,x=run('loopback',False);b,y=run('loopback',True)
    delta=max(abs(u-v) for u,v in zip(x,y));assert delta>1e-4 and a!=b
    a,x=run('external',False);b,y=run('external',True)
    assert a==b and x==y
    assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    (p/'evidence/fast-loopback-chip.json').write_text(json.dumps(dict(status='passed',source_sha256=hashes,
        loopback_analog_change=delta,external_rx_identical=True,elapsed_s=time.monotonic()-start,
        physical_qualification=False,limitations=['Single-mode direct analog stimulus, not calibrated four-path traffic.',
        'Output distortion is memoryless and unloaded; physical coupling remains unqualified.']),indent=2)+'\n')
    print('Common loopback sensitivity and external isolation passed',delta)
if __name__=='__main__':main()
