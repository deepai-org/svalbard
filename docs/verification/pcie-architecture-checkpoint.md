# PCIe Gen1 architecture checkpoint

This checkpoint asks whether the current work is converging on the intended
endpoint, not merely whether its leaf simulations pass. The answer is mixed:
the half-rate analog experiments are technically useful, but the system
contract is not frozen and the implementation order has drifted away from the
integration ladder in `plan.md`.

## Findings

| Question | Current evidence | Decision |
|---|---|---|
| Is the PCIe target frozen? | The project spec still has no lawful revision, electrical limits, clock domains, reference clock, supplies, temperature, package, channel, power budget, or measurable success thresholds. | No PCIe compliance or final-interface architecture can be selected yet. Continue only with explicitly bounded diagnostic contracts while Gate G0/G1 inputs are obtained. |
| Is the half-rate architecture reasonable for GF180? | Extracted TX, RX, sampler, PI, VCO and first divider experiments operate at their local 2.5 GT/s or 1.25 GHz boundaries. The 2.5 GHz VCO-bank experiment fails three of five environments, while the selected 1.25 GHz bank closes five of five. | Retain the 1.25 GHz dual-edge architecture. Do not base the primary path on a 2.5 GHz VCO without a new topology and evidence. |
| Is the PLL frequency plan defined? | The routed VCO/restorer/divider reaches 625 MHz, but `environment.reference_clock` is `null`. A 125 MHz comparison would use integer `/10`; a 100 MHz comparison requires exact `/12.5`, a dual-edge `/25`, or a different VCO plan. | Do not select a feedback divider until the external reference is frozen. A `/5` after the existing `/2` is a diagnostic 125 MHz experiment, not the PCIe PLL architecture. |
| Does the present design meet the stated power contract? | The real project power budget is unresolved. The hypothetical Aether file says 45 mW hard, but the routed clock path alone reaches 21.263 mA at 3.63 V plus 1.415 mW reference power, about 78.6 mW. TX, RX, CDR, PI and retiming power are additional. | The 45 mW value is not credible for the current topology. Freeze a real budget and either raise it or redesign around much less always-on CML, aggressive power gating and one early CML-to-CMOS boundary. |
| Are the right components being integrated first? | The plan requires externally clocked 1.25 GBd PRBS/loopback, then extracted 1000BASE-X, then externally clocked 2.5 GT/s. The serializer and analog top are absent, and there is no extracted end-to-end lane. | Restore the declared order. The serializer and externally clocked loopback are ahead of further autonomous PLL/CDR leaf expansion. |
| Are pad and channel assumptions adequate? | No pad/ESD, package, connector or channel model is selected. TX overshoot already fails its provisional pad-boundary check, and termination is frequency-dependent. | Core-only waveforms cannot close the link. Select a qualified I/O and assembly envelope before final TX/RX sizing; use provisional interfaces only when clearly labeled. |
| Is calibration an implemented system function? | Many leaves expose useful trims and interior-code PVT windows, but there is no always-available reference, observable, search controller, retained-code storage, safe-reset image or failure fallback implementation. | Stop counting programmability as calibration closure. Every retained trim needs a measurable search and manual SPI/JTAG override. |
| Is the full endpoint represented? | The PCIe project contains specifications and BFM dependency records but no endpoint RTL. Receiver detect, electrical idle, serializer, elastic buffering, analog top, shared bias/reference and clock supervisor are also absent. | The present work is a library of experimental PHY leaves, not yet a PCIe endpoint. Digital and analog integration contracts must advance together. |

## Selected architectural spine

The following choices remain justified by current evidence:

1. Use a 1.25 GHz differential half-rate clock and dual-edge 2.5 GT/s data
   path; preserve 625 MHz and lower divided clocks as observability points.
2. Keep static CML only where extracted speed or input sensitivity requires it.
   Convert once to CMOS, then use clock gating and power isolation for low-rate
   counters, calibration and protocol logic.
3. Preserve three independently reachable clock modes: direct external clock,
   reference-assisted sampling, and autonomous PLL/CDR. Neither diagnostic mode
   may require autonomous lock.
4. Retain programmable VCO bands, current, termination, RX threshold/bandwidth
   and phase, but pair each with an explicit observable and bounded search.
5. Treat every closed leaf as reusable experimental evidence until the same
   extracted parent proves its real producer, consumer, power grid and load.

The external reference, exact feedback ratio, pad/ESD family, assembly channel,
active power budget and PCIe electrical thresholds remain decisions, not
assumptions. Numerical placeholders in the hypothetical Aether source do not
override the unresolved project specification.

## Corrected implementation order

1. Define an internal, non-compliance diagnostic contract for externally
   clocked 1.25 GBd operation, including clock amplitude/common mode, supplies,
   provisional load/channel and a power ceiling.
2. Implement and physically close the missing 2:1 serializer. Compose it with
   the extracted TX, a declared provisional interconnect/load, termination, RX,
   sampler and deserializer in PRBS loopback.
3. Measure the complete composed power and timing budget at one common set of
   environments. Reduce always-on CML and duplicate restoration before adding
   more autonomous-clock circuitry.
4. Repeat the integrated lane at externally clocked 2.5 GT/s. Fail explicitly
   if the GF180/public-model or provisional I/O boundary cannot support it.
5. In parallel, freeze the lawful PCIe revision, reference clock, electrical
   limits, pads, package, board/channel, supplies, temperatures and power.
6. Only then select among integer, dual-edge fractional, or alternate-VCO PLL
   plans; close PFD/charge pump/filter/lock behavior against that real contract.
7. Add receiver detect/electrical idle, safe calibration control, clock bypass,
   analog-top PDN/substrate integration and finally protocol training.

This order does not discard the existing PLL and CDR work. It turns those
blocks into candidates behind a verified external-clock lane, so a failure in
autonomous clock generation cannot prevent useful silicon or obscure the root
cause of an integration failure.
