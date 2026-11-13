# Performance review: programmable transceiver platform (GF180)

Reviewed 2026-11-09, branch `transceiver-risk-accepted-tapeout`, working tree with six agents editing in parallel. This review changed no project files and ran no simulations. The only calculations are the light ones shown in §3.

**Question:** if the design is finished as currently architected and planned, will it meet its performance requirements?

**Answer: no, not on the primary on-chip routes. The die is still a reasonable risk-accepted vehicle, because most gaps have an off-chip fallback.**

- **Wired payload: fails at every rate above about 1.07 Gb/s.** The cause is the digital macro's timing, not the analog blocks. On-chip paths reach about 1.25 Gb/s at most at tt (TX serializer, slicer, CDR). PCIe Gen1 (2.5 GT/s), DisplayPort RBR (1.62 Gb/s), SATA (1.5 Gb/s), HDMI 1080p and HD-SDI (1.485 Gb/s) have no qualified route, either on-chip or through the fallbacks as designed.
- **RF payload: works only in a reduced form.** It needs the board LO (B3), a board LNA (B5) for Wi-Fi MCS7 sensitivity, and a board PA or saturated mode for 0 dBm output. Linearity, EVM and spectral mask are unverified. 20 MHz Wi-Fi on the on-chip ADC is architecturally compromised at 20 MS/s: the adjacent channel aliases into the band. Wi-Fi depends on the external-ADC fallback.
- **IO:** the pad cells themselves are probably fine for a 156.25 MHz DDR host link. The core behind them closes at 65 MHz (tt), and the evidence for that is stale. The stress-safe clamp is a direct conflict with the 2 Vpp passive LO on `REF_IN`/`AUX_CLK` at the ff corner. It also loads 3.3 V-referenced TMDS and USB FS levels. Wired-pad capacitance makes return loss marginal at 1.25 GHz (6.6–7.6 dB) for ≥2.5 Gb/s.

Verdict legend: **meets** = current-source extracted evidence across the function window; **marginal** = meets nominally, misses at a corner, or margin under ~1 dB/10 %; **fails**; **unverified** = no evidence or evidence too weak or stale; **spec-missing** = no numeric requirement in the specs (a standard-derived value is used where noted, marked *std*).

---

## 0. Evidence freshness (applies to everything below)

Source hashes recorded in `analog/**/generated/*-evidence.json` were compared with the current working tree (light script; hashes resolved relative to each block directory).

| Evidence | State against current sources | Consequence |
|---|---|---|
| `evidence/digital-hardening-evidence.json` (run FREEZE1) | **18 of 26 hashed sources STALE** (pt_digital_macro, pt_host_link, regfile, SPI, stream/frame, SDC, hardening config…) | All digital timing, area and current numbers describe an older RTL. The file itself says it "must not be transferred to changed RTL". The regfile also needs re-hardening (usbhs bias binding). |
| `analog/wired_rx/generated/slicer-evidence.json` | **slicer.spice, slicer.ext.spice, slicer.gds STALE** (slicer is being edited now) | Slicer rate and offset numbers are not current. |
| `analog/timing/generated/pll_ring-evidence.json` | **pll_ring.spice STALE**, plus run_timing.py | Lock range and phase error must be re-run. The CDR evidence depends on pll_ring r6a. |
| `analog/converters/generated/dac_i/dac_q-evidence.json` | circuits.py, convkit.py, flow.py, benches.py, ADC RTL STALE | DAC numbers predate generator changes. |
| `analog/rf_rx/*`, `analog/wired_rx/{ctle,termination,detect,…}`, `analog/wired_tx/*`, `analog/timing/*` other | Only scripts stale (netlists.py, sims.py, run_timing.py, sim_wiredtx.py) | Probably still valid, but the generated netlists must be re-confirmed. |
| `analog/rf_tx/*`, `adc_i/q`, `refbuf`, `lo_ext` | Netlist hashes match (adc_i: only benches.py stale) | Usable. |

**Checks that cannot fail, or whose criteria were moved after the result was known**, so they give no assurance about performance:
- `aosc`: every corner has `"pass": true`, including ss corners with `in_target_window: false` (35–37 MHz vs 40–60 MHz).
- ADC/DAC `clean`: the criterion was relaxed to "within 32 codes/LSB of a fit" after the first runs. The ADC fallback loading limit was moved from 100 fF to 0.5 pF after measuring about 110 fF.
- Slicer: the gating rate is only 1 Gb/s over short windows (no BER). The wired TX and fallback receiver use 41–61-bit windows.
- CDR: the cell-level "12/12 corners pass" sits alongside closed-loop tracking failures.
- `lo_ext` "12/12 pass" holds only at 4 Vpp open-circuit drive. 2 Vpp and 1 Vpp fail, and the bench uses an ideal "+1 pF pad" rather than the protected `refpad`.
- The ADC FFT uses 32 points at a single tone, 1.875 MHz, at tt only.

**Spec inconsistencies found:**
- **Current totals disagree:** `tapeout-readiness.json:current_envelope_ma` (RF external 236.27, wired 260.96 mA) vs `power-partition.md` (224.09, 244.82 mA).
- **PGA range:** `analog-architecture.json` gives −6…42 dB; the block is designed for 0…24 dB.
- **wirepll VCO range:** the architecture still says 1–2.5 GHz; the plan uses a 480–810 MHz ring with 1/2/4 bits per cycle.
- **CDR line rate:** 480 M–2.5 Gb/s in the architecture, with no BER or jitter-tolerance numbers anywhere.
- **RX filter codes:** the stretch finding says filter codes top out at 9.53 MHz; the measured corner is 15.2 MHz.

---

## 1. Requirements table with evidence and verdicts

Sources are abbreviated as follows:
- **AA** = `spec/analog-architecture.json`
- **TR** = `spec/tapeout-readiness.json`
- **PP** = `docs/roadmap/programmable-transceiver-pin-plan.md`
- **ST** = `spec/streaming-transport-v2.md`
- **BR** = `spec/board-requirements.md`
- **DH** = `evidence/digital-hardening-evidence.json`

Sim types: **X** = extracted, **S** = schematic, **B** = behavioral or RTL, **A** = analytic. Corner coverage is listed as "12/13 env" = tt/ss/ff × 22/32 °C × 3.15/3.35 V (+ nominal).

### 1a. Digital and host transport

| Req | Required (source) | Best evidence | Type / corners | Verdict |
|---|---|---|---|---|
| Host word rate | 312.5 Mword/s per direction (156.25 MHz DDR, 10 bit) (AA digital, ST) | hword fmax 65.3 MHz tt vs 156.25 target (DH) | X-STA routed, tt only in envelope; **stale** | **fails** (2.4×) |
| Wired 20-bit boundary | 125 MHz (2.5 Gb/s) (README) | wtx 53.5 / wrx 63.8 MHz tt (DH) | X-STA, stale | **fails**: caps the wired lane at ≈1.07 Gb/s |
| H2D clock | 78.12 MHz (DH SDC) | 72.3 MHz tt | X-STA, stale | **fails** (marginal) |
| RF sample clocks | 50 MHz rftx/rfrx (SDC) | rftx 40.9 MHz tt; rfrx +1.5 ns slack | X-STA, stale | **marginal**: 20 MS/s fits, 40 MS/s does not |
| Ref / clocktree / freq counters | 100 / 156.25 MHz | 62.2 / 84.0 / 81.7 MHz tt | X-STA, stale | **fails** |
| SPI | ≤1 MHz start, 10 MHz bench (PP); 20 MHz SDC | 18.6 MHz tt | X-STA | **meets** the spec, misses the SDC target |
| Payload throughput | 2.88 Gb/s at the top profile (ST) | 1.20 Gb/s payload at 65.3 MHz (A) | A on DH | **fails** for wired 2.5 GT/s; meets RF 20 MS/s × 2 × 12 b = 0.48 Gb/s |
| Control/response latency | 400 ns reply gate; model 342.25 ns (ST:190) | Model at full clock only | B | **unverified**: about 2.4× slower at achieved clocks, so it breaks the 400 ns gate and USB HS turnaround |
| Digital + memory area | 2.5 mm² (1.65 + 0.85) (AA) | 3.24 mm² (1800², 1580/1650 failed placement) (DH) | X | **fails** (+0.74 mm²) |
| Digital current | 19.5–36.5 mA allocation (AA) | none (no power analysis) | — | **unverified** |
| Max slew/cap DRVs | 0 | hundreds at tt, ~1.7k at ss (DH) | X | **fails** |
| Formal safe defaults | pass | regfile formal not re-run on final map (DH) | — | **unverified** |

### 1b. RF receive

| Req | Required | Best evidence | Type / corners | Verdict |
|---|---|---|---|---|
| RF band | 2.400–2.500 GHz (clock-feasibility) | Mixers and LNA at 2.4/2.45 GHz | X tt | **meets** (band edges not swept) |
| LNA gain | 20 dB code 3 (AA) | −11.0 dB into 50 Ω/leg mixer model; chain conversion gain 26.3–28.9 dB with ideal L-match (lna-evidence) | X, 12 env (gain), tt (chain) | Block **fails**; chain adequate |
| RX NF | 6 dB (AA lna) | Chain 12.1 dB (5–9 MHz), 14.1 dB (2–9 MHz); 2.8 dB with B5 board LNA; bypass 22.2 dB | X tt, ideal lossless match; LNA-only corners 11.3–12.5 dB | **fails** on chip; **meets** with B5 |
| IIP3 / P1dB / blockers | IIP3 0 dBm (AA); 802.11 ACR/AACR, BT blocking (*std*) | "IIP3/P1dB not simulated" | — | **unverified** |
| S11 / input match | 100 Ω diff, board matching allowed | Zin 4.3 − j161 Ω; real board network not simulated | X tt | **unverified** (board loss excluded) |
| Mixer gain / offset | 0 dB voltage arch; residual <10 mV | 19.3 dB; offset −54 mV raw → −3.4 mV after FPGA cal | X tt, cal per point | **meets** |
| PGA range | −6…42 dB in 3 dB steps (AA) | −0.06…23.0 dB (bbfilter-evidence) | X tt | **fails** (−19 dB at top; see §3.1) |
| Channel filter | ≥10 MHz widest, ≥100 kHz narrowest, ≤1 dB ripple | 15.2 MHz tt (11.3–21.2 env), 776 kHz narrowest, peaking 1.7 dB tt / 3.7 dB ff | X 12 env | Ripple **fails**; narrowest **fails** (LoRa 203/406 kHz under-filtered on chip, FPGA must filter) |
| ADC rate | 40 MS/s (AA); ≥20 MS/s for 20 MHz Wi-Fi | 20 MS/s tt/ff; 16 MS/s ss/32 °C/3.15 V; 20 MS/s fails at ss (codes 0/294) | X 12 env | **fails** 40; **marginal** 20 (fails ss) |
| ADC ENOB | 8 (AA) | 8.04 ENOB, SNDR 50.2, SFDR 53.2 dB; 32-pt FFT, fin 1.875 MHz, tt only | X tt | **marginal / weakly verified** (no near-Nyquist tone, no corners, refbuf ripple 27 mVpp not in loop) |
| ADC current / area | 8 mA, 179k µm² (AA) (350k used in evidence) | 2.87 mA; 259k µm² | X | Current **meets**; area over the AA ceiling (179k), under the evidence ceiling (350k) → **spec conflict** |
| VREF | 1.0 V ±2 % | 0.999 V; 0.55 mA; 27 mVpp ripple at 1 mA pulses | X 12 env | **meets** (ripple has no spec) |
| BB tap fallback | ≥20 MHz into 10 pF | 76.5 MHz, −1.37 dB, CM 0.82 V | X tt | **meets** (external ADC must accept 0.8 V CM) |
| Image rejection / IQ balance | spec-missing (`rf-quadrature-budget.md` explicitly "not a requirement") | RX I/Q gain 26.27/26.85 dB (0.6 dB → ~29 dB IRR uncorrected) | X tt | **spec-missing**; FPGA correction assumed |
| Sensitivity (Wi-Fi MCS0 −82 dBm; MCS7 −64; BLE −70; 15.4 −85) *std* | — | §3.1 cascade | A | MCS0 **marginal/fails** without B5; MCS7 **fails** without B5; BLE, BT, 15.4 **meet** |
| ACR (Wi-Fi MCS0 +16 dB) *std* | — | 20 MS/s plus a 15 MHz 5th-order filter → adjacent channel aliases with 3–20 dB attenuation | A | **fails at 20 MS/s** (architectural; see §4) |

### 1c. RF transmit and LO

| Req | Required | Best evidence | Type / corners | Verdict |
|---|---|---|---|---|
| Output power | 0 dBm mean (AA rfdriver) | Linear SSB −5.6 tt (envelope −4.2…−9.9); saturated −0.13 tt (−0.4…−3.1 env); balun loss excluded | X 12 env, ideal L-match Q=30 | Linear **fails**; saturated **marginal** |
| Linearity / EVM | Wi-Fi HE MCS7 −27 dB, MCS0 −5 dB; BT EDR DPSK (*std*) | none | — | **unverified**; saturated mode unusable for OFDM and EDR |
| Spectral mask / ACLR / harmonics | 802.11 mask, BT/15.4 emissions (*std*) | none | — | **unverified** |
| LO leakage / image | spec-missing | LO 44.6 dBc (linear, ideal LO), 38 dBc saturated; IRR 61.6 dB ideal LO, 33.1 dB saturated | X tt | **spec-missing**; ideal-LO only |
| Mute isolation | spec-missing | 22–24 dB | X tt | **spec-missing** (low for TDD/coexistence) |
| Driver current | 28.92 mA (AA) | 25.3–28.9 mA | X 12 env | **meets** (at limit) |
| DAC | ±1 V, 8-bit class, CM 1.65 V, 40 MS/s | ±0.996 V (env 0.82–1.15), ~10 LSB static error, CM 1.43 V, 80 MS/s static codes | X 12 env, **stale sources** | **marginal**: no SFDR or glitch data; CM mismatch |
| RF LO source | Autonomous LC VCO 2.4–2.5 GHz, phase noise per EVM budget (≤~1 ps rms at −30 dB EVM, clock-feasibility) | LC VCO produces no frequency (lcvco/results.json); polyphase fails extracted; **external passive LO only** | X | Autonomous **fails** → fallback `rf_lo_external_ref` |
| External LO drive | ~2 Vpp per leg at the pad, sine (BR B3) | Passes only at 4 Vpp open-circuit behind 50 Ω (+1 pF ideal pad); 2/1 Vpp and square fail | X 12 env | **marginal** (needs about +16 dBm per leg from the board), not checked with the stress-safe refpad (§3.6) |
| LO phase noise / jitter, I/Q accuracy | ≤0.3–0.5 ps rms per on-chip slot (clock-feasibility) | None for lo_ext additive noise; I and Q enter on different pad pairs (`inputs[1:0]`, `inputs[3:2]`) | — | **unverified** |

### 1d. Wired TX / RX / CDR / USB / video

| Req | Required | Best evidence | Type / corners | Verdict |
|---|---|---|---|---|
| Line rates | 0.48–2.5 Gb/s: 1.25 (1000BASE-X/SGMII), 1.485 (SDI, HDMI 1080p), 1.5 (SATA), 1.62 (DP), 2.5 (PCIe), 0.7425 (HDMI 720p), 0.48 (USB HS) (PP) | **TX:** 0.96 Gb/s 11/12 env (ss/22/3.15 aborted); 1.25 tt/ff only; quarter rate 1.92/2.5/2.97 and full 0.81 **fail** (wiredtx, generic-layout routing ~3× slow) | X | ≤0.96 **meets**; 1.25 **marginal**; ≥1.5 **fails** |
| | | **Slicer:** ≥2.97 tt27/ff, 2.5 other tt, 2.0 ss, 1.5 ss/22/3.15; gating only 1 Gb/s | X 12 env, **stale** | 2.5 Gb/s **fails at ss** |
| | | **CDR:** tracking fails extracted (quarter 560/3588 errors, half 104/1768); hand-over drift 5883 ppm; capture fails >480 MHz | X | **fails** at all target rates above 480 Mb/s |
| TX swing | PCIe 800–1200 mVppd; SATA 400–600; 1000BASE-X ≥~500 (*std*); spec-missing on chip | 578.5 mVppd at 1.25 Gb/s tt; ss/3.15 V swing 0.50/0.81 V (pads README) | X tt (eye), corner single point | PCIe **fails**; SATA/1000BASE-X **marginal** |
| TX jitter | PCIe TJ ≤0.25 UI; 1000BASE-X ≈0.24 UI; TMDS ≈0.25 UI (*std*) | Pre-driver DJ 305 ps pp at 1.25 Gb/s (0.38 UI); pad eye width 600.8/800 ps | X, 60 bits | **fails / marginal** |
| TMDS | 742.5 Mb/s and 1.485 Gb/s, 50 Ω to 3.3 V (BR B9) | 1.25 Gb/s eye 955 mV / 663 ps; 2.97 fails; **1.485 not simulated**; ff clamp leakage at 3.3 V not in the bench | X tt | 720p **meets** (inferred); 1080p **unverified** |
| CTLE | ~6 dB peaking, DC gain 0 dB | 7.3 dB tt, 1.6–8.1 dB across corners; DC −0.86 dB | X 12 env, scripts stale | **marginal** (5× corner spread) |
| Slicer offset | trimmed residual <20 mV | −27 mV nominal, −31…−21 mV corners | X 12 env, stale | **fails** |
| Slicer sensitivity | 60 mVppd at 1 Gb/s (gate) | 0 errors over a short window, 12 corners | X | **meets** the stated gate; no BER |
| BER / JTOL | 1e-12 BER, PCIe/SATA/DP JTOL masks, SSC −5000 ppm (*std*); **spec-missing** in repo | RTL loop locks −6000…+1000 ppm in model only | B | **spec-missing / unverified** |
| Pad loading | ≤2.7 pF wired (pads README) | RX/USB 2.34–2.35 pF; **TX 2.706/2.713 pF** | X | TX **fails** (marginal) |
| USB HS | 480 Mb/s; 360–440 mV; squelch 100–150; disconnect 525–625 (*std*) | Amplitude 360–440 reachable, ss/3.15 V 372–379 at full scale (per-board cal B11); squelch 125.5; disconnect 536–546; slicer 0 errors at 480 Mb/s | X 13 env; usbhs/usbdrive tests all **open** | **marginal** (no eye template, no chirp, no turnaround) |
| USB FS / LS | FS 4–20 ns edges; LS 75–300 ns (*std*) | FS 5.8–11 ns; LS 33–67 ns | X | FS **meets** (high level loaded by ~5–6 mA at ff); LS **fails** → B8 |
| Receiver detect / idle / OOB (PCIe, SATA) | spec-missing numerically | detect block clean; no OOB burst timing evidence | — | **unverified** |

### 1e. Timing, IO, power, ESD

| Req | Required | Best evidence | Type / corners | Verdict |
|---|---|---|---|---|
| Ring PLL | 480–810 MHz lock; 1/2/4 bits per cycle | Locks 480/625/810 MHz and host_follow 125/156.25; open loop 0.12–1.09 GHz; phase error 9–10.8° (r5 ≤5.5°); HOLD fails +1545 ppm | X, **pll_ring.spice stale** | **meets** range; **unverified** jitter |
| PLL jitter / phase noise | spec-missing for wired (timing README: "jitter/phase noise and reference spurs are not covered") | none | — | **spec-missing / unverified** |
| Ref receiver | ≤~0.81 GHz ring-rate clocks | 1 GHz at 500 mVpp diff / 600 mV SE; 200 mVpp fails; corners not re-run | X tt | **marginal** |
| aosc | 40–60 MHz | 44.9 tt; ss 35.4–37.1 | X 12 env | **fails at ss** (flagged "pass") |
| Host pad timing | 312.5 Mb/s per pin, 3.2 ns UI | bi_24t DDR f_max 222.8 MHz tt / 177.9 ss_125C (Liberty screen, 6 pF, assumed 1 ns FPGA window, 0.4 ns skew) | Liberty table, no board SI | **marginal** (pads OK; FPGA host family not selected; ECP5 rejected; SSO/ground bounce unverified) |
| Host-pad backfeed | High-Z unpowered | 6.8–82 mA per pin into an unpowered ring → B6 bus switch | X | **meets only with B6** |
| Supply current | 240 mA RF / 292 mA wired+USB envelopes; PDN DC budget computed at 250 mA (tapeout-plan) | Allocations 236–261 mA (TR) or 224–245 mA (power-partition); autonomous RF over by 4.55–13 mA; hostio 110 mA and digital unmeasured | A (allocations) | **marginal / unverified**; the wired allocation exceeds the 250 mA used for the drop budget |
| IR drop | ≤125 mV total inside the 3.15–3.35 V window | Island switch full-RC ≤19.9 mV; wired margin 0.13 mV needs ≥4 edge-bar straps | X cell-scope | **marginal** |
| Thermal | Tj 27 ±5 °C | ~0.8–0.86 W at full wired load; COB θJA not characterized | — | **unverified** (board heater/cooler in B2) |
| ESD | 2 kV HBM / 500 V CDM (pads README "not established") | ±100 mA / 2 ns pulse peak 5.895 V vs 6.0 V gate screen; margin 0.105 V at ss/0 °C | X stress screen | **marginal**; HBM/CDM **spec-missing** |
| Clamp leakage (stress-safe) | spec-missing | At 3.3 V: 18 µA ss / 0.44 mA tt / 5.1 mA ff; 6.3 mA at 3.35 V; onset 2.1 V (ff) | X | Affects TMDS, USB FS, REF/LO (§3.6) |
| Core area | 12.92 mm² ceiling | Digital +0.74 mm² over; no floorplan | — | **unverified / at risk** |

### 1f. Per-interface roll-up (17 capability ids, `mathematical-closure.json`)

| Interface | Line/sample rate | Primary on-chip route | Fallback that covers it | Net verdict |
|---|---|---|---|---|
| PCIe Gen1 x1 | 2.5 GT/s | Fails (TX 4:1 mux, ss slicer, CDR, digital 125 MHz, swing 578 mV < 800) | None: WTX_EXT tops out at 1.6 Gb/s (extracted combined route not simulated, and 2 errors at 1.6 Gb/s in the wired_tx table); D2H cannot carry oversampled 2.5 Gb/s | **fails** |
| 1000BASE-X / SGMII | 1.25 GBd | TX 1.25 tt/ff only; CDR fails; digital caps at 1.07 Gb/s | WTX_EXT TX (≤1.6 Gb/s, needs 1.25 Gb/s FPGA serial out); RX needs an external clock aligned to data | **fails** (on-chip) / **unverified** (fallback) |
| SATA Gen1 | 1.5 Gb/s | Fails (TX, CDR, digital) | TX via WTX_EXT marginal; RX none | **fails** |
| DisplayPort RBR | 1.62 Gb/s | Fails | WTX_EXT 1.6 < 1.62 | **fails** |
| DVI / HDMI 720p | 742.5 Mb/s | TMDS 1.25 Gb/s eye OK (TX); sink RX needs CDR at 742.5 Mb/s, which fails | TX OK; RX via WCLK_IN with the HDMI pixel clock ×10 from an external PLL (a forwarded clock exists in HDMI) | TX **meets**; RX **unverified** |
| HDMI 1080p | 1.485 Gb/s | TMDS untested at 1.485; digital caps at 1.07 | WTX_EXT | **fails / unverified** |
| HD-SDI | 1.485 Gb/s | As above, plus pathological-pattern CDR | WTX_EXT TX; RX none | **fails** |
| USB 2.0 HS/FS/LS | 480 / 12 / 1.5 Mb/s | HS marginal (cal per board), FS meets, LS fails; turnaround unverified | B8 board PHY (`usb_board_phy`) | **marginal**; full coverage only with a board PHY |
| Wi-Fi HE20 | 20 MHz complex, 20–40 MS/s | 20 MS/s ADC (fails ss and ACR), PGA short, NF 12 dB, TX EVM unverified, LO external only | BB_I/Q external ADC/DAC, board LNA/PA, external LO | **fails on chip; plausible with fallbacks** (MCS0 first) |
| BLE 1M/2M/coded | ~1–2 MHz | Constant envelope; saturated TX −0.1…−3 dBm OK; NF adequate | — | **likely meets** (unverified: hop settling, LO from board) |
| BT BR/EDR | 1 MHz, DPSK | EDR needs linear TX (−5.6 dBm linear); EVM/DEVM unverified | External PA | **unverified** |
| 802.15.4 | 2 MHz O-QPSK | ≥−3 dBm needed; saturated −0.4…−3.1 → marginal; RX OK | External PA | **marginal** |
| LoRa 2.4 | 203–1625 kHz | Narrowest filter 776 kHz: FPGA must filter (ADC dynamic range under blockers unverified) | — | **marginal / unverified** |
| Custom GFSK / SDR | — | As BLE | — | **likely meets** |
| Lower-frequency RF (stretch) | 0.6 / 1.2 GHz | Ring PH0/PH2; TX +1.4…+3.1 dBm at LO/2, LO/4 unmatched | External I/Q | non-gating, recorded |
| External frequency conversion (stretch) | — | BB_I/Q pads | — | non-gating |
| (40 MHz, 5 Gb/s stretches) | — | ADC 20 MS/s; ring 1.09 GHz max; slicer fails 4–5 Gb/s | — | **fail** (non-gating) |

---

## 2. Digital throughput vs pad IO timing (312.5 MHz host boundary)

- **Pads:** the Liberty screen gives `bi_24t` fast-slew DDR at 222.8 MHz (tt) and 177.9 MHz (ss_125C) against the 156.25 MHz forwarded clock. The tables say the pads are not the bottleneck. However:
  - the load convention is unresolved (`fpga-host-screen.md`);
  - there is no board or FPGA receive-window analysis;
  - SSO across 11 D2H outputs is unverified;
  - D2H[0] sits on `clk_pad` and needs an input-to-`bi_24t` cell swap;
  - the host family is not chosen (ECP5 LVCMOS33 is rejected at 156.25 MHz).
- **Core:** the routed macro closes the word clock at 65.3 MHz (tt) and 30.5 MHz (ss_125C). The narrow-envelope Liberty does not exist, so tt_025C_3v30 is the only in-window corner, and there it fails 2.4×. The 20-bit wired boundary closes at 53.5–63.8 MHz, i.e. **1.07–1.28 Gb/s line rate**.
- **End to end:**
  - The host link at the achieved clock carries ≈1.2 Gb/s payload. That is enough for RF at 20 MS/s × 12 bit × I/Q, but **not for raw 1.25 GBd wired traffic** (1.25 Gb/s needed vs 1.20 available).
  - Command and response latency scales by the same ~2.4×. The 342 ns model bound with 57.75 ns margin against 400 ns does not survive, which threatens USB HS bus turnaround (192 bit times ≈ 400 ns) and PCIe and Wi-Fi response deadlines.
- **Fallback:** the SDR and reduced-rate host modes, and SPI capture/playback, keep the chip measurable. They do not deliver line-rate wired payload.
- **Design change needed:** pipeline the FIFO read muxes, the stream framer and the regfile commit path named in DH `open_risks`, and floorplan the host-link logic next to the south and north host pads (the die is 1.8 mm). Then re-harden on the current RTL and add a custom Liberty at 22/32 °C × 3.15/3.35 V (or derate tt) so timing is signed off inside the envelope.

## 3. End-to-end budgets nobody owns

### 3.1 RF RX cascade to the ADC (Wi-Fi HE20, the hardest case)
Inputs: extracted chain NF 12.1 dB (ideal lossless match, excludes the ADC), chain gain 26.3 dB (I, matched), PGA max 23 dB, ADC 8 ENOB over ±0.87 V (≈1.96 mV rms noise). The implementation margin of 2 dB is an assumption.

| Case | Thermal noise at ADC | ADC NF penalty | MCS0 sensitivity (req −82) | MCS7 (req −64) |
|---|---|---|---|---|
| On-chip LNA, PGA 23 dB (as built) | 2.3 mV rms | **+2.4 dB** | ≈ −79.7 dBm → **fails by ~2 dB** | ≈ −57.7 → **fails by ~6 dB** |
| On-chip LNA, PGA 42 dB (as specified) | 20 mV | 0 dB | −82.1 → marginal | −60.1 → fails |
| Board LNA B5 (+15 dB / 1.5 dB) | 4.4 mV | +0.8 dB | ≈ −90.6 → meets | ≈ −68.6 → meets |

BLE (−70 dBm required), BT BR and 802.15.4 (−85) have 10–18 dB margin even without B5. Missing from the budget: real match and balun loss (+0.5–1.5 dB NF), IIP3 and blocker desensitization, LO phase noise reciprocal mixing, and RX I/Q imbalance (~29 dB IRR uncorrected, enough for MCS7 after FPGA correction). **Conclusion:** Wi-Fi beyond MCS0 depends on board requirement B5. The PGA shortfall (−19 dB) adds a 2.4 dB ADC-noise penalty that the block-level NF (12.1 dB) hides.

### 3.2 Sampling rate vs channel filter (aliasing)
At 20 MS/s complex, a 20 MHz-offset adjacent channel folds directly onto the wanted band. The 5th-order filter at its 15.2 MHz corner attenuates 12.2 dB at 20 MHz and 2.7 dB at 15 MHz; even assuming Butterworth shape the folded adjacent channel only gets ~3–20 dB rejection. 802.11 ACR for MCS0 is +16 dB, so **the on-chip ADC at 20 MS/s cannot meet adjacent-channel rejection**. 40 MS/s, as architected, fixes it; the ADC reached only 20 MS/s. Cover with `rf_bb_external_adc` (BB tap bandwidth 76.5 MHz is enough).

### 3.3 TX: DAC to pad to mask
- DAC ±1 V into the TX filter (shared bbfilter, 15.2 MHz corner).
- Upmixer gm 1.51 mS (linear).
- Driver gain 1.68 V/V against a 5.36 target: **fails by 3.2×**. This is why linear output is −5.6 dBm.
- For OFDM with a PAPR of ~9–10 dB and P1dB near −0.1 dBm (saturated), the mean output at EVM ≤ −27 dB is likely ≈ −10…−12 dBm (estimate). EVM, ACLR, mask and harmonics are **not simulated**, balun loss is excluded, and LO and image figures assume an ideal LO.
- **Conclusion:** the 0 dBm mean target needs an external PA (`rf_tx_low_power_external_pa` or a board PA after the driver). This is acceptable under the external-component allowance, but nothing yet checks a TX EVM budget.

### 3.4 Clock and jitter: reference → PLL → sampling clocks
- **RF:** the LO is the board source plus `lo_ext` switches. The budget in `clock-feasibility-envelope.md` (≤1.05 ps total at −30 dB EVM, 0.3–0.5 ps per on-chip slot) has **no on-chip number** (no `lo_ext` additive jitter, no I/Q path skew between pad pairs `inputs[1:0]` and `[3:2]`, where 1° = 1.16 ps).
- **Wired:**
  - The ring PLL has no jitter evidence at all. Port phase error is 9–10.8°, and HOLD fails.
  - The serializer adds 305 ps pp DJ at 1.25 Gb/s, about 0.38 UI before the pad, which already exceeds typical TX TJ budgets (0.24–0.25 UI).
  - The CDR loop bandwidth is 5 MHz (model) with no JTOL mask defined.
- **ADC aperture:** 20 MS/s at 8 ENOB tolerates ~60 ps rms, which is not a concern.
- **Conclusion:** wired jitter is the largest unquantified risk, after rate. RF LO quality is entirely a board obligation and unbudgeted on die.

### 3.5 Wired link: TX → channel → RX → CDR
- **TX:** 578 mVppd at tt, 0.50/0.81 V at ss/3.15 V; pad eye width 600.8 ps at 1.25 Gb/s.
- **Channel:** none modeled.
- **RX:** pad capacitance 2.35 pF RX and 2.71 pF TX. **Return loss** at Nyquist (A, 50 Ω ∥ C): 11.8–13 dB at 625 MHz (1.25 Gb/s, meets the 10 dB class), 10.4–11.5 dB at 750 MHz (1.5 Gb/s, marginal), **6.6–7.6 dB at 1.25 GHz** (2.5 Gb/s, fails the ~10 dB class). Board compensation is possible, but there is no T-coil on die.
- **Equalization and slicing:** CTLE peaking ranges 1.6–8.1 dB. Slicer offset after trim is −27 mV against a 60 mVppd sensitivity gate. That offset consumes most of the gate on its own (see §1d).
- **Recovery:** the CDR fails.
- **Conclusion:** there is no closed wired-link budget at any rate. 1.25 Gb/s TX into a short channel with an external-clock RX is the only credible near-term configuration.

### 3.6 IO: stress-safe clamp versus signal swing
The stress-safe clamp starts conducting at 2.1 V (ff) to 3.2 V (ss). It draws 0.44 mA (tt) to 5.1 mA (ff) at 3.3 V.
- **REF_IN / AUX_CLK (the only RF LO):** board requirement B3 asks for ~2 Vpp per leg at the pad. The pads README itself says "single-ended peaks near 2.65 V compressed at ff; source ≤0.55 V peak". The `lo_ext` pass uses an ideal +1 pF pad, not the protected refpad, and passes only at 4 Vpp open-circuit. **The qualified RF LO route and the qualified pad protection have never been simulated together, and their own documents conflict.** At ff the LO may be clipped and the mixers under-driven. This is the highest-consequence IO item, because the RF chain has no other LO.
- **TMDS (50 Ω pull-ups to 3.3 V):** the pad idles at 3.3 V, where the ff clamp sinks 5.1 mA per leg. That shifts levels (~0.25 V) and adds current. The TMDS bench did not include it.
- **USB FS:** the high level is loaded by ~5–6 mA at ff (recorded; external PHY fallback).
- **Wired TX:** 3.3 V-referenced high levels droop ~0.3 V at ff (recorded; AC-couple).
- **RF RX/TX:** unaffected below ~2.1 V. The saturated driver peaks are clipped at ff, which may be part of the −3.1 dBm envelope low.

### 3.7 Power and thermal vs supply limits
- **Mode totals:** 224–261 mA by allocation, and the two spec files disagree.
- **DC drop budget:** the tapeout plan computes it at 250 mA, and the wired allocation (261 mA) exceeds that.
- **Unmeasured:** hostio is 110 mA by allocation only, and the digital current is unmeasured. A 2.4× clock shortfall implies the RTL must grow (pipelining), which raises current.
- **Wired island margin:** 0.13 mV against a strap requirement (≥4 edge bars) that is still only a top-assembly obligation.
- **Thermal:** about 0.8–0.86 W at 27 ±5 °C junction needs an active board thermal solution. No COB θJA figure exists, and mode-switch self-heating is unmodeled.
- **Verdict:** **marginal / unverified.**

## 4. Requirements the architecture cannot meet even if every block closes

| Requirement | Why the architecture caps it | Fallback that covers it |
|---|---|---|
| PCIe Gen1 (2.5 GT/s) | The only non-CDR RX fallbacks are an external clock with raw D2H, or FPGA oversampling. D2H tops out at 2.88 Gb/s even at full digital clock, so 2× oversampling of 2.5 Gb/s (5 Gb/s) cannot fit. The TX fallback (WTX_EXT) is limited to ≤1.6 Gb/s by the `diff_clk_rx` design. Pad return loss is ~7 dB at 1.25 GHz. | **None on die.** Only an off-die retimer or PHY, which the plan does not name. Add a named board route or accept PCIe as unsupported on die 1. |
| SATA Gen1, DP RBR, HD-SDI, HDMI 1080p (1.485–1.62 Gb/s) RX | Same CDR fallback limit: `wire_cdr_external_clock` needs a clock already phase-aligned to the data, i.e. a board CDR. `wire_cdr_fpga_oversample` is explicitly low-rate only. | Partial: a board CDR or retimer feeding WCLK_IN. Not named in BR. |
| Wi-Fi 20 MHz ACR on the on-chip ADC | Delivered 20 MS/s with a 15 MHz filter; adjacent channel aliases (§3.2). | `rf_bb_external_adc` (BB_I/Q). Covered. |
| Wi-Fi MCS7 sensitivity on chip | NF 12.1 dB plus 2.4 dB ADC penalty with PGA ≤23 dB. | B5 board LNA. Covered. |
| 0 dBm mean OFDM TX | Driver gain is 3.2× short; P1dB ≈ 0 dBm leaves no PAPR headroom. | `rf_tx_low_power_external_pa` / board PA. Covered. |
| Autonomous RF LO | No inductor model or EM; the VCO bench produces no frequency. | `rf_lo_external_ref`. Covered, **subject to the §3.6 clamp conflict**. |
| USB LS | Pad has no slew control and no area left. | B8 board PHY. Covered. |
| 40 MS/s / 40 MHz channels, 5 Gb/s | Non-gating stretches | n/a |
| Full-rate host link (312.5 Mword/s) | Not architectural: an RTL pipelining or floorplan problem. | SDR / reduced-rate modes keep the bench working, not line-rate payload. |

---

## 5. Prioritized gaps (what to do)

1. **Digital timing re-closure on current RTL** (blocks every wired rate above ~1.07 Gb/s, the host payload and response deadlines). Pipeline the FIFO read muxes, the stream framer and the regfile commit path. Floorplan the host link at the pad edge. Re-harden from the current sources, because DH is 18/26 stale. Produce envelope-specific STA (custom Liberty or derated tt). Re-establish digital and memory area against 2.5 mm² or formally move the reserve. Run power analysis to replace the 19.5–36.5 mA and 110 mA allocations.
2. **Co-simulate `lo_ext` with the protected `refpad`/`AUX_CLK` pad at ff/ss × 22/32 °C × 3.15/3.35 V** at the board-specified drive. Either derate B3 (and the evidence) or move the LO pads to a protection variant without the shunt. This is the only RF LO.
3. **Wired RX recovery at ≥1.25 Gb/s.** Either close the CDR HOLD and hand-over and the 4-edge PD, or name a board CDR or retimer route into WCLK_IN in `board-requirements.md` and `tapeout-readiness.json`. Without one of these, PCIe, SATA, DP, SDI and HDMI-sink have no route. Define BER and JTOL and SSC acceptance numbers (spec-missing today).
4. **Wired TX 4:1 mux and retiming compact-cell port.** Today 1.92–2.97 Gb/s fail. Also: the ss/22/3.15 abort, a swing of ≥800 mVppd for PCIe or an explicit de-scope of PCIe swing, serializer DJ (305 ps pp), the TX pad at 2.71 pF over 2.7, and simulation of the combined extracted WTX_EXT route (the readiness entry claims 0.5–1.6 Gb/s, but the wired_tx table shows 2 errors at 1.6 Gb/s).
5. **RF linearity and modulation evidence:** LNA and chain IIP3/P1dB and blocker desensitization; TX EVM, ACLR and mask in linear and saturated modes with real balun loss; LO additive jitter and I/Q skew from separate pad pairs.
6. **Fix the RX gain plan:** either restore the PGA to the specified 42 dB or update AA and put B5 into the Wi-Fi recipe; fix filter ripple (1.7/3.7 dB vs 1 dB).
7. **ADC:** a proper coherent FFT (≥1024 points, near-Nyquist tone, envelope corners, refbuf in the loop); fix the ss failure at 20 MS/s or document that external ADC is the Wi-Fi route at ss; restore the original clean criteria instead of the relaxed 32-LSB ones.
8. **Power:** reconcile `current_envelope_ma` against `power-partition.md`; redo the PDN DC drop at the worst mode (261 mA plus measured digital and hostio current); add a COB thermal estimate.
9. **Host IO:** select the FPGA family and bank; do board SI and the receive window at 156.25 MHz DDR; SSO for 11 simultaneous D2H outputs on the provider supply sites; swap the D2H[0] cell.
10. **Re-run stale evidence** after the active agents finish: slicer (netlist and layout stale), pll_ring (spice stale), DAC (generators stale). Fix the `aosc` pass flag so out-of-window results report as failures.
11. **TMDS at 1.485 Gb/s** with the ff clamp leakage at 3.3 V pull-ups; USB HS eye template, chirp and turnaround through the real host latency.
12. **Fill the spec-missing numbers:** image rejection and IQ balance, TX LO leakage, mute isolation, PLL jitter, BER/JTOL/SSC, ESD HBM/CDM, clamp leakage limits.
