# Characterization structures

First-die characterization structures of `spec/tapeout-plan.md`. Each is reachable from the bench. Bindings
are those of `integration/top/pt_chip.conn`; register fields are in `spec/register-map.md`.

| Structure | Cell | Built here | Access | Evidence |
| --- | --- | --- | --- | --- |
| NMOS/PMOS device replicas (LNA, mixer, sampler, driver) | `pt_char_atb` | yes | ATB codes 43–50 | `generated/char_atb-evidence.json` |
| Resistor matching pair | `pt_char_atb` | yes | ATB codes 51, 52 | same |
| MIM matching pair | `pt_char_atb` | yes | ATB codes 53, 54 | same |
| 3.3 V ring oscillator | `pt_char_ro33` | yes (`speed.py`) | `debug.replica.ro33_enable`, CLK_OBS source 15 | `generated/char_speed-evidence.json` |
| 5 V-device ring oscillator | `pt_char_ro50` | yes (`speed.py`) | `debug.replica.ro50_enable`, CLK_OBS source 16 | same |
| Self-oscillating CML divider | `pt_char_cmldiv` | yes (`speed.py`) | `debug.replica.cmldiv_enable`, CLK_OBS source 17; `BIAS` unbound | same |
| RF transistor in a GSG probe frame, with OPEN and SHORT | `pt_char_rffet`, `_open`, `_short` | yes (`rffet.py`) | on-wafer GSG probes (own probe pads, no bond) | `generated/char_rffet-physical.json` |
| VCO replica with its own divider | `pt_vco_replica` | no, `analog/timing` | `debug.replica.vco_enable`, CLK_OBS source 11, frequency counter `fc_src[3]`; `VCTRL` on ATB code 58 | `analog/timing/generated/vco_replica-evidence.json` |
| TLP/ESD test site (`TLP_TEST`, `bidir[25]`) | `pad_tlp` | no, `analog/pads` | its own pad | `analog/pads/generated/tlp-site/` |

`pt_char_atb` and the RF frames sit in the core domain; the three speed cells and the VCO replica are on the
debug island (`RAIL_debug`). Enable one speed cell at a time: they share CLK_OBS input 15.

## `pt_char_atb`

Every structure is a two-terminal device between its ATB node and `VSS`. The cell has no VDD pin.
LEF size 192.1 × 147.0 µm.

- NMOS replicas: drain = gate = NODE; source = body = VSS.
- PMOS replicas: source = n-well = NODE; drain = gate = VSS.

Force a current on ATB0 and read the node on ATB1 (Kelvin) to get the diode I–V (Vt, current factor,
subthreshold slope).

| Code | Port | Device | Fingers | Unit finger of |
| --- | --- | --- | --- | --- |
| 43 | RN_LNA | nfet 5/0.5 | 2 | `rf_rx/lna.spice` (published) |
| 44 | RP_LNA | pfet 5/0.28 | 2 | `rf_rx/lna.spice` (published) |
| 45 | RN_MIX | nfet 5/0.28 | 2 | `rf_rx/rxmix_i.spice` switches |
| 46 | RP_MIX | pfet 20/1 | 1 | `rf_rx/rxmix_i.spice` load |
| 47 | RN_SMP | nfet 8/0.28 | 1 | `converters/adc_i.spice` |
| 48 | RP_SMP | pfet 10/0.28 | 1 | sampler class (no 10/0.28 pfet in the published ADC netlist) |
| 49 | RN_DRV | nfet 20/0.5 | 1 | `rf_tx/rfdriver.spice` |
| 50 | RP_DRV | pfet 20/0.28 | 1 | `rf_tx/rfdriver.spice` |

- Resistor pair (51 RES_A, 52 RES_B): each side is four `ppolyf_u_1k` units (2 × 10 µm) in series to VSS,
  interleaved A B B A A B B A in one row. 20.6 kΩ per side extracted (tt).
- MIM pair (53 MIM_A, 54 MIM_B): each side is two 40 × 40 µm MIM units, placed A B B A, top plate = NODE.
  6.49 pF per side extracted (tt).

### How to measure

Replicas and resistors: select the code on both buses, source current into ATB0, read ATB1 with a ≥ 1 GΩ
meter (SMU voltage sense, or a DMM in its 10 GΩ mode). A 10 MΩ meter loads the sense chain: 26 mV error on
`RN_LNA` at 100 nA (`iv_meter10meg` in `generated/char_atb-sims-extracted.json`). Keep the forced current at or
below 100 µA.

MIM pair: read C on the ATB0 pad with an LCR meter at 100 kHz with the code selected, read again with no leaf
closed (about 2.4 pF of bus and pad), subtract. The A − B difference needs no de-embedding.

Board requirements: B7, B10 (`spec/board-requirements.md`), plus the meter requirement above.

### Criteria and results (`generated/char_atb-evidence.json`)

| Test | Criterion (set in `run_char.py`) | Result |
| --- | --- | --- |
| observable | 5 corners (tt/27, ss/32, ff/22, ss/22, ff/32); replicas at 0.1–100 µA, resistors at 1–100 µA through the extracted ATB chain. Sense pad vs node ≤ 1 mV; sense pad vs directly forced device ≤ 2 mV; force pad ≤ 3.3 V; MIM de-embedded C within 3 % of direct | pass: worst 0.04 mV, 0.35 mV, 2.83 V, 1.5 % |
| safe | tt/27, ff/85, ss/0; VDD 0 → 3.63 V in 1 µs, every leaf open: settled DUT current ≤ 100 nA, ramp peak ≤ 10 µA; ATB0 held at 3.63 V into each node draws nothing from VDD | pass: settled ≤ 2.8 nA, peak ≤ 0.70 µA |
| clean | Magic DRC 0, Netgen LVS unique, GDS with HRES marker, KLayout DRC 0, published-GDS round-trip LVS, LEF pins = schematic ports | pass |
| fallback | waived (characterization structure) | waived |

### Flow

```
python3 run_char.py layout      # layout, Magic DRC, Netgen LVS, GDS + KLayout DRC, round-trip LVS, LEF
python3 run_char.py sims        # extracted benches through the extracted ATB chain (5 corners)
python3 run_char.py abstracts   # LEF + evidence-hash check of referenced structures
python3 run_char.py evidence    # generated/char_atb-evidence.json
```

- Layout uses the converter family's kit (`converters/lib/convkit.py`) and GDS export
  (`converters/flow.py:export_gds`).
- The ATB chain in the benches is island_support's extracted `atb_leaf_f`, `atb_leaf_s`, `atb_grp`, `atb_pad`,
  copied with hashes into `generated/atb_reference/`.
- Containers run with `--network none`. Scratch output goes to `scratch/characterization/`.

## Device-speed structures (`speed.py`, `rffet.py`)

Each has an extracted-netlist prediction; silicon / prediction is the calibration factor for the device-speed
guidance (`scratch/reviews/gf180-device-speed-evidence.md`).

| Cell | Measures | Circuit | Output |
| --- | --- | --- | --- |
| `pt_char_ro33` | 3.3 V CMOS gate delay | NAND enable + 10 inverters, nfet_03v3 4/0.28, pfet_03v3 8/0.28 | ring tap → TSPC /4 → buffer → `OUT` |
| `pt_char_ro50` | 5 V device speed on the 3.3 V rail (standard-cell device class) | same ring, nfet_05v0 4/0.6, pfet_05v0 8/0.5 | same /4 |
| `pt_char_cmldiv` | NMOS fT in a CML latch | two CML latches in a /2 loop with CK = CKB = VDD (self-oscillation), nfet_03v3 10/0.28 pairs, 1.8 kΩ poly loads, 0.6 mA tails; two clocked CML /2, CML→CMOS, TSPC /2 | `OUT` = f(S0) / 8 |
| `pt_char_rffet` (+ `_open`, `_short`) | fT, fmax, Rg of the RF device | one nfet_03v3 w 2 nf 5 (W = 10 µm), gate contacted both ends, 2-port GSG frame: 60 × 60 µm Metal5 pads, 50 × 50 µm GLASS openings, 100 µm pitch | on-wafer S-parameters; de-embed OPEN then SHORT |

- `EN = 0`: rings stopped, CML tails off, TSPC dividers held static (clock low, outputs reset).
- The CML cell biases itself from a 36 kΩ poly resistor into a diode NFET; `BIAS` is the mirror gate.
- The extracted benches add an explicit gate resistance Rg = Rsh·W/(3L), Rsh 7.3 Ω/sq, to every MOS gate
  (`speed.with_gate_r`). The run without Rg is kept as a comparison.
- Probe frames: the GLASS openings sit inside the core. Assembly keeps fill and other metal out of the
  430 × 260 µm frames, and the frames need probe access on the bare die.
- Every published GDS here (including `char_atb.gds`) has its subcells prefixed with the top-cell name and is
  re-checked by round-trip LVS (`published_gds_after_rename` in each `*-physical.json`).

| Cell | Devices | LEF size (µm) | Magic DRC | KLayout DRC | LVS | GDS round trip | LEF pins |
| --- | ---: | --- | ---: | ---: | --- | --- | --- |
| `pt_char_ro33` | 54 | 69.6 × 139.3 | 0 | 0 | unique | unique | match |
| `pt_char_ro50` | 54 | 70.4 × 132.4 | 0 | 0 | unique | unique | match |
| `pt_char_cmldiv` | 85 | 104.8 × 265.8 | 0 | 0 | unique | unique | match |
| `pt_char_rffet` | 1 (nf 5) | 430 × 260 | 0 | 0 | unique | unique | G, D, GND |
| `pt_char_rffet_open` | 0 | 430 × 260 | 0 | 0 | ports G, D, GND separate | not checked (no devices) | G, D, GND |
| `pt_char_rffet_short` | 0 | 430 × 260 | 0 | 0 | G and D merged into GND | not checked (no devices) | GND |

Extracted predictions with gate R (`generated/char_speed-evidence.json`):

<!-- speed-results -->
| Cell | Verdict | f_osc tt/27/3.3 | ss/32/3.15 | ff/22/3.35 | ss/22/3.35 | ff/32/3.15 | f(OUT) range | I_on tt | I(EN=0) max | tt without Rg |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| `pt_char_ro33` | pass | 605 MHz | 475 MHz | 730 MHz | 512 MHz | 689 MHz | 119–183 MHz | 1.66 mA | 0.7 nA | 608 MHz |
| `pt_char_ro50` | pass | 327 MHz | 223 MHz | 435 MHz | 246 MHz | 403 MHz | 56–109 MHz | 0.81 mA | 0.3 nA | 328 MHz |
| `pt_char_cmldiv` | pass | 856 MHz | 692 MHz | 1089 MHz | 692 MHz | 1088 MHz | 86–136 MHz | 4.02 mA | 19.2 nA | 865 MHz |

f_osc is the ring frequency (ring cells) or the S0 toggle frequency (CML cell; the equivalent input-clock
self-oscillation frequency is twice that). The RF FET frames have no simulated prediction beyond the model
fT/fmax.

```
python3 speed.py layout [cell,...]   # ro33, ro50, cmldiv physical flow (+ uniquify + re-LVS)
python3 speed.py sch                 # schematic tt (divider consistency check)
python3 speed.py ext                 # extracted + gate R, 5 corners (primary prediction)
python3 speed.py ext_norg            # extracted, no gate R, tt (comparison)
python3 speed.py evidence            # generated/char_speed-evidence.json
python3 rffet.py layout && python3 rffet.py export
```

## Open items

Risks: INT-04, MOD-06, MOD-14 (`spec/risk-register.md`).

- `pt_char_cmldiv.BIAS` and `pt_vco_replica.ATB_VTAIL` have no ATB code (unbound in `pt_chip.conn`).
- `generated/referenced-structures.json` and `generated/esd_test.lef` describe the single-leg `ESD_TEST` cell;
  the chip binds `pad_tlp` on that site instead, so the `abstracts` step needs repointing.
- `char_atb-evidence.json` hashes the GDS from before the subcell rename, and `run_char.py`, `convkit.py`,
  `flow.py` changed after it; `char_atb-physical.json` holds the current GDS hash and its round-trip LVS.
  `char_speed-evidence.json` is stale on `convkit.py` only.
- The LNA is being redesigned; the LNA replica sizes follow the published netlist.
- The ATB reference netlists come from a scratch run of island_support, not from a published flow output.
- The convkit layout roughly doubles node capacitance (3.3 V ring 1.16 GHz schematic, 605 MHz extracted), which
  halves each ring's sensitivity to device speed (MOD-14).
