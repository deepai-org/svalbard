"""One reproducible entry point for connected mathematical architecture checks.

A successful suite means its declared scenarios pass, not architectural closure
or physical qualification. Every run executes fresh checks, never old reports.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
P = HERE.parents[1]
CASES = (
    ('Phase-aware loaded managed calibration and stop', 'phase_loaded_calibration_screen.py', [], 'connected-phase-loaded-calibration.json'),
    ('Loaded pad independent frame observation', 'loaded_pad_observer_screen.py', [], 'connected-loaded-pad-observer.json'),
    ('Loaded pad host-event capture nonmutation', 'loaded_pad_capture_screen.py', [], 'connected-loaded-pad-capture.json'),
    ('Managed phase-loaded TX clock and analog event ordering', 'phase_loaded_tx_chip_screen.py', [], 'connected-phase-loaded-tx-chip.json'),
    ('Loaded RF phase event splitting and forecast purity', 'rf_phase_events_screen.py', [], 'connected-rf-phase-events.json'),
    ('Noisy oscillator phase forcing of loaded RF network', 'rf_phase_forcing_screen.py', [], 'connected-rf-phase-forcing.json'),
    ('Loaded RF carrier frame invariance and negative controls', 'rf_carrier_frame_screen.py', [], 'connected-rf-carrier-frame.json'),
    ('Managed loaded TX calibration exact updates and stop', 'loaded_tx_chip_screen.py', [], 'connected-loaded-tx-chip.json'),
    ('RF loaded network timed calibration and pad waveform', 'rf_loaded_calibration_screen.py', [], 'connected-rf-loaded-calibration.json'),
    ('RF switched network finite detector independent integration', 'rf_loaded_detector_screen.py', [], 'connected-rf-loaded-detector.json'),
    ('RF switched load charge continuity and energy balance', 'rf_switched_load_screen.py', [], 'connected-rf-switched-load.json'),
    ('RF calibration dummy load preservation and mismatch', 'rf_dummy_load_screen.py', [], 'connected-rf-dummy-load.json'),
    ('RF isolation monitor topology KCL and power audit', 'rf_isolation_load_screen.py', [], 'connected-rf-isolation-load.json'),
    ('Isolated managed TX loaded independent mode0', 'tx_wideband_screen.py', ['--mode', '0', '--managed-host', '--require-rx-quality', '--rf-fast-fraction', '.30', '--host-warmup', 'switching', '--tx-reconstruction', 'elliptic', '--managed-tx-calibration', '--detector-readout', '--relative-tx-gain', '--output-isolation', '--output', 'connected-isolated-tx-wideband-mode0.json'], 'connected-isolated-tx-wideband-mode0.json'),
    ('Isolated managed TX loaded independent mode1', 'tx_wideband_screen.py', ['--mode', '1', '--managed-host', '--require-rx-quality', '--rf-fast-fraction', '.30', '--host-warmup', 'switching', '--tx-reconstruction', 'elliptic', '--managed-tx-calibration', '--detector-readout', '--relative-tx-gain', '--output-isolation', '--output', 'connected-isolated-tx-wideband-mode1.json'], 'connected-isolated-tx-wideband-mode1.json'),
    ('Isolated managed TX host opposite-mode reopening', 'isolated_tx_recovery_screen.py', [], 'connected-isolated-tx-recovery.json'),
    ('RF TX output isolation missing-gate characterization', 'tx_output_isolation_audit.py', [], 'connected-tx-output-isolation-audit.json'),
    ('RF TX finite isolation calibration and fault transitions', 'tx_output_isolation_screen.py', [], 'connected-tx-output-isolation.json'),
    ('TX calibration bounded probe uncertainty and error-box corners', 'tx_fit_uncertainty_screen.py', [], 'connected-tx-fit-uncertainty.json'),
    ('TX nonlinear probe affine-assumption audit', 'tx_fit_discrepancy_screen.py', [], 'connected-tx-fit-discrepancy.json'),
    ('TX analytic probe settling and transfer error bounds', 'tx_probe_error_bound_screen.py', [], 'connected-tx-probe-error-bound.json'),
    ('relative IQ correction monitor gain invariance and headroom', 'tx_relative_calibration_screen.py', [], 'connected-tx-relative-calibration.json'),
    ('monitor attenuation calibration absolute gain and DAC headroom', 'tx_monitor_headroom_screen.py', [], 'connected-tx-monitor-headroom.json'),
    ('RF monitor passive loading KCL and real-power budget', 'rf_monitor_load_screen.py', [], 'connected-rf-monitor-load.json'),
    ('managed TX detector clipping abort and commit rejection', 'tx_detector_managed_screen.py', [], 'connected-tx-detector-managed.json'),
    ('combined TX calibration host opposite-mode recovery', 'managed_tx_recovery_screen.py', [], 'connected-managed-tx-recovery.json'),
    ('TX direct retarget invalidation and rejected mutation preservation', 'tx_retune_validity_audit.py', [], 'connected-tx-retune-validity-audit.json'),
('managed finite TX calibration independent duplex mode0', 'tx_wideband_screen.py', ['--mode', '0', '--managed-host', '--require-rx-quality', '--rf-fast-fraction', '.35', '--host-warmup', 'switching', '--tx-reconstruction', 'elliptic', '--managed-tx-calibration', '--output', 'connected-managed-tx-lockwait-mode0.json'], 'connected-managed-tx-lockwait-mode0.json'),
('managed finite TX calibration independent duplex mode1', 'tx_wideband_screen.py', ['--mode', '1', '--managed-host', '--require-rx-quality', '--rf-fast-fraction', '.35', '--host-warmup', 'switching', '--tx-reconstruction', 'elliptic', '--managed-tx-calibration', '--output', 'connected-managed-tx-lockwait-mode1.json'], 'connected-managed-tx-lockwait-mode1.json'),

    ('TX detector readout uncertainty and rail rejection', 'tx_detector_transfer_screen.py', [], 'connected-tx-detector-transfer.json'),
    ('managed TX calibration resource discovery', 'tx_resource_audit.py', [], 'connected-tx-resource-audit.json'),
    ('TX calibration host preparation bounded failure paths', 'tx_preparation_policy_screen.py', [], 'connected-tx-preparation-policy.json'),
    ('cubic TX envelope expansion and finite detector convolution', 'tx_output_terms_screen.py', [], 'connected-tx-output-terms.json'),
    ('TX shared LO and receiver observability counterexamples', 'tx_observability_screen.py', [], 'connected-tx-observability.json'),
    ('independent TX calibration power verification and blind spots', 'tx_calibration_verification_screen.py', [], 'connected-tx-calibration-verification.json'),
    ('TX calibration queued and pending DAC invalidation', 'tx_calibration_inflight_screen.py', [], 'connected-tx-calibration-inflight.json'),
    ('RF TX-specific calibration admission and independent RX capture', 'tx_admission_screen.py', [], 'connected-tx-admission.json'),
    ('managed TX calibration command ownership and reference cancellation', 'tx_calibration_chip_screen.py', [], 'connected-tx-calibration-chip.json'),
    ('timed TX calibration sequence cancellation and atomic commit', 'tx_calibration_sequence_screen.py', [], 'connected-tx-calibration-sequence.json'),
    ('finite TX power detector settling ADC latency and abort', 'tx_power_detector_screen.py', [], 'connected-tx-power-detector.json'),
    ('paired DAC correction quantization retained filter and headroom', 'tx_dac_correction_screen.py', [], 'connected-tx-dac-correction.json'),
    ('continuous TX reconstruction analytical controls', 'tx_reconstruction_screen.py', [], 'connected-tx-reconstruction.json'),
    ('TX reconstruction exact RX cascade and retained reset state', 'tx_reconstruction_cascade_screen.py', [], 'connected-tx-reconstruction-cascade.json'),
    ('reconstructed managed independent duplex RF quality', 'tx_wideband_screen.py', ['--managed-host','--require-rx-quality','--rf-fast-fraction','.35','--host-warmup','switching','--tx-reconstruction','elliptic','--output','connected-reconstructed-duplex-quality.json'], 'connected-reconstructed-duplex-quality.json'),
    ('output stage analytical controls and frozen trace sensitivity', 'tx_output_stage_screen.py', [], 'connected-tx-output-stage.json'),
    ('power-only TX IQ calibration precision sensitivity', 'tx_iq_calibration_screen.py', [], 'connected-tx-iq-calibration.json'),
    ('managed host activation independent duplex RF quality', 'tx_wideband_screen.py', ['--managed-host','--require-rx-quality','--rf-fast-fraction','.35','--host-warmup','switching','--output','connected-managed-host-duplex-quality.json'], 'connected-managed-host-duplex-quality.json'),
    ('host activation counting timeout and untrained stream rejection', 'host_activation_screen.py', [], 'connected-host-activation.json'),
    ('two-capacitor PLL small-signal response characterization', 'pll_filter_response_screen.py', [], 'connected-pll-filter-response.json'),
    ('independent transmit observation controls', 'tx_observer_screen.py', [], 'connected-tx-observer.json'),
    ('independent transmit waveform and spectral qualification', 'tx_wideband_screen.py', [], 'connected-tx-wideband.json'),
    ('warm retuned calibrated four-path receive quality', 'retuned_wideband_screen.py', [], 'connected-retuned-wideband.json'),
    ('managed warm coarse retune and interrupted centering recovery', 'coarse_retune_screen.py', [], 'connected-coarse-retune.json'),
    ('coarse acquired calibrated four-path RF quality', 'coarse_wideband_screen.py', [], 'connected-coarse-wideband.json'),
    ('passive recenter KCL energy guard and coarse fine retune', 'passive_recenter_screen.py', [], 'connected-passive-recenter.json'),
    ('coarse finite counter wrap CDC bounds and snapshot cancellation', 'coarse_counter_screen.py', [], 'connected-coarse-counter.json'),
    ('managed coarse RF startup and fine acquisition', 'coarse_startup_screen.py', [], 'connected-coarse-startup.json'),
    ('coarse ownership cancellation and stale command recovery', 'coarse_recovery_screen.py', [], 'connected-coarse-recovery.json'),
    ('300kHz fractional full tuning-grid acquisition', 'fractional_grid_screen.py', ['--bandwidth-hz','300000','--output','connected-fractional-grid-300k.json'], 'connected-fractional-grid-300k.json'),
    ('300kHz calibrated fractional combined wideband quality', 'calibration_wideband_screen.py', ['--bandwidth-hz','300000','--output','connected-calibration-wideband-300k.json'], 'connected-calibration-wideband-300k.json'),
    ('fractional full-grid nominal acquisition characterization', 'fractional_grid_screen.py', [], 'connected-fractional-grid.json'),
    ('fractional startup tuning-span and noise sensitivity', 'fractional_startup_screen.py', [], 'connected-fractional-startup.json'),
    ('fractional grid-hole lower-bandwidth comparison', 'fractional_grid_bandwidth_screen.py', [], 'connected-fractional-grid-bandwidth.json'),
    ('unified calibrated fractional continuous traffic and reference recovery', 'calibrated_lifecycle_screen.py', [], 'connected-calibrated-lifecycle.json'),
    ('calibration combined wideband fractional four-path quality', 'calibration_wideband_screen.py', [], 'connected-calibration-wideband.json'),
    ('calibration I/Q targets and fractional waveform quality', 'calibration_iq_screen.py', [], 'connected-calibration-iq.json'),
    ('calibration maintenance abort and restart', 'calibration_recovery_screen.py', [], 'connected-calibration-recovery.json'),
    ('calibration automatic maintenance ADC conversion', 'calibration_adc_screen.py', [], 'connected-calibration-adc.json'),
    ('calibration resource ownership and reference loss', 'calibration_ownership_screen.py', [], 'connected-calibration-ownership.json'),
    ('calibration timed comparator controller', 'calibration_controller_screen.py', [], 'connected-calibration-controller.json'),
    ('fractional wideband full-chain quality with explicit blocker frame', 'fractional_wideband_quality.py', [], 'connected-fractional-wideband-quality.json'),
    ('fractional RF oscillator-noise and conversion qualification', 'fractional_noise_screen.py', [], 'connected-fractional-noise.json'),
    ('fractional RF full-chain bandwidth/qualification comparison', 'fractional_rf_quality.py', [], 'connected-fractional-rf-quality.json'),
    ('second-order fractional feedback and bandwidth comparison', 'shaped_fractional_screen.py', [], 'connected-shaped-fractional.json'),
    ('fractional pulse-divider arithmetic and ripple measurements', 'fractional_pulse_screen.py', [], 'connected-fractional-pulse.json'),
    ('managed integer RF pulse tuning and independent tones', 'pulse_tuning_screen.py', [], 'connected-pulse-tuning.json'),
    ('both pulse loops with combined independent wideband quality', 'pulse_wideband_quality.py', [], 'connected-pulse-wideband-quality.json'),
    ('common-chip pulse RF and wired clock transport', 'pulse_rf_chip_screen.py', [], 'connected-pulse-rf-chip.json'),
    ('common-chip pulse wired clock and mode recovery', 'pulse_wired_chip_screen.py', [], 'connected-pulse-wired-chip.json'),
    ('pulse-loop finite-spectrum noise phase service', 'pump_noise_screen.py', [], 'connected-pump-noise.json'),
    ('pulse-loop rail forcing and serializer retiming', 'pump_supply_screen.py', [], 'connected-pump-supply.json'),
    ('pulse-loop reference loss and reacquisition', 'pump_reference_screen.py', [], 'connected-pump-reference.json'),
    ('pulse-loop phase service drives wired serializer', 'pump_serializer_screen.py', [], 'connected-pump-serializer.json'),
    ('atomic dual-stream scheduling rejection', 'atomic_stream_screen.py', [], 'connected-atomic-stream.json'),
    ('continuous framed TX and duplex run/abort', 'continuous_transmit_screen.py', [], 'connected-continuous-transmit.json'),
    ('continuous RX timed control and overflow abort', 'continuous_receiver_screen.py', [], 'connected-continuous-receiver.json'),
    ('monitor shutdown validity and probe-pad recovery', 'monitor_recovery_screen.py', [], 'connected-monitor-recovery.json'),
    ('internal monitor sampling and diagnostic transport', 'internal_monitor_screen.py', [], 'connected-internal-monitor.json'),
    ('timed diagnostic tile configuration and epoch fences', 'managed_tile_screen.py', [], 'connected-managed-tile.json'),
    ('diagnostic tile ADC transport and exclusive ownership', 'diagnostic_tile_screen.py', [], 'connected-diagnostic-tile.json'),
    ('local gm/C tile analytical state and recovery', 'analog_tile_screen.py', [], 'connected-analog-tile.json'),
    ('combined detector, wideband clocks, references and host pause', 'combined_detector_quality.py', [], 'connected-combined-detector-quality.json'),
    ('public detector supply-coupled lifecycle', 'receiver_detect_entry_screen.py', [], 'connected-receiver-detect-entry.json'),
    ('receiver-detect release uses only local observations', 'receiver_detect_release_policy_screen.py', [], 'connected-receiver-detect-release-policy.json'),
    ('two-way probe supply sensitivity and scheduler refinement', 'receiver_detect_feedback_screen.py', [], 'connected-receiver-detect-feedback.json'),
    ('receiver-detect current coupled to shared rail and RF clocks', 'receiver_detect_supply_screen.py', [], 'connected-receiver-detect-supply.json'),
    ('receiver detection circuit, ownership and managed recovery', 'receiver_detection_screen.py', [], 'connected-receiver-detection.json'),
    ('managed resource discovery and actual engine ownership', 'resource_inventory_screen.py', [], 'connected-resource-inventory.json'),
    ('sampled ADC overload memory and recovery', 'adc_recovery_screen.py', [], 'connected-adc-recovery.json'),
    ('signed wideband blockers with autonomous clocks', 'wideband_blocker_quality.py', [], 'connected-wideband-blocker-quality.json'),
    ('independent wideband quality with sampled clocks and four-path traffic', 'wideband_clock_quality.py', [], 'connected-wideband-clock-quality.json'),
    ('independent tuned RF response and detuning controls', 'tuned_rf_quality.py', [], 'connected-tuned-rf-quality.json'),
    ('managed RF carrier retuning and phase retention', 'rf_tuning_screen.py', [], 'connected-rf-tuning.json'),
    ('edge-driven PFD acquisition with passive pump filter', 'edge_pump_pll_screen.py', [], 'connected-edge-pump-pll.json'),
    ('compliance-limited pump acquisition and recovery', 'compliant_edge_pll_screen.py', [], 'connected-compliant-edge-pll.json'),
    ('programmable local converter relative timing', 'local_timing_screen.py', [], 'connected-local-timing.json'),
    ('explicit charge-pump filter pulses and compliance screening', 'charge_pump_filter_screen.py', [], 'connected-charge-pump-filter.json'),
    ('reference-sampled PLL stability and connected clock operation', 'sampled_clock_screen.py', [], 'connected-sampled-clock.json'),
    ('counted divider edges and integer-N reference candidate', 'integer_clock_screen.py', [], 'connected-integer-clock.json'),
    ('reproducible spectral VCO noise through autonomous loops', 'oscillator_noise_screen.py', [], 'connected-oscillator-noise.json'),
    ('continuous shared-supply pulling of autonomous RF and wired oscillators', 'oscillator_supply_screen.py', [], 'connected-oscillator-supply.json'),
    ('shared autonomous RF LO with independent reception and wired traffic', 'autonomous_rf_screen.py', [], 'connected-autonomous-rf.json'),
    ('autonomous wired PLL owns full-chip scheduling and lock gating', 'autonomous_wire_screen.py', [], 'connected-autonomous-wire.json'),
    ('bounded autonomous PLL acquisition, holdover and phase crossings', 'autonomous_pll_screen.py', [], 'connected-autonomous-pll.json'),
    ('autonomous PLL drives wired bit serialization', 'pll_serializer_screen.py', [], 'connected-pll-serializer.json'),
    ('equalizer state retention and timed boost control', 'equalizer_retraining.py', [], 'connected-equalizer-retraining.json'),
    ('live receive equalization before clock and data detection', 'wired_equalizer.py', [], 'connected-wired-equalizer.json'),
    ('wired TX channel continuity across mode reset', 'wired_tx_mode_reset.py', [], 'connected-wired-tx-mode-reset.json'),
    ('bit-level wired TX and partial-word cancellation', 'wired_bit_timing.py', [], 'connected-wired-bit-timing.json'),
    ('programmable wired TX swing and postcursor shaping', 'wired_tx_settings.py', [], 'connected-wired-tx-settings.json'),
    ('command-driven atomic local RF runs', 'managed_local_run.py', [], 'connected-managed-local-run.json'),
    ('timed programmable resource configuration and recovery', 'managed_resources.py', [], 'connected-managed-resources.json'),
    ('bounded timed management and stale-command fencing', 'timed_management.py', [], 'connected-timed-management.json'),
    ('ADC clipping telemetry and delayed validity', 'adc_clipping_lifecycle.py', [], 'connected-adc-clipping-lifecycle.json'),
    ('independent external modulated RF reception', 'external_rf_lifecycle.py', [], 'connected-external-rf-lifecycle.json'),
    ('declared combined programmable PHY candidate', 'combined_platform.py', [], 'connected-combined-platform.json'),
    ('host switching impulses drive live wired recovery', 'wired_supply_lifecycle.py', [], 'connected-wired-supply-lifecycle.json'),
    ('independent RF continuity across wired RX idle', 'independent_wired_idle.py', [], 'connected-independent-wired-idle.json'),
    ('wired received-energy idle detection', 'wired_idle_lifecycle.py', [], 'connected-wired-idle-lifecycle.json'),
    ('wired channel persistence through digital reset', 'wired_persistent_reset.py', [], 'connected-wired-persistent-reset.json'),
    ('live wired channel and transition recovery', 'live_wired_lifecycle.py', [], 'connected-live-wired-lifecycle.json'),
    ('shared ADC and DAC reference loading', 'shared_reference_lifecycle.py', [], 'connected-shared-reference-lifecycle.json'),
    ('DAC consumption and delayed analog updates', 'dac_pipeline_lifecycle.py', [], 'connected-dac-pipeline-lifecycle.json'),
    ('finite ADC conversion latency and validity', 'adc_pipeline_lifecycle.py', [], 'connected-adc-pipeline-lifecycle.json'),
    ('signed RF phase budget including ADC quantization', 'rf_phase_budget.py', [], 'connected-rf-phase-budget.json'),
    ('full-band custom multicarrier RF quality', 'rf_modulated_quality.py', [], 'connected-rf-modulated-quality.json'),
    ('continuous multipole RF receive filtering', 'rf_multipole_screen.py', [], 'connected-rf-multipole-screen.json'),
    ('wanted bandwidth and RF stopband screening', 'rf_selectivity_screen.py', [], 'connected-rf-selectivity-screen.json'),
    ('RF held-out waveform quality and negative controls', 'rf_quality_screen.py', [], 'connected-rf-quality-screen.json'),
    ('RF phase events and simultaneous combined impairments', 'rf_phase_lifecycle.py', [], 'connected-rf-phase-lifecycle.json'),
    ('RF blockers before nonlinear conversion and filtering', 'rf_blocker_lifecycle.py', [], 'connected-rf-blocker-lifecycle.json'),
    ('independent RF oscillator envelope conversion', 'rf_lo_lifecycle.py', [], 'connected-rf-lo-lifecycle.json'),
    ('management diagnostics and capture register reads', 'diagnostic_lifecycle.py', [], 'connected-diagnostic-lifecycle.json'),
    ('local receive routing and gain selection', 'local_routing_lifecycle.py', [], 'connected-local-routing.json'),
    ('programmable TX and RX filter settings', 'programmable_filters_lifecycle.py', [], 'connected-programmable-filters.json'),
    ('repeated memory epochs and validity reset', 'memory_rearm_lifecycle.py', [], 'connected-memory-rearm-lifecycle.json'),
    ('management-only finite RF operation', 'management_only_lifecycle.py', [], 'connected-management-only-lifecycle.json'),
    ('memory playback owns DAC requests', 'playback_memory_lifecycle.py', [], 'connected-playback-memory-lifecycle.json'),
    ('one-shot capture in integrated traffic', 'capture_memory_lifecycle.py', [], 'connected-capture-memory-lifecycle.json'),
    ('host service pauses with running chip clocks', 'service_pause_lifecycle.py', [], 'connected-service-pause-lifecycle.json'),
    ('source visibility lag and phase', 'source_visibility_lifecycle.py', [], 'connected-source-visibility-lifecycle.json'),
    ('common-reference payload and independent host service', 'matched_rate_lifecycle.py', [], 'connected-matched-rate-lifecycle.json'),
    ('DAC sensitivity to shared switching supply', 'dac_supply_lifecycle.py', [], 'connected-dac-supply-lifecycle.json'),
    ('both host buses drive shared supply', 'return_supply_lifecycle.py', [], 'connected-return-supply-lifecycle.json'),
    ('host switching and shared supply sensitivity', 'shared_supply_lifecycle.py', [], 'connected-shared-supply-lifecycle.json'),
    ('receiver impairments in sustained connected model', 'receiver_impairments.py', [], 'connected-receiver-impairments.json'),
    ('causal reference in sustained loop-driven traffic', 'causal_reference_lifecycle.py', [], 'connected-causal-reference-lifecycle.json'),
    ('sustained traffic with dynamic loop and interventions', 'clocked_sustained_lifecycle.py', [], 'connected-clocked-sustained-lifecycle.json'),
    ('active clock disturbances and causal edge faults', 'clock_disturbance_lifecycle.py', [], 'connected-clock-disturbance-lifecycle.json'),
    ('loop phase drives ADC and DAC edges', 'loop_driven_edges.py', [], 'connected-loop-driven-edges.json'),
    ('dynamic clock lock and lifecycle gating', 'clock_lock_lifecycle.py', [], 'connected-clock-lock-lifecycle.json'),
    ('sustained four-path traffic', 'sustained_lifecycle.py', [], 'connected-sustained-lifecycle.json'),
    ('partial return-frame abort and epoch recovery', 'return_epoch_recovery.py', [], 'connected-return-epoch-recovery.json'),
    ('bounded jitter in persistent four-path model', 'jitter_lifecycle.py', [], 'connected-jitter-lifecycle.json'),
    ('four paths in persistent controller', 'wired_return_lifecycle.py', [], 'connected-wired-return-lifecycle.json'),
    ('persistent sampled RF and framed host return', 'rf_return_lifecycle.py', [], 'connected-rf-return-lifecycle.json'),
    ('independent DAC clock with shared lifecycle', 'timed_lifecycle.py', [], 'connected-timed-lifecycle.json'),
    ('persistent whole-chip lifecycle and mode changes', 'whole_chip_lifecycle.py', [], 'connected-whole-chip-lifecycle.json'),
    ('modulated RF and simultaneous wired paths', 'chip_model.py', ['--modulated'], 'connected-platform-modulated.json'),
    ('wired acquisition phase/frequency', 'chip_model.py', ['--clock-sweep'], 'connected-platform-clock-sweep.json'),
    ('independent host service clock', 'chip_model.py', ['--host-clock-sweep'], 'connected-platform-host-clock-sweep.json'),
    ('framed multicarrier RF', 'multicarrier_screen.py', [], 'connected-multicarrier-screen.json'),
    ('wired clock reset and retraining', 'reset_retraining.py', ['--reset-clock'], 'connected-clock-reset-retraining.json'),
    ('finite burst codec and malformed payload', 'burst_codec.py', [], 'connected-burst-codec.json'),
    ('timed burst return and near-capacity phase sweep', 'burst_return_screen.py', [], 'connected-burst-return.json'),
    ('late burst corruption and RF fault propagation', 'burst_fault_screen.py', [], 'connected-burst-fault.json'),
    ('RF reset with framed drain barrier', 'rf_reset_transport.py', [], 'connected-rf-reset-transport.json'),
)
CLOSURE = P/'spec/mathematical-closure.json'
GAPS = [row['id']+': '+row['remaining'] for row in
        json.loads(CLOSURE.read_text())['requirements'] if row['status']!='complete']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = sorted(set((P/'system_model').rglob('*.py')) |
                   set((P/'verification').glob('*.py')) |
                   set((P/'spec').glob('*top-profile.json')) |
                   {P/'spec/contract.json', P/'spec/mathematical-top-profile.json', CLOSURE, P/'spec/block-diagram.md', P/'spec/clock-rate-ownership.md'})
    return {str(path.relative_to(P)): digest(path) for path in paths}


def report_accepted(report):
    # Legacy screens use descriptive status strings; preserve those contracts,
    # but never accept an explicit failure or a false top-level quality gate.
    if not isinstance(report,dict) or not isinstance(report.get('status'),str):return False
    if not report['status'] or report['status'] in ('failed','error','running','invalidated_by_source_changes'):return False
    if 'quality_pass' in report and report['quality_pass'] is not True:return False
    return True


def main():
    if not __debug__:
        raise RuntimeError('Run without -O: mathematical acceptance checks use assertions')
    before = sources()
    report = dict(status='running', complete_architecture=False,
                  physical_qualification=False, source_hashes=before,
                  scenarios=[], remaining_architecture_gaps=GAPS)
    destination = P/'evidence/connected-architecture-suite.json'
    logs = P/'evidence/connected-architecture-logs'
    logs.mkdir(exist_ok=True)
    def save():
        destination.write_text(json.dumps(report, indent=2)+'\n')
    save()
    for index, (name, module, arguments, artifact) in enumerate(CASES):
        print(f'Running {name}', flush=True)
        start = time.monotonic()
        output = P/'evidence'/artifact
        # Existing evidence stays until replaced by its owner. Successful exit
        # must also produce a fresh report; stale artifacts cannot pass a run.
        prior = output.stat().st_mtime_ns if output.exists() else None
        log = logs/f'{index:02d}-{Path(module).stem}.log'
        with log.open('w') as stream:
            result = subprocess.run([sys.executable, str(HERE/module), *arguments],
                                    stdout=stream, stderr=subprocess.STDOUT)
        fresh = output.exists() and output.stat().st_mtime_ns != prior
        evidence_valid=False;report_error=None
        if fresh:
            try:evidence_valid=report_accepted(json.loads(output.read_text()))
            except (ValueError,OSError) as error:report_error=str(error)
        passed = result.returncode == 0 and fresh and evidence_valid
        row = dict(name=name, command=[module, *arguments], passed=passed,
                   exit_code=result.returncode, evidence_valid=evidence_valid, report_error=report_error, seconds=time.monotonic()-start,
                   log=str(log.relative_to(P)), log_sha256=digest(log))
        if fresh:
            row.update(evidence=str(output.relative_to(P)), evidence_sha256=digest(output))
        report['scenarios'].append(row)
        save()
        if not passed:
            report['status'] = 'failed'
            save()
            raise RuntimeError(f'{name} failed; see {log}')
        print(f'Passed {name} ({row["seconds"]:.1f}s)', flush=True)
    report['sources_unchanged'] = before == sources()
    report['status'] = 'passed' if report['sources_unchanged'] else 'invalidated_by_source_changes'
    save()
    if not report['sources_unchanged']:
        raise RuntimeError('Sources changed during the suite; evidence is not a consistent snapshot')
    print(f'All {len(CASES)} scenarios passed. Architecture closure remains false.\n{destination}')


if __name__ == '__main__':
    main()
