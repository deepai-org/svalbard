# 2.4 GHz Wi-Fi LNA risk macro

This is the first Wi-Fi vertical-slice macro, not a Wi-Fi receiver claim. It
tests a routed GF180 3.3 V common-source transistor core at 2.4 GHz with
external source/matching, bias, source degeneration, drain load, output
coupling, and a high-impedance mixer load explicitly in the bench.

`run_lna_physical.sh` generates the four-terminal NFET core, renders it, runs
DRC, unique LVS, full-RC PEX, and then repeats an AC voltage-gain/PVT search.
The runner claims loaded voltage gain at 2.4 GHz, valid DC operating point,
input delivery, and bounded supply current at one common *external* bias. It
also reports a five-PVT narrowband full-RC PEX **noise screen** at that same
bias. The reported bench-relative noise figure is not RF-model qualification,
receiver noise figure, or sensitivity. It does not model an on-chip reference,
bias, or calibration mechanism. Input/output matching, linearity, blocker
tolerance, LO/IQ behavior, package/antenna EM, EVM, spectral mask, and
regulatory compliance remain named obligations.

The latest review render is
[`wifi-lna-cs-core-layout.png`](../../../../../docs/images/wifi-lna-cs-core-layout.png).

At the fixed external 1.5 V bias, the current full-RC PEX narrowband screen
completes all five public PVT cases. Its largest bench-relative estimated noise
figure is 10.283 dB at SS/125 C. This is intentionally an observed feasibility
number, not an 802.11 sensitivity budget or a signoff threshold: the compact
model and lumped PEX lack the RF/passive/package validity needed to make either
claim.

The next receiver decision uses this macro together with transistor and
open/short/de-embedding structures, an external-LO/IQ fallback, and qualified
package/antenna data. A passing core therefore supports further feasibility
work; it does not establish that GF180 can deliver a compliant single-chip
802.11b radio.
