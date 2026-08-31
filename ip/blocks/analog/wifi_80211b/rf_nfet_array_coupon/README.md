# Wi-Fi 16-finger NFET RF characterization coupon

This is the probeable, die-side active-device replica for the Wi-Fi receive
path. It preserves the LNA core's exact 16 explicit `nfet_03v3` fingers
(`4 um` width, `0.28 um` length and alternating source/drain orientation), but
exposes separate GATE, DRAIN, SOURCE and VSS terminals with M5 landings and
local return geometry.

`run_coupon_physical.sh` generates it, renders it, runs DRC, unique LVS and
full-RC PEX, and fails closed unless the extracted circuit has all four ports
and exactly sixteen target NFETs. The passing result is therefore evidence that
the proposed silicon characterization structure is physical and corresponds to
the active LNA device array. It is deliberately **not** an S-parameter, noise,
linearity, `fT`, `fMAX`, probe-pad, package, or Wi-Fi receiver claim.

[`test_plan.json`](test_plan.json) requires calibrated multi-port wafer data,
the companion open/short/thru/load de-embedding residual, DC and bias sweeps,
and explicit temperature/stackup/probe provenance. Only reviewed measured data
can establish an RF-validity envelope to feed back into the LNA/mixer and
routed receive-parent screens.
