# FPGA offload audit: what on-chip digital can or should move to the host FPGA

Status: read-only audit, 2026-11-10. No RTL or spec edited. Input to the digital AC-1 agent.
Policy basis: MANDATE.md ("concentrate risk", "shared digital datapath"), digital-sharing-plan.md
(S1–S8), interface-architecture-changes.md AC-1/AC-2, interface-requirements.md §3, interface-changes.md
(T-, D-, IX-, GX-, RXR-, AC3- rows).

## 0. Measured baseline (today's rtl/)

Method as in the sharing plan: yosys `synth -run begin:fine; techmap; opt -fast` on all `rtl/*.sv`
except the dead `pt_block_*`/`pt_lane_*`, flop bits counted through the hierarchy.

| Block | FF |
|---|---:|
| pt_regfile (shadow + active, commit validator) + pt_spi | 1,652 + 63 |
| ingress pt_cdc_fifo 28×40 (MEMORY=1, capture peek) | 1,293 |
| egress pt_cdc_fifo 24×40 (MEMORY=2, SPI playback) | 1,149 |
| pt_h2d_gearbox 8×40 + d2h gearbox + host link glue + rate clock | 495 + 88 + 68 |
| pt_freq_count ×2 | 608 |
| pt_lc_rx + pt_lc_tx (8b/10b, IX-2b) | 385 |
| quad framer tx/rx + collect + header | ≈ 344 |
| PRBS checker 143 + generator 74 + cfg syncs ≈ 28 | ≈ 245 |
| pt_interp2x | 149 |
| sample pack / unpack | 127 |
| clocktree_slow 82, pt_calibrator 34, pt_gain_rx 32, pt_vreg_seq 25, syncs/glue | ≈ 210 |
| **Total** | **6,981** (cap 8,192) |

S1 (capture/playback in the transport banks) is **already in** — `pt_memory` is defined but no longer
instantiated. That was the only large lever; what remains is mostly structure that cannot leave the die.
Still to be added per the sharing plan: S2 IX-11 (+25), opcode5 (+20), S4 IX-12 mux + event select (+25),
S5 stamp (+70), GX-4 (+30), ingress→32 (+170, optional), ss32 pipelining (+200–400).

## 1. Host-link capacity re-check (per direction, dense framing 59/64)

Full rate 10 pins × 312.5 Mb/s × 59/64 = **2.88 Gb/s**; div2 1.44; div4 0.72. Wired ≤ 2.5 Gb/s uses the
line/8 word rule (1.152 × line).

| Mode | Payload | Full | div2 | What it decides |
|---|---:|---:|---:|---|
| Wired raw 2.5 / 2.7 Gb/s | 2.5 / 2.7 | fits (line/8) / 94 % | ✗ | no codec needed ≤ 2.7 |
| Wired raw 3.0 / 3.125 / 3.24 | 3.0 / 3.125 / 3.24 | **104 / 109 / 112 %** ✗ | ✗ | 8b/10b must stay on-chip |
| Wired 8b/10b 9 b/sym: 3.0 / 3.125 / **3.24** | 2.70 / 2.81 / **2.92** | 94 / 97.7 / **101 % ✗** | ✗ | see finding F1 |
| IX-12 raw dual lane (ring 750 MHz) | 1.5 | 52 % | 104 % ✗ | full rate only |
| RF RX 40 MS/s × 2 × 12 b (packed) | 0.96 | 33 % | 67 % | PWR-HOST-RF div2 OK |
| RF RX unpacked (24 b in a 40 b quad) | 1.60 | 56 % | 111 % ✗ | pack must stay (div2 power) |
| RF TX 40 MS/s, on-chip halfband | 0.96 | 33 % | 67 % | |
| RF TX 80 MS/s host-fed (GX-2 `external`) | 1.92 | 67 % | 133 % ✗ | **fits** at full rate |

Conclusions:
- **8b/10b offload (IX-2b) is bandwidth-driven and must stay**, in both directions (H2D raw at 3.125 is
  also 109 %).
- **The interpolator was not bandwidth-driven**: 80 MS/s fits a full-rate link (67 %). It is
  power/spur-driven (PWR-HOST-RF div2, SP-01). It is therefore a CAN, not a MUST.
- **F1 (spec gap):** WR-RATE-CONT promises 0.48–3.24 Gb/s. Above ≈ 3.15 Gb/s (2.88 / 0.9 = 3.2 Gb/s minus
  ppm/credit headroom) **no mode streams through the host link**, not even with 8b/10b. 3.13–3.24 Gb/s are
  PHY-reachable but only testable with the on-chip PRBS checker or idle deletion (not implemented) or
  `wire_board_phy_bypass`. The spec owner should state that in WR-HL-LINECODE.

## 2. Loop latency budget (why some loops cannot go through the FPGA)

| Path | Latency |
|---|---|
| H2D frame start on pins → fast gain applied (T9, measured) | 189 ns full / 311–331 ns div2 |
| FPGA decision → gain applied incl. frame alignment (T9) | ≤ 0.4 µs full / 0.74 µs div2 |
| Full FPGA loop (D2H capture→pin + FPGA + H2D + apply), IX-11 budget | ≤ 0.5 µs |
| SPI register write (32 bit) | ≈ 3.8 µs per step |
| CDR proportional path: per-UI vote → ring (AC3-W9) | 1 ring cycle (1.2–2 ns); AC-3 requires ≤ 8 ring cycles (≤ 13 ns) |
| CDR loop delay that 0.5–4 MHz BW tolerates | ≪ 1/(2π·4 MHz) = 40 ns |

So: CDR phase loop (ns) is ≥ 10× too fast for any host round trip; AGC/threshold loops (≤ 1 µs) fit a
host round trip only through the in-band H2D command, not SPI; everything at µs–ms (calibration, FLL
monitoring, profile scheduling, histograms) can be host-side.

## 3. Function-by-function decision

FF are today's measured or the sharing-plan estimate. "Stays" reasons: S = safety, L = loop faster than
link, C = clock domain / pad timing, B = needed with no host link (SPI-only bring-up), W = bandwidth.

| Function | RTL | FF | Decision | Reason / cost of moving |
|---|---|---:|---|---|
| Pad-edge DDR, 1:4/4:1 gearboxes, rate clock, forwarded clock | pt_host_link | 651 | **MUST** (C) | It is the link. |
| Dense framing, header, H2D validate, command decode, collect | pt_quad_link, pt_dense_header | ≈ 344 | **MUST** (C, W) | Protocol endpoint; legality checks protect analog (command faults). |
| Ingress/egress CDC FIFOs (+ S1 capture/playback) | pt_cdc_fifo ×2 | 2,442 | **MUST** (C, B) | CDC between host and line/converter clocks; elasticity for ppm/credits. Memory mode is the SPI-only capture/playback. |
| IQ pack/unpack | pt_quad_gearbox | 127 | **MUST** (W) | Unpacked RX = 1.6 Gb/s, breaks div2 (PWR-HOST-RF); 80 MS/s unpacked TX = 3.2 Gb/s. |
| 8b/10b RX/TX (IX-2b) | pt_linecode | 385 | **MUST** (W) | Raw 3.0/3.125 Gb/s = 104/109 % of capacity. PCS above it (ordered sets, idles, protocol) is already FPGA. |
| 2× halfband interpolator | pt_interp2x | 149 | **CAN** (keep) | Moving = GX-2 `external` as the only mode. Cost: host link at full rate in every RF TX/duplex mode (hostio ≈ 95–117 mA at full vs ≈ half at div2; violates PWR-HOST-RF), SP-01 ch-3 conflict at 312.5 Mword, and no image filtering for 40 MS/s hosts. Gain: −149 FF, one generated clock (`rfhalf`) and one clock mux/STA mode gone. Already bit-exact verified (D9) → keep, but make sure bypass at `rf_tx_clk` = 80 MHz (GX-2) closes STA so the FPGA halfband is the fallback. |
| PRBS generator / checker | pt_pattern | ≈ 245 | **MUST** (B, W) | Only BER route with no host link and the only one for raw PRBS above 2.88 Gb/s (F1). The FPGA does bit-exact BER on the stream ≤ 2.5 Gb/s (reference design). Fix timing on chip (register the mismatch vector; two-stage popcount). Fallback simplification if it still fails 12.3 ns: count errored 40-bit words (one OR-reduce) instead of bits. At BER ≤ 1e-6 word count ≈ bit count. |
| Capture / playback | S1 in banks | ≈ 70 | **MUST** (B) | Already minimal. FPGA captures from the stream in normal use. |
| Freq counters a/b | pt_freq_count ×2 | 608 | b **MUST**, a **CAN** | b drives `cdr_freq_locked` (autonomous CDR handover; L/B). a is pure observation: CLK_OBS (divide-before-mux) into an FPGA/bench counter could replace it (−304 FF). Cost: CLK_OBS toggling as an aggressor during operation, no concurrent TX-ring watch in wired mode, SPI-only bring-up needs a bench counter. Not recommended now: it just closed timing (D4). Cheaper middle option: drop lock/tolerance metrics from instance a only (software compares counts), ≈ −60–80 FF. |
| Clock tree slow functions, word clocks, sync qualification | pt_clocktree_slow | 82 | **MUST** (C) | Serializer word divider, phase-qualified launch for GX-7. |
| CDR digital (FLL, lock, PD votes) | wired_rx `pt_wrx_cdr_loop` + analog PD | (wired_rx island) | **MUST** (L, B) | Votes go straight to the ring (ns). FLL re-acquires autonomously (PCIe idle exit, loss); SPI is 3.8 µs/step. Not in macro FF. |
| Fast analog control apply (opcode4 / IX-11 S2) | pt_core, pt_gain_rx | 32 (+25) | **MUST** apply, decision already FPGA (L) | SPI 3.8 µs > 1 µs AGC budget; no spare pins. The FPGA owns every AGC/threshold decision. The 20-sample settle discard could also move to the FPGA (it gets the mark), but the block is small and verified: leave it. |
| Timestamp / latency unit (S5, IX-8, Thread CSL) | not built | plan +70 | **SHOULD move** (keep only the event mark) | The FPGA already sees every D2H sample and every H2D sample it sent, so it owns the 64-bit sample counters. The chip only has to make the CDC-uncertain events observable: mark TX launch (and fast-control apply) in the RX stream via the **existing** pt_gain_rx `mark_ptr`/`mark_toggle` + status-frame path with a reason code. ≈ +15 FF instead of +70; no 20-bit incrementer; Thread CSL ±16 µs is entirely FPGA. |
| GX-7 multi-die sync | pt_clocktree_slow (sync_arm/epoch) | 0 | **MUST** (C) | Epoch start in the sample clock domain; the FPGA distributes the common H2D sync event and reads the marks. |
| Event / histogram counters (S4 fallback) | not built | plan +20 | **SHOULD NOT build on chip** | Primary is FPGA on the IX-12 stream. SPI-only fallback: IX-12 raw lanes into the ingress capture bank (S1) and read over SPI; software builds the histogram. Avoids putting an event-select mux into the PRBS checker, the path that is already −7 ns at 12.3 ns. |
| Opcode5 RF status frame (RXR-D4 overload) | not built | plan +20 | **SHOULD move to a pin** | Overload is an async comparator flag. Put `rx_ovld` on a DBG_OBS0/1 select (one mux input, ≈ 0 FF) + the sticky status bit. The FPGA AGC reads the pin with ns latency, and no framer/echo change touches the hcore critical path. Cost: one DBG_OBS pin is spent in RF operation (board: route DBG_OBS0/1 to FPGA pins, not just test points); alignment to samples is ± a few samples (fine for AGC). Keep opcode5 only if a second status field needs in-band alignment. |
| GX-4 epoch-switched profile | regfile generator | plan +30 | **CAN move timing to FPGA** | The FPGA drives SCLK, so a COMMIT lands deterministically (falling edge after bit 32, D3) within one SCLK period, far inside the 50 µs profile budget. Alternative to a new "epoch" update class: make the bbfilter/gain fields commit-while-running (live) under the existing validator, and let the FPGA time the COMMIT to the hop. Saves the new generator class (novelty), ≈ 30 FF. Decide with the regfile owner; the warm-hop context path may already give this. |
| Calibration sequencer | none (D11) | 0 | already FPGA | Host runs D-CAL-1 over SPI. |
| Ref-trim SAR | pt_calibrator | 34 | **SHOULD remove** (verify first) | No consumer of `calibration_trial`/`calibration_above_target` was found outside `pt_analog_physical` (blackbox port only); its only side effect is `rf_mute` while busy. If confirmed legacy: delete (−34 FF, one ref-domain FSM). If something uses it: a host SAR over SPI (12 steps, < 0.1 ms) needs the comparator bit in `status` and the trial as a direct field (net ≈ −20 FF). |
| Regulator sequencing, PLL enable hold | pt_vreg_seq | 25 | **MUST** (S) | Protects silicon before any host exists. |
| TX pad sequencing, island isolation, pgood/POR, LU-02/SUB-04 interlocks | pt_tx_pad_sequence, regfile rules | in regfile | **MUST** (S, B) | Host bugs must not be able to damage silicon. |
| SPI + regfile (shadow/active, commit validator) | pt_mgmt | 1,715 | **MUST** (S, B) | Single-copy (no shadow) for stopped-only fields would save up to ≈ 800 FF, but the validator checks the *complete shadow configuration* before anything reaches analog. Moving that to the host removes the safety net. Not recommended. |
| Debug muxes (DBG_OBS, CLK_OBS, ATB) | pt_digital / regfile | small | **MUST** (B) | They are the SPI-only observability. |
| SP-01 clock plan | clocktree dividers + `host_link.rate` | 0 | already FPGA (table) | Chip only provides dividers; per-channel choice is host software (D10). |
| Profile/channel scheduling, AGC, PTA, DC/CFO, histograms, eye scan, oversampling CDR (IX-4, 100BASE-TX) | — | 0 | already FPGA | RXR-D7, IX-11/12. |

## 4. Savings against the plan (≈ 7,050 FF with all features)

| Change | FF vs plan | Timing / risk effect |
|---|---:|---|
| S5 stamp → event mark on the existing gain mark path | −55 | no 20-bit counter; no new CDC |
| S4: no event-counter select in the checker (capture bank + FPGA) | −20 | keeps the −7 ns checker path untouched |
| RXR-D4 on DBG_OBS instead of an opcode5 frame | −20 | no hcore framer change |
| pt_calibrator removed (if no consumer) | −34 | one fewer ref-domain FSM; `rf_mute` simplified |
| GX-4 via FPGA-timed live commit instead of an epoch class | −30 | no new generator update class |
| *Optional:* freq_count a metrics removed | −60…−80 | |
| *Optional, not recommended:* interp2x removed (GX-2 only) | −149 | −1 generated clock and clock mux; +hostio ≈ 50 mA in RF TX |
| **Recommended total** | **≈ −160** (→ ≈ 6,890) | |

Area: ≈ 160 FF + logic ≈ 0.015–0.02 mm² (sharing-plan ratio). Power: negligible. The real value is fewer
new on-chip mechanisms (four features become reuse or pins) and nothing added to the two failing paths
(H2D FIFO read mux, PRBS checker). The large FF levers are already used (S1) or are safety/CDC structure
that must stay; **no further big FF saving exists without giving up a MUST item.**

## 5. Spec / requirement changes

1. **WR-HL-LINECODE / WR-RATE-CONT (F1):** state that streaming covers ≤ ≈ 3.15 Gb/s with 8b/10b
   (3.125 at 97.7 %); 3.15–3.24 Gb/s is PHY-only (on-chip PRBS) unless idle deletion is added.
2. **IX-8:** replace "FPGA-visible sample-index timestamp" by "chip marks TX launch and fast-control
   apply in the D2H stream (status frame reason code, exact ingress quad pointer); FPGA owns sample
   counters". Fixed per-mode pipeline latency stays a chip requirement and is published read-only.
3. **RXR-D4:** overload flag = sticky status + DBG_OBS select `rx_ovld`; in-band flag optional.
4. **board-requirements B10:** DBG_OBS0/1 (and CLK_OBS) routed to FPGA inputs as well as test points.
5. **GX-4:** "profile applied by an FPGA-timed COMMIT (live class)" as the first option.
6. **PWR-HOST-RF:** note the GX-2 exception (full rate in 80 MS/s external TX) explicitly.
7. **sharing plan S4/S5:** amend as above.

## 6. FPGA reference-design gateware (what the host must implement)

1. Host-link PHY: DDR capture with per-bit IDELAY training (HL-TRAIN ≥ 50 ps), edge-aligned forwarded
   clock + UI/2 delay (T7), training pattern, rates full/div2/div4, SDR modes at div2/div4.
2. Dense framing/deframing, sequence and credit handling, fault recovery; opcode4 fast-control issue
   with one-pending rule and echo/reject handling; marker/status frame decode (IX-8).
3. Wired PCS per protocol on 9-bit {K, byte} symbols when `wire.config.linecode=8b10b`; raw mode PCS
   incl. 8b/10b codec and comma alignment otherwise; idle/ALIGN insertion on TX.
4. PRBS7/15/31 generator and bit-exact checker on the stream (same LFSR convention as `pt_pattern.sv`).
5. Oversampling CDR (IX-4 low rate, 100BASE-TX via IX-12), edge/eye histograms, phase-trim
   calibration from IX-12 data (S5 phase trim), IX-11 DC-restore/threshold servo (≤ 0.5 µs loop).
6. RF: AGC (ADC power + DBG_OBS `rx_ovld`), DC tracking, CFO/SFO, low-IF, PTA (RXR-D7);
   GX-2 halfband interpolator when `tx_interp=external` (taps −1 0 9 16 9 0 −1 /16, matches
   `verification/check_interp2x.py`).
7. 64-bit TX/RX sample counters, RTT and CSL timing from the chip's marks; GX-7 common sync event and
   multi-die alignment.
8. SPI master with the generated register ABI (`regmap_runtime`), D-CAL-1 calibration sequence, ref-trim
   SAR if pt_calibrator is removed, SP-01 channel→clock table, COMMIT timing for GX-4 hops.
9. Frequency measurement on CLK_OBS (if freq counter a is reduced).
10. The gateware is never a safety layer: every interlock remains enforced on chip.

## 7. Ordered recommendation for the AC-1 agent

1. Close hcore/PRBS timing first (sharing plan step 2); nothing below adds logic to those paths.
2. **Do not build the S4 event-counter select** in the PRBS checker; SPI-only histograms use IX-12 raw
   capture into the ingress bank (S1).
3. **Build S5 as an event mark**, reusing `pt_gain_rx` `mark_ptr`/`mark_toggle` and the gain-status
   frame with a reason code (TX launch, fast-control apply). No free-running stamp counter.
4. **RXR-D4 overload on a DBG_OBS select + sticky status**; skip the opcode5 frame unless the RF owner
   needs in-band alignment.
5. **Verify and delete pt_calibrator** if `calibration_trial` has no analog consumer (ask integration).
6. Keep 8b/10b, pack/unpack, FIFOs, framer, freq counter b, clocktree, vreg_seq, regfile validator: MUST.
7. Keep interp2x; make sure the GX-2 bypass at 80 MHz closes STA so the FPGA halfband is the fallback.
8. GX-4: propose the FPGA-timed live COMMIT to the regfile owner before adding an epoch update class.
9. Optional, last: trim freq counter a's lock metrics.
10. Report F1 (3.15–3.24 Gb/s does not stream) to the spec owner.
