"""Coupled quality at the previously characterized exploratory PLL stress."""
import hashlib
import json
import sys
import traceback
from pathlib import Path

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'system_model/connected'))
from three_cap_managed_chip import ExactCenteringRetuningClock
from statistical_three_cap_quality import RepeatedObservationChip
from limited_rail_budget_pad_quality import main

RANKING = P / 'evidence/three-cap-sensitivity.json'
stress = json.loads(RANKING.read_text())
case = stress['rows'][-1]
scales = case['worst_margin_case']['scales']
values = {k: v * scales[k] for k, v in stress['nominal_filter'].items()}
values['c3'] += case['added_tuning_capacitance_f']

class StressedClock(ExactCenteringRetuningClock):
    NOISE_FILTER = None

    def __init__(self, **kwargs):
        super().__init__(filter_values=values, **kwargs)
        assert self.time == 0 and not self.reference_history
        self.current_amplitude *= scales['icp']
        self.gains.kvco *= scales['kvco']
        if self.NOISE_FILTER is not None:
            self.filter = self.NOISE_FILTER(noise_bins=128, noise_seed=1249, **values)

class StressedChip(RepeatedObservationChip):
    RF_CLOCK_CLASS = StressedClock

def launch(chip_class=StressedChip, *, prefix='', entrypoint=__file__, extra_sources=()):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=int, choices=(0, 1), default=1)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.smoke:
        chip = chip_class(adc_latency_s=30e-9, dac_latency_s=20e-9, rf_free_offset=-.08, coarse_noise_bound_hz=80e3)
        assert chip.rf_pll.filter.c3 == values['c3']
        chip.advance(100e-9)
        print('Stressed chip constructed and advanced 100 ns; traffic not tested.')
        sys.exit(0)
    files = list((P / 'system_model/connected').glob('*.py')) + [Path(__file__), Path(entrypoint), Path(__file__).with_name('statistical_three_cap_quality.py'), RANKING] + list(extra_sources)
    hashes = {str(f.relative_to(P)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report = dict(status='running', mode=args.mode, source_sha256=hashes,
                  filter_values=values, gain_scales={k: scales[k] for k in ('icp', 'kvco')},
                  limitations=['Exploratory component/load stress, not a PDK corner or yield estimate.',
                               'Calibration uncertainty remains unverified; full physical noise is not included.'])
    if chip_class.RF_CLOCK_CLASS.NOISE_FILTER is not None:
        report['noise_policy'] = dict(temperature_k=300, low_hz=100, high_hz=1e7, bins=128, seed=1249)
        report['limitations'].insert(0, 'Finite-band resistor noise only; centering-switch thermal noise omitted.')
    tag = f'three-cap-{prefix}stressed-repeated-cal'
    path = P / f'evidence/{prefix}stressed-three-cap-quality-mode{args.mode}-launch.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    try:
        main(args.mode, True, actual_chip_class=chip_class, experiment_tag=tag)
        result_path = P / f'evidence/connected-limited-rail20-pad-quality-mode{args.mode}-{tag}-phase-diagnostic.json'
        result = json.loads(result_path.read_text())
        assert result['status'] == 'passed'
        report.update(status='passed', result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest())
    except BaseException as error:
        report.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        report['source_hashes_match'] = all(hashlib.sha256((P / n).read_bytes()).hexdigest() == h for n, h in hashes.items())
        if not report['source_hashes_match']:
            report['status'] = 'invalid_source_change'
        path.write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__':
    launch()
