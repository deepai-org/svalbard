# Sign-off gap check: read-back LVS, density fill, deck/version drift

Date: 2026-11-13/14. Integration sign-off checker. Scope: pre-mortem items 3 (LVS on the shipped GDS), 2 (density
fill) and 7 (PDK/KLayout drift), `scratch/reviews/pre-mortem.md`. Work dir `scratch/integration/signoff-gap/`
(scripts and small result files; nothing in the design tree or any published GDS was modified, all runs on copies).

Evidence labels: **[RUN]** run here and read; **[READ]** read in an artefact; **[INF]** inferred or estimated.

## 1. Ranked findings

| # | Finding | Numbers | Owner | Row |
|---|---|---|---|---|
| 1 | The live precheck's density stage has a new gating rule, DCF.1a (every 20 µm COMP-free area must carry dummy COMP unless marked NDMY / RES_MK / Pad / IND_MK). The project deck (f6eeac7) does not contain it. On the existing top it adds 1296 violations to the 6 global-density fails. | Live deck 792ef67 on `pt_chip_top.gds`: 1302 items (DCF.1a 1296, DCF.1b, PL.8, M1.4, M2.4, M5.4, MT.3). After the stock PDK fill: 10 items (DCF.1a only). | assembly | SG-2 |
| 2 | Stock PDK fill puts dummy metal, COMP and Poly2 under and inside the QVCO spirals, because no block GDS carries a fill keep-out marker (PMNDMY, NDMY, IND_MK: 0 shapes in all 74 block GDS). Tank wire capacitance rises 83–97 %. | Per spiral: 9242 Metal1 + 1516 Poly2 dummies coupled to the tank net; tank net C 1464 fF → 2678 fF (fill floating) / 2884 fF (fill grounded). Estimated f0 shift −3 % (distributed) to −10 % (bound) against a 2.6–3 % band margin (LO-10). | LO/timing + assembly | SG-3 |
| 3 | Fill is feasible at chip level and is cheap: the stock script fills the 247 MB top in 92 s and every layer passes, also with all analog blocks excluded. But it must be a flow step with keep-outs, and no extraction tool in the project sees fill today. | Before → after: COMP 19.2 → 41.2 %, Poly2 11.5 → 35.2, M1 19.3 → 40.5, M2 20.8 → 39.3, M3 30.6 → 46.9, M4 31.3 → 47.4, M5 28.8 → 41.6. With 4.49 mm² of analog blocks kept out of every layer: 35.1 / 27.9 / 35.0 / 35.4 / 43.9 / 44.4 / 38.6. | assembly | SG-2, SG-4 |
| 4 | Ring oscillator with fill: small but not zero. | `pll_ring` ring nodes +3.0 to +7.2 % wire C (max +2.1 fF on XRING/P0), VCTRL node +21.5 % (216 → 263 fF). Open-loop frequency at VCTRL 1.16 V: 661.9 → 655.4 MHz (−0.98 %); at 3.3 V: 1416.6 → 1403.1 MHz (−0.95 %). Adjacent-phase spacing changes by up to 8 ps (1.9°). | timing | SG-4 |
| 5 | Read-back LVS: no INT-19-class defect found. All 74 inventory GDS re-extract to the devices and nets that were simulated; W/L/R/C values equal. | 68 057 devices. 69 blocks match directly; 4 pad families match on devices and nets (two reference-side differences, below); `pt_core_bias` matches leaf by leaf. Negative controls fail as required. | integration | SG-1 |
| 6 | The QVCO top cell `pt_lc_qvco5` has no netlist and no ports; only its core subcell was ever LVS'd. The spiral hookup is unverified by any flow. | Read-back: core 974 devices match; spirals connect IP–IN and QP–QN and nothing else. Top pin list is empty. | LO/timing | SG-5 |
| 6b | `adc_i.gds` has 7 antenna violations and no KLayout DRC record; its twin `adc_q` was rebuilt clean 8 h later. The I and Q ADC layouts are different builds. | `adc_i` (10 Nov 02:17): ANT.16_i_ANT.5 × 7, same count on the project and live decks; `adc_i-kldrc.json` does not exist. `adc_q` (10 Nov 10:22): 0. `adc_q` has 8 antenna diodes that `adc_i` lacks (3735 vs 3727 devices). Both match their own netlists. | converters | SG-7 |
| 7 | Version drift is real on four axes, none of it exercised by the project: PDK deck (5 rule files differ), KLayout (0.30.7 / 0.30.9 here, 0.30.12 in the live image, not 0.30.11), Magic (8.3.623 vs 8.3.677) and device models (`gf180mcu_fd_pr` b6866b8 vs 5e4be87). The live image is amd64-only; this box is aarch64, so the live binaries could not be run. | See section 4. Deck diff: DCF.1a new; DF.11, CO.5a, CO.5b re-implemented. On project data the changed main-deck rules give the same counts (0) on the top and on six blocks; only the density stage differs. | integration | SG-6 |
| 8 | The antenna deck does complete on the top. The 10 Nov crash is KLayout 0.30.7 with `workers=4`; the same binary with `workers=1` finishes. | 0.30.7 workers=1: 436 violations in 3 min 42 s, identical per rule to the 0.30.9 run of 10 Nov. 0.30.7 workers=4: crash reproduced. 0.30.9 workers=4: 436, same. | integration | SG-6 |
| 9 | The PDK KLayout LVS deck cannot be the second LVS gate as the GDS stand: it recognises no MIM capacitor (it needs a MIM_L_MK marker that no project or provider GDS has) and none of the n+/psub antenna diodes. MOS and poly resistors agree with Magic on every block. | 30 blocks full match, 36 match on MOS and resistors only, 7 pad families +0.59 % on `ppolyf_u_1k_6p0` length. MIM covered instead by a FuseTop-area check: 27 of 27 blocks within 0.5 %. | integration | SG-1 |

Not a finding, but a correction to the pre-mortem: the local precheck clone is the same `precheck.py` as the live one
(byte-identical, ID stage included). The 10 Nov run skipped the ID stage because the image has no python `qrcode`
module, and it ran against the image PDK f6eeac7, not the `d658698` the clone's Makefile names. The ID-cell
placement checks pass on the existing top **[RUN]** (`precheck/id_check.py`: four cells, one instance each, at the
template coordinates).

## 2. Read-back LVS (pre-mortem item 3)

### Method
`lvs/rb_lvs.py`, per block:
1. Copy the published GDS into an empty directory (no `.mag` present).
2. Fresh Magic 8.3.623 session (the flows' image): `gds read`, `extract all`, `ext2spice lvs`.
3. netgen 1.5.316 with the PDK setup (property comparison on) against the reference.
4. An independent flattened device census: model, W, L, r_width, r_length, c_width, c_length, counts.

Reference = the netlist the assembly binds and the benches simulate (`<block>.ext.spice`, parasitic C lines
removed). The flows' own `-lvs.txt` records tie that netlist to the schematic; this check ties the GDS to it.

Second extractor, `lvs/kl_lvs.py`: the PDK KLayout LVS deck (variant D, KLayout 0.30.9) extracts devices from the
same GDS; its per-model totals (W per L, resistor length per width) are compared with the reference. It shares no
code with Magic's GDS reader, which is the point for marker layers (HRES, DUALGATE, NAT).

### Proof on one block, with negative controls **[RUN]** (`pt_aosc`, 34 devices)

| Case | Magic + netgen | Census | KLayout deck |
|---|---|---|---|
| Published GDS | match, unique | equal | equal |
| HRES (62/0) deleted, the INT-19 defect | FAIL (pin matching) | FAIL: 2 × ppolyf_u_1k missing | FAIL: 18.8 µm of ppolyf_u_1k missing |
| RES_MK (110/5) deleted | FAIL | FAIL | FAIL |
| One Via1 deleted | FAIL (netlists do not match) | equal | not run |
| One Via2 deleted | match | equal | not run |
| Reference resistor length 9.4 → 9.0 µm | FAIL (property errors) | FAIL | not run |
| Reference nfet W 2.0 → 2.1 µm | FAIL (property errors) | FAIL | FAIL: 34.1 vs 33.0 µm |

The single-Via2 case is a weak control, not a miss: that cut is one of a multi-cut stack and removing it opens
nothing. Via1 shows that a real open is caught.

### Result **[RUN]**
74 GDS (60 from the v6 `bbox.json` list plus the inventory masters and pad families), 68 057 devices.

- **69 match**: netgen "Circuits match uniquely", no property errors, census equal.
- **4 pad families** (`pad_refpad`, `pad_hspad`, `pad_wirepad`, `pad_txpad`): devices and nets match. Two
  reference-side differences: the simulated netlist carries one `diode_nw2ps_06v0` that
  `pads/protection_network.py` appends as a model of the n-well junction (not a drawn device), and the layout has
  a labelled pin ESD_RAIL that the reference subcircuit does not list. With the appended line removed the census
  is equal (404 / 508 / 739 / 595 devices) and netgen reports "match uniquely with port errors".
- **`pt_core_bias`**: no flat device netlist exists (the published LVS is a routing LVS with black-boxed leaves,
  itself run from GDS). Nine leaf masters read back from the routed GDS: six bias banks and `bringup_and` match;
  the bandgap matches with the PNP name alias the core_support README already documents (this PDK's Magic names
  the 5 × 5 µm PNP `pnp_10p00x00p42`); the biasgen is identical (3060 devices, unique match) to a read-back of the
  vendored patched tapeout GDS and differs from the upstream layout netlist only by the four compensation MIM
  capacitors and the dvdd/dvss pins of the two recorded patches.
- **`pt_lc_qvco5`**: finding 6.
- The four timing blocks whose GDS is newer than the bound `.ext.spice` (pre-mortem item 8: clockmux, prescale,
  wordclk, polyphase) match device for device.

KLayout deck: MOS (nfet/pfet 03v3, 05v0, 06v0, `nfet_06v0_nvt`) and poly resistors (`ppolyf_u`, `ppolyf_u_1k`,
`ppolyf_s`) agree on all 73 blocks that have a flat reference. So HRES, DUALGATE and NAT are read the same way by
both extractors on every block. It extracts no MIM and no `diode_nd2ps_03v3`, and 8 of 12 `diode_nd2ps_06v0` in the
pads. MIM is covered by `lvs/mim_area.py`: merged FuseTop area inside CAP_MK equals the netlist's sum of
c_width × c_length within 0.5 % on all 27 blocks with MIM and a flat reference.

Not covered: SAB on the ESD devices and V5_XTOR have no netlist signature in either extractor; parasitics were not
compared (device content only); the digital macro is not in this inventory.

Per-block table: section 6.

## 3. Density fill (pre-mortem item 2)

### What the deck and the script do **[READ]**
- Deck: whole-die COMP 25–70 %, Poly2 ≥ 14 %, Metal1–5 ≥ 30 % each, dummy datatype counted. Live deck adds DCF.1a.
- `fill_metal.rb`: 2 × 2 µm squares, pitch 3.2 µm (Metal5: 4 µm), so at most 39 % (Metal5 25 %) of open area. It
  stays 2 µm from metal on the same layer and on the layers directly above and below, and 6 µm from FuseTop and
  PMNDMY. It has no IND_MK exclusion.
- `fill_comp.rb` / `fill_poly2.rb`: 5 µm tiles; excluded by NDMY, IND_MK, RES_MK, Pad, well edges.
- The project script dies if called with `-rd threads=N` (string passed to `TilingProcessor#threads=`);
  `fill/fill_wrap.rb` works around it.
- The script keeps 26 µm clear of the layout bounding box, so a block filled alone is left with an unfilled rim;
  `fill/frame.py` wraps a block in a frame to avoid that. The live PDK's scripts add `no_scribe_line` and respect
  existing dummy shapes, which is what per-block pre-fill needs.

### Top level **[RUN]** (`scratch/chip-assembly-dev/pt_chip_top.gds`, unrouted v3, digital macro as an abstract)

| Layer | Limit | No fill | Stock fill | Keep-out: oscillators + RF (0.68 mm²) | Keep-out: all analog blocks (4.49 mm²) |
|---|---|---|---|---|---|
| COMP | ≥ 25 | 19.25 | 41.21 | 40.39 | 35.09 |
| Poly2 | ≥ 14 | 11.53 | 35.18 | 33.87 | 27.92 |
| Metal1 | ≥ 30 | 19.30 | 40.46 | 39.50 | 35.03 |
| Metal2 | ≥ 30 | 20.76 | 39.25 | 38.60 | 35.38 |
| Metal3 | ≥ 30 | 30.62 | 46.85 | 46.31 | 43.86 |
| Metal4 | ≥ 30 | 31.33 | 47.44 | 46.96 | 44.37 |
| Metal5 | ≥ 30 | 28.79 | 41.59 | 41.17 | 38.59 |

Keep-outs are PMNDMY + NDMY boxes over the block instances (`fill/keepout.py`). Fill run time 92 s, 715 MB.
The current file fails Metal5 as well (28.8 %); the 10 Nov record (31.0 %) was a different build of the top.
After fill the 250 µm tile minimum is still 8.2 % Metal1 and 9.6 % Metal2 (no local rule in the deck).
Cost of a keep-out: about 1.2 points of Metal1/Metal2 per mm² excluded. The v6 block demand is 8.5 mm², so
excluding every analog block would land near 30 % **[INF]**: keep-outs have to be chosen, not blanket.

### Blocks filled alone **[RUN]** (framed; percent of block area, `!` = below the die limit)

| Block | COMP | Poly2 | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|---|---|
| pll_ring | 5.6 → 24.4! | 3.4 → 20.4 | 2.4 → 26.2! | 2.1 → 14.9! | 7.1 → 16.6! | 9.3 → 14.8! | 13.3 → 20.1! |
| QVCO | 4.1 → 37.6 | 3.3 → 42.8 | 1.7 → 35.2 | 2.1 → 22.7! | 27.5 → 47.0 | 28.3 → 46.3 | 29.5 → 43.3 |
| LNA | 10.6 → 21.3! | 5.2 → 7.8! | 5.2 → 9.8! | 12.0 → 13.8! | 11.4 → 13.8! | 24.6 → 30.6 | 20.4 → 33.6 |
| adc_i | 4.3 → 32.9 | 1.1 → 15.8 | 2.6 → 15.5! | 7.9 → 18.4! | 14.5 → 22.4! | 7.0 → 20.8! | 1.3 → 17.4! |
| pad rf_pair | 9.4 → 36.3 | 8.1 → 32.0 | 5.5 → 26.3! | 23.0 → 45.4 | 11.5 → 32.6 | 15.4 → 39.4 | 16.2 → 34.2 |
| ring_osc | 3.7 → 15.8! | 0.5 → 15.0 | 2.3 → 26.1! | 2.2 → 10.6! | 8.7 → 13.3! | 12.6 → 15.3! | 10.8 → 16.0! |

Dense analog blocks cannot reach the limits by themselves even when filled (the adjacent-layer rule leaves little
room). The chip passes on the average with pads, channels and the digital macro. That is acceptable for the deck
(global rule only) but means the open channels carry the density.

### Where the fill lands **[RUN]**
- **Keep-out markers:** PMNDMY, NDMY, IND_MK are absent from all 74 block GDS (`lvs/marker_check.py`) (the top has 3 + 2 shapes, outside the
  analog blocks).
- **MIM:** no dummy metal over or under any MIM (FuseTop 6 µm rule). Dummy COMP and Poly2 do go under MIM plates
  (QVCO 132 + 103 tiles, adc_i 241 + 135, pad 310 + 315, top 5994 + 5689).
- **Inductors (QVCO, 2 spirals, 0.209 mm² footprint):** 20 387 Metal1 dummies in the footprint, 13 574 directly
  under coil metal, plus 2395 COMP and 2375 Poly2 tiles under the coil, and 6195 / 6192 / 6155 / 3914 dummies on
  Metal2 / 3 / 4 / 5 in the hollow and between turns.
- **RF and clock nodes:** fill comes to 2 µm of any wire on its own layer and the two adjacent layers, everywhere.

### Extraction with fill **[RUN]**
Magic's gf180mcuD tech maps dummy metal to `fillmN` types that are not conductors in its extract section, so the
project's PEX ignores fill whatever is in the GDS. For this check the dummies were moved to the drawing datatype
as floating shapes (`fill/remap.py`), the framed block was extracted flat with and without them
(`fill/pex.sh`, same hierarchy and options), and capacitance was summed per net (`fill/cap_delta.py`):
"grounded" treats every dummy as AC ground (upper bound); "floating" puts each dummy in series with its other
capacitances. Dummy COMP was not modelled.

`pll_ring` (25 231 dummies), wire capacitance per net:

| Net | No fill (fF) | Fill floating (fF) | Change |
|---|---|---|---|
| XRING/N0..N3 | 26.7 / 24.2 / 23.8 / 23.9 | 28.1 / 25.3 / 24.8 / 24.8 | +5.1 / +4.5 / +4.2 / +3.6 % |
| XRING/P0..P3 | 28.8 / 22.0 / 20.1 / 21.0 | 30.8 / 22.7 / 21.0 / 21.6 | +7.0 / +3.0 / +4.4 / +2.9 % |
| XRING/A0..A7 | 7.4–7.7 | 7.8 | +0.9 to +6.1 % |
| PH0..PH7 | 37.5–58.2 | 38.7–59.7 | +2.6 to +4.8 % |
| XRING/VT (control) | 216.3 | 262.8 | +21.5 % |
| all 356 nets | 12 128 | 13 221 | +9.0 % |

Ring frequency: the project's extracted bench (`scratch/wired_rx/r8ring/tscratch/pll_ring/sim/closed_625m.spice`,
tt, 27 °C, 3.3 V) run open loop with VCTRL pinned, published `pll_ring.ext.spice` against the same netlist plus
the 355 per-net fill capacitances (floating value):

| VCTRL | No fill | With fill | Change |
|---|---|---|---|
| 1.16 V | 661.9 MHz | 655.4 MHz | −0.98 % |
| 3.3 V | 1416.6 MHz | 1403.1 MHz | −0.95 % |

The increase is uneven across the ring (P0 +7.0 % against P3 +2.9 %), and adjacent-phase spacing moves by up to
8 ps (1.9° at 655 MHz) in a block whose 5° phase requirement is already missed (5.4–5.9° in the evidence file).
The stated ring margin is 5–13 %, so stock fill costs about a fifth of the smallest margin at tt. Not simulated:
ss corner, closed loop, jitter.

QVCO (147 131 dummies). IP–IN and QP–QN are one net each in extraction (the spiral is metal), so the number is the
total wire capacitance of each tank net:

| Tank net | No fill | Fill floating | Fill grounded |
|---|---|---|---|
| I (spiral 0) | 1464 fF | 2678 fF (+83 %) | 2884 fF (+97 %) |
| Q (spiral 1) | 1453 fF | 2673 fF (+84 %) | 2879 fF (+98 %) |

By dummy layer, per spiral (floating value): Metal1 803 fF (9242 squares), Poly2 293 fF (1516 tiles), Metal2–5
120 fF together. VTUNE +3.5 %.

Frequency shift estimate **[INF]**: tank about 2.65 nH and 2.45 GHz gives 1.59 pF differential. A capacitance ΔC
spread evenly along a differentially driven coil stores energy as ΔC/12 across the tank; lumped at the two ends it
would be ΔC/4. With ΔC = 1214 fF: 101 fF (−3.2 %) to 304 fF (−9.6 %). The even-spread figure is the better
estimate because the dummies sit under the whole coil. Either exceeds the 2.6–3 % band-edge margin of LO-10.
Q **[INF]**, not computed: the coil's capacitance to the substrate side nearly doubles, so the substrate-loss
term grows by up to (1.83)² ≈ 3.3 × where it is in the ωRC ≪ 1 regime; eddy loss in 2 µm squares is expected to be
small. An EM run is needed for a number.

### Fill strategy the project needs
**Top-level fill with block-owned keep-out markers, plus fill-aware extraction for the blocks that stay
fillable.** Evidence:
1. Per-block fill cannot close density: pll_ring, LNA, adc_i and ring_osc stay below the limits when filled alone,
   and the die passes only as an average (tables above). A block owner cannot sign off density.
2. The top fill is cheap (92 s) and passes with 4.5 mm² of analog kept out, so keep-outs are affordable where
   an analysis demands them. Blanket exclusion of all 8.5 mm² is not.
3. The live deck forces the marker route: DCF.1a exempts only NDMY, RES_MK, Pad and IND_MK areas; metal fill is
   excluded only by PMNDMY. An unmarked hole is a violation.
4. Keep-outs are needed first over the spirals (finding 2). Each owner draws PMNDMY + NDMY (+ IND_MK on
   inductors) in the block GDS where fill must not go, citing the analysis; everything else gets filled.
5. For blocks that are filled, the owner re-extracts with the top's fill in place. Today that needs the datatype
   remap used here, because Magic ignores `fillmN`.
6. After fill: full-chip DRC on the filled GDS (dummy rules DM.*, DCF.*, DPF.* have never run on project data),
   and LVS must ignore datatype 4.

## 4. Version drift (pre-mortem item 7)

### What is where **[RUN]**

| | Project images | Live wafer.space precheck (image `main`, revision 9b4e7da, built 2026-10-20) |
|---|---|---|
| open_pdks | 1.0.605, f6eeac7 | 1.0.616, 792ef67 |
| KLayout | 0.30.7 (canary), 0.30.9 (analog) | 0.30.12 |
| Magic | 8.3.623 | 8.3.677 |
| netgen | 1.5.316 | 1.5.323 |
| LibreLane | in canary | 3.1.0.dev3 |
| `gf180mcu_fd_pv` (decks) | e766ad1 | a561909 |
| `gf180mcu_fd_pr` (device models, PCells) | b6866b8 | 5e4be87 |
| precheck.py and scripts | identical to live | — |

`d658698` is not a PDK anyone ran: it is the default in the local clone's Makefile and the "reference" field of
the image's nodeinfo. The 10 Nov precheck used the canary image's `/pdk` (f6eeac7).

How the live precheck was obtained: `git clone` of `wafer-space/gf180mcu-precheck` into `dl/precheck-live`, and
the published image layers streamed from ghcr.io and unpacked selectively (PDK `libs.tech`, the KLayout and Magic
closures from the image's nix database). No install script was run; nothing was executed outside containers with
the network off.

### Could not run: the live binaries
The live image exists for amd64 only. This host is aarch64. Under QEMU user emulation KLayout 0.30.12 prints its
version, then segfaults inside the emulator on any script (a three-line Ruby script included). No native arm64
KLayout ≥ 0.30.11 with the DRC engine was available (Debian 0.30.0; the PyPI wheel has no DRC interpreter). The
LibreLane orchestrator's closure is 5.1 GB, over the disk budget. So: **the live deck was run, the live KLayout
and Magic were not.** The extracted store was deleted.

### Deck diff, f6eeac7 → 792ef67 **[RUN]**
Five of 41 rule files differ:
- `density.rb`: new rule DCF.1a (finding 1).
- `comp.rb`: DF.11 re-implemented (edge-based butted n+/p+ length).
- `contact.rb`: CO.5a / CO.5b now measure enclosure by Nplus / Pplus instead of a derived butted-COMP layer.
- `dummy_comp.rb`, `geom.rb`: comments only. Antenna deck: unchanged.
- Fill scripts: all three changed (respect existing dummies, `no_scribe_line`, Pad spacing 7 → 5 µm).
- Magic tech: 41 lines (version, NPLUS/PPLUS GDS output handling, FILLOBS/NDMY layer, mv diffusion paint rules).

### Live deck on the project's data **[RUN]** (KLayout 0.30.9 native, `workers=1`)

| Target | Decks | Project record | Live deck |
|---|---|---|---|
| top, no fill | density | 4 fails (10 Nov, other build) | 1302: DCF.1a 1296 + 6 global |
| top, stock fill | density | — | 10: DCF.1a |
| pll_ring, QVCO, LNA, pad rf_pair, wiredtx | main (`all,-antenna,-density,-cup`) and antenna | 0 / 0 (0.30.9) | 0 / 0 |
| adc_i | main, antenna | **no record exists** | main 0, antenna 7 (ANT.16_i_ANT.5); 7 with the project deck too |
| adc_q | antenna | 0 | 0 |
| top, no fill | `comp,contact` (all DF.* and CO.* rules, the only main-deck files that changed) | 0 (project deck, rerun here) | 0 |

### Antenna on the top **[RUN]**

| KLayout | workers | Result |
|---|---|---|
| 0.30.7 | 4 | 10 Nov: crash, `rdb.cc:737 cell != 0` in `ReportDatabase::save` |
| 0.30.7 | 1 | completes, 436 (ANT.16_i_ANT.3 16, _ANT.5 39, _ANT.6 311, ANT.16_ii_ANT.4 66, _ANT.6 4) |
| 0.30.9 | 1 | 10 Nov: completes, 436, same per rule |
| 0.30.7 | 4 | rerun here: same crash; the deck itself warns "parallel workers with klayout prior to 0.30.9 is likely to fail" (KLayout issue 2339) |
| 0.30.9 | 4 | completes, 436, same per rule (no dropped violations in this case) |
| 0.30.9, live deck | 1 | completes, 436, same per rule |

Why it crashed: KLayout 0.30.7 fails in `ReportDatabase::save` (an item without a cell) when the deck runs with
parallel workers; this is KLayout issue 2339, which the deck names in its own warning, fixed by 0.30.9 (mechanism
inside KLayout **[INF]**, not traced here). It is tied to `workers > 1`, not
to the top or to the antenna rules: the same binary, deck and GDS finish with `workers=1`, and a block (`pt_aosc`)
finishes in 3 s. The live precheck defaults to `--workers 1`; the project's wrapper passed 4.

## 5. Could not run / not done
- Live KLayout 0.30.12 and Magic 8.3.677 on any project data (amd64-only image, emulator crash). The claim that
  0.30.11+ changes violation counts is therefore untested here for 0.30.12.
- The LibreLane-orchestrated `precheck.py` end to end. Its stages were replayed by hand instead: density, antenna
  and the ID placement checks on the top; top-cell, size, pad-mask and zero-area were passed on 10 Nov with the
  same scripts and were not repeated.
- Full main-deck DRC of the top with the live deck (50–73 min native before the box throttle). Only the changed
  rule files were run on the top.
- Fill on a v6 top: no v6 GDS exists (outline floorplan only). All top numbers are the unrouted v3 top.
- QVCO Q with fill (needs EM), ring at ss and closed loop with fill, dummy COMP in extraction.
- Device-level reference for `pt_core_bias` top and any netlist for the `pt_lc_qvco5` top.
- `processes/gf180/process.lock` was not filled in (not mine to edit); the values are in the table above.

## 6. Per-block read-back table

| Block (top cell) | GDS | Devices ref / read-back | Magic read-back + netgen | KLayout deck (2nd extractor) | Note |
|---|---|---|---|---|---|
| pt_lna | rf_rx/generated/lna.gds | 835 / 835 | match | MOS+R match; not recognised: MIM |  |
| pt_rxmix_i | rf_rx/generated/rxmix_i.gds | 1186 / 1186 | match | MOS+R match; not recognised: MIM |  |
| pt_bbfilter_i | rf_rx/generated/bbfilter_i.gds | 1647 / 1647 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_bb_tap | rf_rx/generated/bb_tap.gds | 152 / 152 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_txmix_i | rf_tx/generated/txmix_i.gds | 62 / 62 | match | match |  |
| pt_txsum | rf_tx/generated/txsum.gds | 16 / 16 | match | match |  |
| pt_rfdriver | rf_tx/generated/rfdriver.gds | 855 / 855 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_adc_i | converters/generated/adc_i.gds | 3727 / 3727 | match | MOS+R match; not recognised: MIM |  |
| pt_adc_q | converters/generated/adc_q.gds | 3735 / 3735 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_dac_i | converters/generated/dac_i.gds | 7524 / 7524 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_dac_q | converters/generated/dac_q.gds | 7524 / 7524 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_refbuf | converters/generated/refbuf.gds | 56 / 56 | match | MOS+R match; not recognised: MIM |  |
| pt_pll_vreg2 | pll_vreg/generated/pt_pll_vreg2.gds | 230 / 230 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_clockmux | timing/generated/clockmux.gds | 150 / 150 | match | match |  |
| pt_aosc | timing/generated/aosc.gds | 34 / 34 | match | match |  |
| pt_pll_ring | timing/generated/pll_ring.gds | 789 / 789 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_polyphase | timing/generated/polyphase.gds | 86 / 86 | match | match |  |
| pt_clk_obs16 | timing/generated/clk_obs16.gds | 505 / 505 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_obs_pre4 | timing/generated/obs_pre4.gds | 41 / 41 | match | match |  |
| pt_ring_osc | timing/generated/ring_osc.gds | 55 / 55 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_pll_ring_core | timing/generated/pll_ring_core.gds | 530 / 530 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_lo_mmd_qdum | timing/generated/lo_mmd_qdum.gds | 44 / 44 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_wordclk | timing/generated/wordclk.gds | 210 / 210 | match | match |  |
| pt_prescale | timing/generated/prescale.gds | 98 / 98 | match | match |  |
| pt_lo_lf | timing/generated/lo_lf.gds | 91 / 91 | match | MOS+R match; not recognised: MIM |  |
| pt_lo_obs | timing/generated/lo_obs.gds | 75 / 75 | match | match |  |
| pt_lo_pfdcp | timing/generated/lo_pfdcp.gds | 151 / 151 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_diff_clk_rx | timing/generated/diff_clk_rx.gds | 127 / 127 | match | MOS+R match; not recognised: MIM |  |
| pt_clk_obs | timing/generated/clk_obs.gds | 400 / 400 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_lo_ext | timing/generated/lo_ext.gds | 481 / 481 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_vco_replica | timing/generated/vco_replica.gds | 219 / 219 | match | match |  |
| pt_lo_mmd | timing/generated/lo_mmd.gds | 528 / 528 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_lc_qvco5 | timing/generated/lcvco/pt_lc_qvco5.gds | 974 / 974 | match (core) | MOS+R match; not recognised: MIM, nd2ps diode | core subcell only (974 devices, read from the top GDS); the top `pt_lc_qvco5` has no netlist and no ports; spiral hookup read back as IP-IN and QP-QN only |
| pt_rxlevel | wired_rx/generated/rxlevel.gds | 70 / 70 | match | match |  |
| pt_cdr | wired_rx/generated/cdr.gds | 407 / 407 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_ctle | wired_rx/generated/ctle.gds | 268 / 268 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_ptrim | wired_rx/generated/ptrim.gds | 670 / 670 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_rxselect | wired_rx/generated/rxselect.gds | 26 / 26 | match | match |  |
| pt_wmon_sel | wired_rx/generated/wmon_sel.gds | 47 / 47 | match | match |  |
| pt_termination | wired_rx/generated/termination.gds | 146 / 146 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_vthdac | wired_rx/generated/vthdac.gds | 166 / 166 | match | match |  |
| pt_detect | wired_rx/generated/detect.gds | 439 / 439 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_wrx_cap | wired_rx/generated/wrx_cap.gds | 6304 / 6304 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_slicer | wired_rx/generated/slicer.gds | 864 / 864 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_wtx_hsbias | wired_tx/generated/hsbias.gds | 53 / 53 | match | match |  |
| pt_wiredtx | wired_tx/generated/wiredtx.gds | 2274 / 2274 | match | MOS+R match; not recognised: nd2ps diode |  |
| tx_steering_buffer_flat | pads/generated/steering-buffer-compact/tx_steering_buffer_flat.gds | 128 / 128 | match | match |  |
| buffer_compensated_flat | pads/generated/termination-buffer-candidate/compact-array/buffer_compensated_flat.gds | 282 / 282 | match | MOS+R match; not recognised: MIM |  |
| pad_tlp_flat | pads/generated/tlp-site/pad_tlp_flat.gds | 8 / 8 | match | match |  |
| pad_rf_pair | pads/generated/stress-safe-families/rf-pair/pad.gds | 388 / 388 | match | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised |  |
| pad_rftxpad | pads/generated/stress-safe-families/rf-tx/pad.gds | 388 / 388 | match | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised |  |
| pad_single_leg | pads/generated/stress-safe-families/single-leg/pad.gds | 388 / 388 | match | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised |  |
| pad_refpad | pads/generated/stress-safe-families/reference/combined.gds | 405 / 404 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pad_hspad | pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds | 509 / 508 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pad_wirepad | pads/generated/stress-safe-families/wired-receive-usb/combined.gds | 740 / 739 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pad_txpad | pads/generated/stress-safe-families/wired-transmit/combined.gds | 596 / 595 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pt_rxmix_q | rf_rx/generated/rxmix_q.gds | 1186 / 1186 | match | MOS+R match; not recognised: MIM |  |
| pt_bbfilter_q | rf_rx/generated/bbfilter_q.gds | 1647 / 1647 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_txmix_q | rf_tx/generated/txmix_q.gds | 62 / 62 | match | match |  |
| pt_wtx_fallback_control | bringup_control/generated/pt_wtx_fallback_control.gds | 50 / 50 | match | match |  |
| gf180mcu_ocd_ip__por | core_support/por/gds/gf180mcu_ocd_ip__por.gds.gz | 494 / 494 | match | MOS+R match; not recognised: MIM |  |
| pt_core_bias | scratch/core-bias-routing-20261110-compact/pt_core_bias_routed.gds | 0 / 4147 | match per leaf (see note) | no flat reference | top = routing LVS with black boxes (already from GDS); 9 leaf masters read back from the routed GDS: 7 match, bandgap matches with the documented PNP name alias, biasgen identical to the vendored patched tapeout GDS |
| isw_wired | scratch/island-support-20261108-075605/layout/isw_wired.gds | 3560 / 3560 | match | match |  |
| isw_rf | scratch/island-support-20261108-075605/layout/isw_rf.gds | 2554 / 2554 | match | match |  |
| isw_pll | scratch/island-support-20261108-075605/layout/isw_pll.gds | 2736 / 2736 | match | match |  |
| isw_conv | scratch/island-support-20261108-075605/layout/isw_conv.gds | 1346 / 1346 | match | match |  |
| isw_debug | scratch/island-support-20261108-075605/layout/isw_debug.gds | 1790 / 1790 | match | match |  |
| iso_clamp | scratch/island-support-20261108-075605/layout/iso_clamp.gds | 6 / 6 | match | match |  |
| atb_leaf_s | scratch/island-support-20261108-075605/layout/atb_leaf_s.gds | 7 / 7 | match | match |  |
| atb_leaf_f | scratch/island-support-20261108-075605/layout/atb_leaf_f.gds | 7 / 7 | match | match |  |
| atb_grp | scratch/island-support-20261108-075605/layout/atb_grp.gds | 20 / 20 | match | match |  |
| pt_decap_tile | decap/generated/pt_decap_tile.gds | 22 / 22 | match | match |  |
| atb_pad | scratch/island-support-20261108-075605/layout/atb_pad.gds | 22 / 22 | match | match |  |
| pt_pll_vreg | pll_vreg/generated/pt_pll_vreg.gds | 196 / 196 | match | MOS+R match; not recognised: nd2ps diode |  |

## 7. Files
`scratch/integration/signoff-gap/`:
- `lvs/rb_lvs.py`, `lvs/kl_lvs.py`, `lvs/mim_area.py`, `lvs/nc_make.py`, `lvs/run_all.sh`, `lvs/blocks.json`,
  `lvs/results.json`, `lvs/results-extra.json`, `lvs/mim_area.json`
- `fill/run_fill.sh`, `fill/fill_wrap.rb`, `fill/frame.py`, `fill/keepout.py`, `fill/dens.py`, `fill/remap.py`,
  `fill/pex.sh`, `fill/cap_delta.py`, `fill/reduce_fill.py`, `fill/out/*.dens.json`, `fill/out/*.capdelta.json`,
  `fill/out/qvco.tank_fill_by_layer.json`, `fill/sim/pub_*.spice` and logs
- `precheck/native_kl.sh`, `precheck/queue1.sh`, `precheck/count_lyrdb.py`, `precheck/id_check.py`, `precheck/runs/*/counts.json`
- not committed: `precheck/pdk_f6eeac7/`, `precheck/pdk_792ef67/` (deck, fill-script and Magic-tech copies of the two PDKs), `dl/precheck-live/` (clone of the live precheck), `lvs/work/` (per-block logs)
