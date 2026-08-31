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
point, input delivery, and supply current.  Matching, source degeneration,
drain load, mixer load, bias source, antenna/filter, package, and reference are
outside the core's physical boundary.

The checked layout render is
[`wifi-lna-cs-core-layout.png`](../../docs/images/wifi-lna-cs-core-layout.png).

The next product work is deliberately small and sequential:

1. Add transistor/open-short/de-embedding and passive test structures, then
   establish an RF/EM model-validity boundary for the actual package and
   antenna/matching network.
2. Compose a probeable mixer path with external LO/IQ and verify its routed
   parent, including noise, conversion gain, linearity, and blocker screens.
3. Only after those gates, add an on-die bias/reference and the minimum
   calibration/control path needed by the selected 802.11b receiver boundary.

The top-level intended behavior and explicit blockers are in
[`wifi_80211b.aether`](analog/wifi_80211b.aether).  The external-passive,
external-reference boundary is a design decision for this early risk track; it
is not a claim of zero-external-component Wi-Fi.
