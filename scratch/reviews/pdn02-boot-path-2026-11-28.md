# PDN-02: does the boot path work under the macro supply ripple? (2026-11-28)

Question (triage `risk-triage-2026-11-28.md`, PDN-02 rated KILLER (unproven)): with the single-phase launch the
digital macro supply ripple is 212 mV (pt_rf) / 313 mV (pt_wired) pk-pk (`spec/power-delivery.md` 5.2, `e8_decap.py`)
against 150 mV. Do reset release, SPI write/read-back, the host link at div4 and the POR still work?

**Verdict: the boot path works under the ripple. Downgrade PDN-02 to PERF for the core functions, with one bring-up
rule.** SPI, reset release, the POR and every host-link domain behind the rate divider have large margin even with the
whole pk-pk ripple applied as a DC droop. The only boot-path logic that fails is the host-rate divider, which still
runs at the full 156.25 MHz host word clock in div4 mode. At ss 3.15 V it fails without ripple too. It passes at the
3.50 V trim, or at 3.15 V with the full droop if the FPGA drives `host_word_clk` at 125 MHz. SPI never depends on it,
so a slow die can always be reached, trimmed and read back. The cheapest fix needs no silicon change: a bring-up rule
(below). The ripple problems that remain are real but they are performance problems: the ref-clock island sequencers
at full droop, the analog victims (QVCO spurs, ring-PLL jitter) and the D2H pin windows.

## What was run and what was assumed

**Run (rerun, not read):**
- Libchar (`verification/digital_hardening/libchar.py`, the same anchored ngspice method as the delivered 3.50 V
  library) of the 6 reference cells used for the earlier trim factor (dffrnq_2, mux2_2, aoi21_2, buf_4, nand2_2,
  clkbuf_8) at ss 32 C and **2.84 / 3.00 / 3.19 / 3.35 V**, i.e. 3.15 V and 3.50 V minus the full pk-pk (313 mV)
  and minus half of it. Cache `scratch/pdn02-boot/cache/`, ratios `scratch/pdn02-boot/ratio.py`.
- Routed OpenSTA on the **delivered macros** (DG9-29 pt_rf, pnl sha d0fe53b3; DG9-30 pt_wired, pnl sha 01a46445;
  final max/min SPEF of their runs), the current SDC (identical to the run's copy), propagated clocks, SDC clock OCV
  ±8 %, 0.25 ns uncertainty, `HOST_RATE_DIV 4`, recovery/removal on. Scripts `scratch/pdn02-boot/sta*.tcl|sh`.
- Known answer: pt_wired ss 3.50 V rate 1 reproduces DG9-30 exactly (hcore -0.060, wtx -0.068, hddr -0.419, hsdr
  -0.309, h2d -0.289, d2h_oddr -0.509, d2h_fwd -1.344); pt_rf reproduces DG9-29 (hddr -0.116, d2h_oddr -0.274,
  d2h_fwd -1.237).

**Model of the droop (assumed, stated):** no Liberty exists below 3.15 V in the window, so the droop is a uniform
cell-delay factor K on the characterized library (data cells x K; clock cells x K x 1.08 late / x K x 0.92 early).
Wires are not scaled. Measured delay ratios (median / p90 over all arcs, worst of the 6 cells):

| Supply | vs library | median | p90 | K used |
| --- | --- | ---: | ---: | --- |
| 2.84 V (3.15 - 313 mV) | ss 3.15 V | 1.143 | 1.202 | **1.20** (bound), 1.14 |
| 3.00 V (3.15 - 157 mV) | ss 3.15 V | 1.062 | 1.088 | (not needed) |
| 3.19 V (3.50 - 313 mV) | ss 3.50 V | 1.111 | 1.164 | **1.16** |
| 3.35 V (3.50 - 157 mV) | ss 3.50 V | 1.049 | 1.073 | (not needed) |

This is pessimistic in four ways:
1. The whole pk-pk is taken as droop. PD2-5 defines the limit as ±2.3 % (symmetric), so the real droop below the
   DC level is about half: K ≈ 1.06-1.09 at 3.15 V.
2. The pt_wired number (313 mV) is applied to pt_rf too (pt_rf: 212 mV, K ≈ 1.10 at full pk-pk).
3. The ripple figures are for full-activity modes: 40 / 60 mA, D2H at div2 / 156.25 MHz, one launch packet per
   12.8 ns. At boot the islands are off and only SPI and an idle or training host link toggle, so the charge per
   edge is a fraction of that.
4. A uniform droop over the whole path ignores the timing of the droop (next section).

**Hold / overshoot:** the ff side uses the existing ff_n40C_3v60 library (the sign-off fast bound) and ff_022C_3v35,
with no extra factor. 3.60 V at -40 C is faster than the overshoot peak in the window (3.35 V + 157 mV = 3.51 V at
22-32 C; even + 313 mV = 3.66 V at 32 C is not faster than -40 C / 3.60 V by more than a few %). The launch and
capture of a hold check see the same edge at the same instant, so the ripple is common-mode for hold.

**POR:** not timed. It is an analog block on the always-on rail, outside the macro. Per `board-requirements.md` B1
(`analog/core_support` evidence), the on-chip POR ignores dips that stay above 1.5 V. The worst macro dip is about
2.8 V even with the full pk-pk taken as droop, so it can neither trip the POR nor block it. RESET_N comes from the
board supervisor (B1). Brownout of the board rail is covered by B1 and has nothing to do with this ripple.

## Results: per chip, per corner, worst setup / hold slack (ns) at div4

Setup = worst slack to the clock, intra-domain and crossings. Boot domains: `sclk` (SPI, 200 ns), `hword` (host word
clock pin, 6.4 ns, carries the rate divider), `hddr` (25.6 ns at div4), `hsdr`, `hcore` (51.2 ns), `h2d`, `h2d_cap`,
`mon_host`, `egress_mem_sclk`. `ref` (10 ns, island sequencers, not a boot domain) is shown for information.

### Setup

| Chip | Corner | sclk | hword | hddr (reg-to-reg / pin windows) | hsdr | hcore | h2d | h2d_cap | ref (info) |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| pt_rf | ss 3.15 V, no ripple | +35.5 | **-0.17** | pin -2.01 | +5.4 | +16.7 | +10.0 | +6.1 | -1.56 |
| pt_rf | ss 3.15 V, K 1.14 | +32.2 | **-0.93** | pin -2.79 | +4.5 | +16.4 | +9.7 | +6.2 | -3.21 |
| pt_rf | ss 3.15 V, K 1.20 | +30.8 | **-1.25** | -0.33 (D2H data pins) / pin -3.12 | +4.1 | +16.2 | +9.6 | +6.3 | -3.92 |
| pt_rf | ss 3.15 V, K 1.20, hword 125 MHz | +30.8 | **+0.35** | pin -2.16 | +7.3 | +16.2 | +12.8 | +7.9 | - |
| pt_rf | ss 3.50 V, no ripple | +39.1 | +0.66 | pin -1.22 | +6.4 | +17.1 | +10.3 | +6.1 | +0.10 |
| pt_rf | ss 3.50 V, K 1.16 | +35.8 | **-0.09** | +1.40 (data) / pin -1.98 | +5.5 | +16.8 | +10.0 | +6.2 | -1.52 |
| pt_wired | ss 3.15 V, no ripple | +37.1 | **-0.13** | -0.02 | +4.8 | +8.9 | +9.9 | +6.1 | -1.39 |
| pt_wired | ss 3.15 V, K 1.14 | +33.9 | **-0.88** | -0.53 | +3.9 | +8.6 | +9.6 | +6.3 | -2.83 |
| pt_wired | ss 3.15 V, K 1.20 | +32.6 | **-1.20** | -0.94 (D2H data pins) | +3.4 | +8.5 | +9.5 | +6.3 | -3.45 |
| pt_wired | ss 3.15 V, K 1.20, hword 125 MHz | +32.6 | **+0.40** | +0.22 | +6.6 | +8.5 | +12.7 | +7.9 | - |
| pt_wired | ss 3.50 V, no ripple | +40.4 | +0.81 | +0.54 | +5.9 | +9.3 | +10.2 | +6.1 | +0.19 |
| pt_wired | ss 3.50 V, K 1.16 | +37.3 | +0.08 | +0.06 | +4.9 | +9.0 | +9.9 | +6.2 | -1.23 |

- **SPI (sclk):** every internal and I/O path has +30 ns or more at K 1.20. The slack falls by about 2.4 ns per 0.1
  of K, so failure would need K ≈ 2.3 (a supply near the threshold region). Write and read-back are safe. The
  SDC's SPI I/O budgets apply; the separate pad / route model of `spi_signoff.py` was not rerun, but it changes
  the I/O terms, not the 30 ns margin scale.
- **Reset release (recovery / removal into every boot domain, both chips):** worst recovery at K 1.20 is +18.9 /
  +19.5 (hddr), +34.6 / +38.9 (hcore), +17.7 / +18.6 (h2d), +89 (sclk, CS_N reset of the SPI counter). Worst removal
  at ff_n40 3.60 V is +0.37 (hcore, `rr_tx` -> `frame_tx.training`), +0.45 (hddr), +0.84 (h2d), +1.37 (h2d_cap).
  No reset-release path of the boot domains fails. The only failing recovery paths are `ref`
  (`vreg_seq.rdy_tx -> wtx.*`, island sequencer), `ctw` (detector) and, on pt_wired, `wstb`
  (`wgear.g_rn -> dx_s`, wired RX gearbox). None of them is in the boot path; their islands are off at reset.
- **Host link behind the divider (hcore, h2d, h2d_cap, hsdr, mon_host):** +3.4 ns or more everywhere, including
  K 1.20 at 3.15 V.
- **The one failing boot element is the host-rate divider in the `hword` domain** (`host_rate.div / gap / cur /
  hold_n / ne`). It runs at the pin clock (6.4 ns) in every rate mode, so div4 does not relax it. It fails at ss
  3.15 V even without ripple (-0.17 / -0.13). This was not reported before: the DG9 rows list the rate-1 domains.
  It fails at -0.9 to -1.25 with the droop and passes at 3.50 V (+0.66 / +0.81). At 3.50 V with the full droop it
  is at -0.09 (pt_rf, inside the 0.25 ns uncertainty) and +0.08 (pt_wired). At 3.15 V with the full droop it
  passes if `host_word_clk` is 125 MHz (8.0 ns): +0.35 / +0.40.
- **hddr pin rows** (`hddr -> d2h_pin*`, `word_clock_mux -> d2h_clk_pin`) are the source-synchronous D2H output
  windows, set by the crude `0.2 x HLINK` output delay in div4 mode. The `d2h_clk_pin` row already fails without
  ripple at 3.50 V (-1.22, pt_rf). These are the same window items as `d2h_oddr` / `d2h_fwd` at rate 1, accepted
  under FPGA phase training (DG9-21 / DG9-32). Data and forwarded clock come from the same edge through matched
  launch cells, so the ripple shifts both together. They are not boot blockers: register read-back over SPI does
  not use them.

### Hold (ff, overshoot side; rate 4; worst over all clocks / boot domains)

| Chip | ff_022C 3.35 V | ff_n40C 3.60 V | worst boot-domain path at ff_n40 3.60 V |
| --- | ---: | ---: | --- |
| pt_rf | +0.199 | +0.096 | h2d +0.096; sclk +0.298, hcore +0.283, hddr +0.340, hword +0.397 |
| pt_wired | +0.106 | +0.027 | h2d +0.027; sclk +0.307, hcore +0.312, hddr +0.393, hword +0.419 |

Hold passes in every domain (reg-to-reg), as in DG9-29 / DG9-30.

## Is the ripple correlated with the boot clocks?

Yes. The ripple is the launch current of the macro's own clock edges, so the droop starts at the launch edge. The
network rings at f_ar 92-108 MHz with Q 2.0-2.3 (`power-delivery.md` 5.2), so one droop lobe lasts about 5 ns and
decays within about 2 ring periods (≈ 20 ns). What this means:

- **SPI (200 ns), hcore at div4 (51.2 ns), hddr at div4 (25.6 ns):** a path starts during the droop but finishes
  long after the ring has died away. The average supply over the path is close to the DC level. The uniform
  full-droop factor applied here is far more pessimistic than the real case, and these domains pass even with it.
  At div4 the 78.125 MHz launch component that sets the 212 / 313 mV figure also drops to 19.5 / 39 MHz, below the
  anti-resonance (|Z| falls toward the low-frequency side), so the ripple itself is lower in the boot mode.
- **hword (6.4 ns):** the whole divider path sits inside the first droop lobe after the edge that launches it, so
  the uniform droop is a fair model here, and this is where the margin is gone. The divider is a handful of flops;
  its own switching is negligible. Its droop comes from whatever else toggles on hword-derived edges. At boot (host
  link idle or training, islands off) that is much less than the 60 mA case, but this run does not quantify it.
- **Capture edge:** in a single-cycle check the capture edge is the next launch edge and sees the next droop lobe.
  Clock insertion is derated with the data (x K x 1.08 / 0.92 OCV), so the slack already carries it.

## Cheapest fix: bring-up rule, no silicon change

1. Bring up with the SPI only. It works on every die with more than 30 ns margin. Set the 3.50 V trim on slow dies
   (`status.health.*`, ring monitor) before using the host link.
2. On an untrimmed slow die, or before the trim is chosen, the FPGA drives `host_word_clk` at **≤ 125 MHz** for
   the div4 boot link. That passes at 3.15 V with the full droop on both chips. At 3.50 V the full 156.25 MHz clock
   with div4 is at 0 ± 0.1 ns with the full droop and passes clearly with the realistic half droop (K ≈ 1.05-1.07).
   **To confirm (fpga-connection-plan owner):** the FPGA host-link gateware can run the word clock below
   156.25 MHz. The macro has no PLL or frequency-dependent logic on that clock, and STA shows it is
   frequency-agnostic.
3. If a silicon fix were ever wanted: retime the `host_rate` divider (decode `gap/cur/hold_n` one cycle earlier,
   a few flops). The two-phase launch is not needed for boot.

## Items for the register owner (not edited here)

- PDN-02: KILLER -> PERF for the core functions (boot, SPI, reset, POR, host link at div4), on the evidence above.
  The analog-victim side (QVCO spur rejection, ring PLL 7.3 ps, `pt_rf` decap tiles) and the full-rate host link
  stay as performance items.
- New: the hword-domain rate divider fails at ss 3.15 V without ripple (-0.17 / -0.13 ns); it needs the trim or a
  slower host word clock. That is a bring-up rule.
- New, not boot: the `ref` domain island sequencers (`vreg_seq.rdy_tx -> wtx.ok_s/ser_q/de_q` RN, `wtx.pad_seq`,
  `wrx.frun -> regs.wrx_fll_err`) fail at ss 3.15 V without ripple (-1.56 / -1.39) and at 3.50 V with the full
  droop (-1.52 / -1.23). They pass at 3.50 V without ripple (+0.10 / +0.19). The mitigation is the trim plus a lower
  REF_IN frequency on slow dies. The wired-RX gearbox reset (`wgear.g_rn`, wstb) recovery is -1.49 at K 1.20,
  -0.26 at 3.50 V K 1.16.

Files: `scratch/pdn02-boot/` (libchar wrapper `lc.py`, `ratio.py`, `sta.tcl`, `sta_b.tcl`, `sta_r.tcl`, run
scripts, logs `out/`).
