# Independent review: capture r7e (`pt_wrx_cap`) and the r11 real-neighbour benches

Reviewer run 2026-11-18, 08:10-08:50 UTC. Standard: `scratch/reviews/MANDATE.md` sections 3 and 4.
Nothing under `projects/` or in existing scratch directories was edited; nothing committed. Reviewer files are in this
directory: `a1/` (capture, full rate, fast corner), `a2/` (LDE synchroniser cell), `b1/` (one chain cell rerun, waveform kept).

Words used: **read** = taken from stored files; **measured** = computed by me from stored waveforms; **rerun** = one of my
three simulation jobs (all three of the budget were used, each one ngspice run through `slot.sh`); **estimate** = scaled, not
simulated.

## 0. Summary

**A. Verdict: GO with conditions** for r7e replacing the published r6, as a known-limited revision with a failing evidence
record. It is not "done".

* The LDE fix removes the reported defect. It leaves a very narrow band where an LDE is dropped altogether (rerun), and its
  lower width limit is an absolute time (about T - 300 ps at the fast corner), not "0.8 T".
* The clock-driver change is sound. Measured shift of the capture clock against r7c: within 10 ps at tt 625 MHz, -15 ps at
  tt 480 MHz, -20 ps ff, -60 to -72 ps ss.
* The gating claim is correct as stated (16 of 17 pass, `ext_f480p0` fails). The cause is a race of the whole full-rate mode,
  not of phase select 0. Phase select 0 is only the slowest input of the 8:1 multiplexer. Quarter and half rate do not use
  that path (source and measured margins).
* New from this review: at nominal ss/32/3.15 V, 625 MHz the last slot-enable hop already violates its flop. The enable is
  1.14 to 1.31 periods long instead of 1, varying from word to word. The gating case passes because the word-load latch
  tolerates it, by 14 to 274 ps in the six words of the stored probe. This is the mechanism that fails at pessimistic values.
* Not covered at all on r7e: ring above 625 MHz, 3.50 V, sf/fs, fast corner at 625 MHz with RCS = 0, metal resistance.

**B. The benches can give both false passes and false fails.** The largest items: no clock-phase negative control has failed
yet; the lock emulation places data on the linear-estimate eye centre, not on the real crossings (up to 0.13 UI apart, against
a 0.05 UI limit); the pad-capacitance table is a linear estimate that reads 11 % high in eye and 0.09 UI wide against the one
transient that exists. The slow-corner 3.24 Gb/s result (36 wrong of 110) is the sampler bank as modelled, not the read-out
(rerun).

---------------------------------------------------------------------------------------------------------------------------

## 1. Subject A: `pt_wrx_cap` r7e

### 1.1 Identity and bookkeeping checks (all pass)

| Item | How | Result |
|---|---|---|
| Tree source = staged cell | regenerated all nine cell netlists from the working-tree `capture.py`; compared with `r7e/fast/*.spice` and with the LVS reference `r7e/cap/top/schematic.spice` | identical |
| Simulated netlist = staged extraction | sha256 of `r7e/gen/wrx_cap.ext.spice`, `r7e/cap/top/pt_wrx_cap.ext.spice`, `cap.spice` of two gating runs | all `831d86f5...` |
| GDS identity | sha256 of `r7e/gen/wrx_cap.gds` | `eff0b36d...` = `wrx_cap-kldrc.json` = `readback.json` |
| Gating list | `run_capture.CASES` minus `NON_GATING` against `r7e/results.json` | 17 gating cases present, 16 pass, `ext_f480p0` fails 11 data / 13 edge of 60; `neg_s2stuck` fails as required |
| Layout records | `wrx_cap-layout.json`, `wrx_cap-cells.json`, `r7e_stage2.log` | DRC 0, LVS unique, precheck main 0 / antenna 0, XOR 0 polygons on 19 layers |

Two notes on the gating runs. The half-rate cases ran 9 words (120 bits) and the full-rate cases 6 words, of which 3 are
judged (60 bits): both sit exactly on `MIN_BITS`. The full-rate passes for phase select 3 and 5 rest on three words at tt only.

### 1.2 Read-back LVS

Genuine. `rb.py` reads the uniquified `gen/wrx_cap.gds` back into Magic, extracts, and runs netgen against the reference with
transistors as primitive devices: all nine subcells are flattened on both sides, 4856 = 4856 devices after merging 290
parallel devices, "Circuits match uniquely", no property errors. The negative control (one pfet W 4 -> 4.1 um in `wc_pair` of
the reference) gives "Property errors were found", so W is compared. The verdict is taken from the report text, which matters
because `layout_engine.netgen_lvs` returns `unique_match = True` even with property errors (the STATUS note is right).

Limits of that evidence: the control proves the property comparison only (a swapped-net control was not run, though a flat
unique match is strong); the 22 antenna diodes are added to the reference from the layout report, so they are checked for
connection, not for intent; DRC in the read-back is Magic's, the KLayout precheck is the separate `wrx_cap-kldrc.json` on the
same sha.

### 1.3 LDE synchroniser (`cnt()`)

Logic: `LDG = LDE | LDE delayed by four inverters`; `INJ1 = FF(LDG)`; `INJ2 = FF(INJ1)`; `INJ = FF(INJ1 & !INJ2)`.

* **The reported defect is fixed.** A one-period LDE seen by two edges now gives one INJ. Read: 13 cell runs at 20 ps steps
  with no double and no miss; full top passes at LDE 0.5 / 0.6 / 0.65 / 0.7 / 0.75 ns (tt). Measured from `results.json`:
  the word alignment changes between 0.65 and 0.70 ns after CKP0 at tt, which is the boundary the author states.
* **Residual 1, rerun `a2` (fast corner, r7e cell, 625 MHz, LDE one period wide, 0.5 ps steps): one LDE is dropped
  completely.** At 74.34 ps after CK at the cell there is no INJ at all (peak 0.01 V); 73.84 ps gives INJ one cycle earlier,
  74.84 ps one cycle later. The band is narrower than 1 ps. Mechanism: INJ2 and the edge-detect flop sample differently
  delayed copies of a marginal INJ1, so one can read "already high" while the other reads "not yet". The author's sentence
  "0 doubles, 0 misses" holds only at 20 ps resolution, and "the word boundary moves by one ring cycle" understates the
  consequence: at the boundary a word can be lost (no WSTB). The mirror case (a doubled INJ) is equally possible in principle;
  I did not see one in 120 phases.
* **Residual 2, rerun `a2` (fast corner, 480 MHz, LDE 0.85 T wide, 20 ps steps): one miss at 76 ps**, neighbours at 56 and
  96 ps fine. With the first point this gives a stretch of about 300 ps at ff (about 400 ps at tt from the author's 0.6 T
  run). The lower width limit is therefore T - 300 ps: 0.86 T at 480 MHz, 0.81 T at 625 MHz, 0.76 T at 810 MHz. The comment
  "from ~0.8 period" and its supporting run (0.85 T at ss, 810 MHz) used the most favourable corner and rate.
* **The forbidden phase moves with the corner.** It follows the capture clock delay: measured CK after CKP0 is 475 ps at ff
  (rerun `a1`), 721 ps at nominal ss and 862 ps at pessimistic ss (stored probes). The band at the pin is therefore near
  0.55-0.6 ns (ff, estimate), 0.65-0.7 ns (tt, measured), about 0.9 ns (ss, estimate) and 1.05 ns (pessimistic ss, estimate). The README contract ("synchronous to CKP0 with a
  fixed phase") gives the macro no numbers. The two ss cases defined for this (`q625_ss_lde70/80`) were never run.
* Reset and enable: with EN = 0 every flop output is forced low, LDG is low and the new inverter chain sits behind the EN
  gate, so nothing toggles (safe-state run 6.9 uA against 10 uA; r7c 7.0). An LDE that is high when EN rises seeds one word,
  which is harmless. Not exercised by any bench: EN rising while CKP0 is high (first clock pulse truncated). State is flushed
  within one word, so I rate it low.

### 1.4 Clock drivers (`ctl()`)

* Logic and gating are right: EN = 0 gives CK = CKN = 0; the added inverter pair sits behind the EN NAND.
* Delay shift, measured as the WSTB phase in the stored r7c and r7e full-top runs: tt 625 MHz 0 to +10 ps, tt 480 MHz -15 ps,
  ff 480 MHz -20 ps, ss 625 MHz -60 to -72 ps. This is close to the "within ~60 ps" claim. The small bench `ckgen.py` behind that claim is not
  accurate in absolute terms (it gives 508 ps at ss; the full top has 721 ps), so the full-top comparison is the evidence.
* Levels at pessimistic ss/3.15, measured: CK 0.02-3.18 V (r7c 0.39-2.85), CKN high for 646 ps of 1600 (r7c 411-442).
* What the shift touches: only the crossing from the CKP0 domain (octet O) through the lanes into the slot flops, and the
  WSTB phase at the macro. Measured at nominal ss 625 MHz in quarter mode: lane data changes 510-530 ps before the slot flop
  clock and about 1040 ps after it. A 65 ps shift is harmless there. Flop-to-flop paths inside the CK domain use the same
  unchanged local buffers.
* Fast-corner hold is covered only at 480 MHz (two cases) and at 625 MHz with RCS = 1 on the C x 0.9 netlist. ff 625 MHz with
  RCS = 0 was not run. From the margins above I expect no hold problem, but it is not shown.
* Cost: width 1212.55 -> 1241.23 um (+6,946 um2, +2.4 %), supply current +1.4 mA at tt 625 MHz (44.9 -> 46.3 mA). The
  die-fit ledger delta should be stated in those terms.

### 1.5 The failing case: full rate

Stored evidence for the author's diagnosis: `p0probe/an.out` contains only a Python traceback and the probe waveform is gone,
so the numbers in STATUS (06:25) have no record. I checked the mechanism independently.

* Measured from the stored `ext_f480p0` output: every wrong bit is a single bit taking its neighbour's value, alignment
  correct. That is what a per-bit choice between the current and the previous ring cycle looks like.
* Rerun `a1`: r7e extracted, **ff/22/3.35**, ring 480 MHz, full rate, one word with phase select 3 then one with phase
  select 0, host ngspice with KLU, timing probes on all lanes and all 20 slot clocks.

  | | phase select 3 | phase select 0 |
  |---|---|---|
  | lane data changes, ps after capture CK rise | 1528-1673 | 1575-1717 |
  | slot flop clocks (GCL) | 1833-1945 | 1835-1946 |
  | smallest setup over 20 pairs | 202 ps | 164 ps |
  | word against PRBS7 | 0 errors of 20 | 0 errors of 20 |

  So at ff the mode works, taking the new sample with 164-360 ps of setup. I had predicted a failure at ff by scaling; that
  prediction was wrong and is withdrawn. Phase select 0 arrives 45-100 ps later than phase select 3.
* Reading the three corners together: the slot clock sits half a period plus a gate-delay chain after CK, the data a longer
  gate-delay chain after CK. At 480 MHz the two meet at tt (stored failure; phase select 3 and 5 pass there by less than the
  100 ps by which they are faster). At ff the data is early by 164 ps or more. At ss the data should be late, so the previous
  cycle is taken; that corner was **not simulated** and my estimate cannot tell whether it has margin.
* Reach. Mode: full rate only. The 8:1 multiplexer feeds the lanes only through the `BF` term; quarter and half rate take
  the octet directly, and their measured margins are in 1.4. Phase select: all eight, phase select 0 worst. Rate and corner:
  the coincidence moves with corner and ring frequency; scaling the ff numbers puts it at about 525-830 MHz at ff and around
  425-630 MHz at tt, so no ring frequency in 480-834 MHz is clear at every corner. Supply trim does not help: it moves slow
  and fast dies towards tt, which is where 480 MHz fails.
* The author's conclusion that sizing cannot fix it is right.

**Minimum fix.** Two flops in `wc_lane` that register DF and EF (the multiplexer outputs) on the capture CK, plus one local
clock buffer. The lanes then see a flop output exactly as in quarter mode, whose setup at ss is 510-530 ps at 625 MHz (measured) and about
350 ps at 810 MHz and 780 ps at 480 MHz (scaled from that).
The multiplexer needs to settle within one period: 1.2 ns at ff (measured), about 1.5 ns tt and 2 ns ss (estimates) against
2.08 ns at 480 MHz, so full rate above about 500 MHz ring would also need a faster multiplexer. Cost: one ring cycle of
latency in full rate; the slip-tag alignment (`SLP/SLM`) must be rechecked. Without a layout change the author's workaround
(0.48 Gb/s received in quarter mode at ring 480 MHz, phase picked in the macro) is plausible, but it is unverified: it needs
an interface row to the digital owner and the bench B "1.92" cells, none of which has run.

### 1.6 Slow-corner margin of the slot-enable chain (new)

Measured from the stored probe `r10cap/probe/nom_ss315_r7e` (r7e extracted, nominal ss/32/3.15, 625 MHz, the condition of
gating case `ext_q625_ss`), six words:

| | value |
|---|---|
| E19C (input of the local ELQ19 flop) rises / falls after the CK pin edge | +94 to +98 ps / +114 to +128 ps |
| ELQ19 high time (should be 1600 ps) | 1831, 1916, 1959, 1973, 1977, 2092 ps |
| ELQ19 falls relative to the next CKN rise | -128 to +137 ps |
| ELW (word-load latch) falls before the next CK rise | 274, 195, 153, 141, 133, **14 ps** |
| GW pulses per word | 1 (no runt above 0.2 VDD) |

For comparison, pessimistic ss at 480 MHz: ELQ19 2080-2085 ps for T = 2083 (healthy). Pessimistic ss/3.50 at 625 MHz: ELQ19
two periods, GW twice per word (the failure the author reports).

So the nominal slow corner is already inside the failure mechanism and is held by the latch. The stored 12-word gating run
and the first bench B cell (`ss315_2.5G_r1`, real sampler bank and clocks, 200 bits, arrived 08:38) both pass, and I found
no runt strobe in either stored output. But the margin varies by 260 ps between words, and all of this is capacitance-only
extraction with ideal or replayed clocks and a quiet supply. The author's "slack 0.1-0.2 ns" is a fair summary; the
word-to-word spread and the 14 ps case are the new part.

Consequences, as estimates: ring 675 MHz removes 119 ps and 810 MHz removes 365 ps from that hop, so ss/3.15 is expected to
fail at both; tt at 810 MHz lands roughly where ss is at 625 MHz. A stretched ELQ19 also overlaps the next CKN high phase by
up to 137 ps, which can clock the phase-select and slip shadow registers a second time. That is harmless in quarter mode and
would matter only in full rate, where 480 MHz has 483 ps more slack.

### 1.7 Not covered on r7e

| Gap | Status |
|---|---|
| Ring 675 / 810 / 834 MHz | cases defined in `rune.py`, none run; expected to fail at ss (1.6) |
| 3.50 V | never run at nominal values; mandate section 2 asks for trimmed results and the minimum passing supply |
| ff at 625 MHz with RCS = 0, ff at the maximum supply | not run |
| sf / fs | not run for any capture revision; TSPC flops and the 1/1 um keepers are skew-sensitive |
| Pessimistic values at 625 MHz | fail at 3.15 and 3.50 V (read; consistent with 1.6); pass at 480 MHz |
| Metal resistance | extraction has 0 resistors. CK and CKN are 415-430 fF nets across rows up to 1.2 mm; `pess.py` scales C and adds gate R, not wire R. Against 0.1 ns of slack this is not negligible |
| Real sampler outputs | gating cases use ideal S with 300 / 470 ps delay; the real bank needs about 0.9 ns (tt) to 1.3 ns (ss). RCS = 0 is therefore untested against anything real. Bench B has one pass (ss/3.15, 2.5 Gb/s, RCS = 1); its negative control has not run |
| Real clocks | same single bench B cell |
| LDE phase at ss / ff in the full top | not run |
| Statistical depth | 60-200 bits per case, no jitter, no supply noise |

### 1.8 Verdict and conditions

**GO with conditions.** Reasons: r6, which the chip top binds today, has the double-seeding band (120-180 ps wide, read), no
current evidence and a "fail" record; r7e fixes that and the dead pessimistic clock tree, is DRC / LVS / read-back / precheck
clean, and I found nothing in which it is shown worse than r6. I could not compare the two in full rate or at ss because r6
has no such runs on record.

Conditions:

1. The evidence file is built with the gating list unchanged. `ext_f480p0` stays gating and failing, so the record says
   "fail" and lists it. Moving it to the non-gating set now would be a limit following a measurement.
2. Full rate is recorded as a design miss (risk register, README), with either the two-flop fix scheduled for the next
   capture revision or the quarter-mode workaround verified and agreed with the digital owner. It is not a physical limit.
3. The LDE contract gets numbers: width between T - 250 ps and (word - 2) periods; the forbidden phase per corner; the
   statement that an LDE at the boundary can be dropped.
4. Before the top binds it, run the cases that already exist and cost minutes each: `ext_q625_ss@3.5`, ff 625 MHz with
   RCS 0 and 1, sf and fs at 625 MHz, `q625_ss_lde70/80`, `q675` and `q810` at tt and ss (reported, not gating), and one ss
   625 MHz run of 50 or more words that reports the ELQ19 width and the ELW-to-CK margin per word.
5. The slow-corner margin of 1.6 goes into the README as a known thin margin, with a resistance-aware extraction of CK, CKN,
   the ELQ nets and GW, or an explicit decision that slow dies run trimmed or at eighth rate.
6. Interface rows for the pin moves, WSTB in place of DX / WCLK40, and the area delta.

---------------------------------------------------------------------------------------------------------------------------

## 2. Subject B: method of the r11 benches

### 2.1 Defects and doubts, ranked by how far they can move a pass / fail

**1. No clock-phase negative control has failed.** The declared control (PH2 0.4 UI late) did not fail and was then withdrawn
with the unsettled ring. Its record is still informative: the bench reported D1 at +0.376 UI, eye 115.9 mV, right margin
0.05 UI, so the arithmetic followed the displacement and the control missed the limit by one 0.025 UI grid step. The
replacement (0.5 UI, on the transition) is queued and will fail trivially; it proves less than a graded control. Until one
fails, every real-clock A-INST and A-BER pass is from an unproven instrument. Cheapest check: one run at 0.45 UI, predicted
to fail A-INST by one or two grid steps, alongside the queued 0.5 UI run.

**2. The lock emulation is not where a loop would lock.** Data is placed so that the linear-estimate eye centre (`tau` from
`ch10.pda`) is half a UI after the mean edge-sampler instant. A bang-bang loop locks to the real crossings. The bench
measures the difference (`sl_crossing_mean_ui`) and does not use it: -0.085, +0.022, +0.063 and +0.128 UI in the four settled
real-clock cells, against an A-INST limit of 0.05 UI. In the three cells whose two margins are stored the correction moves
the samplers towards the wider side (ss 2.5 Gb/s: 0.10 / 0.40 would become about 0.23 / 0.27), so those are pessimistic,
but the sign is not guaranteed. Cheapest check: no simulation; place the judged instant at the measured crossing median plus half a UI and
re-evaluate margins from the stored eye profile (store `hts` in the record).

**3. The aperture record is coarser than the margin it supports.** 8 ps steps; direction difference up to 10 ps at tt / ss /
ff and up to 22 ps at pessimistic ss/3.15, which breaks the bench's own "within the 8 ps step" rule (STATUS reports tt only).
It was measured with ideal 60 ps edges at 625 MHz; the real CKP edges are 143-159 ps (10-90 %, measured in `b1`) and duty
0.60-0.63 at 810 MHz. Together with item 2, an A-INST margin below about 0.15 UI is inside the bench's uncertainty.
Cheapest check: shift the data by +/- 0.05 UI in two reruns of a marginal cell and require zero errors; that tests the
margin by decisions and needs no aperture number.

**4. A-BER reads each output at the best of 40 phases chosen afterwards.** A pass shows that decisions exist, not that the
capture can take them. The chosen phase is the useful by-product: 0.775 P after the decision at ss 2.5 Gb/s, about 1.36 ns
after the clock edge, so RCS = 0 cannot work there and RCS = 1 has roughly 0.25 ns (estimate). Bench B is the real test and has one
cell. Related: the expected bit is `floor()` of the sampler's own position, so a sampler displaced by more than half a UI is
judged against the neighbouring bit and can pass; use a fixed bit index per sampler.

**5. `padc.json` is a linear estimate that reads high.** At ss/3.15, 3.24 Gb/s, T3 it gives 98.3 mV and 0.438 UI; the
transient of the same cell gives 87.5 mV and 0.35 UI. At 2.5 Gb/s the heights agree (108.0 / 108.3) and the width is again
0.10 UI larger. The estimate has 1/16 UI resolution and is not monotonic in added C. Every cell at 0.25-0.31 UI or within
12 % of 60 mV is unsupported: that is all pessimistic-corner entries at 3.125 and 3.24 Gb/s, including "3.50 V rescues" and
"ok to +0.6 pF". The claimed "within 2 %" calibration does not hold on the new pad. Cheapest check: one transient of
pessimistic ss/3.50, 3.24 Gb/s, T3.

**6. Clock items that can flip the 810 MHz cells.** (a) The declared clock-only gate (duty 0.40-0.60) is not evaluated by
any code and `clk.json` carries no verdict; ss/3.15 at 810 MHz has duty 0.597-0.631 and misses it on six of eight phases.
STATUS reports the number but not the miss. (b) Trim range against need at ss 810 MHz is 60.6 against 54.0 ps on phase 6.
The extra chip-level loads on PH0 and PH1 (noted in STATUS, not in the calibration), the 50 fF couplings between ring phases
inside the capture (lumped to ground in bench A) and ring mismatch are not in that 6.6 ps. (c) Pessimistic cells replay the
nominal-ss ring, which is optimistic for duty, position error and for whether 810 MHz is reachable at all (VCTRL is already
1.74 of 2.69 V nominal). Cheapest check for (c): one calibration run with the pessimistic ring netlist at ss/3.15, 810 MHz.

**7. Replay inputs.** `cal.py` writes the table before it judges it and `rc11.py` does not read the `ok` flag: `tt480`,
`tt675` and `ss315480` fail the author's own 0.5 ps settling limit (1.0-1.1 ps) and would be used silently. One picosecond
is harmless physically; either enforce the limit or restate it before those cells run. The table is recorded with the trim
cell at code 0 and replayed as an ideal source, so any dependence of the ring phase on trim code, and all kick-back from the
samplers and capture into the ring, is absent. Calibration and replay use different files for the trim cell (`l8/gen` and
`final/gen`); the trim owner shows they are the same circuit. The replay uses the capacitance-only trim extraction although
`ptrim.ext-r-typ.spice` exists.

**8. Bench B.** Data and LDE are placed from the lumped-load clock delays, and the run with the real capture does not record
the actual CKP instants, so the placement is unverified in the very run that changes the load. The stimulus is an ideal
120 mVppd square wave, which is right for a capture-timing bench but says nothing about eye margin. Only RCS = 1 cells are
queued. The one pass so far has no failed negative control yet.

**9. Solver options.** `.option klu`: the comment in `rc11.py` says "validated against the default solver"; the only record
is a speed test in which both runs ended in an analysis error, and `tran.json` has no like-for-like pair (the default-solver
rows use the old pad). The one comparison is in `jobsQ.txt`, which is no longer run. Risk is low; the check is one 150 s
job. `.option rshunt=1e13` is harmless at these node capacitances and time scales, but it is applied to every deck and hides
a floating island in the pad model.

**10. Records.** `padr_ohm = 40` is written into every `tran.json` row although the value is forced to 0. After the pad was
republished the "gating pad" was not re-declared (typical or high metal). BER is 104-144 deterministic decisions with no
noise, offset or jitter: a functional check only.

**11. Limits before runs.** The limits block is dated 04:50. The repository does not track `r11/`, so the time cannot be
confirmed. Four ring tables (04:39-04:45, later withdrawn) predate it, including ss/3.15 810 MHz with duty 0.61-0.63. The
duty limit was therefore written knowing that this cell would miss it, which is the opposite of self-serving. The first
chain run is 05:04. I see no limit relaxed after a result. The one change (pad model) was forced from outside and tightens
nothing or loosens nothing by itself, but see item 10.

### 2.2 The slow-corner 3.24 Gb/s cell: hardware or read-out?

**The sampler bank as modelled, not the read-out.** Rerun `b1` (the owner's `rc11.py` with two lines changed so that the
waveform is kept) reproduced the stored row exactly: 87.5 mV, 0.35 UI, 79.0 mV at the instants, margin 0.075 UI, 36 wrong
of 110.

* The differential SL voltage at every data sampler's actual instant has the expected sign in all 104 judged decisions, with
  40-82 mV magnitude. The expected-bit bookkeeping is right.
* D1 never changes state in the whole 46 ns (stuck high), E1 never (stuck low), E3 never (stuck high). D0 makes 11 transitions
  where 12 are due in the judged window, with five errors at best; D2 and D3 make 6 where 11-12 are due.
* Scanning the read phase from 0 to 2.5 periods in 1/80-period steps, no sampler has an error-free phase, separately or
  together (best common phase: 34 of 104).

The STATUS explanation ("clock-to-output about one ring period") does not describe this: the outputs are not late, they are
missing. The cause is not isolated by this run. Candidates visible in it: CKP low time 456-499 ps (duty 0.60-0.63), 143-159 ps
edges, 40 mV half-amplitude. Cheapest decisive check: the same cell with `clock=ideal` (50 % duty); clean means ring duty or
trim-cell edges, not clean means sampler speed at ss/3.15, and then ss/3.50 decides whether trim rescues it.

### 2.3 Which stored results I would use

| Result | Use? |
|---|---|
| Ideal-clock proof row and the `sl3p` control | yes |
| Eye height and width at SL (A-EYE) in the settled real-clock rows | yes; nearly independent of clock detail (295.1 against 297.2 mV) |
| Ring tables with `ok = true`; `clk.json` trim range, spread, duty | yes as measurements, with item 6 for range margin |
| `ss315_3.24G` FAIL | yes, as a sampler-bank failure (2.2) |
| A-INST where the margin is 0.15 UI or more (`ss315_1.25G`) | yes |
| A-INST at 0.075-0.125 UI (`ss315_2.5G`, `ss315_3.24G`, `ssp315_2.5G`) | no, in either direction (items 2, 3) |
| A-BER passes as statements about the system | no; they show the sampler decides (item 4) |
| `capb.json` `ss315_2.5G_r1` | provisionally; control pending (item 8) |
| `padc.json` at tt, ss, ff with width 0.375 UI or more | as trends |
| `padc.json` pessimistic corners at 3.125 / 3.24 Gb/s | no (item 5) |
| Aperture at pessimistic ss/3.15 | no (22 ps direction difference) |
| Anything under `unsettled/` | no |

---------------------------------------------------------------------------------------------------------------------------

## 3. Reviewer reruns

| Job | What | Wall time | Result |
|---|---|---|---|
| `a1` | r7e extracted, ff/22/3.35, ring 480 MHz, full rate, phase select 3 then 0, 142 ns, host ngspice-42 with KLU | 12 min | both words error-free; setup 202 ps (psel 3) and 164 ps (psel 0); CK 475 ps after CKP0 |
| `a2` | `wc_cnt` carved from the r7e extraction, ff/22/3.35: (a) 625 MHz, LDE 1.0 T, 120 phases at 0.5 ps; (b) 480 MHz, LDE 0.85 T, 106 phases at 20 ps | 1 min | (a) one dropped LDE at 74.34 ps, 119 single; (b) one dropped LDE at 76.35 ps, 105 single |
| `b1` | `rc11.py tran ss315 3.24 T3`, real clocks, waveform kept | 5.5 min | stored row reproduced exactly; three sampler outputs stuck, no error-free read phase |

`a1` and `a2` use the frozen PDK copy and the host simulator, not the docker simulator of the gating flow. Files:
`a1/a1_ff.json`, `a2/a2.json`, `b1/wave_ss315_3.24G_T3_padtyp_an.json`, with scripts and compressed waveforms beside them.

## 4. Could not verify

* The numbers of the author's full-rate diagnosis at tt (no stored record), and full rate at ss (not simulated).
* Whether r6 is better or worse than r7e in full rate or at the slow corner (no r6 runs on record).
* Width of the band in which an LDE is dropped: below 1 ps at one period wide; at 0.85 T and 480 MHz only "below 40 ps".
* Whether a doubled INJ can occur at the boundary (not seen in 120 phases).
* r7e above 625 MHz, at 3.50 V, at sf / fs, with metal resistance: nothing run, my statements are estimates.
* Why the sampler bank fails at ss/3.15, 810 MHz.
* KLU against the default solver; the time at which the r11 limits were written.
* The cell-level and pessimistic-probe figures in `r10cap/STATUS.md` that I did not recompute (r6 / r7c band widths, the
  pessimistic error counts) are read, not rerun. The r7c / r7e clock levels and delays, the enable timing and the lane margins
  are measured from the stored waveforms.
