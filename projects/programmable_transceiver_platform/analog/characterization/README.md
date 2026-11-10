# Characterization structures

These are the first-die characterization structures from `spec/tapeout-plan.md`
("Characterization structures in the reserve area"). Each one is reachable
from the bench.

| Structure | Cell | Built here? | Access | Evidence |
| --- | --- | --- | --- | --- |
| NMOS/PMOS device replicas (LNA, mixer, sampler, driver) | `pt_char_atb` | yes | ATB codes 43–50 | `generated/char_atb-evidence.json` |
| Resistor matching pair | `pt_char_atb` | yes | ATB codes 51, 52 | same |
| MIM matching pair | `pt_char_atb` | yes | ATB codes 53, 54 | same |
| VCO replica with its own divider | `pt_vco_replica` | no, `analog/timing` | CLK_OBS code 11, freq_count source 4, `debug.replica.vco_enable`; VCTRL force **has no ATB code** (see below) | `analog/timing/generated/vco_replica-evidence.json` |
| Clamp test pad (`ESD_TEST`, `bidir[25]`) | single-leg stress-safe cell | no, `analog/pads` | its own pad | `analog/pads/generated/stress-safe-families/families-report.json` (`esd_test`) |
| 3.3 V ring oscillator (device-speed calibration) | `pt_char_ro33` | yes (`speed.py`) | `OUT` → new CLK_OBS source (requested), `EN` | `generated/char_speed-evidence.json` |
| 5 V-device ring oscillator (standard-cell device class) | `pt_char_ro50` | yes (`speed.py`) | `OUT` → new CLK_OBS source (requested), `EN` | same |
| Self-oscillating CML divider (fT / CML calibration) | `pt_char_cmldiv` | yes (`speed.py`) | `OUT` → new CLK_OBS source (requested), `EN`; `BIAS` → ATB sense (requested) | same |
| RF transistor, nfet_03v3 10 µm = 5 × 2 µm, GSG probe frame + OPEN + SHORT | `pt_char_rffet`, `pt_char_rffet_open`, `pt_char_rffet_short` | yes (`rffet.py`) | on-wafer GSG probes (own probe pads, no bond) | `generated/char_rffet-physical.json` |

`run_char.py abstracts` checks the evidence hashes of the two referenced
structures. It also writes their LEF abstracts next to `char_atb.lef`, so the
assembly has all five structures in one place. The results are in
`generated/referenced-structures.json`.

## `pt_char_atb`

Every structure is a two-terminal device between its ATB node and `VSS`. The
cell has **no VDD pin**.

- **NMOS replicas:** drain = gate = NODE; source = body = VSS.
- **PMOS replicas:** source = n-well = NODE; drain = gate = VSS.

Force a current on ATB0 and read the node on ATB1 (Kelvin) to get the diode
I–V. From that you get Vt, the current factor and the subthreshold slope. Each
replica uses the unit finger its block uses:

| Code | Port | Device | Fingers | Size source |
| --- | --- | --- | --- | --- |
| 43 | RN_LNA | nfet 5/0.5 | 2 | `rf_rx/lna.spice` gm fingers |
| 44 | RP_LNA | pfet 5/0.28 | 2 | `rf_rx/lna.spice` |
| 45 | RN_MIX | nfet 5/0.28 | 2 | `rf_rx/rxmix_i.spice` switches |
| 46 | RP_MIX | pfet 20/1 | 1 | `rf_rx/rxmix_i.spice` load |
| 47 | RN_SMP | nfet 8/0.28 | 1 | ADC bootstrapped sampling switch (`converters/circuits.py:bootstrap`) |
| 48 | RP_SMP | pfet 10/0.28 | 1 | `converters/adc_i.spice` |
| 49 | RN_DRV | nfet 20/0.5 | 1 | `rf_tx/rfdriver.spice` |
| 50 | RP_DRV | pfet 20/0.28 | 1 | `rf_tx/rfdriver.spice` |

**Resistor pair (51 RES_A, 52 RES_B).** Each side is four `ppolyf_u_1k` units
(2 × 10 µm) in series from NODE to VSS. The eight units are interleaved
A B B A A B B A in one row. Each side is 20.6 kΩ extracted, so 100 µA gives
2.06 V.

**MIM pair (53 MIM_A, 54 MIM_B).** Each side is two 40 × 40 µm
`cap_mim_2f0` units, placed A B B A. The top plate is NODE and the bottom plate
is VSS. The extracted value is about 6.5 pF per side at tt.

### How to measure

**Replicas and resistors:**
1. Select the code on both buses.
2. Source current into ATB0.
3. Read ATB1 with a **≥ 1 GΩ input meter** (an SMU in voltage sense, or a DMM in its 10 GΩ mode).

A 10 MΩ DMM draws enough current through the sense chain to matter. The
`iv_meter10meg` diagnostic in `char_atb-sims-extracted.json` puts the error
against the directly forced device at up to 42 mV at 100 nA. Keep the forced
current at or below 100 µA (force pad ≤ 2.5 V at tt).

**MIM pair:**
1. Read C on the ATB0 pad with an LCR meter at 100 kHz, first with the matching code selected.
2. Read it again with the bus pad selected and no leaf closed. That reads about 2.4 pF of bus and pad.
3. Subtract the second reading from the first.

The A − B difference needs no de-embedding, because the two paths are
identical. These are the board/bench requirements B7 and B10, plus the meter
requirement above.

### Flow

```
python3 run_char.py layout      # convkit layout, Magic DRC, Netgen LVS, analog-image GDS + KLayout DRC
                                # + GDS round-trip LVS, Magic LEF
python3 run_char.py sims        # extracted benches through the extracted ATB chain (5 corners)
python3 run_char.py abstracts   # LEF + evidence-hash check of vco_replica and ESD_TEST
python3 run_char.py evidence    # generated/char_atb-evidence.json with verdicts
```

- The layout uses the converter family's correct-by-construction kit
  (`converters/lib/convkit.py`) and its publishable-GDS export
  (`converters/flow.py:export_gds`).
- The ATB chain in the benches is island_support's default-mode extracted
  `atb_leaf_f`, `atb_leaf_s`, `atb_grp` and `atb_pad`. They are copied with
  their hashes into `generated/atb_reference/` from
  `scratch/island-support-20261108-075605/pexd`.
- Containers run with `--network none`. Scratch output goes to
  `scratch/characterization/`.

### Benches and criteria

All criteria are set in `run_char.py` and evaluated by `evidence()`.

**observable**, at 5 corners (tt/27, ss/32, ff/22, ss/22, ff/32):
- **Replicas** at 0.1, 1, 10, 30 and 100 µA; **resistors** at 1, 10, 50 and 100 µA.
- Sense pad vs node: ≤ 1 mV.
- Sense pad vs the same device forced directly with no ATB: ≤ 2 mV.
- Force pad: ≤ 3.3 V.
- **MIM:** de-embedded C within 3 % of the directly measured C.

**safe**, at tt/27, ff/85 and ss/0, VDD 0 → 3.63 V in 1 µs, every leaf open:
- Settled DUT current ≤ 100 nA.
- Ramp peak ≤ 10 µA.
- Bench error: ATB0 held at 3.63 V into each node through a closed force chain. It must draw nothing from VDD.

The safe criterion was revised once, and the revision is recorded in
`run_char.py`. The first rule put 100 nA on the ramp *peak*. The measured peak
is 0.5–0.7 µA, which is displacement current while the leaf wells couple the
open nodes to about 0.5 V. Both numbers are kept.

**clean:**
- Magic DRC 0.
- Netgen LVS unique match.
- Analog-image GDS with the HRES marker.
- KLayout DRC 0.
- Published-GDS round-trip LVS.
- LEF pins equal to the schematic ports.

A mutated schematic (one resistor width and one PMOS body changed) makes LVS
fail. That was checked by hand in `scratch/characterization/neg/`.

**fallback:** waived. These are characterization structures.

Results are in `generated/char_atb-evidence.json`.

## Device-speed calibration structures (`speed.py`, `rffet.py`)

Added 2026-11-10 for the mandate's device-speed guidance
(`scratch/reviews/MANDATE.md`, `gf180-device-speed-evidence.md`). Each one has
an extracted-netlist prediction in its evidence, so silicon/prediction is the
calibration factor for the second die.

| Cell | What it measures | Circuit | Output |
| --- | --- | --- | --- |
| `pt_char_ro33` | 3.3 V CMOS gate delay | NAND enable + 10 inverters, nfet_03v3 4/0.28, pfet_03v3 8/0.28 (device C dominates wiring) | tap on R5 → TSPC /4 → buffer → `OUT` |
| `pt_char_ro50` | 5 V device speed on the 3.3 V rail (the gf180mcu_fd_sc_mcu7t5v0 device class: STA derate) | same ring, nfet_05v0 4/0.6, pfet_05v0 8/0.5 | same /4 |
| `pt_char_cmldiv` | NMOS fT in a CML latch (serializer, LO divider class) | two CML latches in a /2 loop with CK = CKB = VDD (self-oscillation), nfet_03v3 10/0.28 pairs, 1.8 kΩ poly loads (1 × 1.8 µm; 0.8 kΩ did not self-oscillate), 0.6 mA tails; two clocked CML /2, CML→CMOS, TSPC /2 | `OUT` = f(S0) / 8; the self-oscillation frequency quoted as an equivalent input clock is 2·f(S0) = 16·f(OUT) |
| `pt_char_rffet` (+ `_open`, `_short`) | fT, fmax and Rg of the RF device | one PCell nfet_03v3 w 2 nf 5 (W = 10 µm), gate contacted both ends, in a 2-port GSG frame: 60 × 60 µm Metal5 pads, 50 × 50 µm GLASS openings, 100 µm pitch; 430 × 260 µm per frame | on-wafer S-parameters; de-embed OPEN then SHORT |

* EN = 0 is safe: rings stopped (NAND high), CML tails off (mirror gate pulled
  low, reference resistor disconnected), and the TSPC dividers static: their
  clock is held low (`NOR(tap, ENB)`) and their outputs reset by ENB. Without
  that, a stopped TSPC leaves a dynamic node floating; the first run drew
  0.1–0.4 mA with EN = 0.
* The CML cell biases itself from a 36 kΩ poly resistor into a diode NFET
  (about 60 µA); `BIAS` is the mirror gate, for an ATB sense code.
* Explicit gate resistance (the PDK models have rgatemod = 0): the extracted
  benches add Rg = Rsh·W/(3L) per device, with Rsh 7.3 Ω/sq, to every MOS gate
  (`speed.with_gate_r`; 87 Ω for the 10 µm CML devices). That is the primary
  prediction. The run without Rg is kept as a comparison.
* Probe frames: the GLASS openings sit inside the core. Assembly must keep
  fill and other metal out of the 430 × 260 µm frames, and the frames need
  probe access on the bare die (`interface-changes.md`).
* Published GDS: every subcell is prefixed with its top-cell name
  (`speed.uniquify`), and the renamed GDS is re-checked by round-trip LVS
  (`published_gds_after_rename` in each `*-physical.json`). The convkit flow
  otherwise names the PCell masters `prim_0…` in every block (see Open items).

Physical results (Magic DRC / KLayout DRC / LVS / published-GDS round-trip LVS / LEF pins):

| Cell | Devices | LEF size (µm) | Magic DRC | KLayout DRC | LVS | GDS round trip | LEF pins |
| --- | ---: | --- | ---: | ---: | --- | --- | --- |
| `pt_char_ro33` | 54 | 69.6 × 139.3 | 0 | 0 | unique | unique | match |
| `pt_char_ro50` | 54 | 70.4 × 132.4 | 0 | 0 | unique | unique | match |
| `pt_char_cmldiv` | 85 | 104.8 × 265.8 | 0 | 0 | unique | unique | match |
| `pt_char_rffet` | 1 (nf 5) | 430 × 260 | 0 | 0 | unique | unique | G, D, GND |
| `pt_char_rffet_open` | 0 | 430 × 260 | 0 | 0 | ports G, D, GND separate | — | G, D, GND |
| `pt_char_rffet_short` | 0 | 430 × 260 | 0 | 0 | G and D merged into GND | — | GND |

Extracted predictions: see `generated/char_speed-evidence.json` (table below
when the runs finish).

<!-- speed-results -->
| Cell | Verdict | f_osc tt/27/3.3 | ss/32/3.15 | ff/22/3.35 | ss/22/3.35 | ff/32/3.15 | f(OUT) range | I_on tt | I(EN=0) max | tt without Rg |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| `pt_char_ro33` | pass | 605 MHz | 475 MHz | 730 MHz | 512 MHz | 689 MHz | 119–183 MHz | 1.66 mA | 0.7 nA | 608 MHz |
| `pt_char_ro50` | pass | 327 MHz | 223 MHz | 435 MHz | 246 MHz | 403 MHz | 56–109 MHz | 0.81 mA | 0.3 nA | 328 MHz |
| `pt_char_cmldiv` | pass | 856 MHz | 692 MHz | 1089 MHz | 692 MHz | 1088 MHz | 86–136 MHz | 4.02 mA | 19.2 nA | 865 MHz |

f_osc is the ring frequency (ring cells) or the S0 toggle frequency (CML cell; the equivalent input-clock self-oscillation frequency is twice that). Extracted (Magic C) + explicit gate R. The RF FET frames have no simulated prediction beyond the model fT/fmax (`gf180-device-speed-evidence.md` E4/E5).


```
python3 speed.py layout [cell,...]   # ro33, ro50, cmldiv physical flow (+ uniquify + re-LVS)
python3 speed.py sch                 # schematic tt (divider consistency check)
python3 speed.py ext                 # extracted + gate R, 5 corners (primary prediction)
python3 speed.py ext_norg            # extracted, no gate R, tt (comparison)
python3 speed.py evidence            # generated/char_speed-evidence.json
python3 rffet.py layout && python3 rffet.py export
```

## Open items

- **VCO replica VCTRL has no ATB code.** `pt_vco_replica` clamps VCTRL to VSS
  while `EN` = 0, and leaves it floating when enabled.
  `spec/register-map.md` says VCTRL "is forced from the ATB", but the ATB code
  table (1–57) has no `vco_replica_vctrl` or `vco_replica_vtail` node. As
  specified, the replica cannot be swept on the die. This is recorded as an
  open register request in `spec/tapeout-readiness.json`: a force-allowed code
  for VCTRL and a sense code for ATB_VTAIL, on the debug island.
- **The `vco_replica` evidence hash is stale only on `run_timing.py`.** That is
  the shared timing-flow script edited for `pll_ring`. Its `vco_replica` code
  path did not change. See `generated/referenced-structures.json`.
- **ESD_TEST GDS top-cell name collides.** The single-leg GDS top cell is
  `rf_protected_pad_pair`. That is the same name as the RF pair, the protected
  pair and both RF assembly GDS files, and the subcell names are shared too. A
  naive GDS merge in the assembly would silently keep one of them. The
  assembly must rename on import, or `analog/pads` must publish unique names.
- **Every convkit-built GDS names its PCell masters `prim_0`, `prim_1`, …**
  (`char_atb.gds` and the converter family's blocks too). Different blocks'
  `prim_3` are different devices. A naive GDS merge keeps one of them. The new
  speed cells are uniquified; `char_atb.gds` is not yet (its evidence hashes
  the GDS) and the converter blocks are owned elsewhere. Flagged to the
  assembly in `interface-changes.md`.
- **The convkit layout dilutes the speed structures.** Its private-riser
  routing roughly doubles the node capacitance: the 3.3 V ring runs at 1.16 GHz
  schematic and 605 MHz extracted, and the CML S0 at 1.55 GHz and 0.86 GHz.
  The calibration still holds, because silicon is compared with the extracted
  prediction, but each ring's sensitivity to device speed is about halved. A
  compact hand-placed version (timing `fastcells.py` style) would be the
  better second-die structure.
- **The speed structures need register/ATB/CLK_OBS codes** (three CLK_OBS
  sources, three enables, one ATB sense code); requested in
  `interface-changes.md`. Until granted they are not observable.
- **The ATB extracted cells are taken from a scratch run** of island_support.
  They are copied and hashed here, but the island_support flow does not
  publish them.
