# Interface architecture changes: host link capacity and on-chip wired CDR

Status: proposed 2026-11-09 by the spec owner. Under scratch/reviews/MANDATE.md,
these changes put PCIe Gen1, SATA Gen1, DisplayPort RBR, HD-SDI and the HDMI/DVI
receiver on the **primary on-chip route**. Board fallbacks (board-requirements.md
B13–B16) stay as backup entries only. Requirement IDs refer to
[interface-requirements.md](interface-requirements.md). Owner impacts are listed in
`scratch/reviews/interface-changes.md`. Performance is checked only in the operating
envelope (Tj 22–32 °C, rail 3.15–3.35 V, all process corners).

## AC-0. Why the architecture failed by design

| Interface | Blocking fact | Source |
|---|---|---|
| PCIe 2.5 GT/s RX | The only recovery routes are an external clock (needs a board CDR) or FPGA oversampling (2× of 2.5 Gb/s = 5 Gb/s > 2.88 Gb/s D2H). | performance-review §4 |
| All wired rates | `line_divided` uses divider 10 (interface-changes.md R1 note). Dense framing carries 59/64 payload words, so at divider 10 capacity is 0.922 × line rate. **Every framed wired rate is 7.8 % short**, including 1.25 GBd. | streaming-transport-v2.md "Sustained-service admission" |
| All wired rates | The digital boundary is 20 bit at line/20 (125 MHz at 2.5 Gb/s). The routed macro closes 53.5–63.8 MHz at tt. | digital-hardening-evidence.json |
| SATA/DP/SDI/HDMI RX, PCIe RX | CDR tracking fails extracted (quarter 560/3588, half 104/1768 errors). `pt_wrx_cap` fails above 480 MHz. The phase loop makes **one early/late decision per word** in RTL. Ring port phase error is 9–10.8°. | wired_rx README, consolidation-pass-2.md |

No device limit has been shown. The Bode–Fano bound allows ≥29 dB return loss at 1.25 GHz for the present pad C (physical-limits.md L3). Device-speed feasibility (L1/L2) is a model-based estimate only: intrinsic fT, models not RF-validated, no gate resistance. It is pending extracted simulation of the real sampler, CML driver and 4:1 mux at ss in the narrow envelope.

## AC-1. Host link: keep 10+1 pins per direction at 312.5 Mb/s per pin, and fix the divider rule and the core gearbox

**Pads: no change.** All 19 spare signal sites are already taken by debug pads (tapeout-plan.md tier 3). The south edge carrying D2H has no free site. A wider D2H would need sites from another edge, which means routing across the 1.8 mm macro. It is also unnecessary, as shown below.

**Capacity rule (replaces divider 10).** Host word clock = line rate / 8 for every framed wired rate. Framed capacity is then 10 × 59/64 / 8 = **1.152 × line rate**. The 15.2 % headroom covers RX/TX ppm offset (≤ 0.6 % with SSC), control/response traffic and FIFO drain.

| Rate | Line (Gb/s) | Host word clock (MHz) | Framed capacity (Gb/s) | Margin |
|---|---:|---:|---:|---:|
| PCIe Gen1 | 2.500 | 312.500 | 2.881 | 15.2 % |
| DP RBR | 1.620 | 202.500 | 1.867 | 15.2 % |
| SATA Gen1 | 1.500 | 187.500 | 1.729 | 15.2 % |
| HD-SDI / HDMI 1080p | 1.485 | 185.625 | 1.711 | 15.2 % |
| 1000BASE-X | 1.250 | 156.250 | 1.440 | 15.2 % |
| HDMI 720p | 0.7425 | 92.8125 | 0.856 | 15.2 % |
| USB HS | 0.480 | direct bytes 100 MHz SDR | 0.800 | 66.7 % |

2.5 Gb/s is the highest line rate that fits under the 312.5 MHz pad ceiling at divider 8. The 2.97 Gb/s stretch would need 371 MHz and remains non-gating.

**Pad rate evidence.** bi_24t fast-slew DDR output f_max is 222.8 MHz (tt) and 177.9 MHz at ss_125C/2.97 V (hostio_pad_screen). ss_125C is slower than any in-envelope ss point, so outputs pass at 156.25 MHz with ≥ 13.9 % margin. The input f_max of 148.2 MHz at ss_125C is outside the envelope and non-gating. The in-envelope number (HL-H2D-PADIN) must come from a 22/32 °C × 3.15/3.35 V characterization.

**Core gearbox (digital owner).**
- Pad-edge DDR capture and launch flops plus a 1:4 / 4:1 gearbox run at 156.25 MHz. They sit in two small floorplan regions: D2H at the south edge, H2D at the north edge.
- Everything behind the gearbox runs at **word clock / 4 with 40-bit words**: 78.125 MHz at PCIe, 46.4 MHz at SDI.
- This includes the stream framer, the FIFOs and the regfile commit path.
- At tt, the routed macro already reaches 65.3 MHz for the host word path. A 78.125 MHz target at the in-envelope ss point needs about 1.4× from pipelining the FIFO read muxes, the framer and the commit path, plus the pad-edge floorplan. It no longer needs 2.4× at 312.5/156.25 MHz.
- Memory bits are unchanged: FIFOs become 4× wider and ¼ as deep.
- Latency is two extra 78.125 MHz cycles (25.6 ns). The HL-LATENCY ≤ 400 ns budget must be re-run.

**Wired boundary.** The boundary becomes 40 bit at line/40: 62.5 MHz at 2.5 Gb/s (previously 20 bit at 125 MHz).
- wired_rx deserializer: one extra 2:1 stage.
- wired_tx serializer: one extra 2:1 stage at the 62.5 MHz input.
- Macro ports: +20 RX and +20 TX data pins.

**Current impact.** The halved core clock is what makes the PWR-DIG requirement below (≤ 60 mA wired, ≤ 40 mA RF) plausible. The only post-route number today is 207 mA (vectorless, all clocks at SDC target).

## AC-2. Optional: on-chip 8b/10b codec (decimation)

This is not required for capacity after AC-1. It is recorded because the coordinator listed it as an option.
- RX comma alignment plus 10b→8b with a K-flag reduces D2H payload to 0.8 × line + 1 flag bit per symbol (0.9 × line in a 9-bit field). That would raise margin to 28 % for PCIe/SATA/DP/GbE.
- It does not apply to TMDS (TMDS 8b/10b is different) or SDI (scrambled NRZI).
- Cost: about 2 × 1.2k cells at 62.5 MHz.
- Recommendation: **defer**. AC-1 already meets capacity, and protocol logic belongs to the FPGA (streaming-transport-v2.md).

## AC-3. On-chip CDR closure (wired_rx + timing owners)

**Architecture.** Replace word-rate RTL bang-bang decisions with a per-UI Alexander (2×-oversampled) phase detector in the analog/fast-cell domain:

| Item | Requirement | Reason |
|---|---|---|
| Rate plan | Quarter rate for 2.5 Gb/s (ring 625 MHz). Half rate for 1.25–1.62 Gb/s (ring 625–810 MHz). Full rate ≤ 810 Mb/s. | Ring range 480–810 MHz (pll_ring evidence) |
| Samplers | 2 per bit slot (data + edge): 8 at quarter rate, 4 at half rate. StrongARM + SR latch, resolve ≤ 0.35 × ring period at ss/32 °C/3.15 V. | Today `pt_wrx_cap` fails above 480 MHz. Feasibility: pending extracted simulation (physical-limits.md L2 is an estimate only) |
| Clock phases | 8 phases at quarter rate (45° spacing). Static spacing error ≤ 3° (13.3 ps = 0.033 UI at 2.5 Gb/s) after a per-phase delay trim (≥ 5 bit, ≤ 1° step), calibrated from on-chip edge-sampler histograms. | Today 9–10.8° (0.10–0.12 UI) |
| PD → loop | Early/late votes per ring cycle (majority of 4/2 slots) drive the existing BB pump directly. Latency ≤ 2 ring cycles (≤ 8 UI). | Word-rate decisions at 20–40 UI latency cause dither and limit bandwidth |
| Loop bandwidth | Programmable 0.5–4 MHz, jitter peaking ≤ 2 dB. Default 2 MHz at 2.5 Gb/s and 1 MHz at 1.5 Gb/s. | JTOL corners: PCIe 1.5 MHz, SATA f/1667 = 0.9 MHz, SDI 0.1 MHz (WR-*-JTOL) |
| Integral path | Continuous (no HOLD hand-over). Range +600…−5600 ppm around the FLL-acquired centre. Slew ≥ 400 ppm/µs. | SSC 0…−5000 ppm, 33 kHz triangle: 330 ppm/µs. Type-2 tracking error at ωn = 2π × 1 MHz is 0.021 UI. Hand-over drift today is 5883 ppm. |
| Acquisition | Reference-based FLL to ≤ ±1000 ppm, then the phase loop. RTL keeps the FLL, lock detect and status. | FLL works in model (−6000…+1000 ppm) |
| CID / transition density | Hold phase across ≥ 40 consecutive identical bits with drift ≤ 0.05 UI. That needs residual frequency error ≤ 1250 ppm, which the integral path holds. | SDI pathological check field, PCIe/SATA 8b/10b (≤ 5) |
| HDMI/DVI RX | Forwarded TMDS clock (pixel clock = line/10) enters `WCLK_IN` as the **CDR reference**. The ring locks ×10 and the phase loop only tracks (0 ppm). | On-chip route. `WCLK_IN` is a reference input, not a board CDR. |
| Offset | Sampler offset ≤ 10 mV after trim (WR-SLICER-OFFSET). Trim step ≤ 2 mV. | Today −27 mV |
| Jitter (RX implementation) | Phase spacing 0.033 + sampler aperture 0.05 + offset 0.03 + VCO RJ (2 ps × 14) 0.07 + dither 0.05 + SSC tracking 0.03 = **0.26 UI**, against a 0.40 UI eye left after PCIe 0.6 UI TJ → 0.14 UI margin. | WR-PCIE-JTOL, WR-PLL-JIT |

**Front end needed for the same rates (owners noted in interface-changes.md):**
- Wired RX/TX pad loading must reach ≤ 1.6 pF effective at 1.25 GHz. That gives |Γ| = 0.30 and RL 10.5 dB into 50 Ω ∥ C.
- Two ways to get there, either acceptable:
  - (a) a low-C protection variant for the 4 wired pads;
  - (b) series peaking (T-coil, L ≈ R²C = 5.9 nH per leg for 2.35 pF), which Bode–Fano shows can exceed 20 dB.
- WR-PCIE-TXSWING needs ≥ 800 mVppd. A CML driver with a 16 mA tail into 50 Ω on-die ∥ 50 Ω far end gives 0.8 Vppd. 20 mA gives 1.0 Vppd, inside the 36 mA wiredtx allocation.

## AC-4. Power requirements created by these changes

Computed by `spec/budgets/power_budget.py` and summarized in [power-partition.md](power-partition.md#reconciled-mode-currents-2026-11-09):

| Requirement | Limit |
|---|---|
| PWR-DIG-WIRED | Digital macro ≤ 60 mA in wired/USB modes with RF domains gated |
| PWR-DIG-RF | ≤ 40 mA in RF modes with wired domains gated |
| PWR-HOST-RF | RF modes run the host link at `debug.host_link.rate=div2` or lower (1.44 Gb/s framed ≥ 0.96 Gb/s at 40 MS/s), halving pin switching current |
