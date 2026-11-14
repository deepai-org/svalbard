# Bond-map option table (pads owner, 2026-11-14): PROPOSAL for the user, nothing decided

`spec/contract.json` `assembly_policy.bond_map_current` is NOT edited until the user chooses. Facts and methods:
`scratch/pads-core/bond/SITES.md`, `scratch/pads-core/bond/BOND-AUDIT.md`, `scratch/pads-core/rails/RAIL-CONTINUITY.md`, `scratch/pads-core/strap/STRAP.md`, `scratch/pads-core/bond/LO-PAD-OPTIONS.md`.

## 1. What is free

| Site | Where | Board finger / connector contact | What a wire from it can land on (published rules) |
|---|---|---|---|
| E1 | east, provider site `bidir[16]`, bond 22 (was WCLK_IN_P) | `/pad_21` / contact 58 | its own finger (2.61 mm, 23.5 deg) |
| E2 | east, provider site `bidir[17]`, bond 23 (was WCLK_IN_N) | `/pad_22` / contact 57 | its own finger (2.54 mm, 19.6 deg) |
| W-A | west, extra pad opening beside RF_RX_P (was LNA_SRC_P); never placed, no cell exists | none | GND finger 71 by a second wire on that finger (2.54 mm, 30.4 deg); on the run-2 board also the bare GND copper inside the finger ring (1.0-2.75 mm, 0.07 mm from wire 70/71). No supply finger (the wire would cross 71 and 72). No paddle down-bond (34-39 um of paddle visible, rule needs >= 1 mm of wire). |
| W-B | west, extra pad opening beside RF_RX_N (was LNA_SRC_N); never placed | none | run-2 board only: bare GND copper (1.0-1.7 mm). Nothing on the run-1 board. |

Which board the shuttle uses, and whether extra openings, double bonds and copper down-bonds are accepted, is unknown
(`scratch/pads-core/bond/wafer-space-questions.md` 1-5).

## 2. What wants a site, and where it can physically go

| Demand | Sites that can serve it | Sites that cannot, and why |
|---|---|---|
| POR-bypass strap (1). Provider `in_c`, pull-down hard-tied, safe unbonded (evidence `scratch/pads-core/strap/STRAP.md`: holds against 24,000x its worst leakage) | E1 or E2: bench jumper on contact 58 or 57 to 3.3 V (20-35 uA) | W-A, W-B: no finger and no legal wire to a supply finger, so the pad could only ever read 0. A strap there is useless. |
| LNA ground AGND_RX (2), power-delivery section 5.2 / PD2-12 | W-A (finger 71 double bond, or run-2 copper), W-B (run-2 copper only) | E1, E2: 3.8 mm from RF_RX, other side of the die |
| South supply bond (1 spare), power-delivery section 6 | none of the four | E1/E2 sit behind supply bond 18 on the ring: worst D2H drop per 100 mA 15.1 -> 14.8 mV, bond 18 share 31 -> 27 %. A real south site (bond 13): 15.1 -> 10.6 mV, bond 18 share 12 %. |

So the conflict the coordinator recorded ("strap and LNA ground both claim the two LNA sites") dissolves: the strap can
only use an east site, the LNA ground can only use the west sites. One east site is left over.

## 3. Options

### 3a. Strap and LNA ground

| Option | E1 (`bidir[16]`, contact 58) | E2 (`bidir[17]`, contact 57) | W-A | W-B | What it costs / what is open |
|---|---|---|---|---|---|
| S1 | POR_BYPASS strap | spare (see 3b) | AGND_RX | AGND_RX | W-B has no rule-compliant landing on the run-1 board; W-A opening is 16.5 um from the RF_RX_P opening at the placeholder position (pitch to be confirmed); both pads need a custom cell (the TLP-site pattern shorts DVDD to DVSS over the ring: not reusable as is) |
| S2 | spare | POR_BYPASS strap | AGND_RX | AGND_RX | as S1; E2 is 180 um closer to the macro south edge (1.68 vs 1.86 mm route) |
| S3 | POR_BYPASS strap | spare | AGND_RX (finger 71 double bond) | not built | one LNA ground bond only; buildable on either board if double bonds are accepted |
| S4 | POR_BYPASS strap | spare | not built | not built | no LNA ground split (die VSS only); needs 44 / 62 / 76 dB of rejection that is not in evidence (PD2-15); no assembly questions |

### 3b. The spare east site (E1 or E2, whichever the strap does not take)

| Option | Use | Effect (numbers) | Gives way |
|---|---|---|---|
| P0 | keep the map, leave the site as a spare bonded pad (provider cell) | worst supply bond 87.5 mA of the 125 mA cell rating (85 C); ring drop 28-45 mV; worst tap 106 of 117 mV | nothing |
| P1 | east supply bond on the spare | south D2H drop 15.1 -> 14.8 mV per 100 mA; bond 18 share of D2H current 31 -> 27 %. Wired-mode worst bond (pad 18) relief not modelled yet (power-delivery model run needed). Fed from the carrier through one signal contact, no COB capacitor footprint | nothing |
| P2 | move one south-edge signal to the spare east site and make its south site a supply bond | supply at bond 13: D2H drop 15.1 -> 10.6 mV per 100 mA, worst bond 87.5 -> 63.5 mA, ring drop -8 mV (power-delivery option A) without losing the signal. The moved signal gets 2.2-4.5 mm of extra ring distance to its neighbours and leaves its group (D2H lanes are a length-matched group: skew to be rechecked) | a south-edge signal moves (user picks: D2H_D[9] at bond 13 is the power-delivery proposal; any of bonds 10-17 gives 8.4-10.6 mV) |
| P3 | power-delivery option A as written: D2H_D[9] (bond 13) becomes supply, the lane is dropped | same supply numbers as P2 | one D2H lane |
| P4 | second observation / debug pin on the spare (it has a contact) | none on supply | nothing |

### 3c. External-LO pad pair versus RF_RX (INT23)

Filament model of the substrate/pulling check (`m3/mutual.py`, reused unchanged; its published -16 dB reproduces within
0.3 dB). Limit RF-RX-LOLEAK -57 dBm; margins are optimistic / nominal / pessimistic at 4 Vpp external LO. Magnetic
bond-wire coupling only: no capacitive, board or connector term, no EM. West order is north to south. Every option only
renames existing wires, so all bonds stay legal. Details, side effects and the search: `scratch/pads-core/bond/LO-PAD-OPTIONS.md`.

| Option | West order (N to S) | REF_IN / AUX_CLK to RF_RX (um) | I+Q margin at 4 Vpp (dB) | LO swing that passes at the pessimistic bound | Worst PA-to-LO margin (dB) | Side effects |
|---|---|---|---|---|---|---|
| L0 today | TX BBQ AUX REF BBI RX | 844 / 1688 | -10.4 / -18.0 / -27.3 | 0.17 Vpp (0.50 nominal) | +74 / +59 / +36 | none |
| L1 REF_IN swaps with BB_Q | TX REF AUX BBQ BBI RX | 2110 / 1688 | +11.2 / +2.4 / -12.7 | 0.92 Vpp | +44 / +31 / +15 | I and Q LO pairs become neighbours: about 0.7 / 1.5 / 3.6 deg of I/Q error per leg (today about 0.2); I route to the RX mixers 0.9 -> about 2.2 mm; REF_IN on bonds 60/59, contacts 22/23, board skew -14.7 -> +0.4 ps |
| L2 AUX_CLK to the two free east sites, REF_IN into BB_Q's slot | TX REF (free) BBQ BBI RX | 2110 / east | +19.6 / +10.7 / -6.4 | 1.9 Vpp | +44 / +31 / +15 | uses BOTH free east sites (no strap or spare there: conflicts with 3a/3b); Q LO crosses the die (2.0 mm to RX mixers, 3.1 mm to TX mixers); forwarded-clock route 3.4 -> 0.45 mm; frees one west pair slot |
| L3 AUX_CLK east, REF_IN stays | TX BBQ (free) REF BBI RX | 844 / east | -10.4 / -18.0 / -27.1 | 0.18 Vpp | +74 / +59 / +36 | no gain on the I leg |
| L4 RF_TX also moves | REF AUX BB TX BB RX | 2954 / 2110 | +19.3 / +10.5 / -6.9 | 1.8 Vpp | +57 / +42.5 / +24 | RF_TX 844 um from RF_RX; the >= 1.0 mm QVCO strip then lands inside the v6 digital macro outline |
| L5 best of all 720 orders | RX BB TX BB REF AUX | 2532 / 2954 | +24.9 / +16.1 / -3.4 | 2.7 Vpp | +57 / +42.5 / +24 | mirrors the whole RF floorplan (RF_RX to the north end) |

No west-edge order passes the pessimistic bound at 4 Vpp (96 of 720 pass at nominal). Alternatives to moving pads, same
model: lower LO drive (1 Vpp is +12 dB; today's map still needs < 0.50 Vpp at nominal); on-chip QVCO instead of the
external LO (+17 / +16 / +10 dB margin at 1.3 mm from the west edge); pad C 1.5 -> 1.0 pF (+3.5 dB); a ground bond
between pairs or P/N reversal get no credit in the model.

If L2 is wanted, the strap has no east site left: it would then need a different provider site (a signal gives way) or
the keyed RESET_N rescue path alone.

## 4. Other bond-map facts the choice should know

- All 74 bonds pass the published rules in plan view, with the same numbers as 2026-10-18: longest 2.991 mm (limit 3,
  9 um margin), largest angle 38.7 deg (finger-centre landing) or 44.0 deg (near-end landing). A 0.1 mm die shift
  breaks one of the two limits. 3-D wire length is over 3 mm for corner bonds at any plausible die thickness.
- The ring rails are continuous at full width through every custom pad family (measured), on Metal3-5.
- All VDD_IO / VDD_CORE / PWR_AUX pads are one net on the die, all ground pads another.
- `pad_tlp_flat` as generated shorts pad, DVSS and DVDD if placed over the ring rail cell; it has never been assembled.
  It must be fixed before the TLP site (`bidir[25]`) is used.
- With the strap set, RESET_N must be held low until the supply is valid (INT6-3): the strap removes the POR.
