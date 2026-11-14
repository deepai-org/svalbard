# Independent review: pad-free POR override (pt_por_path) and SPI write qualifier (2026-11-14)

Saved by the digital owner from the reviewer's reply (the reviewer could not write files). Scratch benches, mutants and
netlists of the reviewer: this directory (tb_review.sv, tb_h7.sv, my_mutants.py, my_spi_mutants.py).

Verdicts: pt_por_path.sv GO-with-conditions (P1, P2 blocking; P3 mandatory at integration); its bench GO-with-conditions
(B1, B2); pt_spi.sv GO-with-conditions (text only: S1-S3); SPI race bench GO-with-conditions (S4); pt_provider_io.sv
GO-with-conditions (MOSI Schmitt, pull strength vs FPGA pull-ups).

## POR path
- P1 (High): ONE flop of unknown power-up state decides whether a healthy POR counts. With RESET_N tied high and no
  clock edge ever, 6 of 128 (flop, pin) states release reset against an asserted POR with no strap: flop = 1, RESET_N = 1,
  (CS_N, MOSI) in {00, 01, 11}. Those pin states are ordinary at power-up (host unpowered: pins clamp low; unconfigured
  FPGA with pull-ups; host I/O rail not up; host idling MOSI high). The event leaves no trace. Fix (preferred): keep ovr
  and add a multi-bit mixed-polarity key k: dffrnq shift register clocked by SCLK rising, shifting MOSI only while
  RESET_N is low, asynchronously cleared by `idle` alone; rst_n = reset_n_pad & (por_n | por_bypass | (ovr & k == KEY)).
  A uniform or random wake-up state then cannot enable the override; k changes only while the die is in reset or by the
  dead-man clear (which also clears ovr), so the output stays monotonic.
- P2 (Medium): the key is "all three SPI pins high", the commonest non-default bus state: any RESET_N rising edge that
  finds SCLK = 1 and not (CS_N = 1, MOSI = 0) arms a healthy die. Closed by the P1 fix.
- P3 (Medium, integration): the SPI pins now reach every flop's reset pin through a timed RN->Q arc. Required: false
  path through the ovr (and key) Q pins for setup and hold; no create_clock on reset_n_pad; dont_touch / keep hierarchy on
  the pt_por_path cells; list the unclocked flop(s) in the unconstrained-endpoint waiver.
- P4 (Medium, rescue mode only): a runt on the dead-man (CS_N & ~MOSI raw) or on RESET_N can be a runt on rst_n for the
  whole die. Fix: Schmitt on MOSI (pt_provider_io.sv spi_data), procedure text: MOSI leads CS_N by >= 1 us, host clears
  rst_flag after keying and re-keys when it reads it set, 40-clock framing with trailing 0xFF for ordinary controllers.
  A board pull-up on MOSI is NOT an option.
- P5 (Low): status bits are live, not sticky; a host idling MOSI low always reads ovr_armed = 0.
- P6 (Info): no loops; ovr only ORs into the release term so a healthy POR or the strap is never blocked; RESET_N must
  be drivable low for path 2 (board rule); H7 (no runt release at an unkeyed RESET_N rise) holds only because D = SCLK.
- B1: mutant D = 1'b1 survives in zero-delay RTL: rerun the bench on a copy with a delayed clock pin (tb_h7.sv) and
  add the mutant. B2: the bench asserts the P1 residual as correct; add non-idle power-up cases.

## SPI
- All-or-nothing and exactly-once hold by structure for any CS_N rise timing; aborted and read transactions never
  write; regfile commit timing consistent; no extra clock, no new CS_N high-time rule.
- S1: wr_q stays set until the next SCLK rising edge: an SCLK runt in idle that the falling-edge register file sees
  but wr_q does not would commit the frame twice (a COMMIT frame is not idempotent). Host/board rule: SCLK glitch-free
  between transactions (Schmitt helps); mitigation: send 33 clocks.
- S2: the shift register now runs on other devices' clocks (no write can result): dedicated SPI bus recommended.
- S3: a frame whose CS_N rises after the 32nd rise but before its fall now writes; update ABI text and SDC comments.
- S4: bench holes: counter wrap (frame >= 100 clocks), commands 0x81 / 0xC0 / 0xFF must not write, SCLK runt in idle.
- S5: Schmitt on MOSI too; show the pad pulls against an unconfigured FPGA's pull-ups.
