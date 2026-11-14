# Session state (consolidated 2026-11-14)

Current state only. Standing rules are in `MANDATE.md`. The chronological log up to this point is
`archive/SESSION-STATE-2026-11-14-pre-consolidation.md` (look there for detail before 13 Nov).
Branch `main`, pushed to origin. Append dated notes at the bottom; fold them into the sections on the next
consolidation.

## 1. Where the project stands

- **No payload mode ran end to end at the start of this week; the control plane now exists in RTL** and every
  mode family closes in a stub simulation. Nothing is hardened, routed or signed off.
- **The design does not fit the fixed die** (`die-fit.md`): short 2.1–2.3 mm² with staged cells as measured,
  1.3–1.75 mm² with every repack target met, before routing (1.1–2.3 mm² needed vs 0.8–1.0 available) and
  decap risk. After die-fit levers 1–5 plus off-chip passives items: 0.03–0.18 mm² short (targets met),
  0.65–0.73 short (staged). User direction: keep full scope, make 2.7–3.24 Gb/s work, minimise area over time.
- **Agents:** the user stopped all agents on 14 Nov. Stopped agents cannot be resumed; start fresh ones from
  the notes listed in section 4. Running now: wired TX (fresh, 2.7–3.24 Gb/s path).

## 2. Decisions in force (beyond the mandate)

| Topic | Decision |
|---|---|
| CTLE | Source-follower fix approved (+6.3 mA; slicer requalified at ~0.4 V common mode). MW-13-FIX |
| ADC rate | 39.0625 MS/s default in RF modes (128/125 resampler in host); 40 MS/s selectable |
| Reset | Strap pad (provider input, hard pull-down) on east bidir[16] plus the pad-free keyed second path |
| SPI | ≤ 5 MHz (bring-up ≤ 1 MHz), repeater at each pad, Schmitt + pulls |
| Polyphase | Deleted (CP4-2) |
| Forwarded wire clock | Moves onto the AUX_CLK pad pair (CP4-3); needs the 25–810 MHz receiver bench, a differential 3.1 mm route, a pad-exclusion rule, debug island on |
| Islands | Ten islands on existing switch cells (`spec/power-delivery.md`) |
| Isolation | ~130 island-to-macro clamps are AND2 cells inside the macro (CP4-1) |
| Fault monitor | Derived in the macro; second time base in RF modes (management oscillator stays off) |
| Host-follow clock | On the TX ring as baseline (pending owners' confirmation rows) |
| LNA | On-chip source degeneration; source pads withdrawn; small TIA option (rxmix 35.4k µm²); current limits stay 19.0 / 11.8 mA |
| LNA ground | Must be re-planned on standard fingers (no extra bond openings are possible) |
| External-LO pads | Swap REF_IN with BB_Q plus low drive (~1 Vpp), pending LO confirmation of I/Q error |
| Spare east site bidir[17] | Supply/ground bond via option P2 (a south signal moves east) |
| LO loop-filter capacitor | Off-chip on bidir[22]/[23] with Kelvin return IF the WTX_EXT fallback moves to the USB pads (OCP-2: open with the user); MIM-over-MOS variant to be checked meanwhile |
| QVCO spur limit | −60 dBc per tone / 0.2 ps (the −80 dBc figure was underived); regulator to be requalified and shrunk (laid out at 0.44 mm²) |
| Bond rule | Supply slew ≤ 0.3 V/µs, no hot-plug |

Open with the user: OCP-2 (WTX_EXT fallback onto the USB pad pair costs USB HS transmit from external serial
data); whether our Run 3 slot is purchased; the email to wafer.space (14 items at the end of
`wafer-space-answers.md`, incl. modified COB, attach material, layer 24/0, DNWELL/SAB, tester handling).

## 3. Reports from this round (read these before re-deriving anything)

| Report | Key result |
|---|---|
| `pre-mortem.md` | 15 untracked failure routes: fill, read-back LVS, version drift, stale evidence, no board/firmware |
| `mode-walk.md` (MW-0..36) | No analog top existed; register map behind cells; real-neighbour gaps (CTLE −8 dB, LO into mixers −3..−16 dB, ptrim) |
| `always-on-audit.md` | POR single point of failure; aosc.EN floating; bandgap 71 µA when "off"; VBG overshoot at enable |
| `integration-m1.md` (INT1) | Power delivery did not close; led to `spec/power-delivery.md` (PD2-1..21) |
| `integration-m6.md` (INT6) | Fast supply edge fires pad clamps; isolation audit; por_bypass with RESET_N high |
| `integration-m23.md` (INT23) | QVCO runs at the carrier: placement rule (spirals ≥ 1.7 mm from west edge, ≥ 1.0 mm from RF pads); external-LO bond leakage; spur table; substrate keep-aways |
| `signoff-gap.md` (SG) | Read-back LVS clean on 74 blocks; DCF.1a; fill lands in QVCO spirals; adc_i antenna; live precheck needs amd64 |
| `integration/top/` + `scratch/chip-top/` (TOP-1..25) | One connectivity file, 0 unbound; regression still non-zero (12 unbuilt instances, 4 staged converters, audit items) |
| `consolidation-pass-4.md` (CP4) | Merging is worth 0.19 mm² free, ≤ 0.5 with pin sharing |
| `die-fit.md` | Does not fit; ledger, packer, levers |
| `offchip-passives.md` (OCP) | 0.22–0.30 mm²; USB passives are only 0.005 mm² |
| `wafer-space-answers.md` | Fixed bond layout, no larger die, COB facts, process options, precheck versions |
| `pads-core/*.md` (PC-1..17) | Strap proven; clamp rule; stacked hspad published; HS pad termination defect; bond-map options |

## 4. Workstreams: state and resume point

**Digital** — notes `scratch/digital-timing-close/NOTES.md` (sections r6), rows DG6-1..16.
Done: register/decode rework (cfg and macro-port diffs 0), `pt_chip.sv` generated from the conn, strap bound,
second POR path, SPI one-flop write, in-macro clamps, new control logic (wired TX launch, CDR loop, USB FS/LS,
monitor, LO integer-N), stub mode sim (135 checks). Regression green on commit 9211b44.
Open: independent review of 9211b44's pipelining; flow readiness (clamp pins excluded from buffering,
dont-touch, sta_signoff/gls on new ports, pin order); setup closure (post-synthesis ref −2.39 ns); harden with
the pC6 hold flow; routed OCV sign-off; GLS; clock-launch staggering and per-mode power analysis (decap plan
depends on it); timing at 3.5 V; ring-monitor readout; macro area (cells 1.404 mm², write `macro-area.md`);
TOP-25 items (LO enables on the rf group, D-DATAOFF checks, K7 leaves, K1 enable rules); IX-12; USB HS bit
repetition; DG6-7 questions to wired RX.

**Chip top** — `integration/top/` (`pt_chip.conn`, `run.sh`, `decisions.md`), `scratch/chip-top/NOTES.md`.
Open: regression non-zero; last decisions edits unreviewed; `netlist.py` not switched to the conn;
bond map in `spec/contract.json` stale; D-LOVREG, D-ANA, D-PWR bias-bank rails.

**Wired RX** — `analog/wired_rx/README.md` (Resume 9), `PINS.md`, STATUS files in `scratch/wired_rx/*`.
Published: `pt_cdr` r13 (0.083 mm²). Capture r7c (0.294 mm², −0.66) fails one case (LDE edge on the capture
clock edge: `scratch/wired_rx/r7cap/STATUS.md`); CTLE follower not built; ptrim real-load fix not built;
detect needs threshold redesign; interleaved >2.5 Gb/s path (R8-ARCH) not designed; chain rate × corner ×
supply table not produced; closed loop on r13 unevaluated; pad termination variant (142 Ω) to include.
Sub-work stopped mid-flight: CTLE follower + chain requal, ptrim redesign, detect redesign + USB receive,
AUX clock receiver checks: inspect `scratch/wired_rx/` for partial results.

**Wired TX / USB** — agent running (fresh). `analog/wired_tx/README.md`, `INTEGRATION.md`,
`USB-INTEGRATION.md`, `scratch/wired_tx/`. 2.5 Gb/s fails at ss on real ring duty; no >2.5 Gb/s path survives
extraction; `pt_usb_txdrv` rev 3 unreviewed (HS level 351 mV at ss/3.15 V; 400 mV from 3.33 V).

**LO / timing** — `scratch/lo-ap4/NOTES.md`, `analog/timing/LO-INTEGRATION.md`, rows LO20..28.
Staged, unpublished: lo_mmd 0.146 (max frequency regressed, review NO-GO), qdum, lo_obs, clk_obs16, lo_ext
candidate (mixer loss 1.5/3.8 dB tt/ss vs 3.3/9.8 published). Open: QVCO with real tank loads and fill
keep-outs, QVCO top netlist/LVS, regulator vs the −60 dBc limit, loop (preset, lock 60–65 µs at slow filter
corner), LO-01 reopen + placement rule, D-LOVREG, EM on CML paths (LO28), AUX_CLK receiver bench (PC-7),
polyphase removal from the build.

**RF RX** — `scratch/rf-lna-p/NOTES.md`, `v8/`, review `scratch/review-lna3/REPORT.md`; ~33 rf_rx files
uncommitted (design not closed). LNA NO-GO: common-mode input resistance still negative; pessimistic-corner
NF 7.35 dB (tank Q); 220 µm tank coil recovers 2.3 dB; match on the real COB channel not done; fallback-LNA
path not simulated; chain NF must use the real LO levels. bbfilter repack (AP4-3) not started.

**Converters** — `scratch/converters-ap4/NOTES.md`, `analog/converters/INTEGRATION.md`.
Staged: ADC 0.450 mm² each (target 0.33 missed; shared guard rings would give −0.07 each), DAC 0.134; single
CMOS clock pin, PH output. Not published: stage4 not re-reviewed; queued sims in `queue.status` may have
finished; EN=0 window 1.30 µA vs 1 µA needs a ruling; VCM source is a bare divider (CNV-06); adc_i antenna.

**Pads / core support** — `scratch/pads-core/NOTES.md`, `scratch/reviews/pads-core/`.
Published: stacked pad_hspad, pt_bias_tap2, pt_refvcm, pt_txpad_bias, TLP site fix.
Open, in order: ESD implant layer 24/0 dependence; pt_hs_leg termination fix + R-aware extraction for all pad
families; bond plan under the fixed layout (AGND_RX on standard fingers, bond audit with real wire/die
thickness/placement shift, `contract.json`, `package-channel.json`); tester diode check; bias tap rails
(PC-5); back-drive pins; ATB trunk leaf switches; host pulls; 3.5 V tables; LEFs; area items (AP4-6, AP4-7
= 0.40 mm², ESD rows under the rail band, tx_interlock, true L-shaped outlines).

**Power delivery** — `spec/power-delivery.md`, model in `scratch/integration/m1-pdn/`.
Open: digital's real current shape; decap after repacks (over-block MIM shrinks to 1.1–1.4 nF); island strap
routing vs supply-pad positions (lod, pll, wired_tx conflict with signal flow); PSRR evidence rows PD2-14..19;
regulator stack-up for supply trim; reliability at 3.5 V.

**Assembly / floorplan** — no owner running. v6 is the last floorplan; packer and ledger in
`die-fit/`. Needs: ledger keeper, v7 with supply grid, ten islands, placement rules from INT23, side-edge
hspad pins, fill flow with keep-out markers.

**Not started:** adversarial evidence audit (staleness script exists in `pre-mortem/`); bring-up software,
FPGA gateware and carrier design; brownout and slow-corner ramps of the power-up check; top-level routing and
sign-off.

## 5. Notes since consolidation
- 2026-11-14 cleanup: docs under the project rewritten to current state (72 -> 42 .md files; 26 obsolete spec/docs files deleted; risk register 253 -> 220 rows). Digital r7 RTL committed after a green regression (b: digital-rtl-checks, regfile, formal, top-modes, chip-io, por-bypass-chip, contract, ctl-blocks). Unfinished in-flight work of stopped agents is snapshotted on branch wip/2026-11-14-unfinished and still uncommitted in the tree: rf_rx LNA redesign (~39 files), wired_rx (capture/ctle/detect/ptrim/rxselect/flow), pads (hs_leg fix, agnd_pad.py), LO (layout_engine, lo_rows, lo_vreg.spice), pll_vreg.py, antenna_diodes.py, digital hardening outline experiment (config.json 1716 x 2126, hio_placement.cfg). Old scratch waveforms/objects >50 MB and >3 days deleted (9 GB).
- Found by the docs pass (not doc problems): host-link opcodes 5/6 decoded but rejected by the header legality check (pt_quad_link.sv legal_n): unreachable (HL-04); SDC constrains SCLK at 10 MHz vs the 5 MHz decision; ADC 39.0625 MS/s default and SPI 5 MHz not implemented anywhere; analog-architecture.json stale vs pt_chip.conn (diagram generator check fails); the only valid published ADC FFT is ENOB 4.9 (MOD-04); pll_ring safe-state fails on current evidence; nine timing blocks have no evidence json; rfdriver layout uses unconfirmed DNWELL; RTL comments and several spec JSON/scripts still cite deleted docs; removed risk IDs still cited (RXR-03, INT-22, PDN-07, MOD-14, RFT-09, ESD-04, SUB-05, WRX-14). RFR-04 (HT40 RX not supported) reopened: needs a ruling.
