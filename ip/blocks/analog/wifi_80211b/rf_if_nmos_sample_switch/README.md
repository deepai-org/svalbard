# Rejected real-IF NMOS sampling-switch baseline

This is the first physical converter leaf for the selected Wi-Fi real-IF path:
two matched eight-finger NMOS sampling arrays, a symmetric 320-MS/s clock
spine, separate differential IF input/held-output routes, and local substrate
contacts.  It is deliberately a **baseline topology probe**, not an ADC or a
successful sample/hold claim.

`run_physical.sh` regenerates the layout, runs Magic DRC and Netgen LVS,
extracts coupled RC, and runs both schematic and extracted five-corner
transient probes.  The declared boundary is a 100-MHz, 0.25-V differential-peak
input centered at 1.65 V, 320 MS/s, 5 pF per held leg, finite 10-ohm IF/clock
sources, and a quarter-12-bit-LSB (30.518 uV) tracking plus aperture/hold
allocation.  The IF buffer and CDAC remain explicit bench boundaries.

The physical cell is zero-DRC and uniquely LVS-matched, with sixteen 4-um /
0.28-um NFET fingers and 113 resistors / 86 capacitors in its full-RC PEX.
That physical closure is not a performance result.  All five schematic and all
five exact-PEX cases complete, and **all fail** the allocation.  The worst
extracted aperture/hold error is 177.891 mV at SS/125 C, 5,829 times the
30.518-uV allocation.  The schematic baseline's corresponding worst error is
171.098 mV, so layout RC is a measurable increment rather than an explanation
or a tuning target for the failure.

[`nmos_sampling_switch_rejection.json`](nmos_sampling_switch_rejection.json)
binds the exact layout/PEX/testbench/runner evidence and makes the resulting
decision explicit: do not continue tuning the NMOS-only switch.  The next
physical candidate is a matched transmission gate with complementary,
overlap-controlled clocks; its topology, clock feedthrough, common-mode range,
noise, mismatch and calibration must be screened anew.  This baseline does not
establish 12-bit sampling accuracy, ADC ENOB, thermal noise, mismatch yield,
clock-jitter tolerance, an IF buffer, or an integrated receiver.
