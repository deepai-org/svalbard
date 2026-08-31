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

That parent also now has a fixed two-tone full-RC PEX diagnostic: 1 mV at
2.400 GHz plus a 100 mV 2.425 GHz aggressor through its unchanged external
50-ohm source and 2.300 GHz LO. All five PVT cases complete. The desired 100
MHz component changes by at least +0.065 dB, but the 125 MHz aggressor component
is at least 39.872 dB larger. This records that the unfiltered parent contains
no adjacent-channel selectivity; it is not a blocker-tolerance or receiver
linearity result and points directly to the required IF/baseband boundary.

The first die-side RF model-validity artifact is
[`rf_ostl_coupon`](../../ip/blocks/analog/wifi_80211b/rf_ostl_coupon). It
implements comparable M5 G-S-G landing geometry for open, short, thru and a
P+ poly load. Its native run is 0-DRC, uniquely LVS-matched, and 2R/4C
full-RC extracted. This is a silicon-characterization coupon: it preserves its
floating poly-body terminal and 0.1--6 GHz OTSC measurement plan rather than
inventing an RF de-embedding or pad/package qualification from lumped PEX.

The companion active-device artifact is
[`rf_nfet_array_coupon`](../../ip/blocks/analog/wifi_80211b/rf_nfet_array_coupon).
It physically reproduces the LNA's explicit sixteen 4-um/0.28-um NFET fingers
and exposes GATE, DRAIN, SOURCE and VSS at die-side M5 landings. Its native run
is 0-DRC, uniquely LVS-matched and 390R/72C full-RC extracted; the extracted
identity check proves the intended 16 devices, not RF compact-model accuracy.
Its required 0.1--6 GHz bias/S-parameter campaign is deliberately the input to
later LNA/mixer qualification, rather than a fabricated pre-silicon RF result.

The next product work is deliberately small and sequential. The two-tone
result makes one architectural choice before another transistor/layout loop:
with the present 2.300 GHz LO, 2.400 and 2.425 GHz become 100 and 125 MHz.
A low-order on-die RC filter cannot create tens of dB of rejection over that
spacing while passing a wide 802.11b channel. A normal broad Wi-Fi RF
preselector is still necessary for antenna/package and out-of-band control,
but cannot honestly be credited with this 25 MHz separation. The selected
channel-selection boundary is consequently a real-IF ADC/DSP path, with an
explicit 0.25 V peak, 12-ENOB, 320 MS/s input budget and a 65 dB digital
125 MHz attenuation requirement. It is a requirement for the next physical
IF/baseband work, not a claim that the ADC, DSP, or receiver exists. The
testable decision record is
[`channel_selectivity_boundary.yaml`](analog/channel_selectivity_boundary.yaml)
and the byte-bound PEX budget is
[`adc_dsp_selectivity_plan.json`](../../ip/blocks/analog/wifi_80211b/rf_rx_external_lo_parent/adc_dsp_selectivity_plan.json).

The remaining product work is deliberately small and sequential.  In
particular, this track must not turn an unimplemented 12-bit converter into a
large generic-ADC project:

1. Close one physical **differential sampled-input interface** first.  Its
   declared test boundary is 0.25 V differential peak full scale, 320 MS/s,
   a 5 pF per-leg future converter/CDAC load, and a 0.25-LSB settling/noise
   allocation.  DRC/LVS/full-RC PEX must show the actual switch, clock feed,
   input buffer/loading, hold error, and PVT behavior at that boundary.  If a
   simple transmission gate cannot meet it, the evidence determines whether a
   bootstrapped/cancelled switch is warranted or whether the receiver frequency
   plan must be simplified before more converter work is started.
2. Only after that interface passes, implement a bounded converter architecture
   and its calibration observables, followed by the fixed-point channel filter
   against the frozen two-tone headroom/filter budget.  The existing PCIe CML
   error slicer is not a substitute: its demonstrated 40--150 mV window is
   hundreds of times coarser than the roughly 122 uV 12-bit code step here.
   Then compose the actual blocks with the routed parent and rerun two-tone,
   noise, linearity, compression and calibration screens.
3. Bind a measured/vendor RF preselector and matching network for its distinct
   antenna/package/out-of-band role, then measure the active transistor and
   selected passive structures alongside the
   OSTL coupon, then qualify the actual probe, pad, package and antenna/matching
   boundary with reviewed S-parameter/EM evidence.
4. Only after those gates, add an on-die bias/reference and the minimum
   calibration/control path needed by the selected 802.11b receiver boundary.

The top-level intended behavior and explicit blockers are in
[`wifi_80211b.aether`](analog/wifi_80211b.aether).  The external-passive,
external-reference boundary is a design decision for this early risk track; it
is not a claim of zero-external-component Wi-Fi.
