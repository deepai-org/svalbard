# Unified RF driver, clock and converter-reference state

Current experimental entry: `ManagedUnifiedReferenceChip` in
`system_model/connected/managed_unified_reference.py`. This is not the candidate
whose two-mode payload quality has already passed. Its full acquisition and
calibration run passed with verified source hashes in `managed-unified-calibration-launch.json`.
At this historical checkpoint, full mode-0 payload quality was incomplete.
This note does not establish current process status or qualify that run.

The local implicit solve carries four complex RF-network voltages, one driver
rail voltage, detector power, buffered readout and shared reference voltage:
12 real state variables. The autonomous PLL remains a separate event-driven
state, coupled at finite intervals with measured step sensitivity.

The equations use the existing network `C`, `G` and carrier frame:

- `C dv/dt = -(G + jωC)v + [Vs/50, 0, 0, 0]`.
- Driver source `Vs` depends on the reconstruction/modulator command and rail.
- `Cra dVrail/dt = (Vnom - Vrail)/Rra - Idriver - Ireference`.
- `dPdet/dt = adet (|vmonitor|² - Pdet)`.
- `dVreadout/dt = areadout (Pdet - Vreadout)`.
- `Cref dVref/dt = (Vtarget(Vrail) - Vref)/Rref`.

Driver and reference currents use explicit bias and nonregenerative efficiency
assumptions. Source power returned by stored charge is dissipated locally rather
than becoming negative rail current. ADC and DAC events remove charge from the
reference reservoir; replenishment subsequently loads the rail. The same
conversion energy is not separately removed from the rail as a duplicate impulse.

ADC sampling and DAC reference transfer use the existing shared object at an
already solved timestamp. The reference rejects independent future advancement.
The detector preserves its pending sampled result while continuous readout state
changes. Analog advancement does not increment conversion counts.

For each coupling interval, PLL frequency pulling uses the starting driver rail;
PLL phase and charge-pump events drive the RF network in that interval. The next
interval uses the resulting rail. Intrinsic frequency-noise tones and the original
host-supply disturbance remain present. This is a causal finite-step method, not
an exact simultaneous PLL/rail solution.

A whole feedback call stages network, rail, detector, reference and PLL state.
Failure commits none of them. Success updates the existing public objects in
place so ADC/DAC/controller references remain valid. Failure tests include a
charged reference and pending ADC readout.

Remaining closure obligations include acquired-lock and full noisy payload
quality on this exact composition, managed conversion-event coverage, recovery,
retuning, SPI-only operation, numerical convergence across the declared envelope,
current limits/headroom, output-impedance variation, reverse mux loading/kickback,
and physical parameter qualification. Local tests and the older traffic result
cannot substitute for those checks.

## Reference-load sensitivity follow-up

`connected-unified-reference-envelope.json` compares 32 paired DAC/ADC events
at 40 MS/s with 50/200 pF reservoirs and 0.5/2 pF conversion-load assumptions.
Tightening relative integration tolerance from 1e-7 to 1e-9 changes observed
values by less than 2.6e-9. With the 2 pF load, increasing the reservoir improves
the post-event minimum from 0.8511 to 0.8758 V, but maximum sampled reference
gain stays about 1.1315 versus 1.1312. Larger capacitance alone does not resolve
the repetitive-load error in this finite experiment. Buffer resistance/drive
and conversion charge need a joint design budget. These are direct-event local
results, not full payload quality, physical validation or a frozen envelope.

Reference-drive follow-up: 100 pF reservoir / 2 pF load at 40 MS/s gives sampled gain 1.1322, 1.0363 and 1.0240 at 1000, 200 and 50 ohms. The 50-ohm candidate demands about 0.599 mA observed post-event output current. Fixed bias across resistance choices is an assumption, not a power-feasibility result. A fixed-rail periodic recurrence is independently checked; using it as an exact coupled-rail oracle failed because the rail ripples. That approximation differs by up to 9.4e-5 in gain. See connected-reference-drive-budget.json.

## Finite-current reference candidate

`current_limited_reference.py` introduces separate source/sink current ceilings
into a local two-state rail/reference model. The limiter dissipates its excess
voltage-drop power; capacitor energy return does not create negative supply
current. `connected-current-limited-reference.json` checks energy residual
below 3e-20 W and numerical refinement below 3e-8 for 128 paired conversion
events at 40 MS/s, 50 ohms, 100 pF reservoir and 2 pF conversion load.

At 50 uA source/sink limits, reference falls to 0.4154 V and sample gain reaches
2.363: this candidate is unsuitable for the tested load. At 150 uA, minimum
reference is 0.9583 V and maximum gain 1.0242; 600 uA gives 0.9593 V / 1.0231.
These are local held-other-current cases, not a replacement for unified RF
quality. The next integration obligation is to use this finite-current law
in the unified analog state while retaining reference charge, rail feedback,
transactional failure behavior and actual converter timing. Physical bandwidth,
headroom and bias/current tradeoffs remain open. No selected operating envelope
or transistor implementation is qualified by this local numerical pass.

### Finite-current integration candidate

`ManagedLimitedReferenceChip` now binds `LimitedCoupledDriver` to the existing
shared reference, detector and RF network. The constitutive current law is
evaluated inside the unified ODE, so replenishment current loads the same rail
that pulls the RF PLL. This candidate currently duplicates the baseline solver
to keep running baseline experiments unchanged; consolidate that implementation
after baseline results and candidate comparison, retaining explicit current-law
selection rather than silently replacing the tested baseline.

`connected-limited-unified.json` passed short managed advancement, direct ADC/DAC
charge impulses, object identity and overloaded-rail rollback. The first harness
invocation omitted the required nonzero detector latency and failed at constructor
validation; the tested invocation sets 30 ns. Acquisition/calibration is running
in session 74592 with 50 ohms and 150 uA source/sink limits. Payload quality,
recovery and physical feasibility are not established for this candidate.

### Monitor versus acquisition ownership

The attempted acquired-monitor transport run (24007) was rejected at
`rf_coarse_start`, before acquisition or traffic: `CalibrationChip.quiet()`
requires `monitor_route == 0`. The test had enabled the reference monitor
first. Its source hashes were verified and the failed manifest retained.

The intended sequence is coarse search with monitor disconnected, wait for
qualification, select reference monitor and diagnostic ADC route while disarmed,
configure/acquire the operating mode, then capture. New ordered test 6718
implements that sequence; it is not yet a pass. Reference-loss invalidation
and both-mode host transport remain its required assertions. Reacquisition
likewise needs diagnostic routing released before quiet calibration/search.

Monitor capture also requires HostActivationChip host training. Ordered test 6718 omitted it and was deliberately terminated after static review. Replacement 65541 adds the existing 64-frame valid empty-payload switching sequence and checks readiness before requesting capture. Both-mode diagnostic transport remains unproven pending that run.

### Initial-state domain defect and guard

Direct injection of 0.09 V into the limited solver reference was incorrectly accepted: a 100 ns step recovered to 0.24 V and committed. The baseline checks the final reference only. `limited-reference-initial-boundary-audit.json` preserves this reproduction; it does not show a reachable normal-operation fault. `GuardedLimitedDriver` now rejects initial reference <=0.1 V/nonfinite values and initial rail <=minimum/nonfinite values before any advance, including zero-duration calls. Reference rejection/unchanged-state and valid recovery tests pass in connected-guarded-limited-driver.json. Consolidate this guard into the selected solver after source-frozen runs complete; current managed calibration does not yet include it. Inter-event domain crossing still requires examination.

Finite-current managed acquisition/calibration passed (74592, 351 source hashes verified): nine actual shared ADC samples, 3.089995 V final driver rail, 2.414853e-12 C conversion charge. ManagedGuardedReferenceChip now integrates the initial-state guard. Full mode1 quality runs as 88046 at 50ohm reference resistance and 150uA source/sink limits; calibration success is not a payload-quality pass.

The trained unified reference-monitor test completed both modes (65541, 354 source hashes verified). Each case delivers 64 ADC words exactly to the host and invalidates monitoring on reference loss. See connected-unified-monitor-transport.json. This is baseline finite diagnostic coverage, not finite-current guarded full traffic. ManagedDenseReferenceChip full acquisition/calibration now runs as 14659 to compare against the passed nonoptimized finite-current calibration; short state equivalence alone is not promoted to full equivalence.

ManagedDenseReferenceChip full acquisition/calibration completed (14659), with exact matching reported endpoint, correction and probe-power fields versus ManagedLimitedReferenceChip. Launch source hashes verified; see managed-dense-calibration-comparison.json. Optimization is available for subsequent integration tests, while full payload equivalence and final solver consolidation remain open.
