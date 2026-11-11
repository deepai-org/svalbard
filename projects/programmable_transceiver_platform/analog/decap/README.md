# `pt_decap_tile`: MOS decoupling filler (core 3.3 V)

Tileable decap for the pad-family L-notches and channels (interface request I7(b)).

* `decap_cell.py` (KLayout) writes `generated/pt_decap_tile.gds` (40 x 40 um) and `generated/pt_decap_array.gds` (5 x 5 example, 200 x 200 um).
* Ports: `VDD` (Metal1 rail, y 38.8..40) and `VSS` (Metal1 rail, y 0..1.2), both full width. Tiles abut left/right. Rows stack mirrored about x (VDD/VDD and VSS/VSS shared), like standard-cell rows.
* Layers: COMP, NWELL, POLY2, NPLUS, PPLUS, CONTACT, Metal1, Via1, plus one short Metal2 strap (G net, x 20..37.4 at y 1.55..1.95, then x 37.0..37.4 up to y 12.2). **Metal3-Metal5 are free**, so routing or a MIM stack (M4/M5) can go over the tiles.

## Circuit (no MOS gate on a rail)

| Device | Model | Connection | Size |
|---|---|---|---|
| MPCAP | pfet_03v3 | S=D=B=VDD, G=GB | 5 x W 27.5 / L 6 um (825 um^2 gate) |
| MNT | nfet_03v3 | D=GB, S=B=VSS, G=G | 16 x W 4 / L 0.5 |
| MPT | pfet_03v3 | D=G, S=B=VDD, G=GB | W 1 / L 0.5 |

This is the cross-coupled tie used by the PDK `fillcap` cells. MNT holds GB at VSS, and its on-resistance is the capacitor's series R. MPT holds G high and drives only MNT's gate. No gate oxide connects directly to a rail.

## Verification (`generated/`)

* Magic DRC 0. netgen LVS against `reference.spice`: unique match (`lvs.txt`).
* KLayout GF180 precheck decks (`verification/kl_block_drc.py`, main + antenna): tile **clean** and 5 x 5 abutted/mirrored array **clean** (`*-kldrc.json`).
* Extracted simulations (`sim_decap.py`, `sim-results.json`). One tile, VDD to VSS:

| | 1 MHz | 100 MHz | 1 GHz |
|---|---|---|---|
| C (tt/27/3.3) | 3.72 pF | 3.63 pF | 2.25 pF |
| ESR | 47 ohm | 42 ohm | 34 ohm |
| Q | 910 | 10.3 | 1.4 |

  * Across the narrow envelope (tt/ss/ff, 22/32 C, 3.15/3.35 V): C is 3.58-3.88 pF at 1 MHz, Q at 100 MHz is 9.5-11.0, and Q at 1 GHz is 1.3-1.4. (risk: PDN-02)
  * Static current per tile is about 1e-18 A at tt/27/3.3 and ff/85/3.63. The PDK models have no gate tunnelling, so treat this number as a model artefact and expect measured leakage to be higher.
  * VDD ramps 0 to 3.63 V in 10 ns and in 1 us: the tie settles (G = VDD, GB = 0) with no lock-up. The worst oxide voltage is 3.63 V.
  * A 5 V, 2 ns over-voltage on VDD puts about 5.0 V across the MPCAP oxide. Any MOS decap sees this; it is informative only, and the pad/rail clamps are what limit it.

## Density versus the I7 target (risk: PDN-02)

* The tile gives 2.33 fF/um^2, so 0.30 mm^2 of tiles is about **0.70 nF** (about 0.62 nF at ss). (risk: PDN-02)
* The 1.5 nF target needs 5 fF/um^2. That is above the 3.3 V gate-oxide Cox (about 4.5 fF/um^2) even at 100 % gate coverage, so a MOS-only decap cannot reach it in 0.30 mm^2.
* Because Metal3-5 are free, a MIM layer (M4/M5, as assembly's `decap_mim_unit`) over the same tiles can add its own capacitance in the notches where no routing passes.
