# 2.4 GHz Wi-Fi LNA risk macro

This is the first Wi-Fi vertical-slice macro, not a Wi-Fi receiver claim. It
tests a routed GF180 3.3 V common-source transistor core at 2.4 GHz with
external source/matching, bias, source degeneration, drain load, output
coupling, and a high-impedance mixer load explicitly in the bench.

`run_lna_physical.sh` generates the four-terminal NFET core, renders it, runs
DRC, unique LVS, full-RC PEX, and then repeats an AC voltage-gain/PVT search.
The runner only claims loaded voltage gain at 2.4 GHz, valid DC operating point,
input delivery, and bounded supply current at one common *external* bias. It
does not model an on-chip reference, bias, or calibration mechanism. Noise
figure, input/output matching, linearity, blocker tolerance, LO/IQ behavior,
package/antenna EM, EVM, spectral mask, and regulatory compliance remain named
obligations.

The latest review render is
[`wifi-lna-cs-core-layout.png`](../../../../../docs/images/wifi-lna-cs-core-layout.png).

The next receiver decision uses this macro together with transistor and
open/short/de-embedding structures, an external-LO/IQ fallback, and qualified
package/antenna data. A passing core therefore supports further feasibility
work; it does not establish that GF180 can deliver a compliant single-chip
802.11b radio.
