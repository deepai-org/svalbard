# Interface performance requirements (first die)

Status: requirement definitions, 2026-11-09. This file fills the "spec-missing"
items of `scratch/reviews/performance-review.md` (§1d BER/JTOL/SSC, §1c EVM/mask,
§2 host IO). **Requirements apply to the primary on-chip route** (MANDATE.md);
board fallbacks in `board-requirements.md` are verified against the same numbers
but do not discharge them. Stable IDs are referenced from
`performance-requirements.json`.

Values marked *(verify)* were transcribed from memory of the standard and must be
checked against the standard text before they are used as a signoff limit. The
"first-die adaptation" column is a deliberate narrowing to the operating envelope:
tt/ss/ff × 22–32 °C × 3.15–3.35 V, single 3.3 V supply, and a **bench channel of
≤6 dB differential insertion loss at Nyquist** (SMA + ≤15 cm FR4 + connector)
instead of the full compliance channel. Compliance channels are a later-die goal
and are recorded only as the standard value.

## 0. BER and confidence level (all wired interfaces)

Error-free bits for a BER claim at confidence CL: N = −ln(1−CL)/BER.
At 95 % CL, N = 3.0/BER.

| ID | Requirement | Bits | Test time at line rate |
|---|---|---|---|
| WR-BER-SIGNOFF | BER ≤ 1e-12 at 95 % CL, zero errors, PRBS7 (8b/10b links: also K28.5/CJPAT-class pattern; SDI: pathological SDI check field) | 3.0e12 | 2.5 G: 20 min; 1.62 G: 31 min; 1.5 G: 33 min; 1.485 G: 34 min; 1.25 G: 40 min; 742.5 M: 67 min; 480 M: 104 min |
| WR-BER-PRESCREEN | BER ≤ 1e-9 at 95 % CL (3.0e9 bits, 1.2–6.3 s); used per corner/temperature point and in JTOL sweeps (one point per mask frequency) | 3.0e9 | ≤ 6.3 s |
| WR-BER-SIM | Simulation acceptance: statistical eye / bathtub extrapolated to 1e-12 with ≥0.1 UI horizontal and ≥ receiver sensitivity vertical opening; short transient windows (41–61 bits) are smoke tests only | — | — |

Signoff (1e-12) runs at the nominal point and the two worst envelope corners per
interface; the pre-screen runs at every envelope point and every JTOL point.

## 1. Wired interfaces

Common: return-loss and swing are measured at the die pad through the COB
bond and board launch, de-embedded to the board connector. ppm and SSC apply to
the RX CDR (on-chip half/quarter-rate CDR is the primary route).

### 1.1 PCIe Gen1 x1, 2.5 GT/s (PCIe Base 1.1 / 2.0 §4.3, 2.5 GT/s tables)

| ID | Value (standard) | First-die adaptation | Verification |
|---|---|---|---|
| WR-PCIE-BER | 1e-12 | WR-BER-SIGNOFF | BERT / FPGA PRBS checker |
| WR-PCIE-TXSWING | 800–1200 mVppd; de-emphasis −3.5 dB ±0.5 | Full range required; de-emphasis may be 0 dB on the bench channel | Extracted TX + scope |
| WR-PCIE-TXJIT | TX eye width ≥0.75 UI (TJ ≤0.25 UI = 100 ps at 1e-12); TX RJ budget ~2.8 ps rms *(verify)* | Same | Statistical eye, scope TIE |
| WR-PCIE-JTOL | RX accepts eye of 0.40 UI (TJ 0.60 UI) at BER 1e-12; CDR -3 dB tracking BW 1.5–22 MHz (jitter transfer, clock spec) *(verify)* | Sinusoidal JTOL sweep: ≥1.5 UI pp below 1.5 MHz (SSC region), falling 20 dB/dec to ≥0.15 UI pp above 22 MHz, plus 0.3 UI DJ background | JTOL with BERT |
| WR-PCIE-PPM | ±300 ppm (600 ppm max between ends) | Same | Offset sweep |
| WR-PCIE-SSC | 0 to −5000 ppm down-spread, 30–33 kHz triangular | Same; CDR must track 5000 ppm at 33 kHz (slope ≈ 330 ppm/µs) | SSC source on BERT |
| WR-PCIE-RL | Diff RL ≥10 dB, CM RL ≥6 dB, 50 MHz–1.25 GHz (TX and RX) | Same (review §3.5: 6.6–7.6 dB at 1.25 GHz today → fails) | VNA / extracted S-params |
| WR-PCIE-RXSENS | RX min eye 175 mVppd | Same | Swept-amplitude BER |
| WR-PCIE-DETECT | Receiver detect, electrical idle entry/exit, beacon not required | Detect + idle required | Bench |

### 1.2 1000BASE-X / SGMII, 1.25 GBd (IEEE 802.3 cl.36/38; SGMII spec)

| ID | Value | First-die adaptation | Verification |
|---|---|---|---|
| WR-GBE-BER | 1e-12 | WR-BER-SIGNOFF | BERT |
| WR-GBE-TXSWING | 1000BASE-X (cl.39 CX electrical, or SFP host): 500–1200 mVppd at 100 Ω *(verify)*; SGMII 150–400 mV single-ended swing (300–800 mVppd) *(verify)* | ≥500 mVppd over envelope | Extracted TX |
| WR-GBE-TXJIT | TJ ≤0.24 UI (192 ps), DJ ≤0.10 UI at TP1 *(verify)* | Same | Statistical eye |
| WR-GBE-JTOL | RX TJ tolerance 0.749 UI incl. DJ 0.462 UI (cl.38 TP4) *(verify)*; sinusoidal component per 802.3 cl.38 mask, corner at baud/1667 ≈ 637 kHz | Same mask, bench channel | JTOL |
| WR-GBE-PPM | ±100 ppm | Same | Offset sweep |
| WR-GBE-SSC | none | — | — |
| WR-GBE-RL | Diff RL ≥10 dB, 1 MHz–625 MHz (cl.38/SFP-class) *(verify)* | Same | VNA |

### 1.3 SATA Gen1, 1.5 Gb/s (SATA rev 3.x, Gen1i)

| ID | Value | First-die adaptation | Verification |
|---|---|---|---|
| WR-SATA-BER | 1e-12 | WR-BER-SIGNOFF | BERT |
| WR-SATA-TXSWING | 400–600 mVppd (Gen1i) | Same | Extracted TX |
| WR-SATA-TXJIT | TJ ≤0.37 UI, DJ ≤0.19 UI at fbaud/500 (Gen1i) *(verify)* | Same | Scope TIE |
| WR-SATA-JTOL | RX TJ ≤0.60 UI, DJ ≤0.42 UI at fbaud/500 (Gen1i) *(verify)* | Same mask, bench channel | JTOL |
| WR-SATA-PPM | ±350 ppm | Same | Offset |
| WR-SATA-SSC | 0 to −5000 ppm, 30–33 kHz | Same | SSC |
| WR-SATA-RL | Gen1i diff RL bands ≥18/14/10/8/3 dB over 150–300/300–600/600 M–1.2 G/1.2–2.4 G/2.4–3.0 GHz *(verify)*; CM RL ≥5 dB 150 MHz–600 MHz *(verify)* | ≥14 dB to 600 MHz, ≥10 dB to 1.2 GHz | VNA |
| WR-SATA-OOB | OOB: squelch 50–200 mVppd detect threshold; COMRESET/COMINIT/COMWAKE burst/gap timing (106.7 ns bursts, 320/106.7 ns gaps) | Same | Bench with SATA host |
| WR-SATA-RXSENS | 325 mVppd min at RX (Gen1i) *(verify)* | Same | Swept amplitude |

### 1.4 DisplayPort RBR, 1.62 Gb/s (DP 1.2 PHY)

| ID | Value | First-die adaptation | Verification |
|---|---|---|---|
| WR-DP-BER | 1e-9 per VESA (CTS) | Use WR-BER-SIGNOFF (1e-12) for the primary route | BERT |
| WR-DP-TXSWING | 0.4/0.6/0.8/1.2 Vppd levels, pre-emphasis 0/3.5/6/9.5 dB | 0.4–0.8 Vppd required; 1.2 V and >3.5 dB pre-emphasis desired | Extracted TX |
| WR-DP-TXJIT | RBR TX TJ ≤0.43 UI, non-ISI ≤ … (TP2) *(verify)* | Same | Scope |
| WR-DP-JTOL | RBR sink JTOL per DP CTS mask: ≥… UI at 20 MHz corner *(verify — numbers not recalled reliably)* | Use PCIe Gen1 shape scaled to 1.62 G until verified | JTOL |
| WR-DP-PPM | ±300 ppm | Same | Offset |
| WR-DP-SSC | 0 to −5000 ppm, 30–33 kHz (optional at source, mandatory at sink) | Sink must track | SSC |
| WR-DP-RL | RX diff RL ≥12 dB to 270 MHz class *(verify)* | ≥10 dB to 810 MHz | VNA |
| WR-DP-AUX | AUX channel 1 Mb/s Manchester | Out of die scope (FPGA + board AUX) — record only | — |

### 1.5 HDMI/DVI TMDS, 742.5 Mb/s (720p) and 1.485 Gb/s (1080p) (HDMI 1.4b §4.2)

| ID | Value | First-die adaptation | Verification |
|---|---|---|---|
| WR-TMDS-BER | 1e-9 (HDMI practice) | WR-BER-SIGNOFF for primary route | Pattern checker |
| WR-TMDS-TXSWING | VH = AVcc ±10 mV; single-ended swing 400–600 mV into 50 Ω to 3.3 V | Same, including ff clamp leakage at 3.3 V pull-ups (review §3.6) | Extracted TX + clamp |
| WR-TMDS-TXJIT | Source data jitter ≤0.25 UI (TP1 eye) *(verify)*; clock jitter ≤0.25 Tbit | Same | Eye |
| WR-TMDS-JTOL | Sink tolerates TP2 eye with data jitter 0.55 UI (relative to recovered clock), clock jitter 0.3 Tbit, data-clock skew 0.2 Tpixel *(verify)* | Same | JTOL with HDMI source + jitter injection |
| WR-TMDS-PPM | Forwarded clock (no ppm; pixel clock ±0.5 %) | Same | — |
| WR-TMDS-SSC | none | — | — |
| WR-TMDS-RX-VSWING | Sink: differential input 150–1200 mV | Same | Swept amplitude |

### 1.6 HD-SDI, 1.485 Gb/s (SMPTE ST 292-1)

| ID | Value | First-die adaptation | Verification |
|---|---|---|---|
| WR-SDI-BER | Error-free per CRC over ≥ 1 h | WR-BER-SIGNOFF | CRC + PRBS |
| WR-SDI-TXSWING | 800 mVpp ±10 % into 75 Ω (after external cable driver) | Die drives external cable driver/equalizer (power-partition: board obligation); die output ≥400 mVppd into 100 Ω | Extracted TX |
| WR-SDI-TXJIT | Timing jitter ≤1.0 UI (10 Hz–100 kHz HPF), alignment jitter ≤0.2 UI (>100 kHz) | Same | Jitter analyzer |
| WR-SDI-JTOL | RX tolerates ≥1.0 UI timing and ≥0.2 UI alignment jitter; pathological SDI check field (long runs ~40 bits) | Same; CDR must hold lock through check field | Generator |
| WR-SDI-PPM | ±10 ppm video clock (1.485 or 1.485/1.001) | ±100 ppm design | Offset |
| WR-SDI-RL | ≥15 dB 5 MHz–1.485 GHz, ≥10 dB 1.485–2.97 GHz at 75 Ω BNC | Board network (cable driver/EQ) | VNA |

### 1.7 USB 2.0 HS 480 Mb/s / FS / LS (USB 2.0 §7)

| ID | Value | First-die adaptation | Verification |
|---|---|---|---|
| WR-USB-BER | ≤1e-12 implied by packet error rate | WR-BER-SIGNOFF (480 M: 104 min) | Packet + PRBS |
| WR-USB-HSSWING | 400 mV ±10 % (360–440 mV) into 45 Ω | Same, with per-board cal (B11) only as trim | Extracted + eye template 1 |
| WR-USB-TXJIT | HS TX eye template 1 (near end) | Same | Template |
| WR-USB-JTOL | HS RX eye template 4 at receiver | Same | Template |
| WR-USB-PPM | ±500 ppm HS | Same | Offset |
| WR-USB-SQUELCH | 100–150 mV; disconnect 525–625 mV | Same | Extracted |
| WR-USB-TURN | HS inter-packet / bus turnaround ≤192 bit times (400 ns) end-to-end incl. host latency | Same (review §2 latency) | RTL + bench |
| WR-USB-FSLS | FS edges 4–20 ns; LS 75–300 ns | Same | Extracted |
| WR-USB-RL | none numeric; 45 Ω ±10 % HS termination | Same | DC |

### 1.8 Wired RX/TX common on-chip requirements (derived)

| ID | Value | Basis |
|---|---|---|
| WR-PLL-JIT | Ring PLL RJ ≤ 2 ps rms (12 kHz–20 MHz) and DJ ≤ 0.05 UI at 2.5 Gb/s | PCIe TX TJ 0.25 UI split: 0.1 UI PLL, 0.15 UI serializer+pad |
| WR-SER-DJ | Serializer + pad DJ ≤ 0.15 UI at each rate (≤60 ps at 2.5 G) | Same split; today 305 ps pp at 1.25 G |
| WR-SLICER-OFFSET | Residual offset after trim ≤ 10 mV (≤ 1/6 of 60 mVppd sensitivity) | Sensitivity gate |
| WR-PAD-C | Wired pad C ≤ 1.6 pF effective at 1.25 GHz (or compensated by T-coil/peaking, L≈R²C) for ≥10 dB RL | 50 Ω ∥ C with matched source: |Γ| = x/√(4+x²), x = ωRC; RL = 10 dB (|Γ| = 0.316) ⇒ x ≤ 0.666 ⇒ C ≤ 1.70 pF at 1.25 GHz; 1.6 pF gives 10.5 dB. Today 2.35 (RX) / 2.71 (TX) pF ⇒ 7.6 / 6.6 dB. Bode–Fano permits ≥25 dB with matching (scratch/reviews/physical-limits.md L3) |

## 2. Radio interfaces (2.4–2.5 GHz)

Output powers are mean power at the RF_TX pad into the board match, before
balun loss; "board PA" columns are fallback-only. Regulatory limits apply to the
whole radio and are listed so the on-chip spurious budget has a target.

| ID | Requirement | Standard | First-die adaptation | Verification |
|---|---|---|---|---|
| RF-WIFI-EVM | TX EVM ≤ −5 dB (MCS0) … −27 dB (MCS7), HE20 | 802.11ax Table 27-49 *(verify table no.)* | At ≥ −10 dBm mean linear pad output; target −30 dB to leave 3 dB for LO/IQ | Extracted TX + OFDM vector sim; bench VSA |
| RF-WIFI-MASK | HE20 mask: 0 dBr ±9.75 MHz, −20 dBr ±10.5, −28 dBr ±20, −40 dBr ±30 MHz | 802.11ax §27.3.19.1 | Same | Sim + VSA |
| RF-WIFI-SENS | MCS0 −82 dBm, MCS7 −64 dBm (10 % PER, 4096 B) | 802.11ax | Same, on-chip LNA path | Cascade + bench |
| RF-WIFI-ACR | Adjacent channel rejection MCS0 +16 dB, MCS7 −1 dB; non-adjacent +32 / +15 dB | 802.11ax | Same, on-chip ADC (requires ≥40 MS/s or sharper filter) | Sim + bench |
| RF-WIFI-LOLEAK | TX center (LO) leakage ≤ −20 dBc (relative to total power, HE) *(verify)* | 802.11ax | ≤ −30 dBc with real LO | Sim |
| RF-BLE-MOD | 1M: Δf1avg 225–275 kHz, Δf2max ≥185 kHz; 2M: 450–550 kHz, ≥370 kHz; carrier drift ≤±50 kHz/packet, ≤20 kHz/50 µs | BT Core RF-PHY TS | Same | Sim + tester |
| RF-BLE-IBE | In-band emissions ≤ −20 dBm at ±2 MHz, ≤ −30 dBm at ≥±3 MHz (1M) | BT Core | Same | Sim + SA |
| RF-BLE-SENS | ≤ −70 dBm at 30.8 % PER (BER 0.1 %) | BT Core | Target −90 dBm | Cascade |
| RF-BLE-BLOCK | C/I co-channel 21 dB, ±1 MHz 15 dB, ±2 MHz −17 dB, ≥3 MHz −27 dB; OOB blocking −30/−35 dBm | BT Core | Same | Sim + tester |
| RF-BT-EDR | DEVM rms ≤20 % (π/4-DQPSK), ≤13 % (8DPSK); 99 % DEVM ≤30/20 %; peak 35/25 % | BT Core EDR | Linear mode at ≥ −6 dBm | Sim + tester |
| RF-154-EVM | O-QPSK EVM ≤35 % | 802.15.4 §12 | Same, ≥ −3 dBm | Sim + VSA |
| RF-154-PSD | ≤ −20 dB relative or ≤ −30 dBm at |f−fc| > 3.5 MHz | 802.15.4 | Same | SA |
| RF-154-SENS | ≤ −85 dBm (1 % PER, 20 B) | 802.15.4 | Same | Cascade |
| RF-LORA-SENS | SF-dependent (SX1280-class −130 … −109 dBm *(verify)*), BW 203/406/812/1625 kHz | Semtech LoRa 2.4 | Narrowest on-chip filter ≤ 2× BW; FPGA filters residual | Sim |
| RF-TX-POUT | 0 dBm mean (constant envelope); OFDM: ≥ −10 dBm mean at RF-WIFI-EVM | analog-architecture rfdriver | Primary route on chip; board PA fallback | Extracted |
| RF-TX-HARM | Harmonics/spurious: ≤ −41.25 dBm/MHz EIRP in FCC 15.205 restricted bands (incl. 2483.5–2500 MHz edge, 4.8–5.0 GHz 2nd harmonic, 7.2–7.5 GHz 3rd); ETSI EN 300 328 spurious ≤ −30 dBm (1–12.75 GHz, 1 MHz RBW), −36 dBm (<1 GHz) | FCC 15.247/15.209; EN 300 328 | On-chip H2/H3 ≤ −40 dBc at 0 dBm so a ≤ 2-section board filter closes regulatory | Sim (harmonic balance / PSS) |
| RF-TX-ACLR | ACPR in ±20 MHz channel ≤ −28 dBc (from mask) at max EVM-compliant power | derived from RF-WIFI-MASK | Same | Sim |
| RF-TX-IRR | Image rejection ≥ 35 dB uncorrected, ≥ 40 dB after FPGA cal (supports −27 dB EVM with 3 dB margin from image term) | derived | Same | Sim + bench |
| RF-RX-IRR | RX IQ image rejection ≥ 25 dB uncorrected, ≥ 35 dB after FPGA cal | derived (MCS7 SNR ~25 dB) | Same | Sim |
| RF-RX-IIP3 | IIP3 ≥ −10 dBm at max gain (−0 dBm at min gain per AA lna) to meet BLE/Wi-Fi blocking | derived from RF-BLE-BLOCK, RF-WIFI-ACR | Same | PSS/HB |
| RF-TX-MUTE | Mute isolation ≥ 40 dB (TDD spurious into own RX / regulatory off-state) | derived | Same | Sim |
| RF-LO-JIT | LO integrated jitter ≤ 1.05 ps rms total, ≤ 0.3–0.5 ps per on-chip slot; I/Q skew ≤ 1° (1.16 ps) | clock-feasibility-envelope.md | Same | Sim + bench |

## 3. Host-link IO timing budget (source-synchronous DDR, 156.25 MHz forwarded clock)

UI = 3.2 ns (312.5 Mb/s per pin), 10 data + 1 clock per direction, LVCMOS33,
6 pF external load target. Window = data-valid region the receiver needs.
Values in ps; "E" = from evidence, "A" = assumption/allocation (to be replaced
by the host-family numbers once chosen).

### 3.1 D2H (chip launches, FPGA captures, FPGA IDELAY-trained)

| ID | Item | ps | Source |
|---|---|---|---|
| HL-UI | Unit interval | 3200 | 156.25 MHz DDR |
| HL-D2H-SKEW | Chip clock-to-data skew (pad tco spread over 11 bi_24t + on-die launch tree) | 400 | A (hostio_pad_screen skew_budget_ns 0.4) |
| HL-D2H-DCD | Forwarded-clock duty-cycle distortion (±2.5 % of 6.4 ns) | 160 | A |
| HL-D2H-JIT | Clock-to-data uncorrelated jitter (PJ+RJ pp) | 100 | A |
| HL-D2H-SSO | SSO pushout, 11 outputs switching | 200 | A — unverified (review §2) |
| HL-D2H-ISI | ISI at 6 pF, bi_24t fast slew (tr 0.94 ns tt / 1.72 ns ss at 10 pF) | 150 | E (fpga-host-screen.md transitions), A for ISI share |
| HL-D2H-BOARD | Board length mismatch (±2 mm ≈ ±12 ps, + crosstalk) | 50 | A |
| HL-FPGA-WIN | FPGA input setup+hold after IDELAY training | 1000 | A (hostio_pad_screen fpga_rx_window_ns 1.0; 7-series HR LVCMOS class 0.6–1.0 ns) |
| **HL-D2H-MARGIN** | UI − Σ | **1140 (36 % UI)** | requirement: ≥ 0.15 UI (480 ps) |

### 3.2 H2D (FPGA launches, chip captures in pt_host_link)

| ID | Item | ps | Source |
|---|---|---|---|
| HL-H2D-PADIN | Chip pad input DDR limit: bi_24t input f_DDR,max 193.2 MHz tt → min UI 2588 ps; 148.2 MHz ss_125C → 3374 ps (**> 3200, fails**, outside envelope); in-envelope number missing | E (hostio_pad_screen) |
| HL-H2D-CAP | Macro capture window (setup+hold at the flop) | 300 | A (macro_capture_window_ns) |
| HL-H2D-FPGASKEW | FPGA output clock-to-data skew + DCD (ODDR, forwarded clock) | 400 | A host-dependent |
| HL-H2D-JIT/SSO/ISI/BOARD | as D2H | 500 | A |
| HL-H2D-PADEDGE | Pad input edge uncertainty | 1000 (incl. in PADIN limit) | E/A |
| **HL-H2D-MARGIN** | tt: 3200 − 2588 = 612 ps pad-limited; budget sum 300+400+500 = 1200 → margin 1700 ps excl. pad edge; ss_125C: −174 ps (outside the operating envelope, non-gating per MANDATE.md) | requirement: ≥ 0.15 UI at every in-envelope corner, from a characterized 22–32 °C/3.15–3.35 V Liberty |

### 3.3 Host-link requirements

| ID | Requirement |
|---|---|
| HL-RATE | 312.5 Mb/s per pin, 10+1 pins per direction, both directions simultaneously (2.88 Gb/s dense payload); framed wired rates use host word clock = line/8 (1.152 × line capacity), not line/10 (0.922 × line, 7.8 % short) |
| HL-CORE | Core logic behind the pads closes across the envelope: pad-edge gearbox 156.25 MHz, transport core 78.125 MHz × 40 bit, wired boundary line/40 (interface-architecture-changes.md AC-1); today 65.3 MHz tt at the old 1:2 boundary — fails |
| HL-SSO | Ground bounce ≤ 300 mV on quiet D2H/H2D lines with 11 outputs toggling, real bond/ring model |
| HL-TRAIN | FPGA-side per-bit deskew (IDELAY or equivalent) with ≥ 50 ps resolution; chip provides a training pattern |
| HL-LATENCY | Control/response latency ≤ 400 ns at achieved clocks (USB HS turnaround) |
| HL-WIDE | Proposed architecture variant (parent spec): pads stay 10-bit DDR at 156.25 MHz; core moves to a 40-bit / 78.125 MHz gearbox. **This IO timing budget is unchanged** by that variant; only HL-CORE moves. |
