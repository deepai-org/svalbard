# Consolidation pass 2: hardware sharing review (2026-11-09)

This is an analysis only. No RTL, block or assembly files were changed. The
sources are `spec/analog-architecture.json`, `spec/tapeout-readiness.json`,
`spec/register-map.json/.md`, the per-family `generated/*-evidence.json` and
`*-layout.json`, `integration/core_bias.py`, `integration/pt_chip.sv`,
`rtl/pt_digital.sv`, and the timing and wired_rx READMEs as of today.
Recommendations are ranked by **physical area and instances removed**, as the
user clarified. Flow and script consolidation comes last and has low priority.

## 0. Context that sets the priorities

- **Area is not the binding constraint.** Group ceilings minus area used are:
  rf 1.38 mm², timing 0.73, wired 0.60, reserve 0.41, converters 0.34 and
  digital 0.01 mm². About 3.5 mm² of analog headroom remains. Analog sharing
  therefore buys decap/debug area and fewer instances to verify. It does not
  make the chip fit.
- **The binding constraints are elsewhere:** the digital macro is at
  **8177/8192 flip-flops (15 spare)** with nominal setup slack of −6.70 ns.
  The wired RX capture (`pt_wrx_cap`) fails extracted above 480 MHz. The CDR
  fails extracted tracking. `pll_ring` r6a HOLD fails its criterion. Any
  sharing that needs new register bits has to be paid for in flip-flops.
- **Pads are not scarce.** 19 spare provider sites already carry the debug
  set. No pad sharing is recommended (see section 4).

Measured block areas (µm², from evidence/layout JSON) used below:

| Block | µm² | Instances | Total |
|---|---:|---:|---:|
| bbfilter_i/q | 406,239 | 2 | 812,478 |
| adc_i/q | 259,036 | 2 | 518,071 |
| wired pads (2 variants) | 283,003 / 240,599 | – | – |
| wiredtx | 198,723 | 1 | – |
| reference pad assembly | 127,170 | 1 | – |
| dac_i/q | 126,117 | 2 | 252,234 |
| refbuf | 118,270 | 1 | – |
| detect | 96,819 | 1 | – |
| **pll_ring (r6a)** | **80,541** | **3 planned (tx, cdr, host)** | **241,624** |
| rfdriver | 78,468 | 1 | – |
| rxmix_i/q | 76,238 | 2 | 152,476 |
| **clk_obs** | **73,118** | **2 (CLK_OBS, WCLK_OBS)** | **146,236** |
| cdr analog cell | 51,673 | 1 | – |
| polyphase (fails extracted) | 39,329 | 1 | – |
| lo_ext | 39,169 | 1 | – |
| slicer (compact layout) | 28,129 | 1 | – |
| wordclk | 24,969 | 1 | – |
| txmix_i/q | 21,788 | 2 | 43,576 |
| ctle / termination | 21,437 / 21,395 | 1 / 1 | – |
| vco_replica | 21,056 | 1 | – |
| lna | 19,639 | 1 | – |
| wrx_cap | 15,577 | 1 | – |
| clockmux | 15,238 | 1 | – |
| diff_clk_rx | 14,671 | 4 | 58,684 |
| prescale | 12,627 | 1 | – |
| bias banks 8/5/4/3/3 + root | 14,339 / 8,964 / 8,074 / 4,210×2 / 3,952 | 6 | 43,749 |
| bb_tap | 9,978 | 3 | 29,934 |
| ring_osc / aosc | 9,520 / 5,097 | 1 / 1 | – |

## 1. Do now (before freeze), ranked by area and instances removed

### R1. Three `pll_ring` instances become two, sharing the host_follow role. −1 instance, −80,541 µm²

**Today.** `core_bias.py` books `pll_ring_tx`, `pll_ring_rx` and
`pll_ring_host` (plus `lc_vco_reserved`), so there are three rings of
80,541 µm² and 224 devices each. Their roles:

| Mode | Ring TX (line) | Ring RX (CDR) | Ring host_follow |
|---|---|---|---|
| RF (external LO) | idle | idle | H2D → N=4 → prescale (converter/host clock, warm-hop) |
| USB | 480 MHz TX | 480 MHz full-rate RX, locked to the **same reference** | 100 MHz SDR host-follow |
| Wired full rate (≤810 Mb/s) | line rate | line rate, locked to the same reference (8× oversample, digital phase pick) | optional (`wire_host_source`) |
| Wired half/quarter | line rate | dual-loop CDR tracking | optional; default `line_divided` |

In full-rate modes, USB included, the TX ring and the CDR ring run at the
same frequency from the same reference. The CDR ring does no tracking there:
the digital phase pick does. Only half/quarter-rate wired RX needs a
separately steered ring.

**Change (netlist and floorplan).**
1. Delete the third instance (`pll_ring_host`) and its bias-bank output.
   Keep the pll bias bank as `pt_bias_bank4`, because core-bias routing has
   already passed. The two freed outputs (host and `lc_vco_reserved`) become
   ATB-observable spares.
2. **Ring L (line)** keeps today's TX connections (wiredtx serializer,
   wordclk, detector capture clock). Add a **gated fan-out of PH0..PH7 to the
   capture block** through a fast-cell 2:1 select per phase at the `pt_wrx_cap`
   CKP inputs (Ring L or Ring C). Full-rate RX, USB HS included, then
   oversamples off Ring L.
3. **Ring C (CDR / host)** keeps its CDR connections (cdr cell `VCTRL`/`REF`,
   capture via the 2:1 select). Add a **reference select at its REF input**
   (wired REF from clockmux `PREF`, or `H2D_CLK`) and connect **PH0 → prescale**
   (`HF`). This is the host_follow role. It is available in RF, USB and
   full-rate wired, where Ring C is no longer needed for RX.
4. Register map: replace the single stale `consolidation.pll` bank with
   `ring_l {en, feedback_n, hold}` and
   `ring_c {owner: off|cdr|host_follow, feedback_n, hold}`, plus
   `wrx_cap.ckp_source` (1 bit). Rule: `ring_c.owner=host_follow` and
   on-chip half/quarter CDR are mutually exclusive.

**Added hardware.** 8 fast-cell clock 2:1 selects with gating at the capture
CKP inputs, one 2:1 select on Ring C REF (≤160 MHz path) and one gated input
on prescale. Estimated 3–6 k µm². Net saving is about 75 k µm², one ring and
5.0–7.9 mA in any mode that would have run three rings.

**Loading and bandwidth cost.** Each Ring L phase gains one gated buffer input
(about 5–10 fF) plus the wire to `pt_wrx_cap`. Ring port-phase error is
already 9.0–10.8° in r6a, so put a **matched dummy load on every phase** to
keep the spacing. The full-rate RX path tolerates phase-spacing error because
the digital phase pick chooses the best sample. The CKP select adds one mux
delay before capture, which is the block failing above 480 MHz. Full rate runs
at 480 MHz, the only rate where capture passes extracted (quarter 480 MHz
0/200, full psel 5 0/60), so the select must be **in the same compact-cell
row as `pt_wrx_cap`** and included in its extracted rerun.

**What is lost.** Only `wire_host_source=host_follow` together with the
on-chip half/quarter CDR. The default is `line_divided`, and that combination
remains possible with the `WCLK_IN` CDR fallback (Ring C free). **Precondition:
the digital/clock owner confirms that no selected wired rate requires
host_follow concurrently with on-chip half/quarter CDR.** If one does, drop R1.

**Fallbacks and observability.**

| Ring fails | Fallback |
|---|---|
| Ring L | Wired TX → `WTX_EXT` (unchanged). Full-rate RX → Ring C via the CKP select (today's arrangement). |
| Ring C | Half/quarter CDR → `WCLK_IN` (unchanged). RF converter/host clock → `rf_host_source=carrier_divided`, the register default, which needs no ring. |

Both rings stay on `freq_count_a/b` sources and `ATB_VCTRL`. No path loses its
fallback.

**Why do it now.** The full-chip floorplan does not exist yet. The register
map currently has one control bank for three rings (see F1), so it needs
fixing anyway, and fixing it for two rings costs fewer flip-flops than for
three. Cost: about 7 stored bits (14 FF with shadow/active), so it needs R3's
reclaim first.

**Touches.** Timing (ring fan-out and dummy load), wired_rx (capture CKP
select), integration (instance removal, core_bias consumer list), digital
(register fields). Priority **P1**.

### R2. CDR: keep one hold/handover mechanism, not two. −part of the cdr cell (est. 5–15 k µm²)

`pt_cdr` (51,673 µm², 125 devices) has its own `freq_hold` path:
FBCK-synchronized REF gating (`hq*` flops), `REF_IN`→`REF_PLL`. `pt_pll_ring`
r6 added `HOLD` for the same job, which keeps the PFD in reset and floats
VCTRL. Both currently fail by about the same amount: cdr handover +1430 ppm
(r5) and 5883 ppm with r6a; ring HOLD +1545 ppm step and 110 ppm/10 µs. Two
mechanisms doubles the verification for one function, and the README lists
"use of `pt_pll_ring.HOLD`" as open.

**Change.** Pick one. Keep the `pll_ring.HOLD` version because it is inside
the one shared ring design and is also used by the host_follow role. Delete
`pt_cdr`'s REF-gating section, leaving the CDR cell as the BB pump + IB_PLL
switch. The area saving is an estimate; exact device count to be taken by
wired_rx.

**Fallback.** Unchanged (`WCLK_IN`). Observability: the HOLD state goes on
`WDBG_OBS` (`cdr_rx_state*`).

**Touches.** wired_rx (cdr cell), timing (HOLD criterion). Priority **P1**,
because the CDR is being reworked anyway.

### R3. Reclaim digital flip-flops before adding any field. Target ≥64 FF

The macro has 15 FF of headroom. The storage plan sums to 8094 of 8192 bits,
and shadow+active control is 2038 of those. Candidates, in order of safety:

| Item | Bits now | Proposed | FF saved (×2 shadow/active) |
|---|---:|---|---:|
| `cdr.config.acquisition_timeout_ui`, `scheduled_quiet_limit_ui` | 24 + 24 | 4-bit mantissa + 4-bit exponent each | 64 |
| `cdr.config.nominal_rate_khz` | 22 | rate-table index (the rate table has 9 entries) + 8-bit trim | ~10 |
| `freq_count_a/b.target` | 16 + 16 | keep (lock observability) | 0 |
| Stored fields for retired hardware (`quadrature.*` already unstored; check `clocktree.config.*` 57 bits against what `pt_clocktree_slow.sv` actually consumes) | – | unstore any unconsumed field (P2-2 rule) | TBD |

This is an ABI change through `rtl/gen/pt_regmap.py`, so it belongs to the
digital agent. It is required before R1's fields can be added. Priority **P1**.

### R4. `clk_obs`: one parameterized design, smaller second instance. Est. −20–35 k µm²

There are two instances of 73,118 µm² each. A single shared instance is
already rejected because a GHz clock would cross the die, and that still
holds. But `WCLK_OBS` uses only 3-bit source / 3-bit divider fields
(8 sources, ÷1..128), and the timing README notes that `clk_obs` itself only
supports 8 inputs and ÷2^0..7 while `debug.clk_obs` asks for 4+4 bits.
Parameterize the generator for input count and divider depth: CLK_OBS gets 16
inputs and ÷2^15 (closing the open register mismatch), WCLK_OBS gets 8 inputs
and ÷2^7. The saving depends on how much of the 73 k µm² is mux/divider and
how much is the pad driver. Timing should report that split first. Fallback
and observability are unchanged: `DBG_OBS`/`WDBG_OBS` digital muxes and the
frequency counters still observe every clock. Touches timing. Priority **P2**.

### R5. Decap: one shared pool on the unswitched rail, sized from freed area

The 1 nF of MIM (about 1.1 mm²) has no home, because MIM over the digital
macro does not apply (flip-flop arrays, Metal5 conflict). Put **one shared
MIM pool on the always-on core VDD next to the island-switch row**, using the
R1/R4 savings plus rf/timing headroom. Add only small local decap behind each
island switch, sized to the switch inrush limit. A switched-off island needs no
decap, and large decap behind a switch slows power-up and increases inrush.
This adds no SPOF. A MIM short in the shared pool is a supply short, so split
it into 4–8 banks, each with a metal fuse strap or a separate via strap that
can be FIB-cut. Touches integration. Priority **P2**.

## 2. Earlier decisions re-checked against the new evidence

| ID | Status | Finding |
|---|---|---|
| P3-2 one ring design | **Holds** | Every ring role has a non-ring fallback (`WTX_EXT`, `WCLK_IN`, `carrier_divided`), so a common-mode ring design defect is not a SPOF. Port-phase error regressed 4.6–5.5° (r5) → 9.0–10.8° (r6a). This matters for half/quarter CDR. |
| `wired-rate` (ring always 480–810 MHz) | **At risk** | `pt_wrx_cap` passes extracted only at 480 MHz. 625/810 MHz give 31–47/200 errors, in word slots 0–3 and 16–19 (slot-0 restart / `GW`), and extracted current is 2.4× schematic. 8 of the 9 rates in the table need ring ≥625 MHz. The sharing decision is fine. Capture needs a rebuild, not a different split. |
| `wired-cdr` | **Fails; fallback record wrong** | `wire_cdr_external_clock` and `wire_cdr_fpga_oversample` list `shares_failure_with: [slicer]`, but both also pass through `pt_wrx_cap` (`run_fallback.py`: `WCLK_IN → slicer → pt_wrx_cap`, half mode). Half 625 MHz fails extracted 31/180. **Add `wrx_cap` to `shares_failure_with`.** The only RX route independent of the capture is `wire_wmon_scope` (`bb_tap` → `WMON`). |
| P3-3 / P3-4 | **Update** | 2026-11-09 decision: the first die does not qualify an autonomous LO, and LC VCO no longer simulates. `polyphase` (39 k µm²) fails extracted. Keep it as a learning structure (no scope cut), but stop booking a bias output (`lc_vco_reserved`) and area as a functional route. |
| P2-5 bias trunks | **Holds** | Core-bias routing passed: IR VDD 5.5 / VSS 8.8 mV, via-cut use ≤0.19 at 85 °C. The root is a SPOF covered by ATB force (core waiver). **Do not merge banks.** The debug bank3 → rf bank8 merge saves only about 4.2 k µm², would put debug taps on the rf trunk, and would require re-running routing that already passed. |
| P2-6 / P3-6 one pattern gen/checker | **Sharing holds; stated effect stale** | "Closes timing at ss" is no longer true for the macro (−6.70 ns nominal). The shared generator is fine. The FPGA is the fallback generator/checker. |
| P3-7 two freq counters | **Holds; do not merge** | Wired mode needs TX lock status and CDR FLL handover at the same time. `status.pll_lock` reads 0, so these counters are the only lock observation. |
| Item 7 `bb_tap` ×3, item 6 `diff_clk_rx` ×4 | **Hold** | Already one design each. |
| ADC/DAC, I/Q, slicer/ADC comparator sharing | **Rejected still holds** | Turnaround and common-mode reasons are unchanged. |

### Findings needing a record fix (no hardware change)

- **F1. The register map does not match the clock hardware.** One
  `consolidation.pll` bank (`owner`, `feedback_n`, `output_divider`,
  `phase_tap`) is documented as driving `NS16..NS128`, `W1..W10`, `PH1..PH8`
  and `rtl/pt_pll_lock.sv`. The ring has `N4/N8` and `PH0..PH7`, and the
  lock is reserved (reads 0). There is no `HOLD` field and no per-instance
  control for 3 (or, after R1, 2) rings. Rule 26 still refers to a "shared
  pll". The fix belongs to the digital agent, with R1.
- **F2.** Add `wrx_cap` to the CDR fallback routes' `shares_failure_with` in
  `tapeout-readiness.json`.
- **F3.** `consolidation-pass.md` still lists P3-4 as "under evaluation".

## 3. Not worth it

| Candidate | Why not |
|---|---|
| Sharing the `WCLK_IN` and `WTX_EXT` pad pairs and `diff_clk_rx` (−2 pads, −14.7 k µm²) | Pads are not scarce. Both wired fallbacks could no longer run together, which breaks full-duplex debug. |
| Merging `CLK_OBS` and `WCLK_OBS` into one instance | GHz routing across the die (already rejected). Use R4 instead. |
| `prescale` folded into `wordclk` (−12.6 k µm²) | prescale is TSPC for 2.5 GHz /16 (autonomous-LO feedback) and wordclk is ≤810 MHz. This would lose the P3-4 learning path. |
| `vco_replica` replaced by an open-loop ring (`ATB_VCTRL` + `HOLD`) | Already rejected. It is also the only ring not inside a loop, which is useful when HOLD itself is suspect. |
| Merging bias banks | See P2-5 above. |
| Shrinking the third ring's bias bank output after R1 | The bias routing has passed. Spare outputs are free ATB observation points. |
| One freq counter time-shared | See P3-7. Lock observability would become sequential. |
| Merging `cdr` into `pll_ring` | The ring is shared by three roles, and CDR-only pump hardware would load every instance. R2 is the right size of change. |

## 4. Pads

No changes. Shared protection P3-10 (BB_I+BB_Q, WTX_EXT+WMON) still holds.
Each spare site already carries a debug function, and the stretch goals depend
on the two wired pairs staying dedicated.

## 5. Verification and flow code (low priority, after freeze)

- There are five separate DRC/LVS/extract drivers: `timing/timing_flow.py`,
  `wired_rx/wrx_flow.py`, `rf_rx/rfrx_flow.py`, `wired_tx/tools.py` and
  `converters/lib/convkit.py`, plus `rf_tx/layoutlib.py` and `pads/layout.py`.
  Extract one `analog/common/signoff.py` with `klayout_drc`, `netgen_lvs`,
  `magic_extract` and `sha256_tree`.
- The 43 evidence files use three spellings for output hashes
  (`generated_hashes`, `artifact_hashes`, `output_hashes`), and `area` is
  present only in some. Freeze one schema and have `check_tapeout_readiness.py`
  validate it. This one is worth doing before freeze, because readiness reads
  these files.
- `verification/` has 373 `run_*.sh` one-offs, most of them historical screens
  (adc/sar/reference/pump/vco). Move them into a `verification/archive/` index.
  Leave the Make targets alone until freeze.
