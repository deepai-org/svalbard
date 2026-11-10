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
| WR-BER-SIGNOFF | BER ≤ 1e-12 at 95 % CL, zero errors, PRBS7 (8b/10b links: also K28.5/CJPAT-class pattern; SDI: pathological SDI check field) | 3.0e12 | 2.5 G: 20 min; 1.62 G: 31 min; 1.5 G: 33 min; 1.485 G: 34 min; 1.25 G: 40 min; 742.5 M: 67 min; 480 M: 104 min; 2.7 G: 19 min; 3.0 G: 17 min; 3.125 G: 16 min |
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

### 1.9 Added interfaces (user-approved 2026-11-10): reuse map

The rows below add only what is new. Everything else is inherited by ID:

| New interface | Reuses unchanged | New rows |
|---|---|---|
| SATA Gen2 3.0 Gb/s | WR-SATA-PPM, WR-SATA-SSC, WR-SATA-OOB (OOB signalling is rate-independent), WR-BER-SIGNOFF, WR-PLL-JIT, WR-SLICER-OFFSET | WR-SATA2-* (§1.10), WR-RATE-*, WR-HL-LINECODE |
| DisplayPort HBR 2.7 Gb/s | WR-DP-TXSWING (same levels/pre-emphasis), WR-DP-PPM, WR-DP-SSC, WR-DP-AUX, WR-DP-BER (1e-12 on primary route) | WR-DPHBR-* (§1.11), WR-RATE-*, WR-HL-LINECODE |
| 2500BASE-X 3.125 GBd, XAUI lane 3.125 Gb/s | WR-GBE-BER/-PPM (±100 ppm), WR-GBE-SSC (none); 2500BASE-X uses the 1000BASE-X PCS (802.3 cl.36) clocked 2.5× | WR-3G1-* (§1.12) shared by both, WR-RATE-*, WR-HL-LINECODE |
| Continuous line-rate coverage | — | WR-RATE-CONT, WR-RATE-EDGE, WR-RATE-LOW (§1.13) |

BER signoff test time (WR-BER-SIGNOFF, 3.0e12 bits): 3.125 G 16 min; 3.0 G 17 min; 2.7 G 19 min.

**Package check (all four new rates).** `scratch/cob/channel_model.py` `pulse()` rerun at the new rates
(2026-11-10): WIRE_RX eye fraction (1 − ISI) 0.96 / 0.94 / 0.91 / 0.86 at 2.7 / 3.0 / 3.125 / 3.24 Gb/s with
today's 2.35 pF; 0.97 / 0.94 / 0.92 / 0.92 with the S7 target 1.6 pF; WIRE_TX 0.97 / 0.95 / 0.92 / 0.93.
The COB channel alone does not close any new eye; as at 2.5 Gb/s, **return loss and the on-die serializer/CDR
are binding, not the package.**

### 1.10 SATA Gen2, 3.0 Gb/s (SATA rev 3.x, Gen2i/Gen2m)

| ID | Value (standard) | First-die adaptation | Verification |
|---|---|---|---|
| WR-SATA2-BER | 1e-12 | WR-BER-SIGNOFF (17 min at 3.0 G) | BERT / FPGA PRBS + ALIGN/CJTPAT-class pattern |
| WR-SATA2-TXSWING | Gen2i 400–700 mVppd *(verify)* | 400–700 mVppd over envelope (WR-SATA-TXSWING is 400–600 for Gen1i) | Extracted TX |
| WR-SATA2-TXJIT | Gen2i TJ ≤ 0.37 UI, DJ ≤ 0.19 UI at fbaud/500; TJ ≤ 0.55 UI at fbaud/10 *(verify)*; UI 333 ps | Same | Statistical eye, scope TIE |
| WR-SATA2-JTOL | Gen2i RX TJ ≤ 0.60 UI, DJ ≤ 0.42 UI at fbaud/500; TJ ≤ 0.65 UI at fbaud/10 *(verify)* | Same mask, bench channel; CDR BW per S4 (0.5–4 MHz) must not filter below fbaud/500 = 6 MHz corner | JTOL |
| WR-SATA2-RXSENS | Gen2i 275 mVppd min at RX *(verify)* | Same | Swept amplitude |
| WR-SATA2-RL | Gen2i diff RL ≥ 18/14/10/8/3 dB over 150–300 M / 300–600 M / 0.6–1.2 G / 1.2–2.4 G / 2.4–3.0 GHz, RX and TX *(verify)* | ≥ 14 dB to 600 MHz, ≥ 10 dB to 1.2 GHz, **≥ 8 dB to 2.4 GHz** | VNA / extracted S-params |

Feasibility: the 8 dB band to 2.4 GHz sets **C_pad ≤ 1.15 pF** (|Γ| = x/√(4+x²) ≤ 0.398 ⇒ x ≤ 0.868 ⇒
C ≤ 0.868/(2π·2.4 GHz·50 Ω)); the S7 target 1.6 pF gives 5.7 dB at 2.4 GHz. At the 1.5 GHz Nyquist, 1.6 pF gives
9.0 dB (passes 8 dB). The package-channel axis already demands ≥ 8 dB at 2.5 GHz (package-channel.md §6), so
this is a tightening of S7, not a new axis: low-C variant or T-coil (interface-changes IX-3).

### 1.11 DisplayPort HBR, 2.7 Gb/s (DP 1.2 PHY)

| ID | Value (standard) | First-die adaptation | Verification |
|---|---|---|---|
| WR-DPHBR-TXJIT | HBR TX TJ at TP2 ≤ 0.53 UI *(verify — DP 1.2 TP2 HBR mask)*; UI 370 ps | Same; non-ISI part ≤ 0.25 UI | Scope |
| WR-DPHBR-JTOL | HBR sink JTOL per DP CTS mask, corner 10–20 MHz *(verify)* | Until verified: PCIe Gen1 shape (WR-PCIE-JTOL) scaled to 2.7 G | JTOL |
| WR-DPHBR-RL | RX diff RL ≥ 12 dB to 1.35 GHz class *(verify)* | ≥ 10 dB to 1.35 GHz (C_pad ≤ 1.57 pF; the S7 1.6 pF target gives 9.9 dB, i.e. borderline) | VNA |

DP RBR (1.62 Gb/s) sits on the 810 MHz top edge of the half-rate band today (0 % margin); WR-RATE-EDGE fixes that.

### 1.12 3.125 GBd: XAUI lane (IEEE 802.3 cl.47) and 2500BASE-X

2500BASE-X is not an IEEE clause; it is the 1000BASE-X PCS at 3.125 GBd, with electrical specs taken from
XAUI (cl.47) or 2.5GBASE-KX (802.3cb-2018 cl.128) *(verify which the target partner uses)*. Both profiles share
these rows; differences are noted.

| ID | Value (standard) | First-die adaptation | Verification |
|---|---|---|---|
| WR-3G1-BER | 1e-12 | WR-BER-SIGNOFF (16 min at 3.125 G) | BERT, PRBS7 + CJPAT |
| WR-3G1-TXSWING | XAUI 800–1600 mVppd *(verify)*; 2.5GBASE-KX 800–1200 mVppd *(verify)* | ≥ 800 mVppd over envelope (same CML tail fix as WR-PCIE-TXSWING, S8) | Extracted TX |
| WR-3G1-TXJIT | XAUI TJ ≤ 0.35 UI (112 ps), DJ ≤ 0.17 UI *(verify)* | Same | Statistical eye |
| WR-3G1-JTOL | XAUI RX TJ 0.65 UI, DJ 0.37 UI; sinusoidal mask corner baud/1667 = 1.875 MHz *(verify)* | Same mask, bench channel | JTOL |
| WR-3G1-PPM | ±100 ppm, no SSC | Same (inherits WR-GBE-PPM range) | Offset sweep |
| WR-3G1-RL | XAUI diff RL ≥ 10 dB 100–625 MHz, then 10 − 10·log10(f/625 MHz) to 3.125 GHz *(verify)* | Same: ≥ 6.0 dB at the 1.5625 GHz Nyquist (1.6 pF gives 8.7 dB, passes) | VNA |

### 1.13 Line-rate coverage (continuous, 0.48–3.24 Gb/s and below)

Today the ring PLL covers 480–810 MHz, so the full/half/quarter-rate bands are 0.48–0.81, 0.96–1.62 and
1.92–3.24 Gb/s, with **gaps at 0.81–0.96 and 1.62–1.92 Gb/s**, DP RBR (1.62) on an edge and 3.125/3.24 Gb/s
within 3.6 % / 0 % of the top. With N ∈ {1, 2, 4} the bands are gap-free only if f_max ≥ 2·f_min; with a margin
m at every edge, f_max ≥ 2·f_min·(1+m)².

| ID | Requirement | Basis |
|---|---|---|
| WR-RATE-CONT | Every line rate in 0.48–3.24 Gb/s is reachable on the primary on-chip route (TX serializer + RX CDR, same ring) with no gaps, in at least one of full/half/quarter-rate mode, across tt/ss/ff × 22–32 °C × 3.15–3.35 V | User 2026-11-10; standards in §1.1–1.12 plus "intermediate serial rates" (README) |
| WR-RATE-EDGE | ≥ 3 % tuning margin at every band edge, i.e. ring f_min ≤ 393 MHz and f_max ≥ 834 MHz on the **regulated** ring rail (tuning ratio ≥ 2.12:1, coarse band codes allowed). The 3 % covers −5000/+300 ppm SSC/offset (0.53 %), ±1 % PVT drift between calibrations within the envelope, and the CDR integral range (S4: +600…−5600 ppm) | Margin derivation here; ring headroom: analog/pll_vreg/README.md "810 MHz at ss needs ≥ 3.02 V" |
| WR-RATE-LOW | Below 0.48 Gb/s: TX by ring ÷2^k word/serializer clocking (down to USB FS 12 Mb/s class), RX by FPGA oversampling of the full-rate slicer output (`wire_cdr_fpga_oversample`) at ≥ 4× ≤ 120 Mb/s, or full-rate CDR at ring/2^k ≥ 240 Mb/s *(verify CDR loop at reduced ring rate)* | Existing fallback route promoted to a documented rate mode |

Feasibility against current evidence:

- Ring core: `vco_replica` tunes 258 MHz (VCTRL 0.9 V, tt) to 1093 MHz; ss reaches ≥ 852 MHz only at VCTRL = VDD = 3.3 V
  (analog/timing/README.md). On the regulated rail the ss top is 733 MHz (2.75 V) to 778 MHz (2.9 V); 810 MHz runs
  in `BYP` with A3 jitter (≈ 29–33 ps pk DJ, analog/pll_vreg/README.md). **834 MHz regulated at ss needs the
  ring resized for ≥ 900 MHz at 2.6 V ss** (already named there). Low end ≤ 393 MHz needs VCTRL ≈ 1.0–1.1 V at ff
  *(not simulated)* or one extra coarse band.
- Samplers / capture: S4 already demands 625 and 810 MHz; WR-RATE-EDGE raises this to 834 MHz (half-rate up to
  1.67 Gb/s, quarter-rate to 3.34 Gb/s). `wrx_cap` fails above 480 MHz today.
- TX: the 4:1 mux fails 1.92–2.97 Gb/s today (WR-PCIE-TXJIT); the new top is 3.34 Gb/s.
- Word clock: `pt_wordclk` CK→LD ≈ 1.15 ns at tt "close to a period at 810 MHz"; at 834 MHz the period is 1.20 ns.
- Host link: see WR-HL-LINECODE (§3.3).
- Fallbacks: `wire_rx_board_retimer` / B13, `wire_tx_board_serializer` / B14, `wire_board_phy_bypass` (FPGA GTs
  carry the lane, chip unused) for rates the primary route misses.

### 1.14 Twisted-pair Ethernet: 100BASE-TX added, 10BASE-T not added (2026-11-10)

Admission rule (user): add a standard only if it makes the chip more general-purpose by **generalizing existing
hardware**, with no dedicated new blocks. The analysis is
summarised here. The behavioural link model (MLT-3, TX filter, 2 × magnetics HPF, Cat5 skin/dielectric loss, CTLE, eye and
baseline-wander statistics) is `scratch/ethernet/fe100.py`. Demands IX-9…IX-13 are in
`scratch/reviews/interface-changes.md`. Board items are B38, B39 and B38a. Standard values transcribed from memory are *(verify)*
(IEEE 802.3 cl.24/25 → ANSI X3.263 TP-PMD; cl.14 10BASE-T; cl.28 auto-negotiation).

**Verdicts**

| Standard | Verdict | Binding quantity |
|---|---|---|
| 100BASE-TX (MLT-3, 125 MBd, 4B5B + scrambler) | **(b) add, via four small generalizations** (IX-9…IX-13) | TX: 2 × 20 mA = 40 mA gives ±1.0 V into the 49.9 Ω‖100 Ω network (V = I·25 Ω). That is available as MAIN + POST summed at the same sign. RX: no eye beyond ≈ 50 m without a low-frequency EQ zero, and the ±thresholds (≈ ±90…±135 mV at the slicer) exceed the ±52 mV trim range |
| 100BASE-FX / FDDI-style 125 MBd NRZI over an optical module | (a) free: NRZ at 125 MBd on the existing TX (4× repetition) and the IX-4 oversampling path. Nothing added | — |
| 10BASE-T (Manchester, 10 Mb/s, 2.2–2.8 V peak) | **(c) not added** | A current-steering driver at 3.3 V into a matched (back-terminated) load, with any transformer ratio n, gives V_line = 25·I/n and a leg drop of 37.5·I/n² ≤ 2.5 V. So V_line,max = 1.39 V (46.4 mA, MAIN 25.4 + POST 21.05) or 1.45 V (50.8 mA with IX-9). 2.2 V needs I ≥ 116 mA (n ≥ 1.32), or a dedicated low-impedance voltage-mode H-bridge. The RX side would be free (raw oversampling and IX-10 squelch threshold), but a PHY is useless without its TX. Near miss: 10BASE-Te (802.3az, 1.54 V min peak) needs ≥ 57–62 mA, i.e. MAIN+POST+TMDS tails summed and a pad interlock/EM change. Not proposed. 10BASE-T, if needed, goes through the board PHY B38a |

**100BASE-TX function map (existing block → role)**

| PHY function | Implementation | New? |
|---|---|---|
| 4B5B, scrambler/descrambler (11-bit LFSR), NRZI↔MLT-3, idle/JK/TR, link monitor, auto-negotiation state machine, MII/RMII to the MAC | FPGA | none on chip |
| TX levels +1/0/−1 | MAIN and POST tails (pads `tx_protected_pad`), external centre-tap network B39, on-die TX termination off (TMDS-like external pull-up configuration). With POST at the same sign (IX-9): held ±1 = MAIN+POST on one leg (±2·I·25 Ω). 0 = main toggling every line UI so that MAIN(k) and POST = MAIN(k−1) cancel exactly | IX-9 (polarity bit, POST DAC ×1.2) |
| TX clock / rate | Quarter-rate core (WT12) at ring 500 MHz = 2 Gb/s, 16 line UI per symbol. The FPGA builds the 16× pattern. The 0→±1 parity alignment costs ≤ 1 line UI = 0.5 ns DJ | none |
| TX wave-shaping (3–5 ns edges, ≤ 5 % overshoot) | Board doubly-terminated 2nd-order Bessel/Butterworth LC low-pass, fc ≈ 110–120 MHz (B39). It also removes the 1 GHz cancellation residue of the 0 level | board only |
| Link pulses (FLP for auto-negotiation) | Same TX, 100 ns pulses, MAIN+POST summed: 1.16 V peak (tt, today) / 1.27 V (IX-9). This is **below** the cl.14 2.2 V template | best effort (WR-100TX-ANEG) |
| RX termination / CM | `termination` mode 10 (100 Ω differential, trim PKG-W1a). Magnetics RX centre tap biased to 1.0 V on the board (B38), inside the CTLE window 0.8–1.2 V ss. On-die AC coupling (PKG-W1c, HPF 0.8 MHz) **off** | none |
| RX amplitude | `rxlevel` bypass (half only for ≤ 10 m if the CTLE linear range needs it). CTLE code 7 DC gain −11.4 dB | none |
| Cable EQ (0–100 m Cat5) | CTLE with a switchable low-frequency source-degeneration cap bank: zero 4.4–35 MHz at code 7 (IX-13) | IX-13 |
| ± decision thresholds, DC restore (baseline wander), squelch level | Threshold DACs on the edge samplers e0–e3 (IX-10), updated by the FPGA through a fast in-band command (IX-11) | IX-10, IX-11 |
| Clock recovery | FPGA blind oversampling (the IX-4 / `wire_cdr_fpga_oversample` route promoted for this mode). RX ring locked to the board reference at 750 MHz (6× per symbol), full-rate raw mode, psel forced odd so the data (psel) and edge (psel+4) lanes are both e-samplers at +V_th / −V_th (IX-12) | IX-12 |
| Signal detect | Coarse energy from `pt_detect` (squelch 125 mV / disconnect ≈ 540 mV codes) plus FPGA descrambler lock | none |
| Magnetics, RJ45, Bob-Smith termination | Board (B38) | board only |

**Requirements**

| ID | Value (standard) | First-die adaptation | Verification |
|---|---|---|---|
| WR-100TX-TXLVL | Differential output 950–1050 mV peak into 100 Ω; amplitude symmetry 0.98–1.02; overshoot ≤ 5 % *(verify, TP-PMD §9.1)* | Same, through the COB (at 62.5 MHz the COB chain is < 0.05 dB: ~3–4 nH, 2.7 pF) and B39. **Sum current 40 mA (2 × 20 mA)**: today MAIN 25.4 mA + POST 21.05 mA full scale (tt) = +16 % headroom. With IX-9 (POST ×1.2): +27 %. The pad leg sinks ≤ 51 mA and stays ≥ 1.7 V above VSS with the CT at 3.3 V. Per-board code calibration as B11 | Extracted pad + B39 network sim at tt/ss/ff; bench scope at the RJ45 |
| WR-100TX-TXSHAPE | Rise/fall 3.0–5.0 ns, rise/fall symmetry ≤ 0.5 ns, DCD ≤ ±0.25 ns *(verify)* | Edges set by the B39 LC filter (2nd-order, fc ≈ 110–120 MHz). The 0-level cancellation residue (MAIN/POST mismatch at 1 GHz) ≤ 1 % of peak after the filter | Sim with B39 + bench |
| WR-100TX-TXJIT | Transmit jitter ≤ 1.4 ns pp *(verify)*; 125 MBd ± 50 ppm | ≤ 0.7 ns pp: 0.5 ns parity DJ (16× quarter-rate pattern) + PLL/serializer. Half-rate (1 Gb/s, 8×) is allowed if host H2D is short, giving ≤ 1.2 ns | Scope TIE |
| WR-100TX-RL | TX and RX RL ≥ 16 dB 2–30 MHz, ≥ 16 − 20·log10(f/30 MHz) dB 30–60 MHz, ≥ 10 dB 60–80 MHz *(verify)* | TX: B39 49.9 Ω 1 % back-termination with the doubly-terminated filter: ≈ 24 dB at 30 MHz, ≈ 12 dB at 60 MHz (spec 10). RX: on-die 100 Ω trim (PKG-W1a, 40–60 Ω per leg). Pad C is negligible below 80 MHz | VNA at the RJ45 |
| WR-100TX-RXEQ | Operate over 0–100 m Cat5/Class D (IL 1.967√f + 0.023f + 0.05/√f dB per 100 m: 11.7 dB at 31.25 MHz, 17.0 dB at 62.5 MHz) with NEXT | Behavioural model (two 350 µH magnetics, Bessel TX filter, single-zero CTLE, ideal DC restore). Inner-eye opening / outer level: no EQ 1.00 / 0.59 / −0.01 at 0 / 25 / 50 m (**closed at 50 m**). With the IX-13 zero (best of 10–40 MHz): 0.84 / 0.66 / 0.61 / 0.54 at 25 / 50 / 75 / 100 m. FPGA picks the zero code by eye scan (IX-10) | Model + extracted CTLE with IX-13 bank; bench with 0/50/100 m cable |
| WR-100TX-RXTH | Ternary decisions (two thresholds) | Outer level at the slicer A ≈ 0.18–0.27 V (100 m … 0 m, code 7 DC gain). Thresholds ±A/2 = ±90…±135 mV plus ±50 mV DC-restore headroom ⇒ **threshold range ≥ ±250 mV, LSB ≤ 4 mV** (IX-10). Today's trim is −52…+65 mV, which is insufficient | Extracted slicer + DAC |
| WR-100TX-BLW | Tolerate baseline wander, including the "killer packet" *(verify TP-PMD Annex)* | Two magnetics HPFs (OCL ≥ 350 µH, τ = 7 µs). Uncorrected held-level wander: 26 % of A after 1 µs, 110 % after 10 µs. FPGA decision-directed DC restore via IX-10/IX-11, **loop delay ≤ 0.5 µs** ⇒ residual: random scrambled data ≤ 5.6 % A peak (1.3 % rms); worst held level 13.5 % A, against the 27 % half-eye at 100 m (marginal at 100 m, OK ≤ 50 m). A 1 µs loop gives 6.9 % / 26 % | Model + bench killer packet |
| WR-100TX-CDR | 125 MBd ± 50 ppm, TP-PMD jitter tolerance *(verify)* | FPGA oversampling 6× (RX ring 750 MHz), 1.33 ns phase quantization against an 8 ns UI. Two lanes (IX-12) | FPGA model + bench |
| WR-100TX-SD | Signal detect assert > 1000 mVppd, de-assert < 200 mVppd *(verify)* | `pt_detect` energy codes plus descrambler lock in the FPGA; the threshold-DAC amplitude scan gives a level estimate | Bench |
| WR-100TX-BER | BER ≤ 2.5e-10 *(verify)* | ≤ 1e-10 at 95 % CL (3.0e10 bits, 4.0 min at 125 Mb/s payload) at 0, 50 and 100 m | FPGA PRBS / frame CRC |
| WR-100TX-HOST | Host transport of the PHY streams | D2H 2 lanes × 750 Mb/s = 1.5 Gb/s (52 % of 2.88 Gb/s). H2D 2.0 Gb/s at 16× (69 %), or 1.0 Gb/s at 8×. Plus the threshold updates (≤ 2 MHz × 32 b ≈ 64 Mb/s). Full duplex: TX and RX rings separate | Transport model |
| WR-100TX-ANEG | Auto-negotiation FLP bursts (cl.28), link-pulse amplitude 2.2–2.8 V peak (cl.14 template) *(verify)* | **Not compliant: FLP at 1.16 V (today) / 1.27 V (IX-9)**. Best effort, partner link-pulse detection to ≈ 50 m. Primary mode: forced 100BASE-TX full duplex (the partner forced, or its parallel detection giving half duplex) | Bench with a commodity switch |

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

### 2.1 Added radio interfaces (user-approved 2026-11-10): reuse map

| New interface | Reuses unchanged | New rows |
|---|---|---|
| BLE LE Coded S=2 (500 kb/s) / S=8 (125 kb/s) | RF-BLE-MOD (same 1 Msym/s GFSK, h = 0.5, ±250 kHz), RF-BLE-IBE, RF-BLE-BLOCK out-of-band blocking, RF-TX-POUT, RF-TX-HARM, RF-RX-IIP3, RF-LO-JIT; T_IFS 150 µs as for 1M | RF-BLE-CODED-SENS, RF-BLE-CODED-CI, RF-BLE-CODED-PKT |
| BLE Channel Sounding (Core 6.0, Vol 6 Part A/B/H) | RF-BLE-MOD/-IBE (CS uses LE 1M or 2M for CS_SYNC; tones are unmodulated), RF-BLE-SENS, RF-RX-IRR, RF-TX-IRR, RF-LO-JIT | RF-CS-HOP, RF-CS-TIP, RF-CS-PHASE, RF-CS-IQ, RF-CS-RTT, RF-CS-ANT, RF-CS-RANGE |
| 802.15.4 base (gaps in RF-154-*) | RF-154-EVM, RF-154-PSD, RF-154-SENS | RF-154-TURN, RF-154-CCA, RF-154-FTOL |
| Thread (1.3/1.4) | All RF-154-*; MAC/MLE/IPv6 in FPGA/host | RF-THREAD-CSL |
| Zigbee (R22/R23, 2.4 GHz O-QPSK) | All RF-154-* — Zigbee adds no PHY or PHY-timing requirement beyond 802.15.4 | RF-PROF-ZIGBEE (mapping only) |
| Matter (1.x) | Over Thread: RF-THREAD-CSL + RF-154-*; commissioning over BLE 1M: RF-BLE-*; over Wi-Fi: RF-WIFI-* | RF-PROF-MATTER (mapping only) |

Source for all BLE rows: Bluetooth Core Specification v6.0 (Vol 6 Part A RF PHY, Part B Link Layer CS,
Part H CS security/procedures) and RF-PHY.TS. Source for 802.15.4: IEEE 802.15.4-2020 §10/§12 (O-QPSK 2.4 GHz).
Thread: Thread 1.3/1.4 specification (CSL, enhanced ACK). All numbers transcribed from memory are *(verify)*.

| ID | Requirement | Standard | First-die adaptation | Verification |
|---|---|---|---|---|
| RF-BLE-CODED-SENS | Reference sensitivity S=8 (125 kb/s) ≤ −82 dBm, S=2 (500 kb/s) ≤ −75 dBm at 30.8 % PER, 37-byte payload *(verify)* | BT Core 6.0 Vol 6 Part A §4.1 | Target S=8 ≤ −95 dBm, S=2 ≤ −90 dBm (on-chip LNA, FPGA Viterbi/pattern-map demod) | Cascade + bench with CMW/tester |
| RF-BLE-CODED-CI | Co-channel C/I S=8 ≤ 12 dB, S=2 ≤ 17 dB *(verify)*; adjacent ±1/±2/≥±3 MHz per the Coded table *(verify)* | BT Core 6.0 Vol 6 Part A §4.2 | Same; on-chip filter and ADC as for 1M | Sim + tester |
| RF-BLE-CODED-PKT | Packets up to 17.04 ms (S=8, 255 B); carrier drift ≤ ±50 kHz over the packet, drift rate ≤ 400 Hz/µs *(verify)* | BT Core 6.0 Vol 6 Part A §3.1 | RX gain/AGC, DC-offset loop and LO stay fixed for ≥ 17.1 ms (no AGC re-step mid-packet unless the FPGA commands it); TX drift as RF-BLE-MOD over 17 ms | Sim (LO + DC loop over 17 ms) + bench |
| RF-CS-HOP | Every CS step changes channel (72 channels, 2402–2480 MHz, 1 MHz grid excluding advertising channels *(verify)*); frequency-change period T_FCS ∈ {15, 20, 30, 40, 50, 60, 80, 100, 120, 150} µs, chosen from the slower device's capability *(verify)* | BT Core 6.0 Vol 6 Part B §4.5.18 / Part H | Advertise T_FCS = 80 µs (stretch 50 µs): LO **phase**-settled (≤ 2° from final trajectory) and RX/TX path settled within T_FCS − 5 µs; current warm-hop allocation is 50 µs with 35 µs external-source settling (block-diagram.md "Warm RF hopping") | Sim + bench (phase vs time after hop) |
| RF-CS-TIP | T_IP1/T_IP2 ∈ {10, 20, 30, 40, 50, 60, 80, 145} µs, T_PM ∈ {10, 20, 40} µs *(verify)* | BT Core 6.0 Vol 6 Part B | Advertise T_IP2 ≤ 40 µs, T_PM = 40 µs: **TX↔RX direction change on the same channel with the LO running and phase-continuous**, ≤ 30 µs including converter/filter settling | Sim + bench |
| RF-CS-PHASE | Mode-2 PBR: per-tone round-trip phase coherent within a step; Core sets the procedure, not an accuracy | BT Core 6.0 Vol 6 Part H | Derived: LO phase drift between the TX tone and the RX tone of one step ≤ 2° rms (at 80 µs separation ⇒ residual frequency transient ≤ 70 Hz, after FFO compensation); random per-tone round-trip phase error ≤ 5° rms; frequency-dependent systematic phase (linear part) ≤ 10° across 2402–2480 MHz after loopback calibration (≈ 5 cm bias). LO supply pushing of `lo_ext` 0.0025 ps/mV ⇒ 2° = 2.3 ps ⇒ ≤ 900 mV, not binding | Sim (LO + TX/RX switch), bench with reference initiator |
| RF-CS-IQ | Tone phase from IQ imbalance | derived | IQ-induced tone phase error ≤ 1° (⇔ RX image rejection ≥ 35 dB after cal, = RF-RX-IRR post-cal) **held across the 78 MHz span** (per-channel or ≤ 5 MHz-bin cal table on the FPGA); on-chip LO I/Q trim D-LO-2 (±15°, ≤ 1° step) remains the coarse stage | Loopback cal + bench |
| RF-CS-RTT | Mode-1 RTT: ToA/ToD timestamp precision capability 150 ns / 10 ns class, CS_SYNC on LE 1M/2M *(verify)* | BT Core 6.0 Vol 6 Part B | Fixed, readable TX-launch → RX-sample latency (deterministic to ≤ 5 ns rms after per-mode calibration); sub-tick timestamp (the action clock tick is 25.6 ns) by FPGA correlation on ADC samples ≥ 8 MS/s; ToA precision ≤ 10 ns rms at −60 dBm | RTL timing + bench |
| RF-CS-ANT | N_AP 1–4 antenna paths, antenna-switch period T_SW ∈ {0, 1, 2, 4, 10} µs *(verify)* | BT Core 6.0 Vol 6 Part B | First die: N_AP = 1 (no switching). Multi-antenna via an external RF switch driven by FPGA GPIO, timed from the chip's tone/step boundaries (± 0.5 µs); **no chip pin** | Bench |
| RF-CS-RANGE | Ranging accuracy (not a Core requirement; application target) | derived / market practice *(verify)* | PBR ≤ 0.5 m rms, RTT ≤ 3 m rms, cabled/attenuated link at path loss equal to 1–10 m free space; LOS bench ≤ 1 m (95 %). Error budget: σ_d ≈ 0.125 m/rad · σφ (72 tones over 78 MHz) + 0.306 m/rad · linear phase error | Bench vs reference CS device |
| RF-154-TURN | RX↔TX turnaround ≤ aTurnaroundTime = 12 symbols = 192 µs; ACK sent at aTurnaroundTime ± … *(verify)*; channel switch ≤ 500 µs *(verify)* | 802.15.4-2020 §10.2.? / §8.? *(verify)* | Same: chip TDD switch ≤ 40 µs (shared with RF-CS-TIP) + host/FPGA latency; channel switch uses the 50 µs warm hop | Sim + bench |
| RF-154-CCA | CCA over 8 symbols (128 µs); ED threshold ≤ 10 dB above RF-154-SENS; ED range ≥ 40 dB, ±6 dB accuracy *(verify)* | 802.15.4-2020 §10.2.5/10.2.6 *(verify)* | RSSI from ADC + known gain state; gain state readable in ≤ 128 µs | Bench |
| RF-154-FTOL | TX centre frequency tolerance ±40 ppm (≈ ±98 kHz) | 802.15.4-2020 §12.? *(verify)* | Same (external LO / QVCO PLL reference accuracy) | Bench |
| RF-THREAD-CSL | Coordinated Sampled Listening: receiver wakes in a CSL window; transmitter schedules to the CSL phase; CSL accuracy/uncertainty fields in ppm/10 µs units; enhanced ACK with IEs at aTurnaroundTime *(verify)* | Thread 1.3/1.4 §? *(verify)* | Chip: TX launch and RX-window start scheduled on the action clock with deterministic latency ≤ ±16 µs (1 symbol) after calibration; RX warm-up (bias on → valid samples) ≤ 100 µs; enhanced ACK built by FPGA within RF-154-TURN | RTL + bench |
| RF-PROF-ZIGBEE | Zigbee profile = 802.15.4 O-QPSK 250 kb/s, channels 11–26 | Zigbee R23 | Inherits RF-154-* (incl. -TURN, -CCA, -FTOL); no new PHY demand | — |
| RF-PROF-MATTER | Matter transports: Thread, Wi-Fi, BLE (commissioning) | Matter 1.x | Inherits RF-THREAD-CSL, RF-154-*, RF-WIFI-*, RF-BLE-*; no new PHY demand | — |

Feasibility and host link (radio): LE Coded raw air rate is 1 Msym/s and CS tones are CW, so the RF host link is
unchanged (well inside HL-RATE at div2, PWR-HOST-RF). RF-BLE-SENS meets −70 dBm with a 10–18 dB cascade margin
(≈ −80…−88 dBm at 1M); the S=8 code adds ≈ 8–12 dB *(analytic, verify by demod sim)* ⇒ ≈ −88…−100 dBm vs −82 dBm.
CS feasibility is gated by three hardware items with no evidence today: hop **phase** settling (the 35 µs external
allocation is a frequency number; the on-chip QVCO frequency loop is still open, analog/timing/README.md),
a phase-continuous TX↔RX direction change (warm-hop rejects "a direction change disguised as a hop"; the direction
path is not yet timed), and a TX→RX loopback for IQ and group-delay calibration. Fallback: `rf_lo_external_ref` /
B3 with a fast-hopping, phase-settling board synthesizer; `rf_tx_external_baseband` and `rf_bb_external_adc` keep
FPGA timestamping working if on-chip converters miss timing.

### 2.2 Receiver robustness in real-world environments (added 2026-11-10, RX robustness review)

Source analysis: `scratch/reviews/rx-robustness-review.md` (risks RXR-01..12). These rows fill gaps not covered by
RF-*-SENS/-BLOCK/-ACR, RF-RX-IIP3/-IRR and RF-LO-JIT; they do not restate those. Levels are at the RF_RX connector
of the carrier (after any board coex filter) unless stated. Standard values transcribed from memory are *(verify)*.

| ID | Requirement | Standard | First-die adaptation | Verification |
|---|---|---|---|---|
| RF-RX-MAXIN | Maximum input level with PER within spec: 802.11g/n/ax 2.4 GHz −20 dBm mean (OFDM) *(verify)*, 802.11b −10 dBm *(verify)*; BLE −10 dBm; 802.15.4 −20 dBm *(verify)* | 802.11 §17/§19/§27 "receiver maximum input level"; BT Core Vol 6 Part A §4.4; 802.15.4 §12 | Same, via the on-chip AGC states (LNA/TIA/PGA/bypass); no state may clip the TIA output or LNA for the stated level plus 10 dB OFDM crest | Two-tone/compression sim at each gain state; bench |
| RF-RX-AGC | Gain control | derived | Total RX gain range ≥ 70 dB with ≥ 30 dB **before the channel filter** in ≤ 6 dB steps and the PGA in ≤ 3 dB steps; each step settles (≤ 0.5 dB, ≤ 10 % of the DC-offset LSB) in ≤ 0.5 µs; FPGA decision → gain applied ≤ 1.0 µs through the in-band fast gain command (streaming-transport-v2 "Atomic RF gain metadata"); full AGC ≤ 4 µs (half of the Wi-Fi L-STF, BLE 1M/2M 8 µs preamble); gain held for the packet (RF-BLE-CODED-PKT); gain state time-tagged in the D2H stream | Sim (gain steps), RTL (opcode4), FPGA model |
| RF-RX-OVLD | Overload visibility | derived | Pre-filter overload detector at the TIA output (both paths): flag set within 0.2 µs of crossing ≈ 75 % of the TIA linear swing, readable in a status bit and the D2H stream; ADC clip counting in the FPGA | Sim + RTL |
| RF-RX-RECOV | Recovery after a pulsed in-band blocker (microwave oven 2.45 GHz ± 20 MHz, nearby Wi-Fi bursts) up to RF-RX-MAXIN + 10 dB | derived | Gain within 1 dB and DC offset within RF-RX-DCOC ≤ 2 µs after the blocker ends, at every gain state | Transient sim |
| RF-RX-DCOC | DC offset at the ADC | derived | Static residual ≤ 5 % of ADC full scale at **every PGA code used** (per-gain-code calibration table); signal-dependent (self-mixing) offset change ≤ 5 % FS at RF-RX-MAXIN; FPGA digital DC tracking after the ADC; narrowband modes (BLE/15.4/LoRa) may use low IF (LO offset 1–3 MHz) instead | Sim + bench cal |
| RF-RX-IIP2 | Second-order intercept | derived from RF-BLE-BLOCK OOB (−30 dBm) and AM cellular blockers | IIP2 ≥ +47 dBm at max gain (after calibration if any), or the protocol runs low IF so IM2 at DC falls outside the channel | Two-tone sim |
| RF-RX-FLICK | Noise at low IF | derived | Chain NF integrated over the protocol's channel at its IF (BLE 1M zero-IF 0–0.5 MHz or low-IF, 15.4 0–1 MHz) ≤ the 5–9 MHz NF + 3 dB; otherwise the FPGA recipe fixes a low IF | Transient-noise sim 10 kHz–10 MHz |
| RF-RX-LOPN | LO phase noise at the mixers (external synthesizer and any future on-chip LO) | derived from RF-BLE-BLOCK, RF-WIFI-ACR, OOB blocking | L(f) ≤ −95 dBc/Hz @ 1 MHz, ≤ −107 @ 3 MHz, ≤ −115 @ 20 MHz, ≤ −120 @ 40 MHz, ≤ −130 @ ≥ 100 MHz (≥ 6 dB under the reciprocal-mixing limits); integrated per RF-LO-JIT | Board synth datasheet + bench |
| RF-RX-FREF | Frequency reference and tracking | BLE ±50 ppm, 802.11 ±20/25 ppm, 802.15.4 ±40 ppm *(verify)* | LO and converter sample clock derived from one board reference (±10 ppm TCXO); FPGA CFO estimation range ≥ ±250 kHz and sample-clock offset tracking | Bench |
| RF-RX-LOLEAK | LO leakage at RF_RX | EN 300 328 receiver spurious ≤ −57 dBm (30 MHz–1 GHz), ≤ −47 dBm (1–12.75 GHz) *(verify)* | ≤ −57 dBm at the LO and 2·LO in RX state (keeps nearby receivers and the own DC offset quiet) | Sim + SA |
| RF-RX-SPUR | Self-generated spurs | derived (risk register SUB-03/SP-01, A5) | Any CW spur ≤ −100 dBm input-referred on a channel in use, with the clock plan of register-map.md "Macro clock plan" | Spur map + bench |
| RF-RX-COEX | Co-located radios (LTE/NR B40 2300–2400, B41/n41 2496–2690, B7 UL 2500–2570 MHz, B1/B3 UE TX, 5 GHz Wi-Fi) | product practice *(verify)* | With board requirement B34 fitted: desense ≤ 3 dB on channels ≥ 10 MHz from the band edge with +13 dBm (UE TX +23 dBm, 10 dB antenna isolation) at the antenna; without B34 the product declares no cellular coexistence | Bench |
| RF-RX-NFSYS | System NF at the antenna connector | derived from RF-WIFI-SENS | ≤ 8 dB including balun, match, T/R switch (B33) and coex filter (B34) at carrier placement P2 (10 mm), measured over the 5–9 MHz and protocol IF bands | Cascade + bench |
| RF-RX-ESD | Antenna-port robustness | IEC 61000-4-2 *(product)*; HBM per ESD-02 | Chip: RF_RX survives 2 kV HBM and +10 dBm CW (powered and unpowered) with no parametric shift; board: low-C TVS (B36) for ±8 kV contact at the antenna | Pulse/transient sim; bench |
| RF-RX-PSRR | RX with board supply noise | derived | Board ripple per B37 gives spurs ≤ RF-RX-SPUR and ≤ 0.5 dB desense; chip TIA+filter PSRR characterized 10 kHz–20 MHz | AC sim + bench |
| RF-COEX-PTA | Packet traffic arbitration with other radios in the product | 3-wire PTA practice *(verify)* | In the FPGA (no chip pin): REQUEST/PRIORITY/GRANT GPIOs; chip TX/RX state and schedule exposed so grant-to-mute ≤ 2 µs (RF unmute is FPGA-scheduled) | FPGA RTL + bench |

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
| WR-HL-LINECODE | **Host-link fit for line rates above 2.5 Gb/s** (added 2026-11-10). Per-direction dense payload capacity is 10 pins × 312.5 Mb/s × 59/64 = 2.88 Gb/s; the S1 rule (host word = line/8) needs 337.5 / 375 / 390.6 MHz at 2.7 / 3.0 / 3.125 Gb/s, above the 312.5 MHz pad budget (and bi_24t input f_DDR,max 193.2 MHz tt). Raw line bits therefore **do not fit** at 3.0 and 3.125 Gb/s (104 % / 109 % of capacity) and fit at 2.7 Gb/s only with a rate-independent 312.5 MHz host word clock (94 %). Requirement: (a) for > 2.5 Gb/s the host word clock is a fixed 312.5 MHz (not line-divided), with the existing per-frame payload counts absorbing the rate difference; (b) an optional 8b/10b line-code offload in the wired boundary (RX: comma align + 10b→8b + K flag = 9 bits/symbol; TX: inverse with running disparity) so the host carries 0.9 × line: SATA Gen2 2.70 (94 %), DP HBR 2.43 (84 %), 3.125 GBd 2.81 (98 %; with XAUI ‖I‖/‖A‖ or SATA ALIGN deletion and FPGA re-insertion ≤ 95 %). Fallback: `wire_board_phy_bypass` (FPGA GT carries the lane), `debug.host_link.rate` for reduced-rate test |
