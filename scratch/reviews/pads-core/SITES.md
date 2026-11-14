# Free pad sites: facts for the bond-map option table

2026-11-14. Facts only; no recommendation on which signal gives way. Numbers come from `sites.py` -> `sites.json`
(geometry) and from `../rails/RAIL-CONTINUITY.md` (ring widths). Tags as in `BOND-AUDIT.md`:
**[BOARD]** run-2 board file at `5cb4668` (run-1 noted where it differs), **[GDS]**, **[FP]** = `floorplan-v6.json`,
**[CALC]**, **[REPORT]**, **[ASSUMED]**.

To allocate: POR-bypass strap (1), AGND_RX (2), spare (1, candidate south supply bond).
Free: east `bidir[16]`, east `bidir[17]`, and the two west "in-ring" sites beside RF_RX.

## 1. What the four sites are

| | E1 | E2 | W-A | W-B |
|---|---|---|---|---|
| Site | `bidir[16]` (was WCLK_IN_P) | `bidir[17]` (was WCLK_IN_N) | gap `vss_pads[1]` .. RF_RX_P (was LNA_SRC_P) | gap RF_RX_N .. BB_I_P (was LNA_SRC_N) |
| Side | east | east | west | west |
| Bond-opening centre, chip um | 3874.0, 1400.5 [GDS] | 3874.0, 1611.5 [GDS] | 58, 1324 [ASSUMED] | 58, 1729 [ASSUMED] |
| Bond pad number (1-based) | 22 | 23 | none | none |
| Lower neighbour (centre distance, gap between openings) | 21 WIRE_RX_P (211, 151 um) | 22 (211, 151) | 71 `vss_pads[1]` GND (134.5, 74.5) | 69 RF_RX_N (117.5, 57.5) |
| Upper neighbour | 23 (211, 151) | 24 USB_DN (211, 151) | 70 RF_RX_P (76.5, **16.5**) | 68 BB_I_P (93.5, 33.5) |
| Board finger / net | finger 22, `/pad_21` [BOARD] | finger 23, `/pad_22` [BOARD] | none | none |
| Connector contact | **58** [BOARD] | **57** [BOARD] | none | none |
| Wire to own finger, centre landing | 2.608 mm, 23.5 deg | 2.539 mm, 19.6 deg | n/a | n/a |
| Wire to own finger, near-end landing | 2.236 mm, 27.0 deg | 2.156 mm, 22.5 deg | n/a | n/a |
| Nearest supply bonds on the edge | 18 VDD_IO_0 844 um; 26 PWR_AUX_0 844 um | 26 PWR_AUX_0 633 um; 18 VDD_IO_0 1055 um | 72 VDD_CORE_1 345.5 um; 74 VDD_IO_3 767.5 um | 72 VDD_CORE_1 750.5 um; 64 PWR_AUX_1 937.5 um |
| Nearest ground bonds on the edge | 19 at 633 um; 27 at 1055 um | 19 and 27 at 844 um | 71 at 134.5 um; 73 at 556.5 um | 71 at 539.5 um; 73 at 961.5 um |
| To the LNA outline [FP] | 2802 um | 2802 um | 897 um | 899 um |
| To RF_RX_P / RF_RX_N pad | 3816 / 3822 um | 3822 / 3816 um | 76.5 / 287.5 um | 328.5 / 117.5 um |
| To the digital macro south edge, straight [FP] | 1860 um | 1678 um | 2088 um | 1773 um |
| To `rst_n_pad`, straight | 3441 um | 3529 um | 1422 um | 1792 um |
| Ring path to the south D2H pads (bond 13 / 8 / 1) [CALC] | 2175 / 3075 / 4335 um | 2386 / 3286 / 4546 um | 3538 / 2638 / 1378 um | 3942 / 3042 / 1782 um |
| Present state | provider `bi_24t` site; v6 has `pad_wclk_in` (`rf-pair`, 310 x 913 um) on E1+E2 | same cell | placeholder rect only | placeholder rect only |

Notes:

- On die all eight supply sites tie their pad to the DVDD and VDD ring bands, and all ten ground sites to DVSS and VSS [GDS].
  "VDD_IO", "VDD_CORE" and "PWR_AUX" are separate nets on the board only.
- E1 and E2 are regular template sites at the 211 um pitch. Any provider cell (`in_c`, `dvdd`, `dvss`) drops in. Taking
  `pad_wclk_in` out also returns the part of its outline beyond the 350 um provider depth: 310 x 563 um = 0.17 mm2 [CALC].
- **W-A and W-B were never placed.** They exist only as two fixed rectangles in `floorplan-v6.json`
  (`pad_lna_src_p` 26..150 x 1290..1358, `pad_lna_src_n` 26..150 x 1695..1763; 124 x 68 um, the outline of the TLP-site cell).
  No cell, no GDS, no entry in `inventory.py` `CUSTOM_PADS`, nothing in `kl_assemble.py`; the assembled v5 GDS has 74 bond
  openings [GDS]. The centres above assume a 60 um opening in the middle of the placeholder, 32 um deep like every other pad.
  `contract.json` `bond_map_current.west` still lists "in-ring downbond pads beside RF_RX: LNA_SRC_P / LNA_SRC_N".
- The room for them is the fill-cell gap between provider cells: y 1227..1363 and y 1649..1785, 136 um each [GDS].
  A 75 um provider cell fits. Centred in the gap its opening is 105.5 um from each neighbour's centre (45.5 um between
  openings); at the placeholder position W-A's opening is 16.5 um from the RF_RX_P opening. The regular pitch is 211 um
  (east/west) and 180 um (north/south). The provider publishes no minimum pad pitch.
- A cell copied from the TLP-site pattern must not be used over the ring as it is: its pad riser shorts DVDD to DVSS
  (`../rails/RAIL-CONTINUITY.md`).

## 2. What a wire from each site can land on, within the published rules

Rules: no crossing, <= 45 deg, 1 mm <= length < 3 mm, no solder mask. All other wires in place unless stated. [CALC on BOARD]
"Clearance" is the smallest plan distance to a neighbouring wire.

| Target | E1 (bond 22) | E2 (bond 23) | W-A | W-B |
|---|---|---|---|---|
| Own finger | yes (table above) | yes | no finger | no finger |
| Die paddle | **no**: 34 / 39 um of paddle beside the die, and the rule asks for >= 1 mm of wire | no | no | no |
| Bare GND copper between die and fingers, **run-2 board** | yes: 1.00 to 1.89 mm; e.g. 1.37 mm at 19.6 deg, clearance 0.20 mm | yes: 1.00 to 1.83 mm; e.g. 1.50 mm at 15.5 deg, clearance 0.20 mm | yes: 1.00 to 2.75 mm; e.g. 1.84 mm at 26.5 deg, clearance 0.07 mm. Straight out is not possible (crosses wire 70); the wire has to run at 20 to 33 deg beside wires 70/71 | yes: 1.00 to 1.73 mm; e.g. 1.69 mm at 20.0 deg, clearance 0.09 mm |
| Same, **run-1 board** | no (copper ends 0.78 mm from the die; signal vias beyond) | no (one marginal point, 1.006 mm at 42.5 deg, only if bond 22 is also absent) | no | no |
| Nearest GND finger (double bond) | 19: no, 3.05 mm / 49.3 deg. 27: no, crosses 23 to 26 | 19: no, 3.22 mm / 51.7 deg. 27: no, crosses 24 to 26 | **71: yes**, 2.54 mm, 30.4 deg, clearance 0.07 mm, shares the finger with wire 71 | 71: no, crosses 69, 70, 71. 63: no, crosses 6 wires |
| Nearest supply finger (double bond) | 18 VDD_IO_0: no, 3.37 mm / 53.7 deg. 26 PWR_AUX_0: no, crosses 23, 24, 25 | 18: no, 3.54 mm / 55.7 deg. 26: no, crosses 24, 25 | 72 VDD_CORE_1: no, crosses 71 and 72. 74: no, 3.84 mm | 72: no, 3.58 mm. 64 PWR_AUX_1: no, crosses 5 wires |
| Neighbouring signal fingers | 21 (2.93 mm, 27.8 deg), 23 (2.38 mm, 15.6 deg) | 22 (2.94 mm, 23.6 deg), 24 (2.55 mm, 11.9 deg) | 70 RF_RX_P (2.18 mm, 24.0 deg) | 68 BB_I_P (2.77 mm), 69 RF_RX_N (2.46 mm) |

- The solder-mask opening of the footprint is one 9.4 x 10.23 mm rectangle [BOARD], so the GND copper inside the finger
  ring is bare on both boards. Whether it is plated for bonding, and whether the assembler bonds to anything other than a
  finger, is not published. The rules text does not mention down-bonds, double bonds or unbonded pads at all.
- On run-2 the GND copper reaches from the paddle to 3.65 mm from the die centre on east/west (fingers start at 3.8 mm);
  the footprint's six 0.5 mm GND through-holes sit at x = +-2.5 mm, inside the first 1 mm, outside the landing zone.
- Wire inductance was not computed. Lengths: a ground down-bond is 1.0 to 1.9 mm; a bond to a finger is 2.2 to 2.9 mm.

## 3. Question 1: can a free east site act as a "south supply bond"?

Ring model [CALC]: supply ring = DVDD + VDD bands, 138 um on each of Metal3/4/5, 0.0212 ohm/sq in parallel = **0.153 ohm/mm**;
ground ring 115.4 um = 0.184 ohm/mm; corners taken as an L path at mid-band depth; the 11 D2H pads share the current
equally. Not included: core ring, core grid, decap, inductance. The drops are therefore upper bounds for comparison only.

- Path from `bidir[16]` to the nearest D2H pad (bond 13): 2175 um of ring = 0.33 ohm. The existing supply bond 18
  (`dvdd_pads[0]`) lies on that path, 844 um (0.13 ohm) nearer the corner. From bond 18 to pad 13 is 1331 um = 0.20 ohm,
  with or without a new east bond.
- So an east supply bond is in parallel with bond 18 and does not shorten the path to the south edge:

| Case | Worst D2H supply drop per 100 mA (ideal bonds) | Same with 0.13 ohm per bond wire [ASSUMED] | Share of the D2H current in bond 18 / bond 74 (0.13 ohm case) |
|---|---|---|---|
| Today, 8 supply bonds | 11.0 mV | 15.1 mV | 31.1 % / 31.7 % |
| + supply at E1 (`bidir[16]`) | 11.0 mV | 14.8 mV | 26.9 % / 31.2 % (E1 takes 10.5 %) |
| + supply at E2 (`bidir[17]`) | 11.0 mV | 14.9 mV | 28.0 % / 31.4 % (E2 takes 9.1 %) |
| + supply at E1 and E2 | 11.0 mV | 14.7 mV | 25.8 % / 31.1 % |
| + supply at south bond 13 (D2H_D[9]) | 6.5 mV | 10.6 mV | 12.2 % / 24.8 % (bond 13 takes 38.3 %) |

- In numbers: an east bond changes the south-edge drop by 0 to 2 % and takes 4 points off bond 18. A south bond at
  pad 13 changes the drop by 30 to 41 % and takes 19 points off bond 18 and 7 off bond 74.
- None of the four free sites is on the south edge. The south edge has 17 sites and no supply bond; all are in use:

| Bond | Site | Cell | Signal | Contact | Worst D2H drop per 100 mA if this site became a supply bond (ideal / 0.13 ohm) |
|---|---|---|---|---|---|
| 1 | `clk_pad` | `in_s` -> D2H substitution | D2H_D[0] | 8 | 8.6 / 12.7 mV |
| 2 | `rst_n_pad` | `in_c` | RESET_N | 7 | 6.9 / 11.1 |
| 3 | `bidir[0]` | `bi_24t` | D2H_D[1] | 6 | 6.5 / 10.9 |
| 4 | `bidir[1]` | `bi_24t` | D2H_D[2] | 5 | 5.5 / 9.9 |
| 5 | `bidir[2]` | `bi_24t` | D2H_D[3] | 4 | 4.6 / 9.1 |
| 6 | `bidir[3]` | `bi_24t` | D2H_D[4] | 3 | 3.8 / 8.3 |
| 7 | `bidir[4]` | `bi_24t` | D2H_D[5] | 2 | 3.0 / 7.6 |
| 8 | `bidir[5]` | `bi_24t` | D2H_CLK | 1 | 2.6 / 7.2 |
| 9 | `dvss_pads[0]` | `dvss` | GND (the only south supply or ground bond) | GND | n/a |
| 10 | `bidir[6]` | `bi_24t` | D2H_D[6] | 70 | 4.0 / 8.4 |
| 11 | `bidir[7]` | `bi_24t` | D2H_D[7] | 69 | 4.8 / 9.1 |
| 12 | `bidir[8]` | `bi_24t` | D2H_D[8] | 68 | 5.6 / 9.8 |
| 13 | `bidir[9]` | `bi_24t` | D2H_D[9] | 67 | 6.5 / 10.6 |
| 14 | `bidir[10]` | `bi_24t` | HOST_CS_N | 66 | 6.8 / 10.8 |
| 15 | `bidir[11]` | `bi_24t` | HOST_SCLK | 65 | 7.5 / 11.5 |
| 16 | `bidir[12]` | `bi_24t` | HOST_MOSI | 64 | 8.3 / 12.1 |
| 17 | `bidir[13]` | `bi_24t` | HOST_MISO | 63 | 9.0 / 12.7 |

  (When a D2H site becomes the supply bond its own load is removed from the eleven. Today: 11.0 / 15.1 mV.)
- A south supply bond therefore needs one of these 16 signals to move or go. The only way a freed east site helps is by
  receiving a signal moved off the south edge (E1/E2 have fingers and contacts, 2.2 to 4.5 mm of ring from the D2H pads).
  Which signal could move is not a geometry question.
- A supply bond at E1 or E2 would land on a board signal net (`/pad_21`, `/pad_22`): one connector contact each, no
  decoupling footprint on the COB for that net (the 8 capacitor footprints sit on the 8 supply nets [REPORT]).

## 4. Question 2: which sites can take AGND_RX with a short return next to RF_RX?

- Only W-A and W-B are near the LNA: 0.90 mm from its outline, 76.5 and 117.5 um from the RF_RX_P / RF_RX_N pads. E1 and E2 are
  2.8 mm from the LNA and 3.8 mm from the RF_RX pads.
- **A paddle down-bond is not possible**: the paddle is 4.0 x 5.2 mm under a 3.932 x 5.122 mm die, and the rules at HEAD demand
  at least 1 mm of wire. The rules do not mention down-bonds.
- What the geometry allows instead:
  - **run-2 board only:** a down-bond to the bare GND copper between die and fingers, 1.0 mm minimum, 1.0 to 1.7 mm (W-B) or
    1.0 to 2.75 mm (W-A) inside the rules, running 0.07 to 0.09 mm (plan) beside the RF_RX and neighbouring wires;
  - **either board:** W-A as a second wire onto GND finger 71 (`vss_pads[1]`'s finger): 2.54 mm, 30.4 deg. W-B reaches no
    GND finger.
  - On the run-1 board neither site has a rule-compliant ground landing other than W-A onto finger 71.
- Board ground is one net (paddle, GND copper, GND fingers, 6 contacts + 4 shell tabs [REPORT]). A separate AGND_RX exists
  only on the die side of the bond.
- Both options need the assembler to bond a pad that is not one of the 74, onto something that is not that pad's own finger.

## 5. Question 3: strap, bench jumper or assembly-time only?

| Site | Connector contact | Strap = 0 | Strap = 1 |
|---|---|---|---|
| E1 | **58** (`/pad_21`) | unbonded or contact left open (pull-down) | jumper on the carrier from contact 58 to the core supply |
| E2 | **57** (`/pad_22`) | same | jumper from contact 57 |
| W-A | none | unbonded, or a ground bond (finger 71 or GND copper) | **not bondable inside the rules**: the nearest supply finger (72 VDD_CORE_1) needs a wire that crosses wires 71 and 72 |
| W-B | none | unbonded, or a ground bond (GND copper, run-2 only) | **not bondable inside the rules**: fingers 72 and 64 are out of reach (3.58 mm / crossings) |

- E1 and E2 give a bench jumper. W-A and W-B give at most a per-die assembly option, and inside the published rules that
  option can only select 0, which is also the unbonded default.
- Nets to strap on the carrier: finger 22 -> `/pad_21` -> contact 58; finger 23 -> `/pad_22` -> contact 57. Both are plain
  signal nets with no component on the COB [REPORT `spec/package-channel.json`]. Their neighbours at the connector by net
  number are `/pad_20` (contact 59, WIRE_RX_P) and `/pad_23` (contact 56, USB_DN).
- Route length to the macro: the strap input is on the macro's south edge (`pin_order.cfg`: `reset_n_pad`, `por_n`,
  `por_bypass`; exact x not fixed). Straight distance from the pad to that edge: E1 1.86 mm, E2 1.68 mm, W-A 2.09 mm,
  W-B 1.77 mm.
- The ring is one uncut supply net all round (`RAIL-CONTINUITY.md`), so an `in_c` at any of the four sites sits on the
  always-on ring rails.
- Not determined here: pull-down current against pad leakage for the unbonded case (a simulation, not geometry), and the
  tie check for the strap in `kl_assemble.py` / `kl_checks.py` (covers `rst_n_pad` only today).

## 6. Not determined

- Whether the next shuttle uses the run-2 board (the ground down-bond exists only there).
- Whether custom bond diagrams, extra pads, down-bonds and unbonded pads are accepted at all, and the minimum pad pitch.
- The real position of W-A / W-B: no cell exists. All W numbers move with the pad position (a pad centred in the gap sits
  29 um further from RF_RX_P than the placeholder).
- Wire inductance and bond resistance (wire material and diameter are not published; 0.13 ohm is an assumption for
  about 2.5 mm of 25 um gold).
