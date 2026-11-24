# Session state (consolidated 2026-11-14)

Current state only. Standing rules are in `MANDATE.md`. The chronological log up to this point is
`archive/SESSION-STATE-2026-11-14-pre-consolidation.md` (look there for detail before 13 Nov).
Branch `main`, pushed to origin. Append dated notes at the bottom; fold them into the sections on the next
consolidation.

## 1. Where the project stands

- **No payload mode ran end to end at the start of this week; the control plane now exists in RTL** and every
  mode family closes in a stub simulation. Nothing is hardened, routed or signed off.
- **Two chips, each fits its own die** (`die-fit.md`, split 2026-11-19): every block placed with the full 5.4 nF
  decap plan and the routing channels; margin after routing `pt_rf` +0.8 mm² as built (+1.9 targets), `pt_wired` +2.2
  (+2.8). Macro outlines from synthesis (no place and route yet). User direction: full scope across the pair, make
  2.7–3.24 Gb/s work, minimise area over time.
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

**Digital** — notes `scratch/digital-timing-close/NOTES.md` (r8), rows DG8-1..8, SPL-7.
One RTL, two chip configurations: `pt_digital_macro` parameter `PT_CHIP` (1 = `pt_rf`, 2 = `pt_wired`; 3 = both
halves, module-level benches only). Fields of the other chip are not stored (register-map per-chip view, D4; `pt_rf`
447 bits, `pt_wired` 648), `status.chip.id` at 0xFE, the other chip's CP4-1 clamps are not built. Hardening configs
`verification/digital_hardening/{rf,wired}/config.json`. Synthesized cell area (yosys, no PnR): `pt_rf` 1.053 mm2,
`pt_wired` 1.299, both halves 1.375; outlines at r8d density 1716 x 1256 (2.155 mm2) and 1716 x 1554 (2.666).
Open: place and route of both configurations (hio placement for the `pt_rf` height, pin order with the tied ports),
timing closure (r8d: worst setup -5.49 ns at ss, D2H hand-over DG8-6, applies to both), GLS, routed sign-off,
per-mode power analysis per chip.

**Chip tops (two chips)** — `integration/chips/` (`rf/` and `wired/`: `chip.conn`, `bond_map.txt`, `run.sh`;
shared `common.conn`, `check_top.py <chip>`, `decisions.md`), `spec/chips.json`, rows SPL-1..5.
State: both chips at 0 in every connectivity category including the bond map; non-zero only for demand (rf 19,
wired 13, of them 11 / 9 supply cells on signal sites) and staged (rf 4) instances and the isolation audit's open items. Open: D-SPLIT-* in `decisions.md`
(per-chip `core_bias`, supply cells at signal sites, `bias_ext` split, pad generator site map, RF ground model, dead checks), D-LOVREG, D-ANA, D-PWR bias-bank rails;
`netlist.py` (chip assembly) not switched to the conns.

**Wired RX** — `analog/wired_rx/README.md` (incl. pins section), STATUS files in `scratch/wired_rx/*`.
Published: `pt_cdr` r13 (0.083 mm²). Capture r7c (0.294 mm², −0.66) fails one case (LDE edge on the capture
clock edge: `scratch/wired_rx/r7cap/STATUS.md`); CTLE follower not built; ptrim real-load fix not built;
detect needs threshold redesign; interleaved >2.5 Gb/s path (R8-ARCH) not designed; chain rate × corner ×
supply table not produced; closed loop on r13 unevaluated; pad termination variant (142 Ω) to include.
Sub-work stopped mid-flight: CTLE follower + chain requal, ptrim redesign, detect redesign + USB receive,
AUX clock receiver checks: inspect `scratch/wired_rx/` for partial results.

**Wired TX / USB** — agent running (fresh). `analog/wired_tx/README.md`, `INTEGRATION.md`,
`scratch/wired_tx/`. 2.5 Gb/s fails at ss on real ring duty; no >2.5 Gb/s path survives
extraction; `pt_usb_txdrv` rev 3 unreviewed (HS level 351 mV at ss/3.15 V; 400 mV from 3.33 V).

**LO / timing** — `scratch/lo-ap4/NOTES.md`, `analog/timing/README.md` (LO section), rows LO20..28.
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

**Assembly / floorplan** — no owner running. Per-chip ledger, decap plan and packer in `die-fit/` (`chip.sh <chip>`);
sign-off skeletons per chip (`integration/signoff`, `SIGNOFF_CHIP`, `skeleton/floorplan-<chip>.json`). Needs: owner
floorplans with the supply grid and islands, island straps for `wrx_cap` / `ptrim` (G6), the `pt_wired` forwarded-clock
route (AUX pair on the west edge), per-chip power-delivery rerun (D9), side-edge hspad pins.

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

### Decision 2026-11-19: split into two chips

User decided: `pt_rf` and `pt_wired`, each self-sufficient, two Run 3 slots. Reason: the single die was 2.8-3.5 mm2 over as built (1.5-2.0 at targets) with the macro at 2.81-3.65 mm2; split estimate about 9.4 mm2 (rf) and 8.8 mm2 (wired) against 12.77 mm2 core each, before area work. Also removes RF/digital ground-bounce coupling and the decap-vs-area conflict. Plan and rules: `SPLIT-PLAN.md`. All block work is frozen against the single top until phase 3 of the plan is committed (no agents running at the time of the decision).

Disk 2026-11-19: freed 15 GB (old waveforms, superseded hardening runs pC6/run14, docker build cache); 41 GB free. Most of the disk belongs to other projects on the machine.

### Phase 4 started 2026-11-19 (split complete; user: "keep work organized and remove historical junk")

| Role | Agent ID | Scope |
|---|---|---|
| Pads (option A rollout, per-chip pad gen, rail check, AUX site on pt_wired) | a0b585bf24a7dee4f | analog/pads, bond maps for the AUX swap |
| Wired RX + timing (pt_cdr / pt_diff_clk_rx DRC, ring version, ring duty/spacing, RX candidates) | ae237ae42062df4de | analog/wired_rx, analog/timing |
| RF RX (new-map ground model, stability, R+C, TIA x2, fallback) | a6e1dd7a8217d3b6f | analog/rf_rx |
| Digital (D2H ping-pong, pipeline stages, harden both macros) | aa4a00476697338c3 | rtl, sim, SDC, verification/digital_hardening |
| Wired TX (block top, interlock, real-chain table, publish) | ad4984d8f6a49e79c | analog/wired_tx |
| Bias and power per chip (D8, D9, stale checks) | a19eb0e38a50aaf24 | bias/power files, integration/core_bias.py, power-delivery spec |

Every brief requires current-state docs and deletion of superseded files and runs (no archive folders).

### Agents added 2026-11-20

| Role | Agent ID | Scope |
|---|---|---|
| Chip assembly (full-chip floorplan, power grid, top routing, sign-off) | a67ba37dcfd1a2abb | integration/assembly |
| Observation, debug, bring-up, test-board models | a17b557baf31977af | spec/bring-up.md, spec/test-board-models.md, tools/bringup |
| LO synthesis (QVCO, regulator, dividers, PFD/CP, filter, external LO) on pt_rf | ab699c0348c88d032 | LO cells in analog/timing (not the ring cells) |

Machine rule given to all agents: at most one waiting loop each, ending with its job or a timeout; kill only processes you started.

### Paused by the weekly usage limit (2026-11-21; resets 2026-11-24 21:00 UTC)

Resume each by SendMessage to its ID (do not start new agents). State at the pause:
- Pads a0b585bf24a7dee4f: txpad a16 = candidate (EM sized for 100BASE-TX; conditions PC-71 / B54); waiting wired TX's WT53-c confirmation + PC-61; then publish txpad, USB b7 review (reviewer ad5099ba76b60f43a stopped mid-review), option-A rebuilds of rf_pair / rftxpad / single_leg / refpad (905 of the pt_rf precheck DRC errors), DOC-1, SATA2 return loss.
- Wired TX ad4984d8f6a49e79c: WT53-c 100BASE-TX (pump ~4.2 V cascode, 1:0.88-0.90 magnetics, CT <= VDD+0.30 V) confirmation run; NAND phase-buffer rebuild -> bind pt_wiredtx8 (binding sub-agent a6bbf50dab68d5e32, prepared conn in scratch/wired_tx/s16/bind); s16 publishing queue (6-9 days); DOC-4/DOC-6 folds.
- Wired RX / timing ae237ae42062df4de: ptrim r12 (grid-entry modelling, Metal5 trunk option, ch 6/7), capture r7f, CTLE r5 fails; then CDR loop (WRX-01) and >2.5 Gb/s architecture proposal (WRX-06); scratch cleanup.
- Digital aa4a00476697338c3: merge line-code and pad-sequencer branches (worktrees under .claude/worktrees), re-harden both chips (pt_wired at 1676 x 1592.96), sign-off STA / GLS; runaway-guard RTL row from LO.
- Bias/power a19eb0e38a50aaf24: IR rerun with isw_wired_tx moved and the switch pair beside pt_wiredtx8; ATB leaves; DEADCHK repair (sub-agent ab2d1660ea32363b7 stopped); D9 model sub-agent a9bba44f9db39f474 stopped.
- LO ab699c0348c88d032 (may still run): divider probe on published lo_mmd, runaway guard (VTUNE comparator + band-search limits), QVCO r9 rerun on fixcap16 netlist, review/publish.
- RF RX a6e1dd7a8217d3b6f: hand-placed LNA relayout next.
- Assembly a67ba37dcfd1a2abb: pt_rf precheck on the 164-violation layout; pin isw_wired_tx_a/_b beside pt_wiredtx8; pt_wired 183 violations.
- Bring-up a17b557baf31977af: idle (done).
- Wired TX island current limit 56 mA (coordinator 2026-11-21): pt_wired supply tap closes IR at 56 mA with a ~180 um bar; 60 mA needs ASM-8 (Metal5 freed in wrx_cap / ptrim / wiredtx8, ME/SE VSS >= 16 %). On resume, wired TX must confirm every mode (100BASE-TX with raised cascode especially) stays <= 56 mA average, else ASM-8 becomes mandatory.
- Update at pause (2026-11-22): assembly and digital also stopped by the limit. pt_wired east side waits on ASM-8 (wrx_cap / ptrim / wiredtx8 free Metal5) and on moving the macro's wire_tx_data[39:0] + wiredtx8 control pins to the macro edge facing pt_wiredtx8 (assembly owes digital the row: edge, position, pin order; digital does it in pin_order.cfg in the next pt_wired hardening). Best routed pt_wired placement: 183 violations (fails IR); option B: ~2400 (IR closer). pt_rf: 164 violations, precheck on that layout was still running. Digital: three pipeline stages merged; full regression + both-chip hardening on 3d54021b were running.
- On resume after the limit: tell every agent to read MANDATE section 4a (recurring verification lessons) before continuing, and include "read MANDATE 4a" in every new brief.
- Second pause (2026-11-22, limit resets 2026-11-24 21:00 UTC), baseline push in progress. Stopped: assembly, wired TX (+ its "data pins to top edge" sub-agent), pads, bias/power. Baseline state: all wired RX / timing blocks handed off (ptrim r12c included); LO baseline cells published, LO on standby; RF RX handed off, on standby; digital hardening pt_wired with the ASM-11 pin order. Remaining for the baseline: lo_vreg + txpad_bias bindings and the four converters (bias/power), option-A pad publications with chip-top edits (pads), wiredtx8 east landing / top-edge pins / pump (wired TX), new pt_wired macro LEF (digital), then assembly reruns, LVS and precheck. Resume all with "baseline ASAP" (MANDATE section 1).
- 2026-11-22: coordinator merged WT50 + LO-DIG-1 (4 commits, via a clean temp worktree; conflicts only in interface-changes.md and rf/chip.conn, branch version taken) and pushed; clean-HEAD regfile check passes. pt_rf chip-top summary now demand=0 staged=0 (only the known 22 iso-audit findings). Uncommitted power-agent WIP in the main tree (converter publication + lo_vreg/txpad_bias bindings, spec/analog-architecture.json) makes the register map stale: on resume, the power agent must regenerate the map in the same commit, and finish the pt_wired txpad_bias binding (unbound=7).
- 2026-11-23 baseline decision: pt_wired uses the published capture r6 (0.96 mm2, gearbox inside, matches conn and macro; known miss: no 2.5 Gb/s with real neighbours). The smaller r7e (0.30 mm2, LDE fix) needs the W7-GEAR 20->40 gearbox and DW/WSTB inputs in the digital macro: first post-baseline item for digital + wired RX.
- Layout overview images: projects/programmable_transceiver_platform/docs/layout/ (drawchip.py). Found the floorplan ignores analog adjacency (LNA spirals 0.5-0.8 mm from the LNA, LO run ~2.5 mm to TX mixers, RX phases crossing ~1.5 mm); adjacency rules requested from assembly as baseline work.
- 2026-11-23 fix pass started (user: "commit, and start fixing all the many issues, largest and most obvious first").
  Cross-chip ranking: 1 route clean + LVS clean both chips (assembly); 2 pt_lo_txbuf (TX under-driven, LO);
  3 shuttle precheck errors (assembly + owners); 4 digital timing closure 2-3 ns + GLS (digital);
  5 wired capture fails 2.5 Gb/s with neighbours, r7e + W7-GEAR gearbox (wired RX + digital);
  6 LO shields drawn, wired RX clock cluster adjacency (assembly); 7 isolation audit 22/36 (power);
  8 requirements scorecard fails (40) by size, each owner; 9 TX TERM_TRIM register field (digital).
- 2026-11-23 weekly API limit hit (resets 2026-11-24 21:00 UTC): RF RX a6e1dd7a8217d3b6f, power a19eb0e38a50aaf24, wired RX ae237ae42062df4de, pads a0b585bf24a7dee4f stopped; wired TX ad4984d8f6a49e79c hit a rate limit (plan: termination buffer off the island = lever 1 of WT56-b, 16-21 mA; block still ~89 mA at ff with POST on, so 56 mA needs a power-side answer; pump start-up; in-block VSS). Resume each with SendMessage after the reset, same fix-pass briefs. Still running: assembly (64-iteration reroute), digital (both macros + regression; W7-GEAR ports agreed: wire_rx_word[19:0], wire_rx_wstb 6.0 ns), LO (pt_lo_txbuf r1 bench).
- W7-GEAR (branch worktree-agent-a03e94865d3287179, head 4ed06722) lands only together with wired RX's r7e binding. Full rate stays allowed (100BASE-TX receive uses B1=1); wired RX must settle the r7e B1 race (WR11-4) at 125 Mbaud before r7e binds.
- 2026-11-24 supply short: neither chip has a cell/tie VDD-VSS short (LVS without router wiring clean); remaining joins are route shorts (assembly). Pads to confirm on resume: pad_wire_tx internal DNV0/1.SUB, DPV0/1.SUB join VSS (expected substrate ties?).
- Uncommitted WIP of paused agents, for them to finish/commit on resume: analog/antenna_diodes.py (sdA rule; pll_ring r9 -> wired RX/timing ae237ae42062df4de), analog/pll_vreg/pll_vreg.py (power a19eb0e38a50aaf24), analog/rf_rx/generated/{lna_deg,lna_ind}.spice + rxmix-ab.json and scratch/rf-lna-q/r2*.sh (RF RX a6e1dd7a8217d3b6f).
