# `pt_decap_tile`: MOS decoupling tile (core 3.3 V)

Tileable MOS decap. Where and how many tiles are placed is the power-delivery plan's decision
(`spec/power-delivery.md`, decap table); the tile is not instantiated in `integration/top/pt_chip.conn`.

| Item | Value |
|---|---|
| Cells | `generated/pt_decap_tile.gds` (40 × 40 µm), `generated/pt_decap_array.gds` (5 × 5 example, 200 × 200 µm), written by `decap_cell.py` (KLayout) |
| Ports | `VDD` (Metal1 rail, y 38.8..40) and `VSS` (Metal1 rail, y 0..1.2), both full width |
| Abutment | tiles abut left/right; rows stack mirrored (VDD/VDD and VSS/VSS shared) |
| Layers | COMP, NWELL, POLY2, NPLUS, PPLUS, CONTACT, Metal1, Via1 and one short Metal2 strap (net G). Metal3 to Metal5 are free for routing or a MIM stack |

## Circuit

| Device | Model | Connection | Size |
|---|---|---|---|
| MPCAP | pfet_03v3 | S = D = B = VDD, G = GB | 5 × W 27.5 / L 6 µm (825 µm² gate) |
| MNT | nfet_03v3 | D = GB, S = B = VSS, G = G | 16 × W 4 / L 0.5 |
| MPT | pfet_03v3 | D = G, S = B = VDD, G = GB | W 1 / L 0.5 |

Cross-coupled tie as in the PDK `fillcap` cells: MNT holds GB at VSS (its on-resistance is the capacitor's
series R), MPT holds G high. No gate oxide connects directly to a rail.

## Verified numbers (`generated/`)

| Check | Result | File |
|---|---|---|
| Netgen LVS against `reference.spice` | unique match | `lvs.txt` |
| KLayout precheck decks (main + antenna), tile and 5 × 5 array | 0 / 0, sha-bound to the GDS | `pt_decap_tile-kldrc.json`, `pt_decap_array-kldrc.json` |
| C, one tile, tt/27 °C/3.3 V | 3.72 pF at 1 MHz, 3.63 pF at 100 MHz, 2.25 pF at 1 GHz (2.33 fF/µm² of tile at 1 MHz) | `sim-results.json` |
| ESR | 47 Ω at 1 MHz, 42 Ω at 100 MHz, 34 Ω at 1 GHz | same |
| Q | 910 at 1 MHz, 10.3 at 100 MHz, 1.4 at 1 GHz | same |
| Envelope (tt/ss/ff, 22/32 °C, 3.15/3.35 V) | C 3.58–3.88 pF at 1 MHz; Q 9.5–11.0 at 100 MHz, 1.3–1.4 at 1 GHz | same |
| VDD ramps 0 → 3.63 V in 10 ns and 1 µs | tie settles (G = VDD, GB = 0), no lock-up; worst oxide voltage 3.63 V | same |
| 5 V, 2 ns pulse on VDD | 5.0 V across the MPCAP oxide (informative; the rail clamps limit it) | same |
| Static current | about 1e-18 A per tile (model artefact: the PDK models have no gate tunnelling) | same |

The extraction has no channel resistance for the L = 6 µm capacitor, so the ESR and Q above are optimistic;
`spec/power-delivery.md` uses a 335 ps time constant for the tile.

## Flow

```
python3 decap_cell.py     # GDS of tile and array, generated/tile.json
python3 sim_decap.py      # extracted ngspice runs -> generated/sim-results.json (run in generated/)
python3 ../../verification/kl_block_drc.py ...   # precheck decks -> *-kldrc.json
```

## Open items

Risk: PDN-02 (`spec/risk-register.md`).

- No Magic DRC report is stored in `generated/`.
- A MOS-only tile cannot exceed the 3.3 V gate-oxide Cox (about 4.5 fF/µm²); higher density needs MIM on
  Metal4/5 over the tiles, which is not built or checked here.
