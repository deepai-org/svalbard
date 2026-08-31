# Wi-Fi/NB-IoT radio — Wi-Fi evidence track

This is the product-facing Wi-Fi track for the portfolio's
`wifi_nbiot_radio.wifi_dsss` milestone.  It is intentionally staged: a
physically checked 2.4 GHz receive-side LNA core is useful only as a feasibility
gate, not as a claim that an 802.11 radio is integrated, compliant, or ready
for fabrication.

The current executable evidence is
[`rf_lna`](../../ip/blocks/analog/wifi_80211b/rf_lna).  Its focused runner
creates a GF180 layout, runs DRC and LVS, extracts full RC, and tests a fixed
external 1.5 V gate bias across five public PVT environments.  The passing
claim is restricted to loaded small-signal voltage gain at 2.4 GHz, a valid DC
point, input delivery, and supply current. A second full-RC PEX narrowband
noise screen completes all five cases, with a worst bench-relative estimate of
10.283 dB. It is not a qualified RF noise figure or receive-sensitivity claim.
Matching, source degeneration, drain load, mixer load, bias source,
antenna/filter, package, and reference are outside the core's physical
boundary.

The checked layout render is
[`wifi-lna-cs-core-layout.png`](../../docs/images/wifi-lna-cs-core-layout.png).

The second executable primitive is the physically checked
[`rf_switch_mixer`](../../ip/blocks/analog/wifi_80211b/rf_switch_mixer): a
two-bank, external-LO differential switching core. Its exact full-RC PEX
transient screen passes the five public PVT cases with a 2.4 GHz RF source,
2.3 GHz complementary LO, and a measured 100 MHz differential IF component.
The weakest observed conversion is -0.664 dB. This is a bounded leaf screen,
not an LNA-to-mixer routed parent or a mixer performance qualification.

The current composed evidence is
[`rf_rx_external_lo_parent`](../../ip/blocks/analog/wifi_80211b/rf_rx_external_lo_parent).
It physically places and routes the LNA-to-mixer RF net, includes an owned
ground connection, and passes 0-DRC, unique-LVS, 219R/168C full-RC PEX plus
five PVT external-LO conversion cases. The worst observed 100 MHz differential
conversion is -3.402 dB at SS/125 C. Its source, bias, drain load, LO and IF
loads are still deliberately external; this is a routed feasibility parent,
not a receiver noise, linearity, sensitivity, or compliance claim.

The next product work is deliberately small and sequential:

1. Add transistor/open-short/de-embedding and passive test structures, then
   establish an RF/EM model-validity boundary for the actual package and
   antenna/matching network.
2. Expand the routed parent with noise, linearity, isolation and blocker
   screens, then add the selected IF/baseband boundary.
3. Only after those gates, add an on-die bias/reference and the minimum
   calibration/control path needed by the selected 802.11b receiver boundary.

The top-level intended behavior and explicit blockers are in
[`wifi_80211b.aether`](analog/wifi_80211b.aether).  The external-passive,
external-reference boundary is a design decision for this early risk track; it
is not a claim of zero-external-component Wi-Fi.
