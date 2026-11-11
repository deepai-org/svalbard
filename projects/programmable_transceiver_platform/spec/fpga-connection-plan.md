# FPGA connection plan (typical companion FPGAs)

Status: spec screen, 2026-11-11. This is not a gateware spec. It answers one question: will a typical
FPGA board (Artix-7/Spartan-7, ECP5, Cyclone V) run the host link and absorb the offloaded functions, and
what does that imply for the chip? Values marked *(verify)* are from memory of vendor datasheets and must be
checked before a board is committed.

Inputs:
- `interface-requirements.md` §3 (HL-*, WR-HL-LINECODE)
- `board-requirements.md` (B6, B10, HL-B1..B8)
- `scratch/reviews/host-link-bandwidth.md` (eye numbers, RX2, L=256, stagger)
- `scratch/reviews/fpga-offload-audit.md` §3/§6 (function list)
- `rtl/pt_host_link.sv` and `rtl/pt_quad_link.sv` (pin coding, training prefix)

## 1. Chip-to-FPGA signals

The die sits on the 70-pin mezzanine COB board. A carrier board takes the mezzanine connector and fans the
signals below out to the FPGA board connector. Nothing else on the mezzanine goes to the FPGA.

| Group | Chip signals | Dir. BAL / RX2 / TX2 (FPGA view) | FPGA pin requirement |
|---|---|---|---|
| South bank (D2H) | `D2H_CLK`, `D2H_D[9:0]` (11) | in / in / out | Data in one bank with the clock on a clock-capable pin. Bidirectional only if TX2 is ever used |
| North bank (H2D) | `H2D_CLK`, `H2D_D[9:0]` (11) | out / **in** / in | One bank. The clock pin must be clock-capable **and** bidirectional (HL-B1) |
| Management | `HOST_SCLK`, `HOST_CS_N`, `HOST_MOSI`, `HOST_MISO`, `RESET_N` (5) | out ×3, in, out (open-drain via B1) | Any 3.3 V IO |
| Observation | `DBG_OBS0`, `DBG_OBS1`, `CLK_OBS` (3) | in | DBG_OBS: any input (2-FF synchronized). CLK_OBS: a clock-capable input (frequency counting) |
| **Total** | **30** | | All at VCCO = 3.3 V, in ≤ 3 banks (two host groups plus management/observation) |

The FPGA side also needs a few GPIOs that have no chip pin: the PTA (3), the antenna switch B41 (≤ 3), and the
B6 bus-switch enable and power-good (2). The pin budget is therefore **30 chip + ≈ 8 board ≈ 38 IO**.

Pin coding facts the FPGA must know:
- **Plain words on the pins.** The chip's internal XOR prefix exists only for glitch-free DDR launch: each pin is
  `q_r ^ q_f` of consecutive prefixes, so the pin carries the word itself (`pt_host_link.sv`). The FPGA does
  no decoding.
- **D2H_CLK is edge-aligned**, like a DQS. The FPGA centres it by training.
- **Training prefix.** `3A5 05A 2D3 12C 369 096 21E 1E1` is sent once after each link start. The words come in
  complementary pairs, so every lane toggles on both edges. The H2D receiver locks to any of the four word
  rotations.
- **Word alignment is per lane.** With the D2H stagger on, the odd lanes launch 0.4–0.8 ns later than the
  even lanes (T16). After per-bit centring, a lane may sit one bit away from its neighbours. The FPGA therefore
  needs per-lane bitslip, not per-bank bitslip.
- **Frames.** Frame length is L = 64 words (59 payload) or 256 words (251 payload; HL-FRAME). In RX2 the two
  banks run a lockstep twin: one header per bank with a bank-ID bit, south = even quads, north = odd quads
  (HB-6).

## 2. IO standard and voltage compatibility

The chip host pads are 3.3 V LVCMOS (`bi_t` south, `bi_24t` north) with CMOS-threshold inputs (CS=0). Every
FPGA bank on these nets runs at VCCO 3.3 V.

| Family | Bank / standard | Drive and slew (H2D outputs) | Pulls | Input delay | Notes |
|---|---|---|---|---|---|
| Artix-7 / Spartan-7 | HR bank, `LVCMOS33` | 8–12 mA, `FAST` (HL-B4 SSO check) | `PULLTYPE` none, no keeper (HL-B7) | IDELAYE2: 32 taps × 78 ps at 200 MHz IDELAYCTRL = 2.5 ns | HR banks have **no ODELAY**. H2D is centred by MMCM phase (1/56 VCO step ≈ 14 ps at 1.25 GHz VCO), and per-bit H2D skew relies on the board ±2.5 mm match |
| ECP5 | `LVCMOS33` | 8 mA, `SLEWRATE=FAST` | `PULLMODE=NONE` | DELAYF/DELAYG: 128 taps ≈ 25 ps ≈ 3.2 ns *(verify TN1265)* | Input ≤ 200 MHz, **output ≤ 150 MHz** (board-requirements screen), so H2D must run at div2 (HL-RATE-DIR). X2 gearing (IDDRX2F/ECLK) only on left/right banks *(verify)* |
| Cyclone V | `3.3-V LVCMOS` | 8 mA, fast slew | weak pull-up and bus-hold off | Input delay chain, runtime-settable via the IO_CONFIG/ALTIOBUF dynamic delay *(verify step and range)*, plus PLL dynamic phase shift (VCO/8 ≈ 100 ps) | Dedicated CLK pins are input-only, so `H2D_CLK` goes on a regular bidirectional pin (HL-B1). Check the 3.3 V I/O overshoot and DC-current guidance and the DDIO f_max at 3.3 V *(verify)* |

All three families tolerate 3.3 V on these banks and meet the chip's input thresholds with LVCMOS33. No
level translator is needed.

Two things in series with the D2H lines need checking:
- The B6 bus switch (powered-off isolation). Its ≈ 5 Ω and 5–7 pF count against HL-B3's 10 pF.
- **In RX2 the north bank also drives the FPGA.** B6 must therefore cover all 22 host lines plus MISO, not
  12. B6 is updated for this.

## 3. Can each family run the link? (156.25 MHz DDR, 20 D2H lanes in RX2, stagger on)

Eye required at the FPGA pin = FPGA window + residual skew + 0.45 ns (DCD 0.10, jitter 0.10, SSO 0.20,
board 0.05) + 0.15 UI (0.48 ns). Available eye: `bi_t` fast slew at ss/32 °C/3.15 V through the COB and a 6 pF
load, PRBS7, 3.2 ns UI = **2.29 ns**. The north `bi_24t` in RX2 gives 2.66 ns. Both come from
host-link-bandwidth.md §1.1.

| Family (speed grade) | FPGA window | Residual skew after training | Need | Margin (south / north) | Stagger 0.4–0.8 ns | 20 lanes (RX2) |
|---|---:|---:|---:|---:|---|---|
| Artix-7 / Spartan-7 (−1) | 0.60 *(verify DS181/DS189)* | 0.15 + ±0.04 tap | 1.72 | **+0.57 / +0.94** | Absorbed per bit. The 2.5 ns range leaves 0.7 ns of the 3.2 ns UI unreachable, so the worst-case sample is 0.35 ns off centre: margin ≥ **+0.22 ns**. An MMCM-phase capture clock (full 360°) removes this | Two BUFIO/BUFR groups (one per bank) and one IDELAYCTRL per bank; a small mesochronous FIFO joins them |
| ECP5 (−6) | 1.0 *(verify)* | 0.15 + ±0.013 | 2.09 | **+0.20 / +0.57** | DELAYF range ≈ 1 UI: absorbed per bit | RX/D2H at full rate on both banks (input ≤ 200 MHz). H2D only at div2 |
| Cyclone V (−7/−8) | 1.0 *(verify)* | 0.15 with per-bit dynamic delay; 0.40 if delays are static | 2.08 / 2.33 | **+0.21** / **−0.04 ✗** (static) | Separate PLL phase outputs for the even and odd sub-groups (4 C counters in RX2). Needs per-bit dynamic delay *(verify)*, or else div2 | The north clock arrives on a regular pin, so the north group is captured mesochronously from the south PLL with its own phase output |

Verdict:
- **Artix-7/Spartan-7: works**, with the most margin. It is the lead family.
- **ECP5: works for D2H** (BAL and RX2) with a thin +0.20 ns margin. H2D is div2 only, so:
  - BAL full duplex at 3.0–3.24 Gb/s 8b/10b does not fit (H2D 1.44 Gb/s);
  - wired TX streaming tops out at 1.44 × 0.96 / 0.9 ≈ 1.5 Gb/s 8b/10b;
  - above that, TX uses the on-chip PRBS generator.
- **Cyclone V: works only if** the dynamic input delay chain is confirmed per bit. Otherwise run full-rate D2H
  only after a per-board static delay calibration, or use div2.
- **Every family:** div2 (UI 6.4 ns) has ≥ 3 ns of margin. It stays the bring-up and fallback rate (HL-B6).

H2D (FPGA launches, chip captures): the chip pad limit is 191.6 MHz at ss_125C. The budget is HL-H2D-MARGIN.
The only family-specific term is FPGA output skew. Artix/Spartan use OSERDES + an MMCM 90° forwarded clock.
Cyclone V uses DDIO_OUT. ECP5 runs at div2. None changes the §3.2 numbers.

**Training cost today.** The prefix is 8 words, sent once per link start. So the FPGA can only sweep delays by
restarting the link for each tap step (stop → SPI release/train → read lock). All lanes sweep in parallel:
32 taps (Artix) to 128 taps (ECP5) restarts, ≈ 1 ms each over SPI, so **≈ 0.03–0.13 s per training**. That
is workable. Hold-padding (HB-5) also means an idle link has few edges, so continuous eye monitoring during
payload is weak. See C1.

## 4. Pin count against typical boards and connectors

Need: 38 IO at 3.3 V, with the two 11-pin groups each in one bank, plus a return path good enough for
0.76–2 ns edges. A 0.1" header with one ground per ~18 signals does not provide that return path.

| Board (FPGA) | 3.3 V IO available to a carrier | Count OK | Full-rate OK | Notes *(verify all)* |
|---|---|---|---|---|
| Digilent Nexys Video (XC7A200T) | FMC LPC, VADJ selectable to 3.3 V, 68 SE | ✓ | ✓ | Recommended Artix target |
| Digilent Arty A7-35/-100, Arty S7-50 | 4 Pmod + shield header; only JB/JC (16 IO) lack series 200 Ω | ✗ (16 clean IO) | ✗ | The 200 Ω protection resistors kill a 312 Mb/s edge at 10 pF. XC7A35T is also too small (§5) |
| Generic Artix-7 boards with 2 × 40-pin 0.1" headers | ≈ 68 | ✓ | div2 only, unless the header has ≥ 1 GND per 2–4 signals | Header crosstalk/SSN needs an IBIS check |
| Radiona ULX3S (LFE5U-45F/85F) | 56 GPIO on 2 × 28 headers, routed as pairs | ✓ | D2H ✓ (thin margin), H2D div2 | 25F/12F are too small (§5) |
| Lattice ECP5 Evaluation Board (LFE5UM5G-85F) | many 0.1" headers | ✓ | as ULX3S | |
| Terasic DE10-Nano (5CSEBA6 SoC, 41,910 ALM) | 2 × 40-pin GPIO, ≈ 72 IO at 3.3 V | ✓ | div2 sure; full rate subject to §3 Cyclone V | The HPS (ARM) can replace the soft RISC-V |
| Terasic DE0-CV (5CEBA4) | 2 × 40-pin GPIO | ✓ | as DE10-Nano | 18,480 ALM is too small for a single build (§5) |
| Any board via FMC with VADJ = 3.3 V | ≥ 68 SE | ✓ | ✓ | The preferred connector for full rate |

The carrier design rules are HL-B1..B8: 50 Ω, ±2.5 mm match, 22–33 Ω series, ≤ 60 mm, and ground vias.

## 5. Rough fit of the offloaded functions

Units are from the audit §6 list. LUT is 6-input equivalent, BRAM in Kb, DSP is 18×18. RF and wired are
exclusive on the chip (`exclusive-engine-policy.md`). Their FPGA logic can therefore be one bitstream or two
"personality" builds that share a common core.

| Unit (audit §6 item) | LUT | FF | BRAM Kb | DSP |
|---|---:|---:|---:|---:|
| Link PHY: both banks, SERDES, delay control, per-lane bitslip, training, direction handshake (1) | 1,400 | 1,600 | 0 | 0 |
| Frame engine: L = 64/256, RX2 twin deframer, seq/credit, opcode4 one-pending issue, echo/reject, mark/status decode (2) | 2,400 | 2,600 | 144 | 0 |
| Time engine: 64-bit TX/RX sample counters, RTT/CSL, GX-7 sync (7) | 500 | 600 | 0 | 0 |
| Control: VexRiscv-class RV32IMC, 32 KB RAM, SPI master with timed COMMIT (GX-4), CLK_OBS counter, DBG_OBS sync (8, 9) | 3,200 | 2,800 | 288 | 4 |
| Debug capture buffer | 400 | 500 | 288 | 0 |
| **Common** | **7,900** | **8,100** | **720** | **4** |
| Wired line-code engine: 8b/10b at 80 b/cycle (RX2), comma align, idle/ALIGN insert, PCS personalities, PRBS7/15/31 gen + check (3, 4) | 4,600 | 4,000 | 144 | 0 |
| Wired DSP: oversampling CDR (IX-4, 100BASE-TX via IX-12), IX-11 threshold/DC servo, eye/edge histograms (5) | 2,400 | 2,200 | 144 | 4 |
| RF DSP: AGC (ADC power + `rx_ovld` pin), DC, IQ, CFO/SFO, low-IF, GX-2 halfband, ToA correlator, PTA (6) | 4,000 | 4,200 | 216 | 28 |
| **Single bitstream / wired build / RF build** | **18,900 / 14,900 / 11,900** | 18,500 / 14,300 / 12,300 | 1,224 / 1,008 / 936 | 36 / 8 / 32 |

The datapath runs at 78.125 MHz (40 b per bank per cycle). That is easy in every family's slowest grade. The
CPU runs on its own 50 MHz clock and is never in a fast loop.

Fit rule: estimate × 1.3 contingency ≤ 80 % of the device. ECP5 is counted at 1.8 LUT4 per LUT6. Cyclone V is
counted at 1 ALM per LUT6, which is conservative.

| Family | Smallest device that fits | Logic | BRAM | DSP | Too small |
|---|---|---:|---:|---:|---|
| Artix-7 | XC7A50T, single build | 75 % | 59 % | 39 % | XC7A35T: 93 % even for the wired build |
| Spartan-7 | XC7S50, single build | 75 % | 59 % | 39 % | XC7S25 |
| ECP5 | LFE5U-45F with two builds (wired 79 %, RF 63 %); LFE5U-85F single (53 %) | — | 67 % (45F wired) | 58 % (45F RF) | LFE5U-25F |
| Cyclone V | 5CEA5 with two builds (wired 67 %); 5CEA7 or 5CSEBA6 (DE10-Nano) single (≤ 60 %) | — | ≤ 36 % | ≤ 31 % | 5CEA4 (105 % for the wired build) |

Not in this estimate: the board-side data sink. RX2 at 3.24 Gb/s raw fills 1.2 Mb of BRAM in ≈ 0.4 ms. Long
captures need the board's DDR3 or a ≥ 5 Gb/s uplink. This is a board/application choice and does not affect
the chip.

## 6. Chip-side implications (flagged; recorded in interface-changes.md FPGA-1..FPGA-5)

| ID | Finding | Chip-side change | Cost |
|---|---|---|---|
| FPGA-1 | Per-bit training only has the 8-word prefix once per link start, so it must restart the link for every tap step (§3), and hold-padding starves the link of edges during payload | **Recommended:** a stopped-only `train_hold` control that repeats T0/T1 on every enabled D2H group (both banks in RX2) until RUN. It allows one-pass training and periodic retraining without SPI restarts | ≈ 2–4 FF and one mux select in `pt_quad_link_tx`; low risk |
| FPGA-2 | In RX2 `H2D_CLK` is an output, so `host_follow` cannot clock the chip | Validator: reject `lane_dir=RX2` (and TX2 on the south side) with `host_clk=host_follow` or `wire_host_source=host_follow`. In RX2 the host clock must be `internal_pll`/line-divided | validator rule only |
| FPGA-3 | ECP5 needs H2D at div2 with D2H at full rate | HB-4 (`d2h_rate`) is a **requirement** for ECP5 support, not an option. Without it ECP5 hosts are div2 in both directions | ≈ 10 FF (already HB-4) |
| FPGA-4 | After the RX2 release check, nothing on chip detects an FPGA that starts driving a reversed bank later (≈ 30–40 mA per pin, continuous). The gateware becomes a de facto safety layer, which contradicts audit item 10 | Open: either accept it (it is a protocol violation and HL-B7 requires an FPGA handshake) or add a cheap sticky check. Coordinator decision | — |
| FPGA-5 | Cyclone V full rate depends on a per-bit dynamic input delay *(verify)* | None on chip. If the delay is unavailable, Cyclone V runs div2. Optionally FPGA-1 (training hold) also helps a static per-board calibration | — |

No pad, pin-count or pin-rate change is implied. The 30 chip signals and the existing banks suffice for all
three families.
