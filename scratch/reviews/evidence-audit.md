# Evidence audit of the published blocks

Audit of 2026-11-18 on the working tree at commit `be37cc6` plus the owners' uncommitted files. Scope: every block
with a GDS that the chip top binds (`integration/top/masters.txt`), that is registered for block DRC
(`verification/kl_block_drc_blocks.json`) or that was in the read-back LVS inventory: 87 GDS. The auditor changed no
block and no evidence record. Rules audited against: `MANDATE.md` section 4 and `spec/block-deliverables.md`.

**Result: the published status is not supported for 31 of the 83 GDS that the chip uses.** The layouts themselves are
in better shape than their records: 85 of 87 GDS pass the precheck DRC and antenna decks today, and every GDS that
has a flat netlist matches the netlist the chip top binds (four pad families apart from one modelled diode in the
reference; the QVCO top cell and the routed bias assembly have nothing to compare against). What fails is the evidence: records that describe an earlier layout, records that say
fail, pass states their own numbers contradict, and blocks with no record at all. No block of the chip meets the
bench rules: sf and fs corners appear only for three small bias cells and, at the nominal point, for the USB
pre-driver; every extraction is capacitance-only; real neighbours are the exception (`pt_usb_txdrv`, the rf_tx chain
behind `pt_rfdriver`, `pt_char_atb` through the test-bus cells).

## 1. Findings that need a decision or an owner now

1. **Pad ESD evidence is void if the pads owner's resistance extraction is right.** Every pad HBM and CDM pass was
   simulated on capacitance-only netlists. The owner's resistance-aware extraction of the shared protection shell
   (`scratch/pads-core/hsfix/final_part1.md`, finding 1) puts 20–25 Ω (typical metal; 50–65 Ω high) between the bond
   pad and the ESD diodes, through single via cuts: the unchanged 2 kV HBM bench then gives 32–33 V at the bond pad
   against the 6.0 V limit, and 1.33 A through one 0.26 µm cut. The same network measures 25–26 Ω in the reference,
   USB and wired-transmit families. One tool, not reviewed, not yet reproduced with a second extractor. The risk
   register carries this as PAD-11 at score 12 with "unconfirmed 16–17 Ω": the row understates what is now measured.
   Affects all eight pad cells.
2. **The published `pad_hspad` cannot terminate at 100 Ω.** With metal resistance extracted the published cell gives
   129–154 Ω at the last trim code (200–225 Ω at high metal resistance): no code reaches 100 Ω
   (`scratch/pads-core/hsfix/STATUS.md`). A fixed cell is staged, unreviewed. PAD-09.
3. **The TX ring in the published layout is not the committed ring.** `pt_pll_ring_core` (instance `pll_tx`) was laid
   out on 11 Nov with ring cell `ct_ring9` as it then was. Commit `e7b4d14` (13 Nov) changed one device of that cell
   (`XC0b`, gate moved from `ENB` to `P1`); `pt_pll_ring` (the CDR ring) was rebuilt with it, `pt_pll_ring_core` was
   not. The GDS read back from disk matches its own extracted netlist and fails LVS against the committed schematic
   on exactly that net pair (`ENB` 25 against 24 gates, `P1` 3 against 4). The block has no evidence record, so
   nothing else would have shown it. The ring owner must say which version is intended; if the change is the
   start-up or symmetry fix it looks like, the TX ring does not have it. The phase-spacing measurements of WT33 were
   taken on this layout.
4. **The QVCO has no evidence and no top-level LVS.** `lcvco-evidence.json` hashes `qvco.spice`, the previous cell,
   at schematic level with an analytic spiral; the published GDS is `pt_lc_qvco5`. The core subcell matches its
   netlist (974 devices); the top cell cannot match `qvco5.spice` because the two spirals extract as metal shorts
   between IP/IN and QP/QN, so the spiral hookup is verified by nothing. The one surviving real-load run
   (`scratch/lo-ap4/q7/env.log`) gives 2.488 GHz against a 2.558 GHz limit. Eight more LO and clock cells bound at
   the chip top have no evidence record either; their scratch results contain fails that no record or README lists
   (`pt_obs_pre4` fails 20 of 24 corners on swing and duty, `pt_clk_obs16` draws about 200 µA at reset).
5. **`pt_adc_i` fails the antenna deck** (ANT.16_i_ANT.5 × 7; it has no antenna diodes, its twin `pt_adc_q` has 8)
   and has no precheck record. Known as SG-7; still on disk. All four converters are in addition `staged` at the chip
   top: the published cells have the old clock pins, the staged replacements have no evidence record.
6. **Twenty-one GDS have no precheck DRC record** (20 of them are in the registry, so
   `make transceiver-block-kldrc-check` reports 49 of 69 and exits non-zero), and 19 published GDS are not in the
   registry at all (list in section 6). All of them were run here; all are clean except `pt_adc_i` and the
   superseded `attached_tx_buffer` (PP.2 × 10). The
   registry entry `pad_rf_pair` names a top cell that is not in the GDS (`rf_protected_pad_pair`; the cell is
   `pad_rf_pair`), so its make target fails; the entry `core_bias` points at the older of two builds.
7. **The committed tree cannot regenerate two published netlists.** `rf_rx/netlists.py` at HEAD writes the pre-rework
   `bbfilter_i/q.spice` (1130 differing lines); the hook to `bbf_fd.py` exists only in the owner's uncommitted copy.
   `run_rf_rx.sh` from a clean checkout would overwrite the published filter netlist with the old design.
8. **`make transceiver-chip-assembly` cannot start**: `verification/chip_assembly/inventory.py` still binds the
   deleted `polyphase` GDS and netlist (`FileNotFoundError`, confirmed by running stage 1). `netlist.py` and
   `floorplan_rules.py` in the same directory still route the LO through it.

## 2. What was run and what was only read

Run here (two heavy jobs at a time, `OMP_NUM_THREADS=1`), scripts and result files in `scratch/evidence-audit/`:

- **DRC**: `verification/kl_block_drc.py` (precheck decks, main and antenna, KLayout 0.30.9, deep mode) on each of
  the 87 GDS as found on disk, without `--publish`. Bench proof: `pt_aosc` clean, `pt_adc_i` reproduces its known
  7 antenna violations.
- **LVS**: each GDS copied to an empty directory, read into a fresh Magic 8.3.623, extracted, and compared by netgen
  1.5.316 (PDK setup, property comparison on) and by a device census against (a) the netlist the chip top binds and
  (b) the committed schematic from `git HEAD`, local includes inlined, standard-cell library added for the
  converters. Antenna diodes are added by the layout generators and are not in the schematics: they were removed from
  both sides for (b) and are counted in the table. Bench proof on `pt_aosc`: the published pair matches; a resistor
  length changed from 9.4 to 9.0 µm in the schematic and a transistor width changed from 2.0 to 2.1 µm in the bound
  netlist both fail (property errors and census). 67 904 devices read back.
- **Netlist reproduction**: the schematic generators of rf_rx, rf_tx, converters, wired_rx, wired_tx,
  characterization and the bias cells were run in an export of HEAD and their output compared byte for byte with the
  committed `<block>.spice`; rf_rx and wired_rx also in a copy of the working tree. As samples of layout
  reproduction, `pt_txsum` and `pt_aosc` were rebuilt from HEAD: the layout databases are identical to the published
  ones apart from the timestamp (GDS bytes differ, as the converters flow already notes for Magic). Timing netlists
  are hand-written sources; pads, island cells, `por`, `pt_core_bias`, the regulator and the decap tile were not
  checked for reproduction.
- **Freshness**: every hash in every `<block>-evidence.json` compared with the file on disk and with the committed
  version of that file; evidence commit date against the last commit of the block's netlist and scripts; GDS
  modification time against the evidence commit.

Read, not run: bench realism and the trace from evidence numbers to surviving outputs (evidence JSONs, bench code,
`scratch/<family>/` result files, READMEs and owners' status notes), by five read-only sub-audits whose main claims
were spot-checked against the files. No simulation was rerun, so no number in an evidence file is confirmed or
refuted by this audit; where a surviving output contradicts a record, the table says so.

Moving targets: `lna.gds` was rewritten by its owner twice during the audit (the row is for the file of 18 Nov
05:05) and the three `char_rffet` GDS were rebuilt at 04:45 (commit `be37cc6`; rows are for the new files).

## 3. Per-block table

Columns. **Netlist reproduces**: the committed generator writes the committed schematic (yes / no; "hand-written
source" where the `.spice` file is the source). **DRC**: violations main / antenna on today's GDS; "no record" = no
`-kldrc.json` next to the GDS. **LVS**: against the bound netlist and the committed schematic. **Evidence
freshness**: date of the record and whether its hashes still match. **Bench realism**: "ext" = extracted netlist,
"C-only" = no metal resistance, "12c" = tt/ss/ff × 22/32 °C × 3.15/3.35 V (no sf, no fs), "ideal" = ideal sources,
supply, bias and lumped loads. **Verdict**: "not supported" = at least one of the failures listed in section 4;
"physical checks hold, evidence partial" = DRC and LVS pass and the record matches what is on disk, but the bench
rules are not met.
**RF receive**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `lna` | pt_lna (published) | yes | 0 / 0 | bound netlist: match; committed schematic: **no match** (matches the uncommitted one) | **stale** committed record (11-10): recorded lna.mag, lna.ext.spice, lna.spice differ from what is on disk. Uncommitted record: recorded lna.mag, lna.ext.spice, lna.spice differ from what is on disk | ext, C-only; 12c for sweep and match, chain NF at 2 points; ideal balun, bias and square LO, pad = 0.5 pF, no package | **not supported**. Evidence is of an older netlist and layout; own chain NF 9.87 dB tt / 11.53 dB ss against 4.1; IIP3 not simulated; states still read pass; README says NO-GO |
| `rxmix_i` | pt_rxmix_i (published) | yes | 0 / 0 | bound netlist: match; committed schematic: **no match** (matches the uncommitted one) | **stale** committed record (11-10): recorded rxmix_i.mag, rxmix_i.ext.spice, rxmix_i.spice differ from what is on disk. Uncommitted record: recorded rxmix_i.mag, rxmix_i.ext.spice differ from what is on disk | ext, C-only, no gate R; 12c for gain/current/offset, RF metrics at tt; ideal 300 ohm source, ideal square LO, 1 pF load | **not supported**. Evidence is of an earlier layout; IIP3 and ss NF rows fail while clean reads pass; current limit raised 1.0 -> 3.1 mA after the measurement |
| `rxmix_q` | pt_rxmix_q (published) | yes | 0 / 0 | bound netlist: match; committed schematic: **no match** (matches the uncommitted one) | **stale** committed record (11-10): recorded rxmix_q.mag, rxmix_q.ext.spice, rxmix_q.spice differ from what is on disk. Uncommitted record: recorded rxmix_q.mag, rxmix_q.ext.spice differ from what is on disk | as rxmix_i | **not supported**. As rxmix_i |
| `bbfilter_i` | pt_bbfilter_i (published) | **no** | 0 / 0 | bound netlist: match; committed schematic: match (+15 antenna diodes) | 11-12: recorded hashes match; 1 flow or bench scripts changed since | ext, C-only; 12c for AC and trims, noise at 2 points; ideal zero-ohm source, 1 pF loads, ideal bias | **not supported**. Hashes match what is on disk; current 5.22 mA against a 3.77 mA allocation with no fail flag; chain NF pass rests on a reference its own record marks invalid |
| `bbfilter_q` | pt_bbfilter_q (published) | **no** | 0 / 0 | bound netlist: match; committed schematic: match (+15 antenna diodes) | 11-12: recorded hashes match; 1 flow or bench scripts changed since | as bbfilter_i | **not supported**. As bbfilter_i |
| `bb_tap` | pt_bb_tap (published) | yes | 0 / 0 | bound netlist: match; committed schematic: **no match** (matches the uncommitted one) | **stale** committed record (11-10): recorded bb_tap.mag, bb_tap.ext.spice, bb_tap.spice differ from what is on disk. Uncommitted record: recorded hashes match; 2 flow or bench scripts changed since | ext, C-only; 12c observe, inject at tt; ideal sources, pad = ideal node + 10 pF | **not supported**. Evidence predates the layout on disk; pad not co-simulated |
**RF transmit**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `txmix_i` | pt_txmix_i (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-12: recorded hashes match | ext, C-only, no gate R; 12c in the chain; ideal baseband, ideal rail-to-rail LO, 300 ohm + 150 fF load | physical checks hold, evidence partial. Record matches what ships; observable and fallback open |
| `txmix_q` | pt_txmix_q (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-12: recorded hashes match | as txmix_i | physical checks hold, evidence partial. As txmix_i |
| `txsum` | pt_txsum (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-12: recorded hashes match | ext, C-only; 12c in the chain; ideal current sources, 150 fF load | physical checks hold, evidence partial. Transimpedance 220 ohm against 1000 and input impedance 262 ohm against 100 max, neither flagged |
| `rfdriver` | pt_rfdriver (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+6 antenna diodes) | 11-12: recorded hashes match | ext, C-only, no gate R; 12c in the chain with the real extracted mixers and summer; pad = 2 ohm + 1 pF, ideal chokes and balun, no package; modulation at tt from a memoryless model | physical checks hold, evidence partial. Record matches what ships; matched linear output -0.3 to -0.7 dBm at ss against 0 dBm |
**Converters**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `adc_i` | pt_adc_i (staged) | yes | **0 / 7** (ANT.16_i_ANT.5 x7); no record | bound netlist: match; committed schematic: match | 11-10: recorded hashes match; 4 flow or bench scripts changed since | ext, C-only (flat, with the digital macro); static 12c, FFT at tt only; ideal input, reference, clock and bias | **not supported**. Only valid FFT: ENOB 4.6 / 4.9 at tt; the run with the real reference buffer is marked invalid; area 66 % over ceiling; staged: the chip binds a newer pin list than this cell |
| `adc_q` | pt_adc_q (staged) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+8 antenna diodes) | 11-13: recorded hashes match; 4 flow or bench scripts changed since | ext, C-only; one nominal run (tt/27/3.3); ideal everything | **not supported**. Corner row reads all_pass over an empty corner set; clean pass rests on one run; staged |
| `dac_i` | pt_dac_i (staged) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+12 antenna diodes) | 11-13: recorded hashes match; 4 flow or bench scripts changed since | ext, C-only; tt/27/3.3 only; ideal clock, codes and bias, 100 fF loads | **not supported**. Record itself says clean = fail (endpoint spread 0.524 LSB); no corner, 80 MS/s or sine result; staged |
| `dac_q` | pt_dac_q (staged) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+12 antenna diodes) | 11-13: recorded hashes match; 4 flow or bench scripts changed since | as dac_i | **not supported**. As dac_i |
| `refbuf` | pt_refbuf (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-10: recorded hashes match; 4 flow or bench scripts changed since | ext, C-only; 12c; ideal 1.0 V reference and bias, current-pulse load instead of the ADC | physical checks hold, evidence partial. READY rises 50 ns before VREF settles and still passes; never valid with the ADC as load |
**LO, clocks, PLLs**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `pt_lc_qvco5` | pt_lc_qvco5 (published) | hand-written source | 0 / 0 | core subcell: match; top cell against qvco5.spice: **cannot match** (the two spirals extract as metal shorts between IP/IN and QP/QN), spiral hookup unverified | **no evidence record** | schematic of the previous QVCO cell with an analytic spiral model; ideal supply | **not supported**. The only record, lcvco-evidence.json, hashes qvco.spice, not qvco5.spice: it describes a different cell and is not post-layout; real-load scratch run: 2.488 GHz against a 2.558 GHz limit |
| `pt_lo_mmd` | pt_lo_mmd (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+15 antenna diodes) | **no evidence record** | scratch only: C-only ext, three single points, ideal tank sine | **not supported**. No evidence record; one ss case fails; 5 of 21 runs predate the published extraction |
| `pt_lo_mmd_qdum` | pt_lo_mmd_qdum (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+2 antenna diodes) | **no evidence record** | none (only as a load in one scratch run) | **not supported**. No evidence record |
| `pt_lo_pfdcp` | pt_lo_pfdcp (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+1 antenna diodes) | **no evidence record** | scratch only: schematic and ext, three points, behavioural VCO | **not supported**. No evidence record; extracted PFD pulse width NaN at all three corners; pump mismatch 16.5 % |
| `pt_lo_lf` | pt_lo_lf (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | **no evidence record** | scratch only: ext in loop ladder runs, behavioural VCO | **not supported**. No evidence record; ladder runs used an earlier extraction; two lock-time misses |
| `pt_lo_obs` | pt_lo_obs (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | **no evidence record** | scratch only: ext, 24 corners, ideal tank sine | **not supported**. No evidence record; no division at ss/3.15 V (4 of 24) |
| `lo_ext` | pt_lo_ext (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+4 antenna diodes) | **stale** 11-10: recorded lo_ext.ext.spice, lo_ext.mag, lo_ext.lvs.spice differ from what is on disk | ext, C-only, of a superseded cell; 12c; 50 ohm source or ideal tank sine, mixer gates as bare FETs | **not supported**. Evidence and pad evidence describe the previous layout (area 38.7k um2 recorded, 0.155 mm2 published); scratch outputs overwritten; real-neighbour result: mixer gain -3.3 dB tt / -9.8 dB ss |
| `pll_ring` | pt_pll_ring (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+20 antenna diodes) | 11-13: recorded hashes match; 3 flow or bench scripts changed since | ext, C-only; five closed-loop cases at tt/27/3.3 only; ideal supply and reference, control voltage pre-charged, 20 fF loads | **not supported**. Record says safe = fail (87-162 uA at reset); phase within 5 deg false in 4 of 5 runs; lock flag wrong in 3 of 5; no corners, no regulator supply, no jitter number |
| `pt_pll_ring_core` | pt_pll_ring_core (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: **no match** | **no evidence record** | no bench output found | **not supported**. No evidence record; the ring cell in this GDS differs from the committed ring-cell netlist (one gate on ENB instead of P1) |
| `pt_pll_vreg2` | pt_pll_vreg2 (published) | not checked | 0 / 0 | bound netlist: match | evidence/pd28-*.json: netlist hash matches; ring netlist in the runs has changed since | ext, C-only; DC/PSRR at 5 points, ring-load jitter at 3; ideal source and load | physical checks hold, evidence partial. No tests section; jitter runs used a ring netlist that has since changed; ff criterion met only at a changed control voltage |
| `clockmux` | pt_clockmux (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | 11-08: netlist hashes match; GDS hash differs (re-exported after the record); 4 flow or bench scripts changed since | ext, C-only; 12c on one case; ideal pulses, lumped C | physical checks hold, evidence partial. Record GDS hash differs from disk (re-export); observable, fallback open |
| `prescale` | pt_prescale (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | 11-08: netlist hashes match; GDS hash differs (re-exported after the record); 4 flow or bench scripts changed since | ext, C-only; tt/27/3.3 only; ideal 2.5 GHz rail-to-rail pulse, 50 fF, no gate R | physical checks hold, evidence partial. One corner; record GDS hash differs from disk |
| `wordclk` | pt_wordclk (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | 11-08: netlist hashes match; GDS hash differs (re-exported after the record); 4 flow or bench scripts changed since | ext, C-only; 4 cases x 12c; ideal pulse, 30/60 fF | physical checks hold, evidence partial. Record GDS hash differs from disk; best covered timing block |
| `diff_clk_rx` | pt_diff_clk_rx (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | 11-11: recorded hashes match; 3 flow or bench scripts changed since | ext, C-only; 12c on one case (100 MHz), 20 nominal cases; ideal sine through coupling caps, 20 fF, no pad or package | physical checks hold, evidence partial. Hashes match; 2.5 and 3.3 GHz cases fail (non-gating) |
| `pt_clk_obs16` | pt_clk_obs16 (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+28 antenna diodes) | **no evidence record** | scratch only: ext, 24 corners, ideal | **not supported**. No evidence record; scratch shows 201-226 uA at reset against the 1 uA rule |
| `pt_obs_pre4` | pt_obs_pre4 (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | **no evidence record** | scratch only: ext, 24 corners, ideal 40 ps pulse | **not supported**. No evidence record; scratch results fail 20 of 24 corners on swing/duty |
| `ring_osc` | pt_ring_osc (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+1 antenna diodes) | **stale** 11-10: recorded ring_osc.mag, ring_osc.ext.spice differ from what is on disk | ext, C-only, previous layout; 12c; ideal, 20 fF | **not supported**. Layout rebuilt a day after the evidence |
| `vco_replica` | pt_vco_replica (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | 11-10: netlist hashes match; GDS hash differs (re-exported after the record); 4 flow or bench scripts changed since | ext, C-only; 4 cases x 12c; ideal control voltage, 20 fF | **not supported**. 12 of 48 corner cases fail (no oscillation at 0.8/0.9 V) while clean reads pass; record GDS hash differs |
| `aosc` | pt_aosc (published) | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match | 11-10: netlist hashes match; GDS hash differs (re-exported after the record); 4 flow or bench scripts changed since | ext, C-only; 12c, all inside 40-60 MHz; ideal, 20 fF | physical checks hold, evidence partial. Record GDS hash differs from disk (re-export); otherwise the closest to supported in timing |
| `clk_obs` | not bound | hand-written source | 0 / 0 | bound netlist: match; committed schematic: match (+17 antenna diodes) | 11-10: recorded hashes match; 4 flow or bench scripts changed since | ext, C-only; 12c; ideal pulse, 10 pF | physical checks hold, evidence partial. Hashes match; 1 GHz case fails (non-gating); the chip top instantiates pt_clk_obs16 instead |
**Wired receive**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `cdr` | pt_cdr (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+14 antenna diodes) | 11-14: recorded hashes match | ext; 3 corners + ss pessimistic; open loop only: ideal votes, forced control voltage, ideal bias | physical checks hold, evidence partial. No tests section; closed loop with the real ring not run on r13 (WRX-01) |
| `ctle` | pt_ctle (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+8 antenna diodes) | 11-11: record matches the committed netlist; the netlist has uncommitted edits; 5 flow or bench scripts changed since | ext, C-only; 12c; ideal 25 ohm source, 150 fF load | physical checks hold, evidence partial. With the real rxselect + slicer load: -8 dB at 1.25 GHz (README); netlist modified uncommitted |
| `detect` | pt_detect (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+15 antenna diodes) | 11-12: record matches the committed netlist; the netlist has uncommitted edits; 3 flow or bench scripts changed since | ext, C-only; 12c; ideal line, clock and bias | **not supported**. Clean reads pass while the record lists two gating corner failures (HS disconnect at ss/3.15 V) |
| `rxlevel` | pt_rxlevel (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-08: recorded hashes match; 6 flow or bench scripts changed since | ext, C-only; 12c; pad gates as 1.0 / 0.4 pF | physical checks hold, evidence partial. Record current; flow scripts changed since |
| `rxselect` | pt_rxselect (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-08: record matches the committed netlist; the netlist has uncommitted edits; 6 flow or bench scripts changed since | ext, C-only; 12c; ideal AC source, 150 fF | physical checks hold, evidence partial. Netlist modified uncommitted (GDS still matches the committed one) |
| `slicer` | pt_slicer (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+88 antenna diodes) | 11-12: recorded hashes match; 5 flow or bench scripts changed since | ext, C-only; nominal + 2 corners (record says partial 2/12); ideal ring phases, ideal data | physical checks hold, evidence partial. Record declares itself partial; one ss case fails |
| `termination` | pt_termination (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+4 antenna diodes) | 11-11: recorded hashes match; 5 flow or bench scripts changed since | ext, C-only; 12c; resistor/capacitor model of the pad bank | physical checks hold, evidence partial. Record current; flow scripts changed since |
| `wmon_sel` | pt_wmon_sel (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-08: recorded hashes match; 6 flow or bench scripts changed since | ext, C-only; 12c; ideal source, 300 fF | physical checks hold, evidence partial. Record current; flow scripts changed since |
| `pt_ptrim` | pt_ptrim (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+94 antenna diodes) | **no evidence record** | none | **not supported**. No evidence record; README: cannot drive the real clock loads |
| `pt_vthdac` | pt_vthdac (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match | 11-12: recorded hashes match; 2 flow or bench scripts changed since | ext and schematic; 3 corners; 700 fF lumped lines | physical checks hold, evidence partial. No tests section (only pass: true) |
| `pt_wrx_cap` | pt_wrx_cap (published) | not checked | 0 / 0 | bound netlist: match | **stale** 11-11: recorded wrx_cap.ext.spice, wrx_cap.lvs.spice differ from what is on disk | ext and schematic; nominal only; ideal phases and sampler outputs | **not supported**. Record says safe = fail and clean = fail and hashes an extraction that is no longer on disk |
**Wired transmit and USB**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `wiredtx` | pt_wiredtx (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match (+21 antenna diodes) | 11-14: source hashes match; no layout or GDS hash recorded; 1 flow or bench scripts changed since | ext, C-only; 2.5 Gb/s at 2 corners; ideal ring phases and word source | **not supported**. Record says clean = fail; with the real ring 11 errors in 101 bits at ss (wiredtx-realring.json) |
| `pt_usb_txdrv` | pt_usb_txdrv (published) | yes | 0 / 0 | bound netlist: match; committed schematic: match | usbdrv-evidence.json: input hashes match; no tests section | ext; 7 points incl. sf/fs at 27 C; REAL neighbours: extracted wiredtx, hsbias, USB pad, package and line | physical checks hold, evidence partial. No tests section; HS level 351 mV at ss against 360-440; full-speed ok rows carry failed match checks |
| `hsbias` | pt_wtx_hsbias (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | usb_hs_bias-evidence.json hashes a 10 Nov wiredtx state, not this cell | ext, C-only; 12c; 28 gate loads + 0.3 pF instead of the pad | **not supported**. Covered only by usb_hs_bias-evidence.json, which hashes an older wiredtx state, not this cell; LSB target missed at 10 of 13 points but recorded in window |
| `wtx_fallback_control` | pt_wtx_fallback_control (published) | not checked | 0 / 0; no record | bound netlist: match | generated/characterization.json (no evidence JSON) | ext; tt/ss/ff x 3 supplies x 3 temperatures, full truth table; ideal sources, 50 fF | physical checks hold, evidence partial. No evidence JSON (characterization.json instead); standalone only |
| `tx_steering_buffer_flat` | tx_steer (published) | not checked | 0 / 0 | bound netlist: match; chip-top netlist (lifecycle file): match | layout.json + equivalence.json: netlist hash matches | ext, C-only; 5 points, one supply; ideal pulse, 2 pF | physical checks hold, evidence partial. Bound netlist matches this GDS; no evidence JSON |
| `buffer_compensated_flat` | term_buffer (published) | not checked | 0 / 0 | bound netlist: match; chip-top netlist (lifecycle file): match | readiness-settle.json: no hash of what it simulated | ext, C-only; 5 points; October fixture | physical checks hold, evidence partial. At ss the detector de-asserts once and VCM dips to 0.31 V; generator modified uncommitted |
| `attached_tx_interlock` | tx_interlock (published) | not checked | 0 / 0; no record | bound netlist: match | **no evidence record** | October screens of another candidate | **not supported**. No record for this GDS (18 Oct); on the repack list |
**Pads**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `pad_rf_pair` | pad_rf_pair (published) | not checked | 0 / 0 | bound netlist: match | pad-layout.json + pd13-family-sims.json: GDS and extracted-netlist hashes match | pad-extracted.spice, C-only; HBM at 3 points, AC at tt/ss/ff; ideal 50 ohm, no bond, package, LNA or match | physical checks hold, evidence partial. Chip top binds reference.spice (no parasitics), the benches used pad-extracted.spice; no return-loss number against a real neighbour |
| `pad_rftxpad` | pad_rftxpad (published) | not checked | 0 / 0 | bound netlist: match | pd48-esd-tiering.json: hashes match | as pad_rf_pair; 1 kV HBM only | physical checks hold, evidence partial. Clamp onset 2.1 V at ff conflicts with the 3.3 V pad bias (rf_tx excluded coverage) |
| `pad_single_leg` | pad_single_leg (published) | not checked | 0 / 0 | bound netlist: match | layout record only: hashes match | no simulation of its own | physical checks hold, evidence partial. Layout record only |
| `pad_refpad` | pad_refpad (published) | not checked | 0 / 0 | bound netlist: devices and nets equal after removing its one modelled well diode; layout pin ESD_RAIL is not in the bound subcircuit | pd13-family-sims.json: model hash matches; sims script changed since | as pad_wirepad; VCM ideal | physical checks hold, evidence partial. AUX_CLK 25-810 MHz bench not run; see pad note |
| `pad_hspad` | pad_hspad (published) | not checked | 0 / 0 | bound netlist: devices and nets equal after removing its one modelled well diode; layout pin ESD_RAIL is not in the bound subcircuit | ap4-hspad-*.json: model hash matches; layout-screen.json records a generator that has uncommitted edits | ext, C-only; AC at 3-4 points, HBM at tt/ss0/ff85; ideal HBM current source, lumped bond, no package | **not supported**. Owner's resistance-aware run of this published cell: 129-154 ohm at the last trim code, no code reaches 100 ohm (scratch/pads-core/hsfix/STATUS.md); CDM surrogate 9.03 V against 8.0 |
| `pad_wirepad` | pad_wirepad (published) | not checked | 0 / 0 | bound netlist: devices and nets equal after removing its one modelled well diode; layout pin ESD_RAIL is not in the bound subcircuit | pd47-usb-ls-miller.json, pd48-esd-tiering.json: model hash matches | ext, C-only; 12c function, HBM at 3 points; ideal drivers and loads, lumped bond | physical checks hold, evidence partial. HS level below 360 mV at ss/3.15 V (PC-13); see pad note on pad-to-diode resistance |
| `pad_txpad` | pad_txpad (published) | not checked | 0 / 0 | bound netlist: devices and nets equal after removing its one modelled well diode; layout pin ESD_RAIL is not in the bound subcircuit | pd13-family-sims.json: model hash matches; generator committed after the build | as pad_wirepad | physical checks hold, evidence partial. 25 exceedances at 2 kV (risk-accepted ESD-05); see pad note |
| `pad_tlp` | pad_tlp (published) | not checked | 0 / 0 | bound netlist: match | kldrc record only; the review covers another GDS hash | no simulation (measurement site) | physical checks hold, evidence partial. Published GDS is not the reviewed one (review cites another hash) |
**Core, bias, islands, test bus**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `por` | por (published) | not checked | 0 / 0 | bound netlist: match | core_support_evidence.json: all 34 source hashes match | Magic R+C at 13 function points, safety ramps on the schematic; ideal ramp, 1 pF | physical checks hold, evidence partial. Core_support_evidence.json hashes match; 4 of 54 ramps give no reset (1 s ramp at ff and tt/85 C) |
| `pt_core_bias` | pt_core_bias (inline pin list) | not checked | 0 / 0; no record | leaf by leaf: 9/9 leaves match; no flat netlist for the assembly | **no evidence record** | none on the routed assembly (leaf netlists only) | **not supported**. No evidence for the assembly; GDS only under scratch/, two builds exist and the DRC registry names the older one |
| `pt_bias_tap2` | not bound | yes | 0 / 0 | bound netlist: match | layout.json: GDS and netlist hashes match | ext, C-only; 13-19 corners INCLUDING sf/fs and resistor corners; ideal reference, diode consumers | physical checks hold, evidence partial. Layout.json hashes match; closest to the mandate; chip top does not bind it |
| `pt_refvcm` | demand in masters.txt | yes | 0 / 0 | bound netlist: match | layout.json: GDS and netlist hashes match | as pt_bias_tap2 | physical checks hold, evidence partial. Layout.json hashes match; masters.txt still lists it as demand |
| `pt_txpad_bias` | demand in masters.txt | yes | 0 / 0 | bound netlist: match | layout.json: GDS and netlist hashes match; sims hash another build | as pt_bias_tap2 | physical checks hold, evidence partial. X5 rebuild not re-reviewed; masters.txt still lists it as demand |
| `isw_wired` | isw_wired (published) | not checked | 0 / 0 | bound netlist: match | island_support/evidence.json: GDS and netlist hashes match (files under scratch/); design.py, layout.py changed since | C-coupled ext for transients, full-RC for DC drop; 12c; reduced ring model with lumped bond, resistive loads | physical checks hold, evidence partial. Island_support/evidence.json hashes match; GDS and netlist only under scratch/; drop 19.87 mV against 20; safety cases schematic only |
| `isw_rf` | isw_rf (published) | not checked | 0 / 0 | bound netlist: match | as isw_wired | as isw_wired | physical checks hold, evidence partial. As isw_wired |
| `isw_conv` | isw_conv (published) | not checked | 0 / 0 | bound netlist: match | as isw_wired | as isw_wired | physical checks hold, evidence partial. As isw_wired |
| `isw_debug` | isw_debug (published) | not checked | 0 / 0 | bound netlist: match | as isw_wired | as isw_wired | physical checks hold, evidence partial. As isw_wired |
| `iso_clamp` | iso_clamp (published) | not checked | 0 / 0 | bound netlist: match | island_support/evidence.json: hashes match (scratch/) | C-coupled ext; 12c; diode + 28 ohm pad model | physical checks hold, evidence partial. GDS only under scratch/; a second, different iso_clamp GDS exists |
| `atb_leaf_s` | atb_leaf_s (published) | not checked | 0 / 0 | bound netlist: match | island_support/evidence.json hashes the pex/ netlists; the bound pexd/ netlist is in no record | ext; tt/ss/ff function grid, isolation at tt only; 100 kohm / 1 pF node | physical checks hold, evidence partial. The bound netlist (pexd/) carries no hash in any record; GDS only under scratch/ |
| `atb_leaf_f` | atb_leaf_f (published) | not checked | 0 / 0 | bound netlist: match | as atb_leaf_s | as atb_leaf_s | physical checks hold, evidence partial. As atb_leaf_s |
| `atb_grp` | atb_grp (published) | not checked | 0 / 0 | bound netlist: match | as atb_leaf_s | as atb_leaf_s | physical checks hold, evidence partial. As atb_leaf_s |
| `atb_pad` | atb_pad (published) | not checked | 0 / 0 | bound netlist: match | as atb_leaf_s | as atb_leaf_s | physical checks hold, evidence partial. As atb_leaf_s; 56 uA pad-to-bus shunt (ISL-02) |
**Characterization and decap**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `char_atb` | pt_char_atb (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | 11-10: netlist hashes match; GDS hash differs (re-exported after the record); 3 flow or bench scripts changed since | ext through the extracted ATB cells; 5 corners; ideal source and meter | physical checks hold, evidence partial. Passes with a 1 Gohm meter; the 10 Mohm runs miss the limits; GDS hash in the record stale |
| `char_ro33` | pt_char_ro33 (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | char_speed-evidence.json section + physical.json | ext + computed gate R; 5 corners; ideal supply, 50 fF | physical checks hold, evidence partial. No record of its own (section of char_speed-evidence.json) |
| `char_ro50` | pt_char_ro50 (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | as char_ro33 | as char_ro33 | physical checks hold, evidence partial. As char_ro33 |
| `char_cmldiv` | pt_char_cmldiv (published) | yes | 0 / 0; no record | bound netlist: match; committed schematic: match | as char_ro33 | as char_ro33 | physical checks hold, evidence partial. As char_ro33 |
| `char_rffet` | pt_char_rffet (published) | not checked | 0 / 0; no record | bound netlist: match; committed schematic: match | physical.json only; GDS rebuilt 18 Nov | no simulation (probe structure) | physical checks hold, evidence partial. Physical record only; GDS rebuilt during this audit (commit be37cc6) |
| `char_rffet_open` | pt_char_rffet_open (published) | not checked | 0 / 0; no record | no devices on either side | as char_rffet | no simulation (de-embedding frame, no devices) | physical checks hold, evidence partial. As char_rffet |
| `char_rffet_short` | pt_char_rffet_short (published) | not checked | 0 / 0; no record | no devices on either side | as char_rffet | no simulation (de-embedding frame, no devices) | physical checks hold, evidence partial. As char_rffet |
| `pt_decap_tile` | not in the conn | not checked | 0 / 0 | bound netlist: match | generated/sim-results.json (no evidence JSON) | ext, C-only; 12c AC; ideal source | physical checks hold, evidence partial. No evidence JSON; ESR/Q optimistic (no channel resistance) |
**Published GDS that the chip top does not bind**
| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |
| `isw_pll` | not bound | not checked | 0 / 0 | bound netlist: match | as isw_wired | as isw_wired | not used on the chip. Not instantiated (the conn uses isw_debug for the pll island) |
| `pt_pll_vreg` | not bound | not checked | 0 / 0 | bound netlist: match; committed schematic: **no match** | evidence/pll_vreg-ext-packed.json | as pt_pll_vreg2 | not used on the chip. Not instantiated at the chip top |
| `attached_tx_steering_driver` | not bound | not checked | 0 / 0; no record | not run | **no evidence record** | none | not used on the chip. Superseded by the compact steering buffer; still in the DRC registry |
| `attached_tx_buffer` | not bound | not checked | **10 / 0** (PP.2 x10); no record | not run | **no evidence record** | none | not used on the chip. Superseded by the compact termination buffer; still in the DRC registry |

Four GDS that the chip does not use are listed last for completeness; `attached_tx_buffer` has 10 PP.2 violations.

## 4. Blocks whose published status is not supported

31 blocks, grouped by the check that fails. A block can appear in more than one group.

- **The layout on disk is not the committed design** (read-back LVS fails against the committed schematic):
  `lna`, `rxmix_i`, `rxmix_q`, `bb_tap` (the GDS match the owner's uncommitted netlists: redesign in flight, nothing
  of it is committed), `pt_pll_ring_core` (layout older than the committed ring cell, section 1 item 3).
- **The evidence describes another layout or netlist**: `lna`, `rxmix_i`, `rxmix_q`, `bb_tap` (committed records;
  the uncommitted `bb_tap` record does match the disk), `lo_ext` (previous layout: 38.7k µm² recorded, 0.155 mm²
  published; its scratch outputs were overwritten), `ring_osc` (layout rebuilt a day after the record),
  `pt_wrx_cap` (hashes an extraction that is no longer on disk), `hsbias` (covered only by
  `usb_hs_bias-evidence.json`, which hashes a 10 Nov `wiredtx` netlist), `pt_lc_qvco5` (record of the previous cell).
- **The record itself says fail**: `pll_ring` (safe: 87–162 µA at reset against 1 µA), `dac_i`, `dac_q` (clean),
  `pt_wrx_cap` (safe and clean), `wiredtx` (clean).
- **Pass states that the record's own numbers contradict**: `lna` (chain NF 9.87 / 11.53 dB against 4.1, IIP3 not
  simulated, all four states pass), `rxmix_i`, `rxmix_q` (IIP3 and ss NF rows fail, clean passes), `detect` (clean
  passes with two gating corner failures listed), `adc_q` (clean from one nominal run; the corner row is
  `all_pass: true` over an empty set), `vco_replica` (12 of 48 corner cases fail, clean passes), `pll_ring`
  (observable passes with the lock flag wrong in 3 of 5 runs).
- **No evidence record**: `pt_lc_qvco5`, `pt_lo_mmd`, `pt_lo_mmd_qdum`, `pt_lo_pfdcp`, `pt_lo_lf`, `pt_lo_obs`,
  `pt_pll_ring_core`, `pt_clk_obs16`, `pt_obs_pre4`, `pt_ptrim`, `attached_tx_interlock` (the chip's `tx_interlock`:
  an 18 Oct GDS on the repack list), `pt_core_bias` (the routed assembly: leaf cells match leaf by leaf, 9 of 9, but
  the assembly has no netlist, no simulation and exists only under `scratch/`, in two builds).
- **DRC fails**: `adc_i` (antenna).
- **Not reproducible from the committed tree**: `bbfilter_i`, `bbfilter_q` (layout, netlist and record agree with
  each other on disk; committing the owner's `netlists.py` closes this).
- **The chip binds another pin contract**: `adc_i`, `adc_q`, `dac_i`, `dac_q` (`staged` in `masters.txt`).
- **A later result of the owner shows the published cell does not work**: `pad_hspad` (termination, section 1
  item 2), `wiredtx` (11 errors in 101 bits at 2.5 Gb/s, ss, on the real ring: `wiredtx-realring.json`).

## 5. Findings across families

1. **Corners.** The corner list of every flow is tt/ss/ff × 22/32 °C × 3.15/3.35 V: `rf_rx/simlib.py:54`,
   `rf_tx/simulate.py:21`, `timing/run_timing.py:22`, `wired_rx/run_family.py:23`, converters `benches.py`,
   `pads/stress_safe_family_sims.py:298`. sf and fs cannot be produced by these flows as written. Many headline
   numbers come from fewer points still: tt only for `prescale`, `pll_ring` (five runs), `adc_q`, both DACs, the ADC
   FFT, the RF linearity and modulation rows; two or three points for `cdr`, `slicer`, `pt_vthdac`, `wiredtx`.
   Nominal rows are tt/27 °C/3.3 V, which is not one of the mandate points. No block has 3.50 V (trimmed supply) rows.
2. **Extraction is capacitance-only in every family**, including the pads and terminations where the mandate asks
   for resistance-aware extraction. Section 1 items 1 and 2 are what that hides.
3. **Ideal neighbours.** Mixers see an ideal square LO (the real LO delivers about 0.9–1.16 V sine); the RX pad is a
   0.5 pF allowance and the TX pad 2 Ω + 1 pF with no package; dividers and samplers see ideal clock phases; pad HBM
   is an ideal current source into a bare die; the reference buffer is never valid with the ADC as its load; the
   CTLE passes into 150 fF and loses 8 dB at 1.25 GHz into its real load. Explicit gate resistance is absent from
   rf_tx, from the LNA and mixer block rows and from the timing benches except the `lo_ext` CML pair.
4. **How "clean" is computed.** In rf_rx and wired_rx the clean state needs DRC, LVS and a nominal sanity check
   (`rf_rx/characterize.py:44`, `wired_rx/evidence.py:157`), so failing corner or performance rows do not change it.
   In timing the gating sets leave out the failing cases (`timing/evidence.py:25`): `lo_ext` gates on a 4 Vpp case
   while the 2 Vpp and 1 Vpp cases fail, `diff_clk_rx` excludes 2.5 and 3.3 GHz.
5. **Limits that moved after the measurement** (each recorded by its owner, none raised as a budget request):
   rxmix current 1.0 → 3.1 mA (measured 3.007); LNA current 3.0 → 19.0 mA (measured 18.93), citing a power budget
   file that holds the measured value; `char_atb` safe limit 100 nA peak → settled current plus 10 µA; regulator
   jitter criterion met at ff only at a changed control voltage; `pt_usb_txdrv` full-speed rows pass with the
   rise/fall match check dropped; two capture cases made non-gating after their results.
6. **The netlist that is simulated and bound is not in git.** `*.ext.spice` and `*.gds` are ignored. The committed
   rf_rx evidence for `lna`, `rxmix_i/q` and `bb_tap` refers to netlists that no longer exist anywhere.
7. **Chip-top bindings that do not point at the simulated view.** `pad_rf_pair`, `pad_single_leg` and `pad_rftxpad`
   are bound to `reference.spice` (no parasitics) while their benches used `pad-extracted.spice`. `tx_steer`,
   `term_buffer` and `tx_interlock` are bound to subcircuits of the 17 Oct `wired-transmit-lifecycle.spice`; read-back
   LVS shows the published compact steering and termination-buffer GDS do match those subcircuits, so the binding is
   device-correct, but that file is in no record. The test-bus masters point at `pexd/` netlists that no record
   hashes. `masters.txt` still lists `pt_refvcm` and `pt_txpad_bias` as demand although both are published.
8. **`spec/performance-requirements.json` disagrees with the evidence in both directions**: RF-TX-MUTE "fails,
   22–24 dB" (evidence 46.2 dB), RF-TX-POUT "−0.13 dBm saturated" (evidence 9.52), RF-RX-IIP3 "not simulated"
   (the mixer record has −10.03 dBm, a fail).

## 6. Record keeping

- **No precheck DRC record** (21): `txmix_i`, `txmix_q`, `txsum`, `adc_i`, `refbuf`, `rxlevel`, `rxselect`,
  `wmon_sel`, `hsbias`, `wtx_fallback_control`, `char_atb`, `char_cmldiv`, `char_rffet`, `char_rffet_open`,
  `char_rffet_short`, `char_ro33`, `char_ro50`, the three `attached_tx_*` cells (all 20 in the registry), and the
  compact build of `pt_core_bias`.
- **Published GDS not in the DRC registry** (19): `pt_lc_qvco5`, `pt_lo_mmd`, `pt_lo_mmd_qdum`, `pt_lo_pfdcp`,
  `pt_lo_lf`, `pt_lo_obs`, `pt_pll_ring_core`, `pt_pll_vreg2`, `pt_pll_vreg`, `pt_clk_obs16`, `pt_obs_pre4`,
  `pt_ptrim`, `pt_vthdac`, `pt_wrx_cap`, `pt_usb_txdrv`, `tx_steering_buffer_flat`, `buffer_compensated_flat`,
  `pt_core_bias` (compact build), `pt_decap_tile`. All but `pt_core_bias` have a clean, hash-matched record next to
  the GDS; the gate does not look at them. The registry still holds the superseded `attached_tx_steering_driver` and
  `attached_tx_buffer`, a wrong top-cell name for `pad_rf_pair`, and the older `core_bias` build.
- **Record format.** No record uses the `output_hashes` key that `spec/block-deliverables.md` names (the families
  use `artifact_hashes`, `generated_hashes`, `netlist_hashes`, `inputs` or none); `cdr`, `pt_vthdac` and
  `pt_usb_txdrv` have no `tests` section; `wiredtx` records no hash of its layout or GDS; pads, island cells, `por`
  and the bias cells keep their records under other names (the freshness column names them).
- **Flow LVS records.** The committed `-lvs.txt` files compare the layout with the schematic plus the generator's
  antenna diodes; they are records of the in-memory layout, not of the GDS. The read-back runs of this audit are not
  a gate in any flow yet (MOD-18).

## 7. Files

`scratch/evidence-audit/`: `inventory.py` (block list and cheap checks), `freshness.py`, `freshness2.py` (hashes
against disk and HEAD), `run_drc_queue.py` + `drc-jobs.json` → `drc-results.jsonl`, `rb_lvs2.py` +
`run_lvs_queue.py` + `lvs-jobs.json` → `lvs-results.jsonl`, `run_lvs_extra.py` → `lvs-results-extra.jsonl` (chip-top
bindings of the TX attachment cells, QVCO top, core-bias leaves), `sch_pass.py` → `sch-results.jsonl` (committed
schematic), `bench_notes.py` (bench realism as read), `make_report.py` (the table). Per-block netgen reports are in
`lvs/<block>/`, DRC summaries in `drc/<block>/kldrc.json`. To repeat for one block:
`python3 run_drc_queue.py <name>; python3 run_lvs_queue.py <name>; python3 sch_pass.py <name>` (each skips a block
whose GDS hash is unchanged).
