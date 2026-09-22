"""Reachability versus assumed VCO variation; identify required coarse tuning."""
import hashlib,json,time
from pathlib import Path
from chip import TransceiverChip
from shared_tx_traffic import scenario

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Sensitivity values are hypotheses, not GF180 process distributions.',
                     'Static reachability does not establish jitter, loop stability or coarse-bank realizability.',
                     'No oscillator noise in these margin-isolation cases.'])
    output=p/'evidence/fast-tuning-margin.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for free_scale,gain_scale in ((1.,1.),(.995,1.),(1.,.95),(.995,1.05)):
            for target in (2412000000,2500000000):
                c=TransceiverChip(watchdog_s=1e-3)
                pll=c.rf_pll;pll.free_hz*=free_scale;pll.kvco*=gain_scale
                c.install_segment(pll.frequency_hz-c.rf_carrier,check=False)
                needed=(target-pll.free_hz)/pll.kvco
                reachable=abs(needed)<=pll.rail
                c.configure_rf_carrier(target);c.advance(20e-6)
                row=dict(free_scale=free_scale,kvco_scale=gain_scale,target_hz=target,
                    required_control_v=needed,reachable=reachable,locked=pll.locked,
                    final_frequency_hz=pll.frequency_hz,upper_margin_hz=pll.free_hz+pll.kvco*pll.rail-target)
                report['cases'].append(row);save()
                assert pll.locked==reachable,row
                print(free_scale,gain_scale,target,reachable,flush=True)
        # Conservative static design target: keep fine control within +/-0.8 V
        # across the full RF band under exploratory +/-10% VCO variation.
        fmin,fmax=2.3e9,2.5e9;nominal_free=2.304e9
        fine_span=.8*200e6*.9
        low_shift=fmin-nominal_free*1.1+fine_span
        high_shift=fmax-nominal_free*.9-fine_span
        report['coarse_bank_static_requirement']=dict(
            fine_control_limit_v=.8,min_kvco_hz_per_v=180e6,
            required_low_shift_at_most_hz=low_shift,
            required_high_shift_at_least_hz=high_shift,
            maximum_adjacent_frequency_gap_hz=2*fine_span,
            explanation='Coarse coverage must contain both endpoint requirements; actual bank spacing must also satisfy noise/linearity and overlap margins.')
        assert any(not row['reachable'] for row in report['cases'])
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',upper_band_variation_qualified=False,elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
