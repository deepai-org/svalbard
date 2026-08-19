# PLL / VCO work in progress

This directory develops the autonomous clock source for the dual-edge PCIe
receiver. The required oscillator rate is 1.25 GHz, not the 2.5 GT/s serial
rate. It is not yet a PLL macro: the selected bank is now only two complete
split-control half-rate oscillator parents. Both are physically closed, and
their 293/400-case public-model PVT union covers the required target and the
+/-2% design band in 5/5 environments. A reused physical dual 5-bit R-2R DAC
is now qualified as the realizable main/regenerative bias source; the selected
architecture uses one instance per independently power-gated VCO parent. The
two-DAC/two-VCO/selector parent is now physically and deterministically
electrically qualified as a system, including bounded supply/reference ripple.
Its statistical/noise qualification, calibration controller, remaining
feedback-divider ratio, loop, and analog-top integration remain open. A first
static differential CML divide-by-two stage is now physically closed. A
two-stage extracted CML clock restorer now closes the exact VCO-bank-to-divider
electrical boundary across all five declared environments; the routed combined
parent and remaining feedback ratio are still open.
The earlier fixed-control and 2.5 GHz banks are retained as fallback/
falsification evidence rather than selected implementation members.

`ring_vco.spice` is a three-stage differential CML ring followed by an
isolating CML output buffer. Each delay cell has a driven differential pair, a
weaker cross-coupled regenerative pair on a separate tail, matched p-poly
loads, and matched inversion-mode NMOS capacitors. The first unregenerated
version produced transient zero crossings and then decayed to a symmetric DC
point; the checked version requires sustained late-time oscillation.

The architecture exposes load resistance, MOS-cap geometry, and tail control
as independent tuning axes. `run_vco.py` tests stable early/late period,
differential swing, current, and seeded startup. A code is usable only with at
least 200 mV differential peak in both directions, 3--40 mA total VDD current,
less than 1% early/late frequency drift, and the tenth crossing by 10 ns. An
environment covers 2.5 GHz only when two adjacent usable control voltages in
one physical band bracket the target. The checker records local KVCO polarity
because two low-supply/hot bands tune with negative slope; a later PLL must
select matching loop polarity or exclude those bands.

The committed architecture summary records 735 completed schematic cases.
The six speed/gain bounds are covered after adding three targeted interpolated
R/C points. This is deliberately weaker than a PVT closure claim: the broad
12-environment screen must be rerun with the final bank, and the parameterized
choices must become a realizable break-before-make switch network or
independently power-gated VCO variants.

The first physical delay tile is now generated as a 54 by 56 um symmetric
cell. It has zero Magic DRC errors, a unique pin-resolved Netgen LVS match, and
full-RC extraction containing 275 resistors and 79 capacitors. Four instances
of that extracted tile form the three-stage ring plus output buffer. At the
nominal public corner all 7/7 controls sustain oscillation; the frequency range
is 2.459--2.709 GHz and 0.88--0.98 V brackets 2.5 GHz. The committed
`layout.png` is rendered from the checked GDS rather than drawn separately.

`layout.tcl` now generates eleven additional fixed geometries from the same
topology: slow (2.40 um cap / 5.25 um load), fast (0.60/5.25), ultra-fast
(0.50/4.25), high-gain (0.50/6.50), SS/fast-resistor (0.37/6.25 with
15/5 um main/latch tails), and SS/slow-resistor (0.38/4.00 with 15/6 um
tails). Two SS/slow-resistor margin tiles retain the 15/6 um tails and 4.00 um
load while using a 4.0 by 0.50 um low-end cap and a 3.2 by 0.37 um high-end
cap. A 4.0 by 0.85 um center-tail tile adds typical low margin; 4.0 by 0.40 um
and 3.2 by 0.37 um long-load tiles add the SS/fast-resistor low and high
endpoints. All eleven have zero Magic DRC errors, unique Netgen LVS, full-RC PEX,
and a KLayout GDS render. The slow tile covers
FF/fast-resistor at 2.447--2.542 GHz; the fast tile covers FF/slow-resistor at
2.478--2.543 GHz. The two active-tail tiles cover SS/fast-resistor at
2.458--2.508 GHz and SS/slow-resistor at 2.489--2.506 GHz. Together with the
center tile this expands extracted coverage from 1/5 to 5/5 declared
environments.

The old passive-only ultra-fast and high-gain tiles are retained because their
failure identified the loop-gain boundary: reducing load further killed
oscillation, while increasing VCTRL above the frequency peak slowed the ring.
The active-strength screen then separated main-tail and latch-tail current and
the physical generator moved every affected terminal, gate, source return, and
VCTRL route. A later cap-loading screen preserved active-device gain and made
cap width a true geometry parameter: the PCell, terminal straps, gate contact,
and both VSS returns move together. The legality sweep records 0.37 by 3.2 um
as DRC clean and 0.37 by 2.8 um as the first rejected point with 18 errors.

The two regenerated margin tiles close the desired SS/slow-resistor endpoint
range at 2.97 V and 125 C. The low tile has two valid controls spanning
2.432--2.444 GHz; the high tile has three spanning 2.545--2.567 GHz. Each
extracted tile contains 274 resistors and 82 capacitors. This is an aggregate
bank guardband, not one member with an excessively broad analog control.
The final three physical endpoint tiles also preserve their screened margins:
typical-low spans 2.432--2.681 GHz with 11 valid controls, SS/fast-resistor-low
spans 2.430--2.489 GHz with 7, and SS/fast-resistor-high spans
2.499--2.562 GHz with 7. `vco_bank_result.json` records 11/11 added physical
geometries, 5/5 required target environments, and 5/5 environments with full
aggregate +/-2% bank guardband. `layout_vco_bank.png` is the generated
twelve-layout visual index.

This is target coverage, not robust PLL qualification. The SS/slow-resistor
corner has physical endpoint margin, those members also close the
FF/slow-resistor high endpoint, and the three final tiles close typical and
SS/fast-resistor. The tuning-bank sweep still uses a deterministic millivolt
seed to isolate steady-state range from startup behavior.

Startup now has a separate physical mechanism and proof. A matched pair of
1 um NMOS devices can briefly pull either side of one internal differential
node and is off after acquisition. `startup_assist_layout.tcl` generates the
guarded symmetric cell; it has zero Magic DRC errors, a unique Netgen LVS
match, and full-RC PEX with 86 resistors and 12 capacitors. The first 4 um
version started every case but its off-state drain capacitance reduced four of
five sampled target brackets, so it was rejected rather than accepted as a
startup-only result. The regenerated 1 um pair restores all five brackets.

`run_startup_composed.sh` freshly regenerates the assist and seven relevant VCO
tiles, closes DRC/LVS/PEX on all eight cells, and composes four instances of
each selected tile with the extracted assist. With a 500 ps supply/control
ramp, no `.ic`, no `uic`, and a released 270 ps kick, all 42/42 commanded cases
pass across five process/passive/supply/temperature environments and both kick
polarities. All 5/5 environments bracket 2.5 GHz; worst commanded startup is
0.410 ns after release, worst early/late period drift is 0.086%, minimum
differential peak is 429 mV, and worst opposite-kick frequency mismatch is
0.012%. The five no-kick controls are diagnostic only because deterministic
numerical asymmetry is not a statistical noise-startup model.
`startup_composed_result.json` binds these cases to the assist and tile PEX
hashes and records the physical checks.

The first complete full-rate oscillator-band parent was routed rather than assembled
only as leaf PEX instances in a testbench. `vco_band_layout.tcl` places three
delay stages, one isolating output buffer, and the matched startup assist, then
owns the differential ring feedback, VDD, VSS, VCTRL, kick, and output routes.
The initial center-tile parent was physically correct but slowed from the leaf
composition to 1.94 GHz; that result was rejected instead of widening the
frequency checker. A lower-capacitance, stronger-tail `margin_fast` member was
regenerated as the parent child and reclosed against the matching schematic.

The resulting band is 0-DRC, uniquely LVS-matched, and has 1,210 resistors and
329 capacitors in full-RC PEX. At its realizable 1.08 V control it passes a
2.45--2.55 GHz design window in 5/5 nominal transient cases: both no-IC/no-uic
kick polarities with a 25 fF load, both polarities while driving the extracted
high-gain selector input, and commanded shutdown under that nonlinear load.
Frequency is 2.493 GHz, startup is 0.116--0.321 ns after kick release, selector
loading shifts frequency by 0.0137%, and steady band current is 8.47 mA. After
shutdown, differential residue is 1.54 uV and band current is 1.47 uA. The
physical report, electrical result, and simulator all match the exact checked
PEX hash in `vco_band_result.json`; `layout_vco_band.png` is the emitted-GDS
review image. This closed one nominal overspeed boundary, not its PVT behavior.
Regenerating all twelve members in a much shorter vertically folded parent
produced 12/12 zero-DRC, unique-LVS, exact-PEX layouts and improved nominal
speed, but the complete 480-case bank covered 2.5 GHz in only 2/5 environments.
The three hot environments topped out below target; active-width screens raised
capacitance without recovering the slow-device cases. The full-rate
architecture is therefore a retained failed experiment, not the current
clock-source claim.

The current half-rate bank uses the folded parent with three delay stages, one
isolating output buffer, and the symmetric startup assist. Seven complete
parents implement measured load/cap/tail points. Every member is zero-DRC,
uniquely LVS-matched, and full-RC extracted with 1,118--1,122 resistors and
325--333 capacitors. A 280-case no-`.ic`, no-`uic` sweep uses a supply ramp,
physical startup assist, eight realizable controls, five mixed
process/resistor/supply/temperature environments, swing/current/startup/drift
gates, and exact PEX identity. It has 183 passing cases and continuous 1.25 GHz
coverage in 5/5 environments. The deliberately tighter +/-2% design band is
continuous in 3/5; slow-device/fast-resistor and slow-device/slow-resistor
still need finer capacitance or independently controlled signal/regenerative
tail bias. `half_rate_vco_bank_result.json` records both claims separately and
`layout_half_rate_vco_bank.png` is the emitted-GDS visual index.

The focused split-control experiment replaces the shared tail-control net with
independent `VCTRL_MAIN` and `VCTRL_REGEN` pins and routes both through each
complete folded parent. Three legal coarse geometries were regenerated rather
than editing active devices inside an old PEX deck. All three are 0-DRC,
uniquely LVS-matched, and exact full-RC extracted with 1,116--1,120 resistors
and 336 capacitors. Their 240-case no-`.ic`, no-`uic` screen has 84 passing
cases. The aggregate valid intervals cover 1.225--1.275 GHz in both formerly
open 2.97 V, 125 C slow-device environments: slow/fast-resistor reaches
1.2859 GHz and slow/slow-resistor reaches 1.2833 GHz. This establishes the
physical margin mechanism. `split_control_vco_result.json` binds the three
distinct PEX and GDS-render hashes for that focused milestone. The usable emitted-GDS images are
`layout_split_control_vco.png`, `layout_split_fast_control_vco.png`, and
`layout_split_gain_control_vco.png`.

The subsequent full-PVT run freshly regenerated those three parents and ran
200 extracted cases per member across all five environments. It reproduced all
240 shared hot-corner classifications and frequencies from the focused run;
only printed swing roundoff changed, by at most 1 uV. A connected-interval
minimum-cover search proves that the `fast` and `gain` members alone cover
1.225--1.275 GHz in 5/5; no single member covers more than 3/5. The selected
two-parent evidence has 293 passing cases out of 400. Its limiting upper
endpoints are 1.2859 GHz for slow/fast-resistor and 1.2833 GHz for
slow/slow-resistor. `split_control_vco_full_bank_result.json` records the
minimum selected bank and all three candidate identities. The three
`split_*full-screen.json` files retain every numeric case.

The older hash-bound ten-parent union also passes 5/5 with 610/880 valid cases
and remains in `half_rate_vco_full_bank_result.json` as corroborating evidence,
but it is not the selected implementation. Removing eight unnecessary parents
reduces inactive loading, power-gating state, routing, and selector complexity;
the already closed two-input selector is the correct next boundary. This closes
bare-bank deterministic PVT range, not the two-instance bias/reference
composition, selection loading, noise, or the PLL loop.

The realizable bias source reuses the exact physically closed dual-channel
5-bit R-2R phase-control DAC with 0 and 2.0 V references. A fresh VCO-role flow
regenerates its layout and requires zero DRC, unique LVS, full-RC extraction,
and simulation against the identical PEX. Across 160 DC cases in five VCO
environments, all requested main-control points from 0.78 to 1.50 V and
regenerative-control points from 1.20 to 1.65 V have a physical code within
32.6 mV. The recorded worst step is 83.3 mV, the lowest high endpoint is
1.8851 V, and maximum reference power is 1.462 mW. Five worst-carry transients
into 1 pF per output settle within 23 uV of their final values by 50 ns. The
physical PEX has 640 resistors and 265 capacitors.
`vco_bias_dac_result.json` retains the full code maps and exact identities;
`layout_vco_bias_dac.png` is the emitted-GDS review image. This proves a
realizable bias primitive, not the routing, reference integrity, simultaneous
behavior, or sequencing of the two-instance bank composition.

`vco_bank_top_layout.tcl` realizes that selected composition rather than the
obsolete sixteen-leaf bank. It places one dual-output DAC below each folded VCO
parent and the reused two-input selector above them. Parent-owned main/regen
bias routes remain local to each side; shared references cross only the quiet
DAC gap; supplies use perimeter spines; and the four VCO-to-selector clock legs
use separate M4 tracks with deliberate inner-leg detours for first-order
differential length matching. The approximately 472 by 576 um parent is
zero-DRC, uniquely
LVS-matched to `vco_bank_top.spice`, and extracts to 3,872 resistors and 1,287
capacitors. `vco_bank_top_physical_result.json` and
`layout_vco_bank_top.png` bind the report and usable emitted-GDS image. This
same complete PEX now passes a realizable-code nominal search, 10/35 candidate
cases covering all five declared environments, and a live-parent handoff from
1.2575 to 1.2452 GHz. The break-before-make interval leaves only 3.46 mV at the
output, reduces current by 2.96 mA, and old-parent DAC shutdown reduces current
by 4.07 mA. `vco_bank_top_result.json` binds every component pass to one exact
parent PEX hash and requires at least three codes of selected rail headroom.
The same selected configurations pass 55/55 bounded disturbance cases spanning
50 mV peak VDD ripple at 10 and 100 MHz, 25 mV at 625 MHz, and 20 mV peak
reference ripple at 10 and 100 MHz, each at two phases. The worst displacement
of any measured cycle from its same-environment baseline is 8.59 ps, worst
cycle peak-to-peak variation is 16.96 ps, and worst median-frequency pushing is
0.467%. These are deterministic public-model bounds, not random phase-noise or
PDN signoff claims.

`divider_layout.tcl` implements the first feedback-clock division stage as two
opposite-phase static CML latches with complementary reset. The compact,
left/right-symmetric cell uses one common 7.5 um load geometry and a
programmable tail bias. It is zero-DRC, uniquely LVS-matched, and its exact
full-RC extraction contains 510 resistors and 193 capacitors. A 25-case
post-layout screen at a 1.25 GHz input has 19 passing bias points and finds a
working code in 5/5 process/resistor/supply/temperature environments; every
selected code produces 625 MHz, with 0.9 V selected in all five. This closes a
divide-by-two primitive, not the complete ratio from the eventual PCIe
reference, its loading on the VCO parent, phase detector, or loop dynamics.
The usable checked-GDS image is `layout_divider.png`; numeric evidence is in
`divider_extracted_result.json` and `divider_physical_result.json`.

Direct composition of the exact VCO-bank and divider PEX decks passed nominal
and fast-device environments but failed both slow-device environments. The VCO
frequency shifted by little, showing that source-frequency loading was not the
limiting mechanism; the divider lacked a sufficiently regenerated clock and
could also produce a large output at the wrong rate. Increasing divider clock
device width in a retained-RC screen did not recover the boundary.

`clock_restorer_layout.tcl` realizes one compact matched CML limiting stage.
`clock_restorer_cascade_layout.tcl` composes two independently guarded stages
with matched intermediate routes, and is zero-DRC, uniquely LVS-matched, and
full-RC extracted to 366 resistors and 92 capacitors. The exact VCO-bank,
cascade, and divider PEX decks pass 24/30 control cases covering 5/5
environments. Both slow environments have three adjacent passing divider-bias
points. Across passing cases the minimum restored differential rails are
+0.591/-0.484 V, minimum divider rails are +0.286/-0.277 V, worst divide-ratio
error is 0.258%, worst late-period drift is 0.453%, and maximum VCO frequency
shift is 0.030%. This closes extracted children joined by ideal parent wires;
it does not yet close the placed-and-routed combined parent. The review image
is `layout_clock_restorer_cascade.png`, structural evidence is
`clock_restorer_cascade_physical_result.json`, and composition evidence is
`vco_divider_restorer_full_result.json`.

Phase noise, statistical noise/mismatch startup, combined PDN/aggressor stress,
runtime band-selection control, routed VCO/restorer/divider composition,
remaining divider ratio, and loop dynamics remain open.

The first safe-selection primitive is now physical and extracted. Rather than
duplicate nearly identical circuitry, the closed phase-interpolator macro is
used at its one-hot endpoints: one weighted input tail is biased, the other is
off, and its second CML stage restores and isolates the clock. A seven-code
paired tail/buffer-bias search runs 210 full-RC cases at 2.5 GHz with the
unselected branch driven by a live 2.0 GHz aggressor. All 5/5 environments find
an interior code that passes A and B selection at 0.55, 0.72, and 0.86 VDD
input common mode. Across selected codes, minimum differential peak is 206 mV,
worst cycle-period modulation is 5.33 ps, and worst frequency error is 0.029%.

The extracted primitive also passes a 0.95 ns break-before-make handoff with
both input clocks live: the output buffer is off during dead time, differential
gap residue is 25.9 mV, and gap current is 33.9 uA. A separate fresh composition
connects two complete extracted VCOs directly to the extracted selector. Its
5/5 cases cover either powered-down neighbor, either different-frequency live
aggressor, and an A-power-down/B-start/B-select sequence. Worst powered-down
reverse feedthrough is 25.8 mV or -30.76 dB; worst selected-output cycle jitter
with a live aggressor is 2.98 ps, and the handoff gap falls to 1.17 mV. These
results close the two-band primitive, not the complete twelve-band hierarchy or
its extracted top-level interconnect. `selector_result.json` and
`selector_vco_composed_result.json` retain the two evidence layers.

The complete selector hierarchy is now physical as a balanced sixteen-leaf
tree: twelve band inputs plus four defined quiet spares traverse four identical
stages and fifteen selector instances. The first extracted tree passed handoff
but only 14/16 static cases because the reused PI-sized signal pairs lost gain
at slow/hot/low-supply corners. Maximum existing bias recovered one case but
left `ss/res_ff` at 46 mV. A full-RC candidate screen rejected longer output
loads because the opposite resistor corner lost headroom, then selected doubled
input and restoring pairs. The physical selector realizes each logical device
as two parallel, already-proven two-finger PCells; the attempted single
four-finger routing was rejected by LVS rather than waived.

The regenerated tree is 0-DRC, uniquely LVS-matched, and extracts to 6,947
resistors and 3,061 capacitors. All twelve nominal leaves pass with every other
input driven by a distinct live aggressor; four additional cases cover five
total environments. The combined result is 16/16 plus a leaf-0-to-leaf-11
0.95 ns break-before-make transition that changes every tree level. Worst
static differential rail magnitude is 472 mV, worst cycle jitter is 6.02 ps,
worst frequency error is 0.032%, and maximum supply current is 14.46 mA. The
handoff dead interval has zero crossings and 28.3 mV peak residue. The checked
numeric evidence and usable GDS render are `selector_tree_result.json` and
`layout_selector_tree.png`.

The bounded reproduction sequence is `run_active_screen.sh` for the
parasitic-preserving active-width screen, `run_cap_drc.sh` for legal cap
length/width boundaries, `run_vco_active_physical.sh` for the four active-tail
tiles and endpoint checker, `run_guardband_screen.sh` and
`run_guardband_physical.sh` for the remaining endpoints, and `run_vco_bank.sh`
for the complete 11/11-physical, 5/5-target, 5/5-guardband result and generated
visual index. `run_startup_assist_physical.sh` closes the assist alone and
`run_startup_composed.sh` reproduces the eight-cell physical and 42-case
commanded-start proof. `layout_startup_assist.png` is the KLayout render of the
checked startup cell. `run_selector.sh` qualifies the shared PI geometry in its
2.5 GHz selector role; `run_selector_vco.sh` regenerates all three physical
cell types and runs the direct two-VCO composition.
`run_selector_tree_gain_screen.sh` preserves the baseline tree's extracted
routing RC while screening active geometry, `run_selector_tree_physical.sh`
closes the regenerated hierarchy, and `run_selector_tree.sh` reruns physical
closure plus the all-leaf/PVT/handoff matrix. `run_vco_band_physical.sh` closes
the routed oscillator parent alone; `run_vco_band.sh` additionally regenerates
the extracted selector load and proves startup, steady state, loading, shutdown,
and exact PEX identity.
`run_vco_band_bank.sh` reproduces the failed twelve-parent 2.5 GHz overspeed
matrix. `run_half_rate_vco_screen.sh` is a candidate-only retained-RC cap
screen; `run_half_rate_vco_bank.sh` regenerates all seven 1.25 GHz parents,
checks every DRC/LVS/PEX identity, runs the 280-case matrix, and emits the
numeric result plus visual index. `run_split_control_vco.sh` regenerates the
three independently biased parents, closes each physical boundary, runs the
focused 240-case hot-corner screen, and rejects duplicate PEX identities in
its compact aggregate result. `run_half_rate_vco_full_bank.sh` expands the
three new parents to 600 five-environment cases, proves the minimum connected-
band subset, and also combines them by checked hash with the unchanged seven-
parent evidence. Its primary selected-bank gate requires two unique PEX
identities, exactly 400 selected cases, and full target/design-band coverage in
5/5; the ten-parent 880-case aggregate is a corroborating output.
`run_vco_bias_dac.sh` regenerates and physically closes the reused dual R-2R
DAC, runs 160 extracted DC cases plus five conservative 1 pF worst-carry
transients, and emits the environment-specific target-to-code map.
`run_vco_bank_top.sh` regenerates every selected leaf, routes the actual
two-DAC/two-VCO/selector parent, and requires zero DRC, unique LVS, full-RC
extraction, a GDS-bound review image, realizable-code nominal/PVT calibration,
break-before-make handoff, inactive isolation, old-parent shutdown, one common
PEX identity, selected-code rail margin, and 55 exact-parent VDD/reference
ripple cases with individual-cycle measurements.

`run_divider_schematic.sh` screens four load geometries and five tail-bias
codes over five environments; `run_divider_physical.sh` regenerates the cell,
requires DRC/LVS/full-RC closure, renders the emitted GDS, and repeats the fixed
geometry over 25 extracted cases. `run_clock_restorer_cascade_physical.sh`
regenerates the two-stage limiter hierarchy and requires DRC, unique LVS,
full-RC extraction, and a GDS render. `run_vco_divider_restorer_full.sh` then
composes the exact VCO-bank, limiter, and divider decks over the five selected
VCO environments with an 8-worker bounded sweep. `run_schematic.sh` runs the 12-environment
adversarial screen and intentionally
returns failure until every environment has a bracketing band. The next
milestone is defensible mismatch/statistical startup and phase-noise analysis
against the complete parent, plus a routed VCO/restorer/divider parent and loop
integration. The remaining feedback-divider ratio, PFD, charge pump, loop
filter, lock detector, and external-clock bypass remain separate unimplemented
boundaries.
