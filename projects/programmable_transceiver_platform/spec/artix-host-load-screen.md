# Pass 8: Artix-7 candidate and host load correction

## Primary evidence

[AMD DS181](https://docs.amd.com/v/u/en-US/ds181_Artix_7_Data_Sheet), v1.27.1, July 3 2024: Table 3 specifies up to 8 pF die input capacitance, excluding package. Table 8 gives LVCMOS33 low/high input boundaries of 0.8/2.0 V. Table 19 uses a 1.65 V input timing reference. Table 21's -1 input-logic setup/hold values are internal-pin values, not a board interface timing guarantee. Published LVDS throughput does not establish LVCMOS throughput. Source PDF SHA-256 is retained in the report.

## Fresh native-pad evidence

Run `verification/run_artix_load.sh` from this project or its absolute path. It uses the repository's bounded, pinned analog container and the unchanged native pad deck generator. Two fresh nominal 3.3 V, 25 C cases use 8 pF external lumped loading per data/clock output, alternating and PRBS7 patterns. Four existing measurement regressions passed first.

The [raw result summary](../evidence/artix-load-screen.json) records deck, waveform and log hashes. The minimum host-threshold margin across 20 bits per case is 0.799 V in the assumed ±0.2 ns aperture. This analysis includes all saved interior samples plus interpolated aperture boundaries. Clock edges are paired in order; no phase search selects a passing result. The 1.65 V reference is a measurement convention, not proof of the actual receiver's switching point. No claim of Artix timing closure follows.

The alternating pair draws 16.409 mA average from DVDD. Applying the existing per-output extrapolation and allowances produces 53.28 mA for HOST_A and **63.54 mA for HOST_B**, exceeding HOST_B's 55 mA planning ceiling. See the [power screen](../evidence/artix-load-power-screen.json). The measured extrapolation before allowances is 49.23 mA for HOST_B; the result rejects the present planning margin, not a direct measurement of a six-pad bank exceeding its supply-cell rating.

The original 5 pF result remains valid only for its load. Its passing power check does not close this 8 pF case. Package and board loading are still absent, and 8 pF is not a complete host load model. Narrow temperature/voltage operation does not remove that load or the associated power demand.

## Execution provenance and next decision

Both simulations completed and waveforms were archived. The initial harness invocation then reported failure because it expected a signoff-style `result` field absent from this characterization JSON. Requested outputs were preserved; the reproducible wrapper now treats simulation completion separately from design acceptance. No rerun is claimed. The raw archive is `scratch/transceiver-artix-load-waveforms.tar.gz`; its SHA-256 is retained in the power report.

Artix-7 remains an unqualified candidate, with no chosen package or completed DDR implementation. Next investigate host-bank power/driver options at realistic loading without changing the 50-terminal or full-rate targets. A third supply pair, lower-capacitance host, driver redesign or another electrical interface must earn its own area/power/timing evidence; merely reducing an allowance to turn the check green is not closure. Host timing, H2D behavior and protocol latency remain open in parallel with this physical issue.
