# Host-link bandwidth expansion: per-pin rate, reversible banks, lanes, overhead, exotic options

Status: analysis/spec, 2026-11-10 (host-link review). Demands: `interface-changes.md` § "Host-link bandwidth (HB-1..HB-9)".
Spec rows updated: `spec/interface-requirements.md` §3 (HL-H2D-PADIN, HL-RATE, WR-HL-LINECODE, new HL-DIR / HL-FRAME / HL-MARGIN / HL-STRETCH),
`spec/performance-requirements.json` (WR-HL-LINECODE), `spec/board-requirements.md` (HL-B1, HL-B2, HL-B7, ECP5 row).
Risk policy: `MANDATE.md` (conventional first; novelty only where nothing low-risk works). Not committed.

## 0. Answer

Yes. Every listed mode fits with ≥ 4 % margin **without new pads, without a faster pin rate and without custom IO**:

1. **Long frames** (L = 256 words, 251 payload) for exclusive streaming modes: 59/64 → 251/256, **+6.4 %**. No header-format change (the 12-bit count is `{iq,wc}`, legal because ownership is exclusive).
2. **8b/10b offload stays in both directions** (`pt_lc_rx`/`pt_lc_tx` already exist): 0.9 × line.
3. **Reversible north bank (RX2)**: the H2D group (H2D_CLK + 10 data, all bidirectional `bi_24t`) flips, whole-bank, into a second forwarded D2H group. Raw wired RX ≤ 3.24 Gb/s runs at 52–56 % of a 5.76 Gb/s D2H.
4. **Per-direction rate** (D2H and H2D dividers independent). Combined with MODE8, this makes HT40 TX fit at div2. It also lets ECP5 hosts run D2H at full rate.
5. **Fix the full-rate D2H electricals that are wrong today**: D2H uses `bi_t`, not `bi_24t`. Slow slew does not hold a full-rate eye at ss. Fast slew needs the (register-only, unimplemented) `d2h_stagger`.

A pin rate above 156.25 MHz is kept as a **zero-hardware stretch** (175 MHz, host-chosen). 200 MHz is marginal and 250 MHz fails. Exotic IO is rejected.

## 1. Per-pin rate (item 1)

### 1.1 Evidence

**Liberty, frozen PDK** (`hostio_pad_screen.py` rerun against the frozen PDK, scratchpad copy). The provider Liberty has **no max toggle attribute**: `max_transition 1.0 ns`, `max_capacitance 50 pF` (bi_24t). All f_max values below are derived screens: UI_min = t_tr + DCD + 1.0 ns FPGA window + 0.4 ns skew.

| Cell / config (as wired in `integration/pt_chip.sv`) | tt 3.3 V | ss_125C 2.97 V | Note |
|---|---:|---:|---|
| D2H **`bi_t`** PDRV=11, fast slew, 10 pF | 182.6 MHz | **134.3 MHz** | AC-1's "177.9 MHz" was `bi_t`'s neighbour `bi_24t`, **not the D2H cell** |
| D2H `bi_t` PDRV=11, **slow slew** (reset default `hostio.controls.slew=1`), 10 pF | **137.3** | 88.5 | fails 156.25 even at tt by this screen |
| D2H `bi_t` reset default drive=1 (PDRV0), slow, 10 pF | 108.5 | 67.3 | bring-up only (div4 = 39 MHz clock: fine) |
| `bi_24t` fast, 10 pF | 204.9 | 158.4 | north-bank cell |
| H2D input `bi_24t` **CS=0** (what `pt_chip` wires) | **235.2** | **191.6** | |
| H2D input `bi_24t` CS=1 (Schmitt) | 193.2 | 148.2 | the number HL-H2D-PADIN quoted |

**Finding F-1.** HL-H2D-PADIN "fails at ss_125C (148.2 MHz)" used the Schmitt arc. The chip wires CS=0, which gives 191.6 MHz at ss_125C, **+22.6 %** over 156.25 MHz even outside the envelope. The H2D pad input is not the limit.

**Light SPICE (1 deck × 2 corners, provider `gf180mcu_fd_io.spice`).**
- Chain: driver → 0.3 Ω + 2.2 nH bond → 0.08 pF finger → 86.6 Ω/30 ps COB → 0.4 nH/0.1 pF via → 1.0 nH/0.25 pF connector → 27 Ω series (HL-B2) → 50 Ω/300 ps carrier → 6 pF FPGA pin.
- Stimulus: PRBS7 at UI 2.5 ns, ideal supplies (no SSN).
- Eye width = UI − spread of all 0.8 V/2.0 V threshold crossings (LVCMOS33 V_IL/V_IH).
- Files: scratchpad `hlsim/` (`gen.py`, `eye.py`).
- The ss run stopped at 54 ns (timestep), so it covers 20 bits. tt covers 76 bits.
- **The PDK `ss` section moves the 6 V devices the IO cells use. At ss/32 °C/3.15 V the driver edges equal the Liberty ss_125C/2.97 V ones (bi_t fast t_r 2.03 ns vs 2.04 ns).** For these pads, ss_125C is a fair proxy for the in-envelope slow corner, not a pessimistic one.

| Driver | tt27 eye @UI 2.5 | ss32 eye @UI 2.5 | ss32 eye @UI 3.2 (spread-scaled) | I_pk |
|---|---:|---:|---:|---:|
| `bi_t` PDRV=11 fast | 1.81 ns | 1.59 ns | 2.29 ns | 22–31 mA |
| `bi_t` PDRV=11 slow | 0.71 | 0.95 | **1.65** | 15–24 mA |
| `bi_24t` fast | 2.05 | 1.96 | 2.66 | 28–36 mA |
| `bi_24t` slow | 1.15 | 0.97 | 1.67 | 15–22 mA |

**Required eye at the FPGA pin.** Build-up: FPGA trained sampling window 0.60 ns (Artix-7 HR ISERDES+IDELAYE2 class, *verify DS181 T_SAMP*) + residual skew after per-bit training 0.15 + forwarded-clock DCD 0.10 + jitter 0.10 + SSO push-out 0.20 + board 0.05 = **1.20 ns**, plus 0.15 UI margin (HL-D2H-MARGIN).

| Pin clock (UI) | Need | `bi_t` fast | `bi_t` slow | `bi_24t` fast | Verdict |
|---|---:|---:|---:|---:|---|
| 156.25 MHz (3.2 ns) | 1.68 | 2.29 ✓ | 1.65 ✗ | 2.66 ✓ | **fast slew required at full rate** (F-2) |
| 175 MHz (2.857 ns) | 1.63 | ≈ 1.95 ✓ | ✗ | ≈ 2.32 ✓ | stretch only (core 87.5 MHz, see below) |
| 200 MHz (2.5 ns) | 1.58 | 1.59 (0 ps) | ✗ | 1.96 ✓ | D2H needs `bi_24t`-class cells. H2D input 191.6 < 200 MHz at ss (−4 %) ✗ |
| 250 MHz (2.0 ns) | 1.50 | ≈ 1.09 ✗ | ✗ | ≈ 1.46 ✗ | **no** |

### 1.2 Costs of going faster

**SSN.** Package-channel `host_ssn` (0.8 nH D2H return):

| Edge | Bounce |
|---|---:|
| t_r 0.76 ns / 42 mA (fast, tt) | 486 mV |
| 1.0 ns / 35 mA | 308 mV |
| 1.4 ns / 30 mA (slow) | 189 mV |

Limit HL-SSO 300 mV. **F-2.** Full rate at ss needs fast slew, which means 486 mV at tt/ff unless the two-group stagger is used (≈ 245 mV, package-channel: "halves bounce"). `hostio.controls.d2h_stagger` exists only as a register: no RTL consumes it (`rtl/pt_regfile.sv` drives `analog_cfg[317]`, and nothing reads it). That is a gap **today**, independent of any expansion.

Stagger offset: 0.4–0.8 ns (a short delay chain on odd lanes), **not** ½ UI. A ½-UI offset would put the second group's bounce at the first group's sampling point. The FPGA per-bit IDELAY (≥ 1.6 ns range) absorbs the offset.

**Power.** Average current per data pin is ≈ 2.4 mA at 156.25 MHz PRBS (tt sim, 3.1 mA at UI 2.5 scaled), and ≈ 4.8 mA for a clock pin. It is linear in rate: 200 MHz costs +28 %.

**Core clock.** The transport core runs at word/4. 175 / 200 MHz pins mean an 87.5 / 100 MHz core. AC-1 already needs 1.4× over the routed 65.3 MHz (tt) to reach 78.125 MHz. Any pin-rate increase **raises the hardest digital closure item**. That is the deciding cost.

**FPGA side.**

| Family | Assessment |
|---|---|
| Artix-7/Spartan-7 HR | IDELAYE2 on every input. **No ODELAY on HR**, so H2D cannot be deskewed per bit. Xilinx publishes no LVCMOS33 toggle maximum; 156.25 MHz DDR is common practice, while 175–200 MHz needs an IBIS check per board (*verify*). |
| Cyclone V | 3.3-V LVCMOS DDIO plus input delay chains. Toggle limit at 10 pF *verify* (Cyclone V datasheet I/O f_max). |
| ECP5 | LVCMOS33 **input 200 / output 150 MHz** (fpga-host-screen). It can receive D2H at full rate but cannot send H2D at 156.25 MHz. |

**Verdict.** DDR at 200–250 MHz is **not** the route. 156.25 MHz stays nominal with fast slew + stagger. 175 MHz is a host-chosen stretch (the H2D clock is the FPGA's, and D2H follows the configured clock): no hardware, enabled only if STA closes 87.5 MHz and silicon shows the eye.

## 2. Direction-programmable lanes (item 2)

**Granularity: whole bank, not per lane.** A data lane has no timing reference except its bank's forwarded clock. A lane flipped alone would need either a cross-die clock (chip-side capture of a south input on H2D_CLK, 1.8 mm away) or FPGA per-group launch-phase training. HR banks have no ODELAY, so per-bit H2D deskew is impossible on Artix/Spartan-7.

Flipping a **whole bank including its clock pin** keeps each bank a self-contained source-synchronous group. Each group keeps its own pad-edge gearbox and is trained exactly like today's group. Both banks are already bidirectional provider cells: H2D = `bi_24t`, D2H = `bi_t` (both have OE/IE/PU/PD).

| Mode | South bank (D2H_CLK + D2H_D) | North bank (H2D_CLK + H2D_D) | D2H | H2D | Use |
|---|---|---|---:|---:|---|
| **BAL** (reset) | out | in | 2.88 (3.06 L=256) | 2.88 (3.06) | everything today; full-duplex |
| **RX2** | out | **out** (H2D_CLK = second forwarded clock) | **5.76** | 0 (SPI control) | raw wired RX / capture > 2.9 Gb/s |
| TX2 (optional) | **in** (FPGA forwards a 2nd clock) | in | 0 (SPI status + XOFF on DBG_OBS0) | **5.76** | raw wired TX playback > 2.9 Gb/s; 12-bit HT40 TX at div2 |

Wired RX streaming at 3.125 Gb/s raw in RX2 uses **54 %** (3.24: 56 %), against 108.5 % today.

**What RX2 gives up.** No in-band H2D, so there are no fast commands or echoes. Wired streaming and capture use none: the FPGA must always accept D2H, so there are no credits. Control runs on SPI, which is independent of the link (pin plan).

**What TX2 gives up.** No D2H. Flow control comes from a FIFO-watermark XOFF on a new `dbg_obs` select (async, ns latency, ≈ 0 FF), and status from SPI.

TX2 is optional because no listed mode *needs* it once 8b/10b and MODE8 are used (§5).

**Bring-up safety.**
- **Power-up and reset.** Every bank OE is 0. North OE is a new macro output from an async-reset flop, ANDed with link enable; south is unchanged (tristate until `d2h_enable`). `lane_dir` resets to BAL, so power-up behaviour is identical to today. The pads are already qualified for an unpowered peer.
- **Turnaround** (stopped-only, validator-enforced):
  1. Both sides stop the link.
  2. The FPGA tristates the group and confirms.
  3. SPI writes `hostio.lane_dir`, then commit.
  4. **Release check.** The chip probes the bank with the cell's own PD and then PU, ≈ 10 µs each (RC ≈ 1 µs at 50–100 kΩ × 10 pF), and requires Y = 0 then Y = 1 on every lane. If any lane fails, it sets sticky `dir_contention` and OE stays 0.
  5. OE on.
  6. The training pattern runs per group.

  Reverse direction: the chip drops OE first.
- **Contention if the FPGA violates the protocol anyway.** 3.3 V across driver R_on + 2 × 22–27 Ω ≈ 30–40 mA per pin, transient. That is not instantly destructive but must not be continuous; the release check makes it a protocol error, not a hazard.
- **Floating inputs** during turnaround are held by the PD that is left on.

**SSN and power of RX2.** The north bank returns through its own `VSS_HOST_B` bonds, so the bounce is per bank and needs the north return-set number (demand HB-7). Both banks stagger.

With **hold-padding** (unadvertised payload slots repeat the previous word, so they do not toggle), D2H switching scales with *payload*, not lane count. 3.125 Gb/s raw ≈ 1.08 × today's full-rate D2H data current plus one clock pin (≈ +5 mA). Without hold-padding it is ≈ 2×.

**Asymmetric rate (not direction).** H2D inputs cost the chip no driver current, and H2D is captured through the CDC FIFO on the FPGA's clock. So the H2D and D2H dividers can be independent (HB-4).

This helps two cases:
- **HT40 TX**: H2D full rate with D2H at div4.
- **ECP5**: D2H at full rate (input ≤ 200 MHz) with H2D at div2 (output ≤ 150 MHz). ECP5 moves from "div2 only" to 2.88 / 1.44 Gb/s, and in RX2 to 5.76 Gb/s D2H.

## 3. More lanes (item 3)

| Candidate | Verdict | Why |
|---|---|---|
| DBG_OBS1 (bidir[39], north, 3 sites from H2D_D[9]) | **keep** | A 21st lane breaks the 10-bit word: both framers and the FPGA would need an 11-bit format, for +10 % in one direction only. It is the only simultaneous second status bit (PD22), and it is the natural XOFF / overload (RXR-D4) pin. |
| SPI (4 pins, south, next to D2H) | keep | Independent recovery and SPI-only MCU operation are pin-plan obligations; RX2 also relies on SPI. |
| CLK_OBS, DBG_OBS0, RESET_N | keep | Observability and reset. |
| WCLK_IN, WTX_EXT, WMON, ESD_TEST, USB, east debug | no | Functional or characterization pins, on the wrong edge (≈ 3 mm from both host banks). |

**Net: 0 lanes added.** Reversing a bank adds 10 lanes to one direction at no pad cost, which is the "more lanes" answer.

## 4. Overhead (item 4)

| Lever | Gain | Verdict |
|---|---|---|
| Frame L = 256 (251/256 = 0.980 vs 0.922) | **+6.4 %** | **Adopt**, stopped-only, streaming modes only. Frame period 819 ns, so the three-frame command budget is 2.46 µs; forbidden where fast commands are used (RF AGC, 100BASE-TX threshold, USB). Count = `{iq[5:0],wc[5:0]}` (exclusive ownership makes the inactive count zero today), so the 30-bit metadata layout is unchanged. |
| L = 128 (123/128) | +4.2 % | subsumed by L = 256 |
| 8b/10b offload (9 b/sym, exists) | 0.9 × line | **keep (MUST)**, both directions |
| 8b + escape coding (0.8 × line) | variable | reject: not rate-deterministic (all-K worst case expands) |
| Idle/ordered-set deletion | **worst case ≈ 0.8–1.3 %** (2500BASE-X IPG 12 B per 1538 B frame; SATA ALIGN 2 per 256 dwords) | reject as a capacity fix: helps only averages. FPGA-side if wanted. |
| IQ packing | already 24 b/complex (packed); MODE8 16 b | use MODE8 for HT40 TX: 8-bit SQNR ≈ 50 dB − 12 dB OFDM crest ≈ 38 dB ≫ 19 dB EVM (MCS0–4) |
| Hold-padding | 0 capacity, −≈ 45 % D2H switching at 54 % utilisation | adopt (power/SSN) |

## 5. Per-mode fit (recommended configuration)

Required margin **HL-MARGIN ≥ 4 %** for exclusive streaming. It covers status/marker frames ≤ 1 per 64 frames (1.6 %), ±100 ppm × 2 (0.02 %), and ≈ 2 % rate-adaptation/drain. AC-1's 15.2 % was what line/8 happened to give, not a requirement.

| Mode | Need (Gb/s/dir) | Config | Available | Load | Margin |
|---|---:|---|---:|---:|---:|
| Wired RX raw 3.0 / 3.125 / 3.24 | 3.00 / 3.125 / 3.24 | RX2, L=64 | 5.76 | 52 / 54 / 56 % | ≥ 44 % ✓ |
| Wired RX 8b/10b 3.0 / 3.125 / 3.24 | 2.70 / 2.81 / 2.92 | BAL, L=256, `pt_lc_rx` | 3.06 | 88 / 92 / 95 % | 12 / 8 / 4.8 % ✓ |
| Wired TX 8b/10b 3.0 / 3.125 / 3.24 | 2.70 / 2.81 / 2.92 | BAL, L=256, `pt_lc_tx` | 3.06 | 88 / 92 / 95 % | ✓ |
| Wired TX raw > 2.9 | 3.0–3.24 | TX2 (optional) | 5.76 | 52–56 % | ✓ if TX2 built; else on-chip PRBS generator (raw patterns) |
| **Full-duplex** 8b/10b 3.0 / 3.125 / 3.24 | 2.70 / 2.81 / 2.92 each | BAL, L=256, both codecs | 3.06 each | 88 / 92 / 95 % | ✓ |
| Full-duplex PCIe 2.5 / raw ≤ 2.7 | 2.5 / 2.7 | BAL (line/8 rule) / L=256 | 2.88 / 3.06 | 87 / 88 % | ✓ |
| Full-duplex raw 3.0 / 3.125 / 3.24 | 3.0–3.24 each | BAL L=256 | 3.06 | 98 / 102 / 106 % | ✗; **stretch** 175 MHz: 3.43 → 87 / 91 / 94 % ✓. No listed standard needs raw FD above 2.7 Gb/s (all > 2.7 standards are 8b/10b). |
| **HT40 TX** 80 MS/s | 1.92 (12 b) / 1.28 (MODE8) | **BAL div2 + MODE8** (no HW) | 1.44 | 89 % | 11 % ✓, PWR-HOST-RF kept |
| HT40 TX, 12-bit option | 1.92 | BAL, H2D full / D2H div4 (HB-4); or TX2 div2 | 2.88 | 67 % | ✓ |
| RF RX 40 MS/s, SDR capture | 0.96 | BAL div2 | 1.44 | 67 % | ✓ (unchanged) |

The WR-HL-LINECODE F1 ceiling (fpga-offload-audit: "above ≈ 3.15 Gb/s no mode streams") is lifted:
- raw RX streams to 3.24 Gb/s in RX2;
- 8b/10b streams to 3.24 Gb/s in both directions and full duplex.

## 6. Exotic options (item 5): rejected

**Custom LVDS/SLVS host pads.**
- 2 pins per lane, so the 22 sites become 11 pairs.
- At ≈ 0.8–1 Gb/s/pair that is ≈ 8–10 Gb/s per direction-split. But it needs:
  - two new custom pad designs (driver/receiver, 100 Ω termination, CM control, ESD/HBM requalification as PD21–PD23 needed);
  - FPGA banks at VCCO 2.5 V (Artix HR LVDS_25 outputs);
  - a different board.
- It breaks the pin-plan product promise ("companion for FPGA *regular* GPIOs"), and it spends risk on a path that is not the point of the chip.
- The low-risk alternative (§5) meets every listed mode. MANDATE "state the low-risk alternative and why it is insufficient": it is sufficient, so reject.

**Wired TX lane as an uplink into an FPGA GTP.**
- It needs a GT-equipped FPGA: Artix-7 yes; Spartan-7 none; Cyclone V only GX; ECP5 only -5G. That excludes host candidates.
- It occupies the wired TX that full-duplex and TX modes are testing, so it serves only RX-only modes, which RX2 already covers with ordinary IO.
- It adds a protocol/serializer dependency (ring PLL jitter) to the host path. Reject.

## 7. Cost and risk of the recommendation

| Item | RTL / FF (est.) | Pads | SSN / power | Board / FPGA | Risk |
|---|---|---|---|---|---|
| HB-1 stagger + fast slew at full rate | delay chain on odd D2H lanes + ≈ 4 FF | none | 486 → ≈ 245 mV; needed **today** | none | low (conventional) |
| HB-2 L = 256 frames | ≈ 25 FF (quad counter +2 b, count remap, validator) | none | none | FPGA decoder: frame length param | low; touches `pt_quad_link` after AC-1 lands |
| HB-3 8b/10b both directions | exists | — | — | — | done (keep MUST) |
| HB-4 per-direction rate | ≈ 10 FF (`d2h_rate` field; H2D via existing CDC) | none | lowers hostio in TX/RF modes | ECP5 H2D ≤ 150 MHz | low |
| HB-5 hold-padding | ≈ 0 (mux select) | none | −≈ 45 % D2H toggles at 54 % load | none | low |
| HB-6 RX2 (north bank reversible) | north 4:1 gearbox + DDR launch (≈ 160 FF), lockstep twin framer / 80-bit egress pair (≈ 150 FF), release-check FSM (≈ 20 FF); +14 macro pins (11 A, OE, SL, PU/PD); one clock-tree branch (chip launch clock to north) | **none**: `bi_24t` already bidir; `pt_chip` wiring of A/OE/SL/PU/PD instead of ties | north 11 outputs need the north return set ≤ 300 mV with stagger; hostio ≈ +5 mA (2nd clock) with hold-padding | H2D_CLK on a bidirectional clock-capable FPGA pin; 22 Ω series at **both** ends of north lines; IDELAY on north inputs; gateware handshake | low-moderate: whole-bank keeps the proven topology; new = turnaround protocol |
| HB-8 TX2 (optional) | south 1:4 + CDC (≈ 480 FF), twin deframer (≈ 150 FF), D2H_CLK input path, XOFF select | none | none on chip | D2H_CLK bidirectional CC pin; FPGA forwards a 2nd clock | moderate; build only if FF budget allows |
| HB-9 stretch 175 MHz | 0 | 0 | +12 % hostio | IBIS check per board | none (opt-in; gated by STA 87.5 MHz) |

Total for the recommended set (HB-1..6): **≈ 370 FF, 0 pads, 0 new pad cells**, +14 macro pins at existing pad-edge gearbox regions. TX2 adds ≈ 650 FF.

**Fallbacks.** Unchanged:
- `debug.host_link.rate` div2/div4;
- BAL (reset default);
- the on-chip PRBS checker/generator for raw rates;
- `wire_board_phy_bypass`.

## 8. Open items

- In-envelope Liberty (22/32 °C × 3.15/3.35 V) for `bi_t`/`bi_24t`. The SPICE above suggests ss_125C is a fair proxy for these 6 V pads.
- Full eye sim with SSN on the real return set for both banks (PKG-08 / HB-7).
- FPGA family numbers marked *verify*: DS181 T_SAMP and HR LVCMOS33 rate; Cyclone V 3.3-V I/O f_max; Cyclone V dedicated CLK pins are input-only, so the RX2 clock may need a bidirectional DQS/regular pin plus training.
- HT40 TX MODE8: confirm the GX-2 `external` 80 MS/s path accepts MODE8 samples.
