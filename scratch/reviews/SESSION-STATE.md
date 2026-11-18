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

### Wired TX session 12 closed (2026-11-14)

- Nothing new published. Full table `scratch/wired_tx/s12/TRUTH.md`, resume point `scratch/wired_tx/STATUS.md`, review `scratch/wired_tx/s12/review/REVIEW.md`, rows WT32-WT37 in `interface-changes.md`.
- Real chain (extracted ring on regulator output, extracted pad, COB bond, 50 mm line): published `pt_wiredtx` + `tr7` fails 2.5 Gb/s at ss at 3.15 V and 3.50 V; old eighth-rate `wtx_serq8` fails even at tt (architecture).
- New path `wtx_ser8d` + `wtx_mux8` (both extracted, DRC 0, LVS unique from disk): passes 3.125 and 3.24 Gb/s at tt / ss 3.15 V / ff, 3.24 at ss 3.50 V, 2.7 at ss-pessimistic 3.15 V. Fails 3.125 Gb/s ss-pessimistic at 3.15 V (23 errors) and 3.50 V (eye 0.148 V). Not run: 3.0 Gb/s, 3.24 pessimistic, 2.5 Gb/s in the real chain.
- Open: ring phase spacing -44 / +70 ps at ss (WT33) absorbed only by hand-derived trim codes, no on-chip calibration; POST bank same-sign mode 28 errors; stopped-ring current interlock; power 22-28 mA MAIN only, 44-52 mA with POST; block top does not exist.
- Area: new path 0.278 mm2 against 0.22 reserve; net +0.085 mm2 over today's transmitter if it replaces the quarter-rate core, steering buffers and `tr7`.
- Coordinator recommendations, not yet user-confirmed: adopt the new path as the single transmit path once it publishes; ring owner fixes phase spacing to about +-10 ps and the trim stays as residual; pads go ahead with the 0.6x MAIN switch; accept the MAIN-only current, subject to the power-delivery budget for that island being rechecked.

### Round started 2026-11-18 (user: "work on these", all eight items)

Agent IDs by role (verify before any SendMessage):

| Role | Agent ID | Directories it may edit |
|---|---|---|
| RF RX / LNA | a09c6a4be6f49e716 | analog/rf_rx |
| Shuttle acceptance (precheck, fill, top DRC/LVS) | a912644b99f31bf31 | integration/signoff |
| Wired RX | af72cfb7b4d5300b5 | analog/wired_rx, analog/timing (receive parts) |
| Pads (termination, LNA ground plan) | a07714b3f18166709 | analog/pads, scratch/reviews/pads-core |
| Digital macro timing/area | ac1c48346cd362a80 | rtl, sim, verification/digital_hardening, SDC |
| Wired TX | a24b8b22700674705 | analog/wired_tx |
| Area ledger / reduction | ab39f0b6ba2280833 | scratch/reviews/die-fit*, unowned blocks only |
| Housekeeping / evidence audit | afc52a09b47511c00 | non-owned files, scratch/reviews/evidence-audit.md |

Limits given: 3 sims (RF RX, wired RX, pads, wired TX, digital sims), 2 heavy jobs (signoff, area, audit, digital hardening), OMP_NUM_THREADS=1. Not started, awaiting user decisions: LO ring phase fix, 0.6x MAIN pad switch, OCP-2, HT40 ruling.

### Housekeeping and evidence audit (2026-11-18)

- Evidence audit done: `evidence-audit.md` (table per block), scripts and results in `scratch/evidence-audit/`. Published status not supported for 31 of 83 blocks; 85 of 87 GDS pass precheck DRC and antenna today (`pt_adc_i` antenna, superseded `attached_tx_buffer`); every GDS with a flat netlist matches the netlist the chip top binds. Rows to owners: EA-1..11 in `interface-changes.md`.
- Needs an owner or a ruling: pad ESD evidence against the owner's resistance extraction (PAD-11 understated); `pt_pll_ring_core` layout older than the committed ring cell (TIM-12); QVCO without evidence or top LVS; `rf_rx/netlists.py` uncommitted (HEAD cannot regenerate the published bbfilter); `make transceiver-chip-assembly` stops on the deleted polyphase.
- Housekeeping: references to deleted docs fixed in spec JSON and unowned scripts; the remaining ones are in owned directories (EA-2, EA-3, EA-8, EA-9). `spec/analog-architecture.json` has a block → conn-instance cross-reference checked by `spec/check_architecture_conn.py`; its nets, ports, area and current books are still the model-era ones (INT-10).

### Die-area ledger rebuilt (2026-11-18)

- `die-fit.md` and `die-fit/ledger.md` rewritten from layouts measured on disk (107 GDS). Rows DF-1..12 in `interface-changes.md`. Supersedes the die-fit numbers in section 1.
- Block demand 14.02 mm2 as built, 12.51 with targets met, 10.24 at measured lower bounds, against 12.772 of core. Does not place: 2.8-3.5 mm2 as built (3.2-3.9 with channels), 1.5-2.0 with targets, 0.4-1.2 after the pad, bank and core-ring levers on top of targets. Everything places only at the lower bounds with the macro at 2.81 mm2; with the macro at 3.65 (r7c, failed routing) 0.16-0.90 stays out even then.
- Largest levers: digital macro 0.83, debug pads on provider cells 0.43, core ring 0.26-0.53, decap bank 0.39, ADC pair 0.39, baseband filter pair 0.29, WTX_EXT pad 0.15 (OCP-2), QVCO regulator 0.14, core bias 0.14.
- Done: RF probe frames 430 x 260 -> 260 x 260 um (-0.133 mm2, commit be37cc6, reviewed GO-with-conditions). Accepted risk to confirm: 200 um port spacing for facing GSG probes.
- Found: the INT23 QVCO rule and the `lo` switch at pad 64 cannot both hold (QVCO 1.0 mm from its switch in every packing); area levers remove grid-MIM area one for one (2.0 / 1.4 / 0.8 nF as built / targets / lower bounds); channels are 0.7-1.0 mm2 short at realistic pitch unless static control crosses blocks; pad-ring corners hold nothing.

### Decision 2026-11-18: pad ESD architecture (PC-23)

User chose option A: primary ESD diodes inside the pad site tied straight to the ring rails, in all custom pad families. Back-feed into an unpowered chip is accepted; the board controls sequencing (rule to be written by the pads owner). Reason: metal resistance of 23-32 ohm pad-to-diode (56-85 ohm full loop) left every custom pad unprotected at 2 kV; the isolated-rail alternative cost 0.3-0.9 pF per pad. All pad evidence must use R+C extraction with the return side in the model.

### Coordinator decisions 2026-11-18 (RF receive)

- `pt_chip.conn`: LNA pins `tail`, `vtk` bound (RQ-1); spirals rebound to `LNA_VTK` / `LNA_TAIL`; `AGND_RX`, its two down-bond pads and the tie are removed, LNA and RF RX pad ground are die VSS (no down-bonds on the fixed bond layout). Chip-top check back to unbound=0.
- Bond map: RF_RX moves to bonds 67/68, BB_I to 69/70 (PC-26, RQ-5; both owners asked for it): die-VSS bounce pickup into the RF input falls from about -18 dB to -40 dB; cost is 8-9 dB more external-LO coupling, to be checked by the RF RX owner. Pads owner applies it to the bond map and contract.
- LNA status: candidate, NO-GO for publication. Real fails: common-mode Re(Z) negative at 47-66 MHz at ff with 3 nF decap and 1-2 nH rails (supply anti-resonance), 0.74-0.88 ohm in band in duplex bias; chain NF 6.15 dB tt / 8.1 dB ss against 4.1 dB (package loss 2.4-2.7 dB before the LNA is a floor). Supply rules RQ-3/3a accepted as requirements on power delivery: no undamped capacitor >= 50 pF on the rf_rx island rail, die decap >= 3 nF with anti-resonance Q <= 3, <= 0.5 nH per rail. This conflicts with the area lever of dropping the decap bank (die-fit lower bound holds about 2.9 nF).

### Wired TX session 13 ended early (2026-11-18)

- Nothing published. Resume point `scratch/wired_tx/STATUS.md` ("RESUME HERE"), facts `analog/wired_tx/README.md`, rows WT38-WT40.
- Cause of the 3.125 Gb/s pessimistic failure found (hop timing in `wtx_ser8d`) and fixed: real chain 0 errors / 360 bits, eye 0.122 V untrimmed (still a fail on the eye; pad=C, ring=layout-11Nov, schematic mux).
- `pt_wiredtx8` exists as a first layout pass (DRC 0, LVS unique from disk, 0.351 mm2 bounding box); the schematic is ahead of it (phase buffers) and the second pass stopped half way when the layout sub-agent hit its usage limit.
- With the pads owner's R-aware transmit pad the eye roughly halves (ss 3.125 Gb/s mux level 0.367 -> 0.203 V typical metal, errors at high metal).
- Simulation queues were left running detached (pad matrix, trim calibration with the real ring, ring tuning); the rate x corner table on final netlists, supply / Monte Carlo rows and the independent review are not done.

### Wired RX resume 11 closed (2026-11-18)

- Nothing new published. Resume point `scratch/wired_rx/r11/STATUS.md` (end section); rows WR11-1..8; reviews `scratch/wired_rx/r11/review/ctle/REVIEW.md` (equaliser r4 NO-GO, selector r2 GO with conditions) and `review/capture/REVIEW.md` (capture r7e GO with conditions; bench critique).
- Staged, sources committed: `pt_ctle` r4 + `pt_rxselect` r2 (bias sensitivity, wiring resistance, deep n-well), `pt_ptrim` r10 l8 (passes everything run, matrix incomplete, unreviewed), `pt_detect` r10 q27 (50 ohm supply trunks, fails pessimistic slow corner), `pt_wrx_cap` r7e (full-rate race, pessimistic 625 MHz fail).
- Real neighbours on the republished pad, settled ring, 120 mVppd: 1.25 and 2.5 Gb/s pass at ss/3.15 V (2.5 also at tt and ss-pessimistic for the eye); 3.24 Gb/s passes at tt and FAILS at ss/3.15 V (36 of 110 decisions wrong) and at ss/3.50 V (1 of 112): cause is the RX ring's 0.60-0.63 duty at 810 MHz (0 errors with ideal clocks on the same eye). 0.48 and 2.7 Gb/s, ff, sf/fs not run.
- Found on the way: the ring needs more than 60 ns to settle (a first 30 ns calibration was wrong and withdrawn); LVS wrappers accepted property errors (wired RX one fixed, `layout_engine.netgen_lvs` open); thin supply trunks in the generic wired RX layouts.
- Decisions wanted: ring duty / spacing fix versus sampler requalification at 0.63 duty; equaliser bias scheme; capture r7e now as known-limited or after its revision; 0.48 Gb/s through quarter mode with digital phase picking; deep n-well for the equaliser followers.
