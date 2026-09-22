# Ricardo Nunes TT07 SAR ADC review

Reviewed 2026-09-20 at the user's request. This is a design-reference review,
not a simulated GF180 port or a change to the retained ADC.

Sources inspected:
- https://tinytapeout.com/chips/tt07/tt_um_rnunes2311_12bit_sar_adc
- Wrapper repository https://github.com/rnunes2311/tt07-12bit_SAR_ADC at
  8552c5feec6dc6641e0f6fefb52748b432064b98.
- Its pinned core submodule https://github.com/rnunes2311/SAR_ADC_12bit at
  e830a7501b718e00acdbaa7f620a72dc49c078cd (also retrieved core HEAD).
- Core README, layout/SAR_ADC_12bit_sch.spice, state_machine.v,
  simulations/DNL_INL_extractor.py and schematic hierarchy inspected locally.
  Repositories declare Apache-2.0. No third-party circuit source copied into our
  implementation. Review checkouts are under /tmp/svalbard-*-review.

## Useful experiments for our design

1. Compare its IMCS/common-mode-based DAC switching sequence against our actual
   switching schedule. Our reference-driver failures make load reduction worth
   testing, not merely stronger regulation. Use our resolution, GF180 capacitors,
   conversion deadline and real reference drivers; measure signed charge on every
   reference including common mode, peak demand, decision error and acquisition.
   Reduced demand is a hypothesis, not a finding from this review. Moving current
   demand to VCM is not eliminating it.
2. Inspect its preamplifier and analog comparator-offset storage/update circuit
   when implementing calibration. Test range, polarity, convergence, residual
   offset, leakage and timing under our GF180 models. This cannot correct our
   code-dependent reference droop or replace noise/linearity verification.
3. Adapt its explicit switch sequencing and break-before-make concept to actual
   transistor-generated controls. Our selected ideal phase separation is not a
   physical timing implementation. Include adverse skew and real gate loads.
4. Retain the extracted-capacitance-to-DNL/INL analysis idea for the layout stage.
   Before layout, equivalent charge-domain sweeps can examine assumed mismatch
   and parasitic scenarios. These do not replace full transistor settling/noise
   tests or establish bounds on undisclosed mismatch.

## Why it is not a drop-in solution

The documented 20MHz clock gives1.25MS/s at16cycles/conversion, below our radio
converter throughput objective. Twelve output bits do not demonstrate12ENOB.
TinyTapeout feedback reports operation but also noise, distorted output and
missing codes under some tests. The core README's11.8ENOB is explicitly without
noise; its verification table includes unresolved RC-extracted and corner cases.
Its older submission-status checklist is not current silicon status.

VREF, VREF_GND and VCM are external inputs: this design does not demonstrate an
integrated reference driver solving our current reference problem. Its tiny
metal capacitor geometry and1.8V Sky130 device choices require new GF180 design
and verification. The preamplifier uses several threshold/device variants;
renaming models or scaling dimensions is insufficient. The schematic netlist has
an empty CDAC subcircuit and local include paths: extracted capacitor content and
hierarchical dependencies must be resolved before attempting reproduction.

A particularly useful failure lesson in the core README is the sampling/MSB
node excursion approximately2*VCM-VIN: below-ground excursions can lose stored
charge. Audit absolute switch-terminal voltages across the whole sequence, not
only comparator differential voltage. This is directly relevant to our uncertain
common-mode and switching-load scenarios even with narrow supply/temperature.

Decision: retain as a concrete reference for a future controlled ADC switching
comparison and calibration work. Do not replace our ADC or infer a speed/power
benefit without matched GF180 experiments. Current LO candidate remains running
and unchanged; this review does not displace that highest-risk active experiment.
