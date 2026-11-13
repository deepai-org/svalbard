# Digital sharing plan: wired and radio on one datapath (AC-1 restart input)

Status: read-only audit, 2026-11-10. No RTL changed. Applies the MANDATE "Shared digital
datapath" rule to the RTL as it is now (the transport agent's AC-1 quad core plus the queued
features of the other digital agent: 8b/10b offload, opcode4 fast gain, interp2x, pattern engine,
freq counters, vreg_seq).

## 0. Baseline FF count (measured)

Method: `yosys` with `read_verilog -sv` on the 20 synthesized rtl files, `synth -top
pt_digital_macro -run begin:fine; techmap; opt -fast`, flip-flop cells counted per module and
multiplied up through the hierarchy. The figures agree with T11/D12 (8,423) within 0.3 %.

| Block | FF | Owner use today |
|---|---:|---|
| pt_regfile / pt_mgmt (568 analog + 255 debug cfg bits, shadow + active) | 1,626 | shared |
| **pt_memory** capture 32×24 + playback 32×24 + control | **1,580** | **radio only** (rf_rx/rf_tx sample clocks) |
| ingress `pt_cdc_fifo` 28×40 (+ptrs) | 1,275 | shared (stopped-only clock mux) |
| egress `pt_cdc_fifo` 24×40 (+ptrs) | 1,110 | shared (stopped-only clock mux) |
| pt_h2d_gearbox (8×40 Gray FIFO, capture) | 481 | shared |
| pt_freq_count ×2 | 592 | shared (source mux) |
| pt_lc_rx + pt_lc_tx (8b/10b) | 385 | wired only |
| pt_interp2x | 149 | radio only |
| pt_pattern_check + pt_pattern_gen + syncs | 251 | **wired only** (wire_rx/tx clocks) |
| quad framer tx/rx + header + collect | 340 | shared |
| sample pack / unpack | 127 | radio only (necessarily) |
| pt_d2h_gearbox + host_link + rate clock | 128 | shared |
| pt_gain_rx + opcode4 state in pt_core | ~70 | radio only (fast gain) |
| pt_spi, calibrator, clocktree_slow, vreg_seq, syncs, glue | ~328 | shared |
| **Total** | **8,442** | limit 8,192: **over by 250** |

`pt_block_*`, `pt_lane_compact*` are not instantiated (only verification miters); they cost
nothing in the netlist but should be moved to `verification/` or deleted to avoid confusion.

## 1. Function inventory

| Function | RTL | Classification | Comment |
|---|---|---|---|
| Host pad-edge DDR, 1:4/4:1 gearbox, rate clock | pt_host_link | shared | already one path |
| Dense framing, header, H2D validate, command decode | pt_quad_link, pt_dense_header | shared | `payload_iq` only picks owner |
| Ingress / egress CDC FIFOs (40-bit quads) | pt_core `pt_cdc_fifo` ×2 | shared | **the 40-bit lane already serves both**: wired quads directly, IQ via pack/unpack into quads |
| H2D FIFO | pt_h2d_gearbox | shared | |
| IQ sample pack/unpack, mode8 | pt_quad_gearbox | radio only | true difference (24-bit samples ↔ quads) |
| 8b/10b RX/TX | pt_linecode | wired only | true difference |
| 2× halfband interpolator | pt_interp2x | radio only | true difference |
| PRBS / pattern gen + checker | pt_pattern | wired only today | **should be shared** (see S3) |
| Capture/playback memory | pt_memory | radio only today, separate storage | **duplicate storage** of the transport banks (see S1) |
| Fast gain (opcode4) | pt_core, pt_gain_rx | radio only | IX-11 threshold is the wired twin (see S2) |
| IX-11 fast threshold | not implemented | wired | fold into S2 |
| IX-12 raw dual-lane capture | not implemented (digital side) | wired | ride the shared ingress lane (S4) |
| Edge histograms (S5 phase trim) / eye scan | not implemented | wired | reuse checker counter + capture bank (S4) |
| Freq counters a/b | pt_freq_count ×2 | shared (source mux) | small further sharing (S6) |
| IX-8 timestamp / latency, Thread CSL, IX-11 readable latency | not implemented | radio + wired | one stamp unit (S5) |
| Calibration | pt_calibrator (ref trim SAR) + host-driven D-CAL-1 | shared | no on-chip sequencer (D11), keep |
| Status bits 4/5, obs mux | pt_core / pt_digital | shared (owner-multiplexed) | keep pattern: owner-multiplexed status |
| Pattern / memory register fields | regfile | named wired (`debug.pattern`) / RF (MEMORY 0x20–0x26) | rename/re-document as owner-generic |

The transport is already the shared structure the user asked for. The duplication left is in
the debug/test side: memory, pattern engine, and the two fast-command paths that are being added.

## 2. Target architecture

```
                         SPI (SCLK) ── pt_mgmt/regfile ──┬── analog_cfg / debug_cfg
                                                         │  (fast-control override: S2)
 host pins ─ pt_host_link (DDR, 1:4/4:1, hddr, hcore) ───┤
                 │ H2D quad                ▲ D2H quad    │
                 ▼                         │             │
          quad_link_rx ── cmd decode ──► FAST-CTRL (one pending, toggle CDC, echo)  [S2]
                 │                         ▲   │apply in ingress_clk domain
           collect                         │   ▼  gain(RF) | VTH_A/B (wired)
                 ▼                   quad_link_tx ◄── status/echo frame (opcode4/5), STAMP [S5]
   ┌────────── EGRESS BANK 24×40 ───────────┐   ▲
   │ write: rx_quad (host) | SPI quad (S1)  │   │
   │ read : FIFO | playback loop  (S1)      │  INGRESS BANK 28×40 ◄── write: lane mux
   └──────────────┬─────────────────────────┘   │ read: FIFO | SPI index (capture, S1)
        egress_clk│ (stopped-only mux)          │ ingress_clk (stopped-only mux)
                  ▼                             │
         PATTERN GEN (40b) ──mux──┐   PATTERN CHECK (40b) + event counter [S3,S4]
                  │               │             ▲
         ┌────────┴──────┐        │      ┌──────┴────────────────────────────┐
         ▼ wired         ▼ radio  │      │ wired: raw | 8b/10b RX | IX-12 raw │ radio: sample_pack
     8b/10b TX (opt)  sample_unpack      └───────────────────────────────────┘
         ▼                ▼ interp2x (opt)
     wire_tx 40b      rf_tx 24b                       freq_count a/b (shared ref timer, S6)
```

Rule: everything between the host pins and the two "lane adapters" (wired: raw/8b10b/raw-IX12;
radio: pack/unpack/interp) is one 40-bit quad structure clocked by the stopped-only owner clock
mux. Mode-specific logic exists only in the lane adapters and in the fast-control apply table.

## 3. Sharing proposals

Timing basis: characterized in-window slow library `ss_032C_3v15` (D14): dffrnq clk→Q 1.86 ns +
setup 0.84 ns, so a 12.8 ns hcore cycle has ≈ 10 ns of logic; a mux2 level costs ≈ 0.5–0.7 ns at
ss32 unwired (estimate from the same library family, not run). The existing hcore critical path is
the H2D FIFO read mux (−10.56 ns in the last evidence run, pre-pipelining) and the PRBS checker on
`wire_rx_clk` (≈ −7 ns at 12.3 ns, T10). No proposal below may add a level to either.

### S1. Capture/playback lives in the transport banks (largest saving)

- Delete `pt_memory`. In stopped-only "memory mode" (ENABLE=0 to change, like the present
  disarmed rule):
  - **capture** = the ingress bank fills from the active lane (IQ samples via `pt_sample_pack`,
    wired raw quads, 8b/10b symbols, or IX-12 raw lanes) and stops when full (`capture_done`); the
    host engine is not popping. SPI reads by quad index.
  - **playback** = SPI writes the egress bank by quad index; the read pointer recirculates
    (loop) or stops after N quads (one-shot), feeding the normal output path (unpack/interp for
    radio, direct or 8b/10b TX for wired).
- Capacity: ingress 28 quads = 46 IQ samples (12-bit) / 70 (mode8) / 1,120 wired bits; egress
  24 quads = 40 IQ samples / 960 wired bits. Both ≥ today's 32 samples.
- New capability for free: SPI-only wired TX playback and wired RX capture (bring-up with no
  host link, the stated purpose of the MEMORY fallback), and IX-12 eye snapshots.
- Implementation detail that keeps timing neutral:
  - ingress read: the SPI index loads the **registered** read pointer, so the read mux tree gets
    no extra level;
  - egress write: array write clock is `mux(hcore, ~SCLK)` with one more stopped-only
    `pt_clock_mux`, and the write data/address get a 2:1 mux. That adds ≈ 0.6 ns on an hcore
    write path that is short (collector register → array), not the read mux.
- FF: −1,580 (pt_memory) + ≈ 40 (40-bit SPI quad staging register is shared with the existing
  24-bit memory_wdata, plus 16) + ≈ 30 (loop count, capture_done, mode) = **−1,510 FF**. Area: ≈
  −0.13 mm² of flops+muxes (T11 estimate ≈ 0.15 mm² for pt_memory).
- Must stay different: nothing in storage; the lane adapter decides the format.
- Lost: capture **concurrent** with live host streaming (today pt_memory taps the ADC
  in parallel). That is redundant because the stream already carries those samples, and an
  in-memory TX→RX loopback still works (egress playback + ingress capture are different banks).
- Risk: medium. The MEMORY register ABI 0x20–0x26 changes from 24-bit samples to quads (or
  sample-indexed access through software packing). One clock mux is added on the egress array
  (CTS + SDC `set_clock_groups -physically_exclusive`). The lifecycle proof
  `transceiver-shared-egress-lifecycle` must be extended to cover memory mode. A failing FIFO
  bank now takes the debug memory with it. That is acceptable because the same flops are proven
  by the stream benches.

### S2. One "fast analog control" command (opcode4 generalized)

- The H2D decode, legality check, one-pending rule, 8-bit argument register, toggle CDC,
  apply-domain register, mark-pointer and echo frame are identical for RF gain (RXR-D2) and wired
  threshold (IX-11). Today `pt_gain_rx` runs on `rf_rx_clk`. Move it to `ingress_clk` (it already
  marks the *ingress* write pointer, and that clock is the owner-muxed one).
- Argument semantics by owner (no new opcode needed):
  - RF: `{LNA[6:5], PGA[4:0]}` as now; RXR-D1 `tia_gain/lna.att` extend the **macro mapping
    table**, not the command (T9).
  - wired: `arg[7]` = A/B target (or a reserved code for "common offset"), `arg[6:0]` = signed
    VTH. SETTLE becomes a per-owner constant: 20 samples (RF) or 0–3 quads (wired, DAC 50 ns).
- Echo/rate: IX-11 needs ≥ 2 MHz updates and ≤ 300 ns latency. The measured gain path is 189 ns
  at full rate (wired runs full rate). The echo (status frame, ≤ 1 frame = 205 ns) completes
  before the next 500 ns command, so the one-pending rule holds. Add a "no echo" argument variant
  only if a bench shows rejects.
- Fold the proposed opcode5 RF status (overload RXR-D4) and the wired IX-11 "capture→pin latency"
  into the same echo/status frame generator.
- FF: one implementation ≈ 80 versus ≈ 150 for two → **≈ 70 FF avoided**. Timing: unchanged
  (moving to ingress_clk at ≤ 62.5/80 MHz, one 2:1 owner mux in the apply table).
- Must stay different: the apply table in `pt_digital_macro` (RF gain codes vs VTH DAC
  overrides) and the settle constant.
- Risk: low. `check_fast_gain.py` already covers the mechanism; add a wired variant.

### S3. One pattern engine on the shared lane

- Move `pt_pattern_gen` to the egress side (clock = `egress_clk`), replacing the bank head: wired
  directly, radio through `pt_sample_unpack` (PRBS into the DACs or a digital loopback).
- Move `pt_pattern_check` to the ingress side (clock = `ingress_clk`), tapping the lane-mux output
  (wired raw, 8b/10b-decoded, or packed ADC quads in digital/converter loopback).
- That gives radio converter-interface BER coverage and a test of the 8b/10b output with the same
  logic, at no FF cost (≈ +10 FF of select). The existing `pt_sync_vec` cfg synchronizers move to
  the muxed clocks.
- Timing: no change for wired (same rate). The checker is already −7 ns at 12.3 ns (T10) and
  must be pipelined anyway: register the mismatch vector, then a two-stage popcount (D4 did part
  of this). The added input 2:1 lane mux must sit **before** the checker's input register.
- Must stay different: none.
- Risk: low to medium. The `prbs_select` muxes in pt_digital move into pt_core, and
  `tb_digital_prbs` must be updated (it is already broken, D13).

### S4. IX-12 raw capture and eye/edge histograms through the same lane

- IX-12: the wired boundary already delivers 40-bit quads. In raw mode the lane adapter carries
  20 data + 20 edge bits (psel / psel+4) per WCLK40 into the **same** ingress bank and framer. The
  1.5 Gb/s at a 750 MHz ring is inside the 2.88 Gb/s framed capacity. Cost is a 2:1 input mux in
  the wired lane adapter, ≈ +5 FF, versus a separate path with its own FIFO (≈ +1,100).
- Histograms (S5 phase trim, eye scan): the FPGA computes them from the IX-12 stream (primary).
  The on-chip fallback (SPI only) uses:
  - one ingress capture (S1) of raw lanes; or
  - the pattern checker's 16-bit saturating error counter as a generic event counter, with an
    event select (data≠edge transitions on a selected phase, or VTH_A hits), swept by
    software.
  That is ≈ +20 FF instead of 8 × 16-bit dedicated counters (128 FF).
- Risk: low. Histogram speed over SPI is slow but it is only the fallback.

### S5. One timestamp / latency unit

- One 20-bit free-running counter on the **egress** owner clock (sample index for RF, quad
  index for wired), plus latch registers for:
  - TX launch: first valid output after `*_running` rises;
  - fast-control apply (mark);
  - the RX quad index at the same instant (counted on ingress_clk, latched through the existing
    toggle).
  Values are reported in the echo/status frame (S2) and readable over SPI.
- Serves IX-8 (Channel Sounding RTT, sample-index timestamp at TX launch), Thread CSL (±16 µs: a
  coarse epoch is enough) and IX-11 "D2H capture→pin latency fixed and readable" (a constant per
  rate, published as read-only status).
- Determinism comes from fixed start thresholds (WIRE_START, RF_START), quad-boundary launch and
  the FIFO prefill. The stamp only makes it observable.
- FF: ≈ 70 total versus ≈ 140 for separate RF and wired units → **≈ 70 FF avoided**. Timing:
  20-bit incrementer at 80 MHz is fine (carry-select if needed).
- Risk: low. The ≤ 5 ns rms RTT is a calibration result on fixed pipelines, not a counter
  property.

### S6. Frequency counters

- Already shared between modes through the 6-source mux. Instance b must run concurrently with
  a in wired mode (CDR handover `locked_ref` while a watches the TX ring), so do not merge the two.
- Small saving: one reference-domain window LFSR timer and one commit capture for both instances
  (windows are configured per instance but can be required equal, or derived from one timer by
  tap) → **≈ −30 FF**. The D2 SCLK-sync removal is already done.
- Risk: low, but it touches a block that just closed timing (D4). Do it last, or skip it.

### S7. 8b/10b and interpolator: keep separate

- The two blocks are mutually exclusive by owner but have unrelated datapaths: 10b
  decode/encode tables, comma barrel shift and repack on 40-bit quads at wire clocks, versus a
  7-tap halfband on 2×10-bit samples at rf_tx_clk/2 and 80 MHz.
- Register sharing (muxing their flop D-inputs) would save at most ≈ 149 FF. It would cost a mux
  level in front of each of those flops, a third clock on those flops, and the loss of
  two bit-exact, independently verified blocks. Net area ≈ −0.01 mm².
- Recommendation: **do not share.** This is the "truly differs" exception in the mandate. They do
  share their *slot* (the lane adapter position and the stopped-only select), so the pipeline
  around them (bank head, running/starved logic, valid) is common already.

### S8. Register fields and debug muxes

- Re-document `debug.pattern` as owner-generic (lane pattern), and MEMORY 0x20–0x26 as the bank
  capture/playback (quad indexed, owner-generic).
- Name status bits 4/5 per owner (already requested in T8).
- Add `fast_ctrl` status (pending/rejected), which replaces gain-only wording.
- No FF change.
- Not recommended: banking the 823 analog/debug config bits by owner. It would save several
  hundred FF of shadow/active, but wired and RF islands can be configured at the same time, and
  aliasing analog configuration is a debuggability and safety loss.

## 4. FF budget before / after (limit 8,192)

| Item | FF |
|---|---:|
| Baseline (measured) | 8,442 |
| S1 capture/playback in banks | −1,510 |
| S6 shared freq-count timer | −30 |
| S3 shared pattern engine (select, re-sync) | +10 |
| S2 IX-11 threshold on the fast-control path (incremental: target/apply regs, settle) | +25 |
| S2 opcode5 status (RXR-D4 overload, latency) in the same echo generator | +20 |
| S4 IX-12 raw lane mux + event-counter select | +25 |
| S5 timestamp/latency unit | +70 |
| **After, with all new features** | **≈ 7,052** |
| Margin to 8,192 | ≈ 1,140 (14 %) |

The same features implemented separately (pt_memory kept, a second fast-command path, separate
timestamp units, dedicated histogram counters, a separate raw FIFO) would come to ≈ 9,900 FF.
Even without IX-12 its own FIFO, ≈ 8,800. Neither fits.

The margin should go partly back into the transport. T11 says ingress 24/26 overflowed at the
3.125 Gb/s start-up transient, and ingress is 28 today. Restoring ingress to 32 quads (+170 FF)
leaves ≈ 970 FF. Keep the rest for ss32 pipelining registers (H2D FIFO read mux, framer, commit
path, PRBS checker popcount), estimated +200–400.

## 5. Ordered implementation list for the AC-1 restart

1. **Freeze the lane boundary in pt_core**: one `lane_in[39:0]/lane_in_valid` (ingress side) and
   `lane_out` (egress side) with the adapters (wired raw / 8b10b / IX-12 raw; radio pack /
   unpack / interp) as the only owner-specific code. Pure refactor. Re-run
   `transceiver-dense-*`, `check_linecode`, `check_interp2x`, `check_fast_gain`.
2. **Close hcore at 78.125 MHz on ss_032C_3v15 first** (H2D FIFO registered read, framer and
   commit pipelining). Sharing must not be merged on top of a failing core.
3. **S1 memory mode in the banks**, then delete `pt_memory`. Add the egress-array clock mux
   with its SDC exclusivity. Port the MEMORY register ABI (regfile generator) and extend the
   lifecycle formal. This takes the design under 8,192 by itself (≈ 6,930).
4. **S3 pattern engine moved onto the lane** (fix `tb_digital_prbs`, D13; pipeline the checker
   to meet 12.3 ns).
5. **S2 generalize opcode4** to fast analog control: move `pt_gain_rx` onto `ingress_clk`, add
   the wired apply table for VTH_A/B (IX-10/11), and add the per-owner settle constant. Write
   `check_fast_ctrl.py` (RF regression + wired variant at 2 MHz).
6. **S5 stamp unit** and the shared echo/status frame (opcode5: RXR-D4 overload, latency).
7. **S4 IX-12 raw mux** in the wired adapter plus the event-counter select on the checker.
8. Ingress back to 32 quads if the 3.125 Gb/s start-up bench still needs it.
9. Optional: S6 shared freq-count timer. Move the dead `pt_block_*` files out of `rtl/`.
10. Re-run yosys FF count, module STA screen on ss32, GLS loopback, and report the numbers in
    interface-changes.md (T-row) with the budget table above.

## 6. Top savings

1. **S1: capture/playback in the transport banks: −1,510 FF** (the whole overflow and more).
   It also adds wired capture/playback over SPI.
2. **S4: IX-12 raw capture through the shared ingress lane: ≈ 1,100 FF avoided** (no second
   raw FIFO).
3. **S2: one fast analog control command for gain and threshold: ≈ 70 FF avoided**, and one
   verified mechanism.
4. **S5: one timestamp/latency unit for CS RTT, Thread CSL and wired: ≈ 70 FF avoided.**
5. **S4: histogram via the checker event counter instead of 8 counters: ≈ 110 FF avoided.**
6. **S3: one pattern engine: 0 FF, but radio gains BER/loopback coverage.**

Kept separate on purpose: 8b/10b vs interpolator (S7), sample pack/unpack (radio only), the two
freq-counter instances (concurrent in wired mode), and the analog configuration registers (no
owner banking).
