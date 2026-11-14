# wafer.space answers from public sources (web research, 2026-11-14)

Answers to `pads-core/wafer-space-questions.md` (Q1-Q11) and to the related open questions (a)-(h) from
`pre-mortem.md` / `signoff-gap.md`. Packaging scope per the user: **chip-on-board only** (bare dice exist but are not wanted).

Confidence labels: **P** = confirmed by a primary source (wafer.space website, its GitHub repositories, files in them);
**T** = stated by a wafer.space team member in the public Discord archive (not a document, can change);
**S** = stated by a secondary source (community member, Tiny Tapeout, PDK maintainer); **I** = inferred; **NF** = not found publicly.

Who is who in the Discord quotes: `mithro_` = Tim Ansell (founder); `mole99` = Leo Moser (template, precheck, reticle);
`anfroholic` = Andrew Wingate (COB board designer, die sorting); `saladchap` = "stuart" (runs the bonding for wafer.space and
Tiny Tapeout); `lauri4332` = Lauri (COB tester, bonding trials); `kris____` = Kristaps Jurkans (announcements);
`246tnt` = Sylvain Munaut (Tiny Tapeout, **S**); `rtimothyedwards` = Tim Edwards (open_pdks maintainer, **S**).

Sources used (all public, fetched 2026-11-14):
- Website `https://wafer.space/` and its source `github.com/wafer-space/wafer-space.github.io` (HEAD `59c1915`, 2026-11-11): `_data/runs.yml`, `_posts/`.
- COB boards `github.com/wafer-space/chip-on-board-wire-bonded-pcbs` (main `5cb4668`, 2026-10-10; branch `nextpcb-drc` `3458335`, 2026-11-14).
- Precheck `github.com/wafer-space/gf180mcu-precheck` (main `9b4e7da`, 2026-10-20) and its open PR #49 (branch `leo/layer-checks`).
- Public Discord archive `https://discord.wafer.space` (source `github.com/wafer-space/discord.wafer.space`, branch `gh-pages`,
  exported 2026-11-14, 19,596 messages). Quotes are cited as *channel or thread, date, author*.
- Crowd Supply pages returned HTTP 403 to the fetcher; their content is quoted only where the website or Discord repeats it.

## Summary

| # | Question | Answer in one line | Conf. |
|---|---|---|---|
| a | Run 3 deadline, later run | Purchase 9 Dec 2026, clean GDS 16 Dec 2026 (23:59 AoE), parts Q2 2027. **Run 3 1x1 slots sold out 22 Sep 2026.** Run 4: "in the works", earliest close about end of Jan 2027, not announced, prices will change | P / T |
| b | Process options | gf180mcuD: 5 metals, 11 kA (1.1 um) top metal, MIM option B (Metal4-Metal5) at 2 fF/um2, 1 kohm/sq high-res poly, native-Vt NMOS allowed, 6 V devices and LDMOS allowed. Deep n-well, `_dss` / SAB: in gf180mcuD and the precheck deck, no explicit wafer.space statement. **The `ESD` layer (24/0) is "not part of the wafer.space process stack"** (open precheck PR) | T / S |
| c | PCM / e-test data | Yes for Run 1: GF e-test data was published as a Google Sheet (4 Apr 2026), "pretty close to typical"; MIM measured 1.92 fF/um2. Run 2 data not posted yet | T |
| d, Q7, Q11 | Die thickness, back side, attach | Run 1 dies were back-ground to about 250 um; later runs not promised. Attach: glue, intended conductive, not confirmed in writing for wafer.space; Tiny Tapeout (same bonder) uses conductive epoxy. Board paddle is GND; "GND pads ... shorted together and to the chip backside". Back-side metal: NF | T / S |
| e, Q2-Q6 | Bonding rules | One fixed bonding layout per slot size, shared by all customers; no custom or per-die bond diagram inside the COB add-on. Published rules unchanged (no crossing, <= 45 deg, < 3 mm, >= 1 mm or 2x die thickness). Down-bonds, double bonds, extra bonds: not offered; custom bonding only as a separate contract with "stuart" | P / T |
| Q8 | Wire | Run 1: aluminium (AlSi 1 %), 0.8 mil (about 20 um), wedge bonded. Since Sep 2026 new bonding partners, trialling Al wedge and gold thermosonic. Current rating: only a community figure (500 mA fusing for 25 um Al) | T / S |
| f | The COB board | Fixed wafer.space design per run, KiCad files public. 1x1: 14 x 16 mm, 4 layers, 0.8 mm, ENIG, 74 fingers, 70-pin 0.4 mm mezzanine connector on the back, **8 x 1 uF 0201 capacitors on the back, one per supply net**, GND paddle 4.0 x 5.2 mm, black or clear epoxy glob-top over die and wires. Customer-modified boards were accepted in Run 1 only with the same fingers, outline, connector and passives area; "not certain we will be accepting any custom cob this time" | P / T |
| Q1 | Which board for Run 3 | Not stated. Run-2 board is the newest; a NextPCB re-spin of the run-2 1x1 board is in progress (10-14 Nov 2026) with **identical fingers, paddle, capacitors and connector** | P / I |
| g | Precheck | `gf180mcu-precheck` 1.7.4, PDK `792ef67` (open_pdks via ciel), LibreLane `99148a9`. DCF.1a added 20 Oct 2026. Density is a gating step; the user must run fill (template does it; analog tops run `fill_all.rb`). Pad-mask check: template openings must exist, extra openings are fine | P |
| h | Slot sizes | 1x1 3.932 x 5.122 mm, 0.5x1 1.936 x 5.122, 1x0.5 3.932 x 2.531, 0.5x0.5 1.936 x 2.531. Nothing larger than 1x1. Several slots can be bought (separate dies). Half and quarter sizes may shrink in a later run (wider saw street); 1x1 is meant to stay | P / T |
| Q9 | Devices built | See (b). Nothing says gf180mcuD devices are excluded except the forbidden layers Via5, MetalTop, ESD, FuseWindow_D / POLYFUSE (PR #49, not merged) | P / S |
| Q10 | Custom pad cells, VDD/DVSS shorts | Custom pads are allowed ("what circuit is connected to the bond pad is entirely up to you"). GND fingers are one net on the board; supply fingers are separate nets, each with a 1 uF capacitor. On-die DVDD/VDD short in the stock cells: NF | T |

---

## (a) Run 3 deadline and later runs

- **Dates (P).** `https://wafer.space/` and `_data/runs.yml` (`gf180mcu_run_3`): purchase deadline "9 December 2026 @ 11:59 PM" AoE,
  submission deadline "16 December 2026 @ 11:59 PM" AoE, described as "Final deadline to submit clean GDS"; parts "Q2 2027"
  (`delivery_date` 2027-04-16). The dates were changed in commit `9c7c43a` "Update submission date" on 2026-07-31.
- **Conflict.** The two announcement posts still show the old dates: `_posts/2026-07-24-run3-coming-soon.md` and
  `_posts/2026-08-10-run3-announcement.md`: "15 December 2026 | Slot purchase deadline", "29 December 2026 | Deadline to submit GDS files".
  Every later post (23, 25, 28, 30 Sep, 7 Oct 2026) says 9 / 16 December. Treat 16 December as the date.
- **No extension expected (S, Crowd Supply text via search result).** For Run 2 the two-week GDS extension was called a one-time
  extension that "will not be happening on future runs".
- **1x1 slots are sold out (P).** `_posts/2026-09-22-run3-1x1-slots-gone.md` (22 Sep 2026): "All of our full-sized slots are gone for
  this run"; "We're looking into additional capacity, but the next opportunity will most likely be a future run."
  Discord, thread *run-3-sold-out...*, 2026-10-11, `kris____`: "it's unlikely that any run 3 slots will open up, but run 4 is in the works."
  **This only matters if the project has not already bought its 1x1 slot.**
- **Run 4 (T).** Same thread, `mithro_`, 2026-10-11: "I'm trying to figure out how aggressive to be on Run #4 - earliest would be
  like end of Jan (which is like ~1 month after Run #3 closes)." 2026-10-20: "the biggest problem is going to be what GF is able to
  provide. It seems like they are having capacity issues ... Hopefully will have things figured out so I can announce the first
  week of November." and "there will be some price changes on Run #4." No Run 4 dates are in `runs.yml` or in the announcements
  channel as of 2026-11-14. A Crowd Supply page `crowdsupply.com/wafer-space/gf180mcu-run-4` exists (not readable by the fetcher).
- **Ask by email:** whether the project's slot is a confirmed Run 3 1x1; Run 4 purchase and GDS dates.

## (b), Q9: process options

| Option | Answer | Conf. | Source and quote |
|---|---|---|---|
| PDK variant | `gf180mcuD` | P | Precheck `Makefile`: `PDK ?= gf180mcuD`, `PDK_COMMIT ?= 792ef67037d74c8c51811eab3ce23cf793491296` |
| Metal stack | 5 metal layers (1P5M); Via5 and MetalTop forbidden | P | Website "5 Layers"; precheck README "the max metal layer is Metal5" |
| Top metal | 11 kA = 1.1 um | T | *top-metal-thickness*, 2025-10-01, `mithro_`: "We are using the B option" ... "1.1um (a.k.a. 11 kiloAngstroms)". open_pdks NOTES (quoted there): gf180mcuD "has a top metal thickness of 1.1um instead of 0.9um" |
| MIM | Option B (between Metal4 and Metal5), 2 fF/um2, device `cap_mim_2f0_m4m5_noshield` | T / S | *what-mimcaps-can-we-use*, 2026-06-02, `246tnt`: "Yes, MIM-B is what you can use." Tim Edwards 2026-06-03: the magic tech file "assumes the options 1kOhm/sq for the resistor and 2fF/um for the MiM capacitor"; `246tnt` 2026-06-03: e-test "spec is 1.7 fF/um^2 minimum and 2.3 fF/um^2 maximum and we hit 1.92 fF/um^2 on run 1". **Conflict:** `246tnt` first wrote "1.5 fF / um^2 is the config used" (2026-06-02) and corrected it the next day; the PDK stack-up page lists only 1.0 and 1.5 for option B (doc error per the thread) |
| High-res poly | 1 kohm/sq (`ppolyf_u_1k`, 3.3 V and 6 V) | T / S | *high-res-poly-resistor-option*, 2026-03-20, Tim Edwards: "it's all what's defined in `gf180mcuD`"; *metal-and-module-selection-for-run3*, 2026-08-06, `246tnt`: "11KA / MiM Option B / 2 fF/um^2 / 1000 ohm/sq" |
| Native-Vt NMOS (NAT) | Allowed; needs no extra mask | S | *are-native-vt-nmos-available*, 2025-10-09, Tim Edwards: "It does not involve an additional mask layer ... I have always assumed that NAT and native Vt devices are available." 2026-05-26: "assuming that the NAT layer is included in the process options (which I think is true for Wafer.Space)". `246tnt` 2026-08-02: "It supports: 2 fF/um^2 MiM, 1k / sq HRES poly, Native 6.0v nmos". No statement from wafer.space itself |
| 6 V devices, LDMOS | Allowed | T | `mole99`, 2026-05-15: "It does not seem that LDMOS requires any additional mask layers. So as long as your design is DRC clean, you're good to go." Template supports 3.3 V and 5 V cells and I/O |
| Deep n-well | In gf180mcuD and its decks; no wafer.space statement | NF | Only indirect: "it's all what's defined in gf180mcuD" |
| `_dss` devices, SAB | SAB (salicide block) is a normal layer; `_dss` devices are in the PDK; the provider I/O cells use SAB | S / T | *salicidation*, 2025-10-01 (confirmed by Tim Edwards); `mole99` 2026-08-11: "There shouldn't be much SAB in the layout except for the ESD devices." |
| **ESD implant layer (24/0)** | **Not in the wafer.space stack** | P (open PR) | Precheck PR #49, branch `leo/layer-checks` (2026-08-20), `scripts/klayout/check_size.py`: "Layer 'ESD' is not part of the wafers.space process stack." Same list: Via5, MetalTop, FuseWindow_D, POLYFUSE. Not merged, so today's precheck does not reject it |
| `cap_nmos_03v3_b` | In the PDK; modelled as an ideal capacitor | S | Tim Edwards, 2025-11-22: moscap devices "are just modeled as ideal capacitors" |
| Mask count | "1P5M26ML" = 26 mask layers | S | `246tnt`, 2026-08-06, quoting the Crowd Supply page |

- The process options are not written down on any wafer.space page. Tim Edwards, 2026-06-03: "there is *no* indication in the way
  of layer ID markers to indicate which option is which ... The only other place it's decided is when Wafer Space submits the form to GF."
  `mithro_` linked his mask-layer notes (Google Sheet `1RRPZ5prd2J3x1TO8l8eW8O50F2o9tF4JRuRT-NS01oU`, 2026-05-27); not fetched.
- **Check in the project:** search the chip GDS for shapes on layer 24/0 (ESD). If the custom ESD cells draw it, that implant will not exist.
- **Ask by email:** written confirmation of NAT, DNWELL, SAB / `_dss` outside the provider cells; whether layer 24/0 is dropped.

## (c) PCM / WAT data

- **Yes, for Run 1 (T).** *general*, 2026-04-04, `mithro_`: "E-Test data provided by GF can be found @
  https://docs.google.com/spreadsheets/d/10zQF_L-KsV-n5zMISB8C67llsldodtbSALWoNdpY17Y/ ... anyone see anything interesting?"
  `246tnt`, same day: "Doing a few spot check vs the PDK values, it's pretty close to typical."
- 2026-05-05, `mithro_`: "GlobalFoundries puts process test structures into the margins of the reticle - this is where the
  'etest' data for the production run comes from". 2026-09-17: "we don't control the e-test structures or data."
- Run 2: 2026-09-28, `mithro_` to `246tnt`: "Poke me again about the etest data as well" (not posted yet).
- It is lot-level data shared with everyone, not a per-customer deliverable, and nothing promises it for Run 3.
- The sheet was not fetched here (a Google document). **Action:** open it and compare with the ss/ff corner assumptions.

## (d), Q7, Q11: die thickness, back side, die attach, paddle

- **Thickness (T).** Thread *overall-die-thickness*, 2026-03-27, `mithro_`: "For Run #1 it is looking like the final thickness will be
  250um or 0.25mm -- Unclear if this will be the thickness going forward for future runs." 2026-04-23: "The die people just received are ~250um thick."
- **Back-grind for Run 2 (T).** 2026-10-03, `anfroholic`: "Dicing house has them, they wanted to back grind again".
  2026-10-05: "Again this time, they're requesting we back-grind the wafers. We're looking to reduce costs as best we can."
  `mole99`, 2026-10-09: "we are now doing 60um total width with backgrinding". Dicing-house note, 2026-10-16: "After we thin down the
  wafer, we see a lot of unusual backside chipping". So Run 2 appears to have been thinned again; its final thickness is not stated; a full-thickness
  (about 0.75 mm) option with a wider saw street is under discussion for later runs.
- **Back-side finish / metal: NF.** Nothing says back metal is applied; the dies are ground and sawn (I: bare ground silicon).
- **Die attach (T / S, not confirmed).** *cob*, 2026-02-27: question "Which glue is planned ... conductive or non-conductive?"
  `anfroholic`: "there seems to be little reason why we would have anything other than conductive, so would imagine that would be
  what we ask for. I also imagine we can have whatever we ask for." `246tnt` (Tiny Tapeout, same bonding contact): "We use conductive epoxy."
  Website post `2026-06-03-chip-on-board-progress`: "the die is physically glued to the PCB" and "Since the die is mounted by hand,
  the machine uses a computer vision system to readjust the bond".
  2026-09-28, `246tnt`, thread *requirements-for-cob*: "GND pads must be identical to the defaults (They are all shorted together and to the chip backside)".
- **Paddle (P).** Footprint `waferspace_default_padring_v0.2`, pad 75: 4.0 x 5.2 mm, net `GND`, in run-1, run-2 and the `nextpcb-drc` branch.
- **Change since Run 1:** the bonding house changed ("new bonding partners", Sep 2026), so the Run 1 attach material is not evidence for Run 3.
- **Ask by email:** attach material for Run 3 (silver epoxy or not), final die thickness for Run 3, back-side finish.

## (e), Q2-Q6: bonding rules

- **Published rules (P), unchanged at HEAD.** `run-1/wirebonding/README.md`: "No wires may cross." / "Wire angle must be not greater
  than 45°." / "Maximum wire length must be less than 3 mm" / "Minimum wire length is 1 mm from the die, or 2× the die thickness
  (whichever is greater)." / "No solder mask is allowed in the area to be bonded." With a 250 um die the minimum is 1 mm.
- **How the angle is meant (S).** *cob*, 2026-04-30, review quoted by `anfroholic`: "The bond wires should have an angle of at least
  45 degrees with the die edge (this is relaxed for pads 1, 24, 37 and 60 because they are the last pads on the particular die edge
  so there is no next pad to disturb)". That is the same measure BOND-AUDIT uses (angle to the edge normal <= 45 deg), and it
  suggests the end-of-row pads have some tolerance. Whether length is plan view or wire length: NF.
- **Fixed or custom bond diagram (T): fixed.** `mole99`, 2025-10-09: the COB option "can only be used with this exact padframe,
  since the setup cost is shared across all designs." 2025-10-27: "If you adjust the padring, we need to pay a second bonding setup fee."
  `anfroholic`, 2026-08-02: "all standard slot sizes will have COB available, you do not need to do custom bonding diagrams, just
  use the default pad structure (VSS, VDD are the only ones that need to be the same)". `mithro_`, 2026-09-28: "The minimum cost is
  pretty much ~$1,500 per run -- no matter if we bond 10 die or 1,000 die." A per-project diagram is generated by wafer.space
  (`run-1/wirebonding/BTAP.pdf`, `MOLE.pdf`, ...), for the operator, from the fixed layout.
- **Per-die variation: no (I from the above).** One program per project; "Each 1,000 unit run is pretty much a separate run as far
  as the wire bonders are concerned" (`mithro_`, 2025-10-20).
- **Leaving a pad unbonded (I).** Not stated. The precheck requires every template opening to exist; the tester treats a pad
  without a connection as OPEN (see (f)). Ask.
- **Extra pad openings (P for the layout, T for bonding).** Precheck `scripts/klayout/check_mask.drc`: "Additional pad openings,
  e.g. in the center of the die, are fine." (`input(37,0).and(mask).xor(mask)` must be empty). They pass the precheck; nothing
  says they will be bonded, and the fixed diagram has 74 wires.
- **Down-bonds, double bonds, two wires on a finger: NF for wafer.space.** Only general remarks: `mithro_`, 2025-10-05: "Frequently
  people seem to double bond power stuff."; the MOSbius group (own board, Run 1): "We double bond the VDD and have VSS in the four corners".
  Cost is per wire ("1-2 cent per wire bond", `mithro_`, 2025-11-26).
- **Min pad pitch / opening: NF for the bonder.** The bonder has no design guide (`anfroholic`, 2026-08-10: "They don't have a guide
  like this"). A "fairly representative" guide from another house was linked
  (`https://drive.google.com/file/d/1touEQHWAOTon_98TdiVLKKqsQ8RJJ1tP/view`, not fetched); `anfroholic`, 2025-11-07, reading it:
  "Looks like 15µm between pads". Template pad: opening 60 x 60 um on a 65.35 x 68 um metal pad (`246tnt`, 2026-04-28).
- **Die placement tolerance, loop height: NF.** Dies are glued by hand; the bonder's vision aligns to the die, not to the board
  (website post; `namibj`, 2026-09-20), which is why the fingers are 1.0 x 0.25 mm.
- **Custom bonding route (T).** `saladchap`, 2026-09-09: "people can contact me ... This is also generally applicable if you need a
  custom PCB to bond your die to". `mithro_`, 2026-09-23: "@stuart offers such a service". That means bare dice go to a separate
  contract, outside the COB add-on.
- **Run 1 bonding quality (T).** April 2026: several Run 1 COBs had failed bonds and pads shorted to the ground rail
  (`246tnt`, 2026-04-28: "I have 9 chips here, 6 have several failed bonds"). Later results: 95-100 % per project
  (`lauri4332`, 2026-09-16 / 09-20, `github.com/wafer-space/ws-run1-cob`); `saladchap`, 2026-09-05: "with the new bonding partners
  we're up at over 90% pass rate based on recent trials".

## Q8: wire and current

- **Run 1 wire (T).** Thread *maximum-current-carrying-capacity...*, 2026-06-04, `246tnt`: "the wire used for this run was AlSi1% 1mil";
  `mithro_`, 2026-06-06: "I believe it's actually 0.8mil?" ... "I think they normally use 1mil but needed to use 0.8mil for our parts."
  `mithro_`, 2026-08-08: "Only Al bonds at the moment."
- **Run 2 / 3 (T).** `saladchap`, 2026-09-05: "We're trialling both alu wedge and gold thermosonic". Not decided publicly.
- **Current (S).** `246tnt`, 2025-10-20: "500 mA per bond wire (for 25u Al wedge bonded) *fusing* current, so you'd want to stay way
  away from that, say half." For 0.8 mil (20 um) the fusing current is lower (I: roughly 0.7x, about 350 mA). The project's 88 mA
  worst bond is inside that, without a rated figure from wafer.space.
- **Connector contact rating: NF.** Part: HCTL `HC-PBB40C-70DP-0.4V-02`, 70 pins, 0.4 mm pitch (LCSC C19089236, mate C19089262);
  the datasheet was not found by search.

## (f), Q1: the COB board

- **What it is (P).** `run-2/1x1-cob/1x1-mezzanine.kicad_pcb` (KiCad, with schematic, panel, BOM, position files; licence in repo):
  - 14 x 16 mm, 4 copper layers, stack-up 0.747 mm ("JLCPCB's 4-layer 0.8mm thick PCB with ENIG", `saladchap`, 2026-05-27);
  - top: footprint `waferspace_default_padring_v0.2` (74 fingers 1.0 x 0.25 mm at 0.4 mm pitch, GND paddle 4.0 x 5.2 mm), pin-1 fiducial hole;
  - bottom: 70-pin 0.4 mm mezzanine connector under the die, and **eight 1 uF 0201 capacitors** C101-C108, one from each of
    `VDD_IO_0..3`, `VDD_CORE_0..1`, `PWR_AUX_0..1` to GND, at x = +-6.25 mm from the die centre (about 1.4 mm outside the E/W finger
    rows, on the other side of the board), inside a silkscreen box "Allocated Space For Passives";
  - Run 1 board `run-1/1x1-cob` has the same eight capacitors. Website post `2025-11-11-chip-on-board-strategy`:
    "1 µF decoupling capacitors on VDD_IO, VDD_CORE, and PWR_AUX pins".
  - `anfroholic`, 2026-08-10: "ground are tied together. power are all separate, *but* they all each have a decoupling cap".
    `246tnt`, 2026-09-28: "Power pads are routed independently but they have decoupling caps, so you can pretty much only use them
    for power, or bias signals."
- **Passives near the die (T).** `saladchap`, 2026-03-20: "Passives are OK on the top as long as they're not too tall. If on the bottom
  then they should be in the 'designated' area since we will be making a jig with cut outs for that area" and "'too tall' meaning
  0201s/0402s and similar are fine, headers and pins are not". `anfroholic`, 2026-03-15: "They will be populating the boards with
  the mezzanine connector and the passives before the die is wire-bonded." `anfroholic`, 2026-10-10: "the length from the die to
  the pcb is probably the most determining factor. And having them on the PCB itself gets it as close as possible".
- **Encapsulation (P / T).** Website post 2026-06-03: "an epoxy glob-top is applied to protect the sensitive die and wires" then baked.
  Clear or black were both discussed for Run 1 (`anfroholic`, 2026-03-15 / 03-20: "I'm sure we can do them all dark"). Rule being
  adopted for run 2 boards: "No vias/holes/etc. under globtop" (COB repo issue #11).
- **Can the customer supply or modify the board? (T): not as a standard option.**
  - `mithro_`, 2026-03-07, thread *multiple-pcb-design*: "At the moment it isn't really possible to submit a custom PCB for
    wire-bonding without a lot of extra work."
  - What Run 1 allowed, `anfroholic`, 2025-12-17: "You're also welcome to design your own COB chip as long as you respect the pad
    locations on the die, the wirebond pads on the COB PCB, and the location of the mezzanine connector. But going outside the
    standards will leave all the remaining details to you." `mithro_`, 2026-04-29: "It's important to keep the same footprint and
    placement of capacitors/connectors as the existing board - otherwise the CoB house has to make a new jig."
    `anfroholic`, 2026-04-29: "the edge.cuts layer should stay the same ... Anything on the back should remain in the designated areas".
    Two Run 1 projects did this (MOSbius `mosbius-panel/V3_COB_Original`, TQVA `tqva-cob`, both in the repo).
  - For this run, `anfroholic`, 2026-08-07: "I'm also not certain we will be accepting *any* custom cob this time? Keep in mind the
    only custom ones last time shared the wirebonding layout, just had different traces and routing on the pcb."
  - Outside the add-on: custom board and custom bonding through "stuart" (see (e)).
- **So, per feature:** different traces, net assignment, ground copper, extra top-side 0201/0402 parts on the unchanged finger
  pattern: done in Run 1, uncertain for Run 3 (ask). Different finger pattern, extra fingers, a second wire per finger, down-bonds:
  not available in the add-on.
- **Which board for Run 3 (Q1): not stated.** `anfroholic`, announcements, 2026-10-09, about the run-2 boards: "this Run's CoB. Now
  with: More sane orientation, Pin 1 Fiducial, Overall better routing and yield improvements, Anti-reverse element".
  `mole99`, 2026-09-27: "We didn't plan on any functional changes to the CoB, but Andrew can confirm that for sure."
  Run-1 README: pinouts, connector and footprint "are specific to this run and are expected to change in future runs".
  Branch `nextpcb-drc` (10-14 Nov 2026, "1x1 passed") re-works the run-2 1x1 board for another PCB vendor: U102 fingers and paddle,
  the eight capacitors and the connector are at identical positions with identical nets (compared here). No `run-3/` directory exists.
- **Testing (T).** Every COB is tested on a bond tester (`github.com/szfate/BondTest72`): each signal pad's ESD diode is measured at
  10 uA / 100 uA / 1 mA and reported "OPEN / GOOD"; "Power pads now tested via capacitor charging curve monitoring"
  (`lauri4332`, 2026-09-03 / 09-21). `mole99`, 2026-09-09: "we don't know what's underneath the pad openings. People could ... even
  make their own fully custom pads. Therefore, we would need to require the user to specify which tests ... should be done."
- **Delivery form (S).** `246tnt`, 2026-08-28: "you probably get them still on the panel ... v-grooved / pre-cut". Customers who buy
  COB may also get "a few bare die" (`mithro_`, 2026-10-07, "hoping (but not promising)").
- **Ask by email:** whether a modified 1x1 board (same outline, fingers, connector, passives area; extra 0201/0402 parts on the top
  near the fingers; changed ground copper) is accepted for Run 3 and by what date; glob-top colour and material.

## (g) Precheck

- **Repository and pins (P).** `github.com/wafer-space/gf180mcu-precheck`, main `9b4e7da` (2026-10-20, "chore: update pdk and
  librelane (#50)"), release 1.7.4; `Makefile`: `PDK_COMMIT ?= 792ef67037d74c8c51811eab3ce23cf793491296` (fossi-foundation/open-pdks,
  fetched with ciel); `flake.lock`: `librelane/librelane` `99148a9c1e`, `nix-eda` `8a8e673d53`. Template 1.6.0 uses the same PDK.
  KLayout and Magic versions are not written in the repository (they come from nix-eda); `signoff-gap.md` read 0.30.12 and 8.3.677
  out of the published image, which is consistent with these pins. Not re-derived here.
- **History (T).** `mole99`, project-template channel: 2026-07-05 PDK `d658698b` (precheck 1.7.1, density rules upstreamed);
  2026-07-14 PDK `f6eeac7d` (1.7.2); 2026-10-20 PDK `792ef670` (1.7.4): "KLayout DRC: Add DCF.1a, Fix DF.11, Improve CO.5a/b;
  KLayout LVS: Fix LDMOS extraction; KLayout filler generation: Consider DCF.1a properly". And: "Please update your projects to the
  latest project template to ensure a smooth tapeout experience." The platform re-runs the latest precheck on uploaded designs.
- **Steps (P).** README: top cell; origin, dbu 0.001, max metal Metal5, slot size; with `--cob` the four ID cells and the pad mask;
  "Checks the density of the layout"; zero-area polygons; KLayout antenna; Magic DRC (`ERROR_ON_MAGIC_DRC: False`); KLayout DRC
  with decks `all,-antenna,-density,-cup`. Default `--workers 1`.
- **Density and fill (P / T).** Density is its own gating step (`KLayout.Density`, deck `density`, which now contains DCF.1a).
  **wafer.space does not fill for the user.** `mole99`, 2026-07-15: "The LibreLane template does the fill and density check for you";
  for an analog top, 2025-12-01: "The fill for the entire chip is added at the end. If you do an analog top-level integration you
  can add the fill manually: `klayout -b -zz -r ${PDK_ROOT}/${PDK}/libs.tech/klayout/tech/drc/filler_generation/fill_all.rb -rd
  input=chip_top.gds -rd output=chip_top_filled.gds`" and 2025-12-03: "You should also generate the fill before doing DRC and LVS".
  2026-09-02: the filler scripts now "consider pre-existing fill as blockage". The script "adheres to rules such as leaving a 26um
  spacing from the edges".
- **DCF.1a and keep-out markers: no public statement beyond the deck.** The rule text is the PDK page
  `gf180mcu-pdk.readthedocs.io/.../drm_13_1.html`; the marker exemptions (NDMY, RES_MK, Pad, IND_MK) are as `signoff-gap.md` read
  them from the deck at `792ef67`. Nobody from wafer.space has said which keep-out markers they accept or whether density waivers
  exist for analog dies. A community remark (2026-10-16, `brookieoz`): "you also need to do metal dummy fill block all the way up".
- **Open items in the repo (P).** Issue #51 (2026-11-04) "Precheck not verifying the ID actually exists"; PR #49 layer checks
  (forbidden Via5, MetalTop, ESD, FuseWindow_D, POLYFUSE; required GUARD_RING_MK), not merged.
- **Ask by email:** whether PMNDMY / NDMY / IND_MK keep-outs over RF blocks are accepted when the whole-die density still passes;
  whether any density or DCF.1a waiver exists.

## (h) Slot and die sizes

- **Sizes (P).** Website and reticle numbers (`mole99`, 2026-10-13): 1x1 3932 x 5122 um; 0p5x1 1936 x 5122; 1x0p5 3932 x 2531;
  0p5x0p5 1936 x 2531; seal ring about 26 um per side inside that. Prices Run 3: 1x1 $7,000 early / $8,000, COB add-on $1,500.
  The project die (3.932 x 5.122 mm) is exactly the 1x1 slot.
- **Larger slots: none.** No 2x1 or larger is offered or discussed. The Run 1 reticle held 40 slots in about 30 x 24 mm.
- **Multiple slots (T).** `mithro_`, 2026-09-28: "You are welcome to purchase two slots (one with CoB and one without) and put the
  same design in both." These are separate dies, not one larger die. FAQ: "Can I put multiple test chips or multiple macros in one
  slot? Allowed. You own the full ~20 mm²."
- **Possible change (T).** Saw street 60 um today; 100-150 um proposed after the dicing house's feedback (thread
  *info-from-disco-engineers*, 2026-10-09 to 10-13). `mole99`: "Personally, I would keep the full slots the same size ... and adjust
  the half and quarter slots instead" and "The question now is whether we want to change the saw street width already for **Run 3**?"
  No decision is public. If it changes, the precheck size check and golden masks would change with a template update.

## Q10: custom pad cells and supply shorts

- **Custom pads (T).** `mole99`, 2026-09-27: "The `Pad` layer (pad opening) is checked against a golden reference (first AND and then
  XOR) to ensure that the bonding machine has something to bond to. Which circuit is connected to the bond pad is entirely up to you."
  2026-09-09: people can "change power/ground pads or even make their own fully custom pads".
- **Supply and ground sites (T).** `mole99`, 2025-11-27: "Do not change the number of pads on any side ... The VSS pads are shorted
  on the default breakout PCB. This is why you should not change any of the ground pins." Supply fingers are separate board nets
  (VDD_IO_0..3, VDD_CORE_0..1, PWR_AUX_0..1), each with 1 uF to GND.
- **On-die short of all DVDD/VDD and DVSS/VSS by the stock cells: NF.** Only: `246tnt`, 2026-09-27: "We have an io library with
  separate VDD and DVDD already" (the `gf180mcu_ocd_io` library), and a Run 3 user was told a split pad ring passes the precheck.
- **Seal ring (T).** `mole99`, 2026-11-06: the template's seal ring is not connected to VSS; "this missing connection has not caused any problems".

---

## Contradictions with the project's current assumptions

1. **The COB board carries passives.** Eight 1 uF 0201 capacitors sit on the back of the standard 1x1 board, one per supply
   finger net, about 2 mm of board from the supply fingers; top-side 0201/0402 parts are acceptable to the bonder. The assumption
   "no passives on the COB, nearest part 5-6 mm of trace plus a connector away" is wrong for the supplies. It is still true for
   signal and RF pins on the unmodified board.
2. **Supply-site fingers have 1 uF to ground.** Any signal moved onto a VDD_IO / VDD_CORE / PWR_AUX site sees that capacitor.
3. **Custom bond diagrams are not part of the COB add-on.** Extra bonds for the two west pads (W-A, W-B), a double bond on finger 71,
   copper or paddle down-bonds, and a per-die strap bond (`bond-map-options.md` S1-S3, Q2-Q5) have no public path; only the
   74-wire layout is bonded. S4 (no extra LNA ground bond) is the only option that needs nothing from the assembler.
4. **Run 3 1x1 slots sold out on 22 Sep 2026.** If the slot is not already bought, Run 3 is closed for this die size; Run 4 would
   close no earlier than end of January 2027 and has no dates yet.
5. **Die thickness is known for Run 1: about 250 um** (BOND-AUDIT treats it as unpublished and brackets 0.2-0.5 mm). With 0.25 mm the
   3-D length of the corner bonds is about 3.04 mm for centre landing, over the 3 mm rule if it means wire length. Run 2 appears to
   have been thinned too; Run 3 is not promised.
6. **Wire is thinner than a default assumption of 25 um:** 0.8 mil (20 um) AlSi in Run 1, and the bonder has changed since
   (aluminium wedge or gold thermosonic under trial). Bond-wire inductance, resistance and current figures should cover both.
7. **Glob-top epoxy covers the die and wires.** Anything in the RF and coupling models that assumes air above the die and around
   the bond wires should be checked.
8. **Every COB is electrically tested through the pads' ESD diodes.** Custom pads without a diode to ground at 10 uA - 1 mA, the TLP
   site, and deliberately unbonded pads may be reported OPEN.
9. **PCM data exists.** `pre-mortem.md` item 11 says none is confirmed; Run 1 e-test data is public and reads close to typical.
10. **Layer 24/0 (ESD implant) is not in the wafer.space mask set** per an open precheck PR. The custom ESD cells should be checked for it.
11. **Precheck versions:** `signoff-gap.md` is right (PDK `792ef67`, DCF.1a since 20 Oct 2026). `pre-mortem.md` item 7's `d658698`
    is the July pin and is superseded. Nothing found contradicts KLayout 0.30.12 / Magic 8.3.677.
12. **Deadline:** 9 / 16 December 2026 confirmed; the 15 / 29 December dates in the announcement posts are stale.
13. **MIM 2 fF/um2, 1 k poly, 11 kA top metal, native-Vt:** consistent with the project; one Discord message saying 1.5 fF/um2 was corrected.
14. **Board for Run 3:** the audit's use of the run-2 file is the best available choice; the re-spin in progress keeps the
    fingers, paddle, capacitors and connector unchanged.
15. **Run 1 COB yield was poor at first** (failed bonds, pad-to-ground-rail shorts on several samples), later 95-100 % on tested lots.
    The 9 um / 1 deg margins sit on a hand-placed die.

## Still must ask by email

1. Is the project's Run 3 1x1 slot confirmed? If not: any 1x1 capacity left, and Run 4 purchase / GDS dates and prices.
2. Which 1x1 COB board revision will Run 3 dies be bonded to, and are the finger coordinates final?
3. Will a customer-modified 1x1 board be accepted for Run 3 if the outline, the 74 fingers, the connector and the passives area are
   unchanged (extra 0201/0402 parts on the top near the fingers, changed ground copper, capacitor values)? Deadline for the files?
4. Is anything beyond the 74 standard wires possible inside the add-on: two extra bonds from added pads, a second wire on a GND
   finger, a down-bond to the ground copper or paddle, a pad deliberately left unbonded? If not, what does "stuart" need for a
   custom job and can it be done on dies from a COB order?
5. Die attach for Run 3: conductive (silver) epoxy onto the GND paddle or not; back-side finish; final die thickness.
6. Wire for Run 3: aluminium or gold, diameter; loop height; die placement tolerance; whether 3 mm and 45 deg are plan-view limits
   and where on the finger the wire lands.
7. Bond tester: how are custom pads (no ESD diode to ground, TLP site, RF pads) and unbonded pads handled; can the customer supply
   an expected-result list?
8. Glob-top: material, black or clear, and can it be left off or kept off the die face for a few boards?
9. Process: written confirmation of NAT (`nfet_06v0_nvt`), DNWELL, SAB / `_dss` devices outside the provider cells,
   `cap_nmos_03v3_b`; is layer 24/0 (ESD) dropped at mask making?
10. Fill: are PMNDMY / NDMY / IND_MK keep-outs over RF blocks accepted when die-level density and DCF.1a pass; any waiver process?
11. Will the 1x1 size or the saw street change for Run 3?
12. Run 2 / Run 3 e-test data: will it be shared as for Run 1?
13. Do the stock `dvdd` / `dvss` cells short all supply pads and all ground pads on the die, as the project's supply plan assumes?
14. Current rating per connector contact (HCTL HC-PBB40C-70DP-0.4V-02) and per bond wire.
