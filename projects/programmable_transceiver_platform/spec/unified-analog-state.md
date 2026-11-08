# Coupled analog state and accounting

The planned architecture is owned by [the inventory](analog-architecture.json).
Current electrical composition is constructed in
[`baseline_envelope.py`](../verification/baseline_envelope.py), with lifecycle
integration in [`selected_lifecycle.py`](../verification/selected_lifecycle.py).
[Closure gates](mathematical-closure.json) own
remaining integration requirements.

## Retained circuit model

[`LimitedCoupledDriver`](../system_model/connected/limited_coupled_driver.py)
couples the RF network, driver rail, detector/readout, optional converter
reference, receive-filter states and optional shared pad branch. A local
configuration may omit these optional paths; it must identify those omissions.
The passive network uses the carrier-frame equation
`C dv/dt = -(G + jωC)v + drive`. Reference replenishment has explicit source
and sink current limits. Supply/domain and host-return states are included
when supplied by the composition.

Converter events remove charge from the shared reference reservoir.
Replenishment loads its supply; do not charge the supply a second time for the
same conversion energy. Charge returned by the network must follow its declared
dissipation law, not create unexplained negative supply consumption. Continuous
analog advancement must not manufacture converter samples or observations.

## Requirements for joined evidence

- Give each continuous state and converter event exactly one advancement owner.
  Detector capture and publication must remain distinct, with explicit latency.
- Include finite reference drive, headroom, conversion charge and the resulting
  rail disturbance together. Increasing reservoir capacitance alone does not
  establish repetitive-load accuracy or current feasibility.
- Reject invalid initial states and failed solves without partially committing
  the affected state. Check inter-event excursions as well as endpoints.
- Check numerical refinement for the actual coupled composition. A fixed-rail
  recurrence is a useful simplified control, not an exact oracle for a moving rail.
- Feed the same delivered-clock assumptions to the RF and wired benches.
  Explicitly prescribed clocks are valid isolated controls, not autonomous
  acquisition or supply-to-phase evidence.
- Keep startup, retuning, recovery, conversion timing and loaded waveform quality
  as separate obligations. Local conservation and successful calibration do not
  qualify payload quality or physical parameter assumptions.

The model is not a transistor or package qualification. Current failures and
uncertainties belong in [risk priorities](risk-priorities.md), rather than a
second chronological status log here.
