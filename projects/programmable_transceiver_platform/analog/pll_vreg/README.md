# `pt_pll_vreg2`: supply regulator of the two ring PLLs

One cell regulates the supplies of `pll_tx` (`pt_pll_ring_core`) and `pll_cdr` (`pt_pll_ring`). It exists because
the rings convert supply ripple into deterministic jitter; the requirement is at least 20 dB of supply rejection
over 10-200 MHz and less than 5 ps peak of supply-borne ring jitter (risk PDN-04).

## Interface

Ports (`generated/pt_pll_vreg2_layout.spice`): `VIN VOUT_TX VOUT_CDR VSS BYP_TX BYP_CDR ATB_OUT ATB_G`

| Pin | Chip-top net (`integration/top/pt_chip.conn`, instance `pll_vreg2`, pll island) | Notes |
| --- | --- | --- |
| `VIN` | `RAIL_pll` | switched pll island rail |
| `VOUT_TX` | `VREG_TX` -> `pll_tx.VDD` | the output inside the OTA loop |
| `VOUT_CDR` | `VREG_CDR` -> `pll_cdr.VDD` | follows the same gate, open loop |
| `BYP_TX`, `BYP_CDR` | `c_pllvreg_byp_tx`, `c_pllvreg_byp_cdr` (`pllvreg.config.tx_bypass`, `rx_bypass`) | 1 shorts that output to `VIN`. **Reset value 1**; software clears it before use. Bypass is a fallback, not an operating mode (`spec/power-delivery.md` section 5.3) |
| `ATB_OUT`, `ATB_G` | not bound to a test-bus leaf | `VOUT_TX` and the pass gate through 20 k; forcing `ATB_G` sets both outputs externally |

## Circuit

* Shared: divider (30 k / 270 k, output = 0.9 x `VIN`), slow OTA, 30,000 um2 MOS gate capacitor.
* Per output: one pass macro `pt_vreg_pass` (native `nfet_06v0_nvt` source follower, 60 fingers of
  W 100 um / L 2.7 um), a 3,000 um2 MOS output capacitor and a W 1000 um bypass PMOS.
* The output impedance is 1/gm of the follower, so the ring's current steps do not move the output and the PLL
  sees no extra pole. The output tracks 0.9 x `VIN` at low frequency.

## Published layout

| Item | Value | Source |
| --- | --- | --- |
| Top cell | `generated/pt_pll_vreg2.gds` | |
| Outline | 447.9 x 390.5 um (bbox -29..418.9 x 0..390.5) = 0.175 mm2 for both rings | `generated/pt_pll_vreg2-layout.json` |
| Pass macro | `generated/pt_vreg_pass/`, 199.6 x 103.4 um, Magic DRC 0 | `pt_vreg_pass/drc.txt`, GDS |
| Magic DRC | 0 | `pt_pll_vreg2-layout.json` |
| LVS | unique, also on the exported GDS after the native-device marker fix | `pt_pll_vreg2-lvs.txt`, `-layout.json` |
| KLayout precheck | main 0 / antenna 0 | `pt_pll_vreg2-kldrc.json` |
| Extraction | `generated/pt_pll_vreg2.ext.spice` (Magic, parasitic C) | |

The Magic export under-sizes the NAT layer around the native device; the generator regrows it in the exported
GDS and LVS is repeated on that GDS.

## Verified numbers

Extracted cell, output under test `VOUT_CDR` with the other output loaded; evidence `evidence/pll_vreg2-ext-*.json`
(the model hash equals the published extraction).

| Check | Result | Criterion |
| --- | --- | --- |
| Supply rejection, worst over 10-200 MHz (6 mA, `VIN` 3.15 V) | 22.8 dB tt, 23.3 dB ss/32, 23.6 dB ff/22 | >= 20 dB |
| Rejection at 100 kHz | 8-11 dB | - |
| Dropout (`VIN` 3.05 / 3.25 / 3.35 V, 3 and 8 mA, tt/27, ss and ff at 22 and 32 C) | 0.26-0.50 V | pass device saturated |
| Ring on the regulated output, 60 mV ripple at 78 MHz on `VIN` | tt 13.9 MHz/V, 2.71 ps peak, -45.5 dBc; ss/32 10.3 MHz/V, 2.02 ps, -48.0 dBc; ff/22 14.7 MHz/V, 2.88 ps, -45.0 dBc | - |
| Same, `VOUT_TX`, tt | 13.9 MHz/V, 2.71 ps | - |
| Scaled to 90 mV of ripple | <= 4.3 ps peak | < 5 ps |
| Start-up, 10 us `VIN` ramp: time to 95 % | 26-37 us, no overshoot, output never above `VIN` | <= 50 us |
| Bypass drop at 8 mA | 33-43 mV | - |

## Flow

```
python3 analog/pll_vreg/pll_vreg2_pass.py     # pass macro
python3 analog/pll_vreg/pll_vreg2_layout.py   # top cell, DRC, LVS, GDS, records in generated/
python3 analog/pll_vreg/pll_vreg2_ext.py      # extracted benches -> evidence/pll_vreg2-ext-*.json
```

`pll_vreg.py` holds the shared benches and the single-output schematic generator.

## Single-output cell `pt_pll_vreg`

`generated/pt_pll_vreg.gds` (ports `VIN VOUT VSS BYP ATB_OUT ATB_G`, 398.0 x 605.6 um = 0.241 mm2, Magic DRC 0,
LVS unique, precheck clean; evidence `evidence/pll_vreg-ext-packed.json`) is the one-ring version of the same
circuit. It is not instantiated at chip top.

## Open items

Risks: `spec/risk-register.md` PDN-04, LO-02.

* The ring-load runs used the ring extraction current when the evidence was written; the published ring has
  been revised since (`../timing/README.md`, `pt_pll_ring`). Not rerun.
* Ring-to-ring coupling through the shared pass gate (both extracted rings on one cell) is not simulated.
* No runs at a trimmed `VIN` of 3.50 V, at sf / fs, or with resistance-aware extraction of the output path.
* Rejection below about 1 MHz is small (8-11 dB at 100 kHz); the loop bandwidth of the ring PLL is relied on
  there, without a simulation of the two together.
* `ATB_OUT` / `ATB_G` are unbound at chip top; the enable terms `vreg_tx_ok` / `vreg_rx_ok` of the rings
  (`integration/top/ctl_ports.txt`) have no source in this cell.
* This cell does not meet the QVCO rail requirement; the QVCO needs its own regulator
  (`../timing/LO-INTEGRATION.md` section 3).
* `pll_vreg.py` has an uncommitted one-line bench edit (ring port list).
